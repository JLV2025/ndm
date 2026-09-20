"""AI 专家简报 —— 让 AI 把**确定性审计结论**讲成人话。

铁律（总计划定案）：**判定归引擎，叙事归 AI**。prompt 里硬约束"只根据给定条目组织语言，
不得新增任何未列出的问题、命令或日期" —— 简报一旦自由发挥，就会编出引擎没发现的问题，
而"零幻觉"正是整套审计可信度的来源（与 netstd 时期"规则引擎跑分 vs 资深专家评审"的定位一致）。

两份简报：
  · 单台（`generate_device_briefing`）：设备上下文 + 统计 + findings 摘要 + 例外
  · 全网（`generate_network_briefing`）：最新一次运行的聚合 + 收敛/恶化榜 + 集体性条目

**发送前所有文本过 `utils.redact.redact_secrets`**（凭据值绝不外发）。
LLM 不可用 → 抛 `BriefingError`（可读中文）；审计本身不受任何影响。
"""
from __future__ import annotations

import datetime
import json
import re

import requests

from utils.redact import redact_finding, redact_secrets

SYSTEM_PROMPT = (
    "你是一名资深网络工程师，擅长把审计结论讲清楚。"
    "你只负责组织语言，不做新的判定。"
)


class BriefingError(RuntimeError):
    """简报生成失败（可读中文原因）。"""


def _providers() -> list[dict]:
    """复用日志分析的 provider 链（settings + LLM_API_KEY_N 环境变量覆盖）。"""
    from services.log_analyzer import _load_providers
    return _load_providers()


def _call_llm(prompt: str, max_tokens: int = 1200) -> tuple[str, str]:
    """按 provider 链降级调用，返回 (正文, provider 名)。"""
    providers = _providers()
    if not providers:
        raise BriefingError("没有可用的 LLM provider —— 请在「日志分析 → LLM 设置」里配置 api_key"
                            "（或设 LLM_API_KEY_1 环境变量）")
    errors = []
    for p in providers:
        try:
            resp = requests.post(
                f"{p['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {p['api_key']}",
                         "Content-Type": "application/json"},
                json={"model": p["model"],
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": prompt}],
                      "temperature": 0.3, "max_tokens": max_tokens},
                timeout=p.get("timeout", 30))
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            if text:
                return text, f"{p['name']}({p['model']})"
        except Exception as e:                       # noqa: BLE001 —— 逐个降级
            errors.append(f"{p['name']}: {e}")
    raise BriefingError("所有 LLM provider 都调用失败：" + "；".join(errors[:3]))


# ---------------------------------------------------------------- prompt 构建（纯函数，可单测）

_BRIEFING_RULES = """硬约束（必须遵守）：
1. 只能使用下面给出的条目与数据；**不得新增任何未列出的问题、命令、日期或数字**。
2. 不要逐条复述（同事自己会看表）—— 讲清楚：整体印象、最该先做的 2-3 件及理由、
   哪些条目其实是同一件事的配套、时效风险的紧迫程度。
3. 标了「已批准例外」的条目是已知并接受的情况，不要当成新问题。
4. 信息缺失（如生命周期未登记）就如实说"这块还没有数据"，不要猜。
5. 输出中文 Markdown，不要用代码块包整篇，也不要写"作为 AI"之类的话。"""


