"""日志 AI 分析服务

功能：
- 轻量脱敏（替换设备 IP/名称，保留端口名/日志级别/时间戳）
- 关键词提取（FACILITY-SEVERITY-MNEMONIC）
- 本地缓存匹配（remediation_hints 精确匹配）
- LLM 调用（OpenAI 兼容接口，优先级链降级）
- 往返脱敏（发前替换占位符，回复后还原真实名称）
"""

import re
import json
import logging
import requests
from typing import Optional, Dict, List, Tuple
from storage.database import get_connection as _get_db

logger = logging.getLogger(__name__)


# === 脱敏 / 还原因 ===

def _build_sanitize_map(device_name: str, device_ip: str) -> Dict[str, str]:
    """构建替换映射表：真实名 → 占位符

    Args:
        device_name: 当前设备名 (如 BJQD1SWI01)
        device_ip: 当前设备 IP (如 10.210.255.1)

    Returns:
        {真实名: 占位符, ...} 以及反向映射 {占位符: 真实名, ...}
    """
    mapping = {}
    # 当前设备
    mapping["[本设备]"] = device_name
    mapping["[本设备IP]"] = device_ip

    # 同 location 的邻居设备
    db = _get_db()
    if db:
        try:
            row = db.execute(
                "SELECT location FROM devices WHERE name=?", (device_name,)
            ).fetchone()
            if row and row["location"]:
                loc = row["location"]
                others = db.execute(
                    "SELECT name, ip FROM devices WHERE location=? AND name!=?",
                    (loc, device_name)
                ).fetchall()
                for i, dev in enumerate(others, 1):
                    if dev["name"]:
                        mapping[f"[设备{i}]"] = dev["name"]
                    if dev["ip"]:
                        mapping[f"[IP_{i}]"] = dev["ip"]
        except Exception:
            pass

    return mapping


