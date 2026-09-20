"""全网审计执行器 —— API 端点与「采集后自动跑」共用同一实现。

为什么单独一个模块：这段逻辑（遍历设备 → 判定 → 落库）原本写在 `api/audit.py`
的端点函数里。采集后自动跑也要用它 —— 放在 api 层会被 services 反向依赖，
放在 analyzers 层两边都干净。

语义要点（与端点一致）：
  · 不可用的设备（采集失败 / 全文已被保留策略清理 / 从未采集）照样进 skipped 并带原因 ——
    静默跳过会让人以为"这些都审过了、没问题"。
  · 命中例外且生效中的 findings 记 `exempt_by` / `exempt_json`（当时的快照），
    并计入 `audit_runs.exempt_count`；已过期的例外照常计入建议统计（自动失效）。
"""
from __future__ import annotations

import datetime
import json
import time

from . import engine, loader, source


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def run_full_audit(db, std: dict, trigger: str = "manual") -> dict:
    """全网审计并入库，返回摘要（字段与 API 响应一致）。"""
    started = _now()
    cur = db.execute(
        "INSERT INTO audit_runs (started_at, trigger, ruleset_hash, ruleset_version, "
        "exceptions_hash, status) VALUES (?, ?, ?, ?, ?, 'running')",
        (started, trigger, loader.ruleset_hash(std), std.get("meta", {}).get("version"),
         loader.exceptions_hash(std)))
    run_id = cur.lastrowid

    t0 = time.time()
    items = source.list_audit_inputs(db)
    usable = [it for it in items if it.snapshot.usable]
    skipped, findings_total, exempt_total = [], 0, 0
    for item in items:
        snap = item.snapshot
        if not snap.usable:
            skipped.append({"device": snap.name, "reason": snap.reason})
            continue
        analysis = engine.analyze(snap.name, snap.config, std, site=snap.location,
                                  port_context=item.port_context,
                                  startup_config=snap.startup_config)
        for f in analysis["findings"]:
            exempt = f.get("exempt") or None
            if exempt and exempt.get("status") in ("active", "expiring"):
                exempt_total += 1
            db.execute(
                "INSERT INTO audit_findings (run_id, device_id, device_name, collection_id, week, "
                "rule_id, level, source, severity, title, detail, current_text, fix_text, why_text, "
                "note_text, evidence_json, lines_json, missing_json, controls_json, config_hash, "
                "ruleset_hash, exempt_by, exempt_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, snap.device_id, snap.name, snap.collection_id, snap.week,
                 f["rule_id"], f["level"], f["source"], f.get("severity", ""), f["title"],
                 f.get("detail", ""), f.get("current", ""), f.get("fix", ""), f.get("why", ""),
                 f.get("note", ""),
                 json.dumps(f.get("evidence", []), ensure_ascii=False),
                 json.dumps(f.get("lines", []), ensure_ascii=False),
                 json.dumps(f.get("missing", []), ensure_ascii=False),
                 json.dumps(f.get("controls", []), ensure_ascii=False),
                 snap.config_hash, loader.ruleset_hash(std),
                 (exempt or {}).get("exception_id") or None,
                 json.dumps(exempt, ensure_ascii=False) if exempt else None,
                 _now()))
            findings_total += 1

    db.execute("UPDATE audit_runs SET finished_at = ?, device_count = ?, finding_count = ?, "
               "exempt_count = ?, status = 'done' WHERE id = ?",
               (_now(), len(usable), findings_total, exempt_total, run_id))
    db.commit()
    return {
        "run_id": run_id,
        "device_count": len(usable),
        "finding_count": findings_total,
        "exempt_count": exempt_total,
        "duration_ms": int((time.time() - t0) * 1000),
        "ruleset_hash": loader.ruleset_hash(std),
        "exceptions_hash": loader.exceptions_hash(std),
        "skipped": skipped,
    }