def build_device_prompt(env: dict) -> str:
    """单台简报 prompt。env = 审计 envelope（前端拿到的那个结构）。"""
    counts = {k: v for k, v in (env.get("counts") or {}).items() if v}
    lines = [
        "你是资深网络工程师，正在给同事讲**一台交换机**的配置评审结果。",
        _BRIEFING_RULES, "",
        "## 设备上下文",
        f"- 设备：{env.get('device', '')}（{env.get('location', '') or '未知站点'} / "
        f"{env.get('platform', '') or '未知平台'} / 型号 {env.get('model', '') or '未知'}）",
        f"- 配置采集：{env.get('week', '')} {env.get('collected_at', '')}",
        f"- 建议统计：{counts or '无'}；已批准例外 {env.get('exempt_count', 0)} 条",
        "",
        "## 已判定的条目（由确定性规则引擎给出，共 %d 条）" % len(env.get("findings") or []),
    ]
    for f in env.get("findings") or []:
        rf = redact_finding(f)
        lines.append(f"- [{rf.get('level')}][{rf.get('source')}] {rf.get('title')}"
                     f"（规则 {rf.get('rule_id')}）")
        if rf.get("detail"):
            lines.append(f"  说明：{rf['detail']}")
        if rf.get("current"):
            lines.append(f"  现状：{redact_secrets(rf['current'])[:300]}")
        if rf.get("fix"):
            lines.append(f"  建议命令：{redact_secrets(rf['fix'])[:300]}")
        if rf.get("why"):
            lines.append(f"  依据：{redact_secrets(rf['why'])[:200]}")
        if rf.get("exempt"):
            ex = rf["exempt"]
            lines.append(f"  ⚑ 已批准例外 {ex.get('exception_id')}（批准人 {ex.get('approved_by')}，"
                         f"到期 {ex.get('expires_at')}，状态 {ex.get('status')}）："
                         f"{redact_secrets(ex.get('reason', ''))[:150]}")
    if not (env.get("findings") or []):
        lines.append("- （本次没有命中任何规则 —— 请说明「未发现可改进项」，不要凭空找问题）")
    lines += ["", "请写一段 300–500 字的评审意见。"]
    return "\n".join(lines)


def build_network_prompt(data: dict) -> str:
    """全网简报 prompt。data 由 `collect_network_data()` 装配。"""
    lines = [
        "你是资深网络工程师，正在给网络团队与主管写**本周配置审计简报**（全网视角）。",
        _BRIEFING_RULES, "",
        "## 本次审计",
        f"- 运行 #{data.get('run_id')}：{data.get('started_at', '')}（触发方式 {data.get('trigger', '')}）",
        f"- 设备 {data.get('device_count', 0)} 台；建议 {data.get('finding_count', 0)} 条；"
        f"已批准例外 {data.get('exempt_count', 0)} 条",
        f"- 按档位：{json.dumps(data.get('counts') or {}, ensure_ascii=False)}",
        f"- 按来源：{json.dumps(data.get('by_source') or {}, ensure_ascii=False)}",
    ]
    if data.get("ruleset_changed") or data.get("exceptions_changed"):
        changed = [n for n, v in (("标准", data.get("ruleset_changed")),
                                  ("豁免", data.get("exceptions_changed"))) if v]
        lines.append(f"- 注意：与上一次相比，{'、'.join(changed)}发生了变化 —— "
                     f"条目数的变化可能来自这里，而不是设备本身")
    lines += ["", "## 命中设备数最多的规则（Top %d）" % len(data.get("top_rules") or [])]
    for r in data.get("top_rules") or []:
        lines.append(f"- [{r.get('level')}] {r.get('title')}（{r.get('rule_id')}）：命中 {r.get('devices')} 台")
    if data.get("collective"):
        lines += ["", "## 集体性条目（已折叠成一条）"]
        for c in data["collective"]:
            lines.append(f"- {c.get('title')}：{c.get('device_count')} 台")
    diff = data.get("diff")
    if diff and diff.get("rules"):
        lines += ["", f"## 收敛 / 恶化（{diff.get('from', {}).get('week', '?')} → "
                      f"{diff.get('to', {}).get('week', '?')}，按命中设备数）"]
        for r in diff["rules"][:10]:
            arrow = "收敛" if r["delta"] < 0 else "恶化"
            lines.append(f"- {arrow} {abs(r['delta'])} 台：{r.get('title')}（{r.get('rule_id')}）")
    if data.get("lifecycle_unknown"):
        lines += ["", "## 数据说明",
                  f"- 有 {data['lifecycle_unknown']} 台设备尚未登记生命周期信息（型号 EoL / 保修期），"
                  f"时效风险这块的结论**不完整**"]
    lines += ["", "请写 4–6 段：整体态势 / 本期变化 / 建议关注的三件事 / 数据可信度说明。"]
    return "\n".join(lines)


# ---------------------------------------------------------------- 数据装配（只读）