def sanitize_logs(log_entries: list[dict], mapping: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
    """脱敏日志条目

    Args:
        log_entries: [{"timestamp": "...", "message": "...", ...}, ...]
        mapping: {占位符: 真实值}

    Returns:
        (sanitized_text, reverse_map) — reverse_map 用于还原 LLM 回复
    """
    # 构建正向映射: 真实值 → 占位符
    forward = {v: k for k, v in mapping.items()}

    lines = []
    for e in log_entries:
        msg = e.get("message", "")
        for real, placeholder in sorted(forward.items(), key=lambda x: -len(x[0])):
            msg = msg.replace(real, placeholder)
        ts = e.get("timestamp", "")
        sev = e.get("severity", "")
        fac = e.get("facility", "")
        lines.append(f"{ts} {fac}-{sev}: {msg}")

    return "\n".join(lines), forward


def desanitize_response(text: str, reverse_map: Dict[str, str]) -> str:
    """还原 LLM 回复中的占位符为真实名称"""
    result = text
    # 反过来: 占位符 → 真实值
    for placeholder, real in sorted(reverse_map.items(), key=lambda x: -len(x[0])):
        result = result.replace(placeholder, real)
    return result


# === 关键词提取 ===

_CISCO_MNEMONIC_RE = re.compile(r'%(\w+-\d-\w+)', re.IGNORECASE)
_ARUBA_MNEMONIC_RE = re.compile(r'\b(\w+):\s+(\w+):', re.IGNORECASE)


def extract_keywords(log_entries: list[dict]) -> list[str]:
    """从日志条目提取关键词

    优先提取 %FACILITY-SEVERITY-MNEMONIC（Cisco），
    其次提取 Aruba facility:mnemonic 格式。

    Returns:
        关键词列表，如 ["BGP-5-ADJCHANGE", "LINK-3-UPDOWN"]
    """
    keywords = []
    for e in log_entries:
        msg = e.get("message", "")
        # Cisco: %FACILITY-N-MNEMONIC
        m = _CISCO_MNEMONIC_RE.search(msg)
        if m:
            keywords.append(m.group(1))
            continue
        # Aruba: facility severity: mnemonic: ...
        facility = e.get("facility", "")
        m2 = _ARUBA_MNEMONIC_RE.search(msg)
        if m2 and facility:
            keywords.append(f"{facility}:{m2.group(2)}")
            continue
        # 回退: 用 facility-severity 组合
        if e.get("facility") and e.get("severity"):
            keywords.append(f"{e['facility']}-{e['severity']}")
    return keywords


# === 缓存查询 ===

def query_cache(keywords: list[str]) -> Optional[dict]:
    """从 remediation_hints 表精确匹配关键词

    Returns:
        命中时返回 {"suggestion": "...", "alert_type": "..."}, 否则 None
    """
    db = _get_db()
    if not db:
        return None
    for kw in keywords:
        row = db.execute(
            "SELECT suggestion, alert_type FROM remediation_hints WHERE keyword=? LIMIT 1",
            (kw,)
        ).fetchone()
        if row:
            return {"suggestion": row["suggestion"], "alert_type": row["alert_type"], "keyword": kw}
    return None


def save_cache(keyword: str, suggestion: str, alert_type: str = "log_analysis"):
    """将 AI 分析结果写入 remediation_hints"""
    db = _get_db()
    if not db:
        return
    try:
        db.execute(
            "INSERT INTO remediation_hints (alert_type, keyword, suggestion) VALUES (?, ?, ?)",
            (alert_type, keyword, suggestion),
        )
        db.commit()
        logger.info(f"[LLM] 缓存已写入: {keyword}")
    except Exception as e:
        logger.warning(f"[LLM] 缓存写入失败: {e}")


# === LLM 调用 ===

def _load_providers() -> list[dict]:
    """从 settings.yaml 加载 LLM provider 配置，环境变量覆盖 api_key"""
    from utils.settings_loader import load_settings
    settings = load_settings()
    llm = settings.get("llm", {})
    providers = llm.get("providers", [])
    timeout = llm.get("timeout", 30)

    result = []
    for i, p in enumerate(providers, 1):
        # 环境变量优先: LLM_API_KEY_1, LLM_API_KEY_2, ...
        env_key = os.environ.get(f"LLM_API_KEY_{i}", "")
        key = env_key or p.get("api_key", "").strip()
        if not key:
            continue  # 跳过未配置的 provider
        result.append({
            "name": p.get("name", f"Provider{i}"),
            "base_url": p.get("base_url", "").rstrip("/"),
            "api_key": key,
            "model": p.get("model", ""),
            "timeout": timeout,
        })
    return result


import os


def _build_prompt(logs_text: str, device_info: dict) -> str:
    """构建 LLM prompt"""
    return f"""你是一名网络运维专家。请分析以下交换机日志，给出诊断建议。

设备信息：
- 设备型号: {device_info.get('model', '未知')}
- 软件版本: {device_info.get('version', '未知')}
- 日志时间范围: {device_info.get('time_range', '未知')}
- 严重级别分布: {device_info.get('severity_stats', '')}

日志内容（设备名和IP已替换为占位符，请在回复中也使用占位符）：

{logs_text}

请用 JSON 格式回复，不要包含其他内容：
```json
{{
  "summary": "一句话问题概述",
  "root_cause": "根因分析（2-3句）",
  "suggestion": "建议操作步骤（编号列表）",
  "severity": "critical|warning|info",
  "related_errors": ["错误助记符列表"]
}}
```"""


def _call_one_provider(provider: dict, prompt: str) -> str:
    """调用单个 LLM provider"""
    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": "你是一名网络运维专家，精通 Cisco IOS 和 Aruba CX 交换机日志分析。请严格按照 JSON 格式回复。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    resp = requests.post(url, json=payload, headers=headers,
                         timeout=provider.get("timeout", 30))
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_llm_response(raw: str) -> dict:
    """解析 LLM 返回的 JSON"""
    # 尝试提取 JSON 块
    m = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)


