"""日志分析 API 路由"""

import re
import yaml
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from storage.database import get_connection as _get_db
from services.log_analyzer import analyze_logs

router = APIRouter()

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "config", "settings.yaml")


class AnalyzeRequest(BaseModel):
    log_ids: List[int]
    device_name: str


class LLMProviderUpdate(BaseModel):
    name: str
    base_url: str
    api_key: str
    model: str


class LLMSettingsUpdate(BaseModel):
    timeout: int = 30
    providers: List[LLMProviderUpdate] = []


SEVERITY_LABELS = {
    "0": "Emergency", "1": "Alert", "2": "Critical",
    "3": "Error", "4": "Warning", "5": "Notice",
    "6": "Info", "7": "Debug",
}


@router.get("/logs/tree")
async def logs_tree(week: Optional[str] = None):
    """返回所有设备的日志树结构（设备 + 严重级别计数）"""
    db = _get_db()
    if not db:
        raise HTTPException(status_code=404, detail="数据库未就绪")

    params = []
    week_condition = ""
    if week:
        week_condition = "AND c.week = ?"
        params.append(week)

    query = f"""
        SELECT d.id as device_id, d.name, d.ip, d.model, d.version,
               dl.severity, COUNT(*) as cnt
        FROM device_logs dl
        JOIN devices d ON dl.device_id = d.id
        JOIN collections c ON dl.collection_id = c.id
        WHERE typeof(dl.severity) = 'text' AND dl.severity IN ('0','1','2','3','4','5','6','7') {week_condition}
        GROUP BY d.id, dl.severity
        ORDER BY d.name, CAST(dl.severity AS INTEGER)
    """
    rows = db.execute(query, params).fetchall()

    devices_map: dict = {}
    for r in rows:
        did = r["device_id"]
        if did not in devices_map:
            devices_map[did] = {
                "device_name": r["name"],
                "device_info": {
                    "ip": r["ip"] or "",
                    "model": r["model"] or "",
                    "version": r["version"] or "",
                },
                "total_logs": 0,
                "severity_groups": [],
            }
        sev = r["severity"]
        cnt = r["cnt"]
        devices_map[did]["total_logs"] += cnt
        devices_map[did]["severity_groups"].append({
            "severity": sev,
            "label": SEVERITY_LABELS.get(sev, sev),
            "count": cnt,
        })

    return {"devices": list(devices_map.values())}

