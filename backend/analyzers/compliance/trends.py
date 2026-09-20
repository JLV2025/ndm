"""审计趋势的查询核心 —— 从 api/audit.py 抽出（API 与 AI 简报共用）。

口径（与例外机制一致）：
  · 建议数 = **未豁免**的 findings（生效中的例外单列；已过期的例外照常计入建议）
  · 例外数 = 生效中 + 即将到期（audit_runs.exempt_count）
周粒度：**每周取该周最后一次运行**（用户定案，与"配置按周存/流量周锚定"的惯例一致）；
本周尚无运行时该周不出现 —— 否则周一早上会把上周数据画成"本周"。
"""
from __future__ import annotations

import datetime
import sqlite3


def iso_week(ts: str) -> str:
    """ISO 周 'YYYY-WW'（与库内 collections.week 同格式）；解析失败返回空串。"""
    try:
        d = datetime.date.fromisoformat(str(ts)[:10])
    except ValueError:
        return ""
    y, w, _ = d.isocalendar()
    return f"{y}-{w:02d}"


def weekly_last(db) -> list[tuple[str, sqlite3.Row]]:
    """每周最后一次 done 运行，按周升序。"""
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, started_at, trigger, device_count, finding_count, exempt_count, "
        "ruleset_hash, exceptions_hash FROM audit_runs WHERE status = 'done' ORDER BY id"
    ).fetchall()
    weekly: dict[str, sqlite3.Row] = {}
    for r in rows:
        wk = iso_week(r["started_at"])
        if wk:
            weekly[wk] = r          # 按 id 递增覆盖 → 留下的是该周最后一条
    return sorted(weekly.items())


def exempt_case() -> str:
    """SQL：该 finding 是否**生效中/即将到期**的豁免（用 JSON1 读快照里的 status）。"""
    return ("CASE WHEN af.exempt_by IS NOT NULL "
            "AND json_extract(af.exempt_json, '$.status') IN ('active', 'expiring') "
            "THEN 1 ELSE 0 END")


def aggregate_run(db, run_id: int, site: str | None = None) -> dict:
    """某次运行的聚合（可限定站点）。站点经 device_name 关联 devices.location ——
    设备已删/改名时退化为"无站点"（LEFT JOIN），不算错。"""
    sql = (f"SELECT af.level, af.source, af.device_name, {exempt_case()} AS exempt "
           "FROM audit_findings af LEFT JOIN devices d ON d.name = af.device_name "
           "WHERE af.run_id = ?")
    params: list = [run_id]
    if site:
        sql += " AND d.location = ?"
        params.append(site)
    total = exempt = 0
    counts: dict[str, int] = {}
    by_source: dict[str, int] = {}
    devices: set = set()
    for level, source, dev, ex in db.execute(sql, params):
        devices.add(dev)
        if ex:
            exempt += 1
        else:
            total += 1
            counts[level] = counts.get(level, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1
    return {"total": total, "exempt": exempt, "counts": counts, "by_source": by_source,
            "devices": len(devices)}


def trends_series(db, weeks: int = 26, site: str | None = None) -> dict:
    """趋势序列：每周一条（该周最后一次运行）。"""
    picked = weekly_last(db)[-max(1, min(weeks, 260)):]

    points = []
    for idx, (wk, r) in enumerate(picked):
        agg = aggregate_run(db, r["id"], site)
        prev = picked[idx - 1][1] if idx else None
        points.append({
            "week": wk, "run_id": r["id"], "started_at": r["started_at"], "trigger": r["trigger"],
            "device_count": r["device_count"],
            "total": agg["total"], "exempt": agg["exempt"],
            "counts": agg["counts"], "by_source": agg["by_source"], "devices": agg["devices"],
            "ruleset_changed": bool(prev) and prev["ruleset_hash"] != r["ruleset_hash"],
            "exceptions_changed": bool(prev) and prev["exceptions_hash"] != r["exceptions_hash"],
        })
    return {"points": points, "site": site or "", "weeks": len(points)}


def trend_diff(db, from_run: int | None = None, to_run: int | None = None) -> dict:
    """收敛/恶化榜：按规则对比两次运行的**未豁免命中设备数**。

    缺省基准 = 最新周最后一条 vs 上一周最后一条（与趋势图同基准，
    避免"榜变了但图没动"的困惑）。只有一周数据时返回可读的 reason，不造数。
    """
    db.row_factory = sqlite3.Row
    weekly = weekly_last(db)
    if to_run is None:
        to_run = weekly[-1][1]["id"] if weekly else None
    if from_run is None:
        from_run = weekly[-2][1]["id"] if len(weekly) >= 2 else None
    if not from_run or not to_run:
        return {"from": None, "to": None, "rules": [], "converged": 0, "worsened": 0,
                "reason": "需要至少两周的运行记录才能对比（当前不足）"}

    def per_rule(run_id: int) -> dict:
        out: dict[str, dict] = {}
        for rid, title, level, dev, ex in db.execute(
                f"SELECT af.rule_id, af.title, af.level, af.device_name, {exempt_case()} AS exempt "
                "FROM audit_findings af WHERE af.run_id = ?", (run_id,)):
            e = out.setdefault(rid, {"rule_id": rid, "title": title, "level": level,
                                     "devices": set(), "exempt": 0})
            if ex:
                e["exempt"] += 1
            else:
                e["devices"].add(dev)
        return out

    a, b = per_rule(from_run), per_rule(to_run)
    rules = []
    for rid in set(a) | set(b):
        ea, eb = a.get(rid), b.get(rid)
        fa = len(ea["devices"]) if ea else 0
        tb = len(eb["devices"]) if eb else 0
        if fa == tb:
            continue                     # 只列有变化的（零变化的规则不占版面）
        ref = eb or ea
        rules.append({"rule_id": rid, "title": ref["title"], "level": ref["level"],
                      "from_count": fa, "to_count": tb, "delta": tb - fa,
                      "exempt_count": (eb or ea)["exempt"]})
    rules.sort(key=lambda x: (-abs(x["delta"]), x["rule_id"]))

    def meta(run_id: int) -> dict:
        row = db.execute("SELECT started_at, trigger FROM audit_runs WHERE id = ?",
                         (run_id,)).fetchone()
        return {"run_id": run_id, "week": iso_week(row[0]) if row else "",
                "started_at": row[0] if row else "", "trigger": row[1] if row else ""}

    return {"from": meta(from_run), "to": meta(to_run), "rules": rules,
            "converged": sum(1 for r in rules if r["delta"] < 0),
            "worsened": sum(1 for r in rules if r["delta"] > 0)}