def call_llm(logs_text: str, device_info: dict) -> Tuple[dict, str]:
    """调用 LLM 分析日志（优先级链降级）

    Returns:
        (parsed_response, provider_name)
    """
    prompt = _build_prompt(logs_text, device_info)
    providers = _load_providers()

    if not providers:
        raise RuntimeError("没有配置可用的 LLM provider，请在 settings.yaml 或环境变量中设置 api_key")

    last_error = None
    for p in providers:
        try:
            logger.info(f"[LLM] 尝试 {p['name']}...")
            raw = _call_one_provider(p, prompt)
            parsed = _parse_llm_response(raw)
            logger.info(f"[LLM] {p['name']} 调用成功")
            return parsed, p["name"]
        except Exception as e:
            logger.warning(f"[LLM] {p['name']} 失败: {e}")
            last_error = e
            continue

    raise RuntimeError(f"所有 LLM provider 均失败，最后错误: {last_error}")


# === 主入口 ===

def analyze_logs(
    log_entries: list[dict],
    device_name: str,
    device_ip: str,
    device_info: Optional[dict] = None,
) -> dict:
    """分析日志主流程

    Args:
        log_entries: 用户选中的日志条目列表
        device_name: 设备名
        device_ip: 设备 IP
        device_info: 设备信息 {model, version, ...}

    Returns:
        {
            "suggestion": dict | str,  # 结构化 or 纯文本建议
            "source": "cache" | "llm",
            "provider": "DeepSeek" | None,
            "keyword": "BGP-5-ADJCHANGE" | None,
            "from_cache": bool,
        }
    """
    # 1. 提取关键词 → 查本地缓存
    keywords = extract_keywords(log_entries)
    if keywords:
        cached = query_cache(keywords)
        if cached:
            return {
                "suggestion": cached["suggestion"],
                "source": "cache",
                "provider": None,
                "keyword": cached["keyword"],
                "from_cache": True,
            }

    # 2. 脱敏
    mapping = _build_sanitize_map(device_name, device_ip)
    sanitized_text, reverse_map = sanitize_logs(log_entries, mapping)

    # 3. 构建设备上下文
    info = device_info or {}
    info["time_range"] = _compute_time_range(log_entries)
    info["severity_stats"] = _compute_severity_stats(log_entries)

    # 4. 调 LLM
    try:
        llm_result, provider_name = call_llm(sanitized_text, info)
    except RuntimeError as e:
        return {
            "suggestion": {"summary": str(e), "root_cause": "", "suggestion": "",
                           "severity": "info", "related_errors": []},
            "source": "error",
            "provider": None,
            "keyword": None,
            "from_cache": False,
        }

    # 5. 还原真实名称
    if isinstance(llm_result, dict):
        for key in ("summary", "root_cause", "suggestion"):
            if key in llm_result and isinstance(llm_result[key], str):
                llm_result[key] = desanitize_response(llm_result[key], reverse_map)

    # 6. 写入缓存
    for kw in keywords:
        save_cache(kw, json.dumps(llm_result, ensure_ascii=False), "log_analysis")

    return {
        "suggestion": llm_result,
        "source": "llm",
        "provider": provider_name,
        "keyword": keywords[0] if keywords else None,
        "from_cache": False,
    }


def _compute_time_range(entries: list[dict]) -> str:
    """计算日志时间范围"""
    timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
    if len(timestamps) >= 2:
        return f"{timestamps[0]} ~ {timestamps[-1]}"
    elif len(timestamps) == 1:
        return timestamps[0]
    return "未知"


def _compute_severity_stats(entries: list[dict]) -> str:
    """统计严重级别分布"""
    from collections import Counter
    sevs = Counter(e.get("severity", "") for e in entries)
    return ", ".join(f"{k}: {v}条" for k, v in sevs.most_common())