@router.get("/logs/analysis-history")
async def analysis_history(limit: int = 20):
    """返回最近的 AI 分析历史记录"""
    db = _get_db()
    if not db:
        return {"history": []}

    rows = db.execute(
        "SELECT id, alert_type, keyword, suggestion FROM remediation_hints "
        "WHERE alert_type='log_analysis' ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()

    return {
        "history": [
            {"id": r["id"], "keyword": r["keyword"],
             "suggestion": r["suggestion"],
             "created_at": f"#{r['id']}"}
            for r in rows
        ]
    }





@router.get("/logs/{device_name}")
async def get_device_logs(
    device_name: str,
    week: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 200,
):
    """获取设备的日志列表（从 SQLite）"""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', device_name):
        raise HTTPException(status_code=400, detail="设备名包含非法字符")

    db = _get_db()
    if not db:
        raise HTTPException(status_code=404, detail="数据库未就绪")

    # 获取设备 ID
    dev_row = db.execute("SELECT id, ip, model, version FROM devices WHERE name=?",
                         (device_name,)).fetchone()
    if not dev_row:
        raise HTTPException(status_code=404, detail="设备不存在")

    device_id = dev_row["id"]
    device_info = {
        "ip": dev_row["ip"], "model": dev_row["model"],
        "version": dev_row["version"],
    }

    # 构建查询
    conditions = ["dl.device_id = ?"]
    params = [device_id]

    if week:
        conditions.append("c.week = ?")
        params.append(week)

    if severity:
        conditions.append("dl.severity = ?")
        params.append(severity)

    query = f"""
        SELECT dl.id, dl.log_timestamp, dl.severity, dl.facility, dl.message,
               c.week, c.collected_at
        FROM device_logs dl
        JOIN collections c ON dl.collection_id = c.id
        WHERE {' AND '.join(conditions)}
        ORDER BY dl.log_timestamp DESC
        LIMIT ?
    """
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    logs = [
        {
            "id": r["id"],
            "timestamp": r["log_timestamp"] or "",
            "severity": r["severity"] or "",
            "facility": r["facility"] or "",
            "message": r["message"] or "",
            "week": r["week"],
            "collected_at": r["collected_at"],
        }
        for r in rows
    ]

    return {"device_name": device_name, "device_info": device_info, "logs": logs}


@router.post("/logs/analyze")
async def analyze_device_logs(req: AnalyzeRequest):
    """AI 分析选中的日志条目"""
    if not req.log_ids:
        raise HTTPException(status_code=400, detail="请选择至少一条日志")

    db = _get_db()
    if not db:
        raise HTTPException(status_code=404, detail="数据库未就绪")

    # 查询日志原文
    placeholders = ",".join("?" for _ in req.log_ids)
    rows = db.execute(
        f"SELECT id, log_timestamp, severity, facility, message FROM device_logs "
        f"WHERE id IN ({placeholders}) ORDER BY log_timestamp ASC",
        req.log_ids,
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="未找到指定日志")

    # 获取设备信息
    dev_row = db.execute(
        "SELECT ip, model, version FROM devices WHERE name=?",
        (req.device_name,)
    ).fetchone()
    if not dev_row:
        raise HTTPException(status_code=404, detail="设备不存在")

    log_entries = [
        {"timestamp": r["log_timestamp"] or "", "severity": r["severity"] or "",
         "facility": r["facility"] or "", "message": r["message"] or ""}
        for r in rows
    ]

    device_info = {
        "model": dev_row["model"] or "未知",
        "version": dev_row["version"] or "未知",
    }

    try:
        result = analyze_logs(
            log_entries, req.device_name, dev_row["ip"] or "",
            device_info,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

    return {
        "device_name": req.device_name,
        "log_count": len(log_entries),
        "keyword": result.get("keyword"),
        "from_cache": result.get("from_cache", False),
        "source": result.get("source", "unknown"),
        "provider": result.get("provider"),
        "suggestion": result.get("suggestion"),
    }


# === LLM 设置接口 ===

@router.get("/settings/llm")
async def get_llm_settings():
    """获取 LLM 配置（api_key 脱敏显示）"""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="读取配置文件失败")

    llm = settings.get("llm", {})
    timeout = llm.get("timeout", 30)
    providers = []
    for p in llm.get("providers", []):
        key = p.get("api_key", "")
        providers.append({
            "name": p.get("name", ""),
            "base_url": p.get("base_url", ""),
            "api_key": _mask_key(key),
            "model": p.get("model", ""),
        })
    return {"timeout": timeout, "providers": providers}


@router.put("/settings/llm")
async def update_llm_settings(data: LLMSettingsUpdate):
    """更新 LLM 配置（保留已有的 api_key 如果不传则不变）"""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="读取配置文件失败")

    old_providers = settings.get("llm", {}).get("providers", [])
    old_map = {p.get("name", ""): p.get("api_key", "") for p in old_providers}

    new_providers = []
    for p in data.providers:
        # 如果传入的 api_key 是脱敏版本或为空，保留旧值
        key = p.api_key.strip()
        if not key or _is_masked(key):
            key = old_map.get(p.name, "")
        new_providers.append({
            "name": p.name,
            "base_url": p.base_url,
            "api_key": key,
            "model": p.model,
        })

    settings["llm"] = {
        "timeout": data.timeout,
        "providers": new_providers,
    }

    # 写回文件（保留格式）
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(settings, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return {"status": "ok", "message": "LLM 配置已保存"}


def _mask_key(key: str) -> str:
    """脱敏显示 api_key：只显示前4后3位"""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "****" + key[-3:]


def _is_masked(key: str) -> bool:
    """判断是否已是脱敏格式"""
    return "****" in key or "***" in key