def collect_network_data(db, run_id: int | None = None) -> dict:
    """装配全网简报所需数据：最新（或指定）运行的聚合 + 榜 + 集体性条目。"""
    db.row_factory = __import__("sqlite3").Row
    run = None
    if run_id is not None:
        run = db.execute("SELECT * FROM audit_runs WHERE id = ?", (run_id,)).fetchone()
    else:
        run = db.execute("SELECT * FROM audit_runs WHERE status = 'done' "
                         "ORDER BY id DESC LIMIT 1").fetchone()
    if run is None:
        raise BriefingError("还没有完成的审计运行 —— 先跑一次「全网审计」再生成简报")

    rid = run["id"]
    counts: dict[str, int] = {}
    by_source: dict[str, int] = {}
    per_rule: dict[str, dict] = {}
    collective = []
    for row in db.execute(
            "SELECT rule_id, title, level, source, device_name, exempt_by, exempt_json "
            "FROM audit_findings WHERE run_id = ?", (rid,)):
        exempt = False
        if row["exempt_by"]:
            try:
                exempt = (json.loads(row["exempt_json"] or "{}").get("status")
                          in ("active", "expiring"))
            except ValueError:
                exempt = False
        if exempt:
            continue
        counts[row["level"]] = counts.get(row["level"], 0) + 1
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
        if row["device_name"] == "全网":
            collective.append({"title": row["title"], "device_count": None})
            continue
        e = per_rule.setdefault(row["rule_id"], {"rule_id": row["rule_id"], "title": row["title"],
                                                 "level": row["level"], "devices": set()})
        e["devices"].add(row["device_name"])

    top_rules = sorted(
        ({"rule_id": e["rule_id"], "title": e["title"], "level": e["level"],
          "devices": len(e["devices"])} for e in per_rule.values()),
        key=lambda x: -x["devices"])[:15]

    # 集体性条目的台数在标题里（"…（36 台）"），从标题提取即可
    for c in collective:
        m = re.search(r"（(\d+)\s*台）", c["title"] or "")
        c["device_count"] = int(m.group(1)) if m else None

    prev = db.execute("SELECT ruleset_hash, exceptions_hash FROM audit_runs "
                      "WHERE status='done' AND id < ? ORDER BY id DESC LIMIT 1", (rid,)).fetchone()
    data = {
        "run_id": rid, "started_at": run["started_at"], "trigger": run["trigger"],
        "device_count": run["device_count"], "finding_count": run["finding_count"],
        "exempt_count": run["exempt_count"] or 0,
        "counts": counts, "by_source": by_source, "top_rules": top_rules,
        "collective": collective,
        "ruleset_changed": bool(prev) and prev["ruleset_hash"] != run["ruleset_hash"],
        "exceptions_changed": bool(prev) and (prev["exceptions_hash"] or "") != (run["exceptions_hash"] or ""),
        "lifecycle_unknown": next((c["device_count"] for c in collective
                                   if "生命周期" in (c["title"] or "")), 0),
        "diff": None,
    }
    try:                                  # 榜是加分项，取不到就算了
        from analyzers.compliance import trends
        diff = trends.trend_diff(db)
        if diff.get("rules"):
            data["diff"] = diff
    except Exception:                     # noqa: BLE001
        pass
    return data


# ---------------------------------------------------------------- 对外

def generate_device_briefing(env: dict) -> dict:
    """单台简报（不落库：讲解随时可重新生成）。"""
    if not env.get("usable"):
        raise BriefingError(f"本次审计没有可用配置（{env.get('reason') or '原因未知'}），无法生成简报")
    prompt = build_device_prompt(env)
    text, provider = _call_llm(prompt, max_tokens=1000)
    return {"briefing": text, "provider": provider, "scope": "device",
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}


def render_network_briefing(data: dict) -> dict:
    """只做 LLM 调用（数据已装配好）。

    **拆出来是为了线程边界**：SQLite 连接不能跨线程用，端点里读库必须在主线程，
    只有这段阻塞的 HTTP 调用放 `asyncio.to_thread`。
    """
    text, provider = _call_llm(build_network_prompt(data), max_tokens=1400)
    return {"briefing": text, "provider": provider, "scope": "network",
            "run_id": data["run_id"],
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}


def generate_network_briefing(db, run_id: int | None = None) -> dict:
    """全网简报（同步便捷版：读库 + 调用；测试与脚本用）。"""
    return render_network_briefing(collect_network_data(db, run_id))
