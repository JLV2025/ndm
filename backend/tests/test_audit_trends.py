"""审计趋势端点测试 —— 周聚合、统计口径、对比榜。

三条要点：
  1. **每周取该周最后一次运行**；本周无运行则该周不出现（否则会把上周数据画成本周）
  2. **建议数只数未豁免的**：生效中的例外单列 exempt；已过期的例外照常计入建议
  3. 榜的缺省基准与图一致（最新周最后一条 vs 上一周最后一条）；数据不足时给 reason 不造数
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from api import audit as audit_api  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.execute("INSERT INTO devices (id, name, ip, type, location) VALUES (1, 'BJQD1SWI01', '10.0.0.1', 'aruba_aoscx', 'BJQ')")
    c.execute("INSERT INTO devices (id, name, ip, type, location) VALUES (2, 'ZGND1SWI01', '10.0.0.2', 'aruba_aoscx', 'ZGN')")
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def call(coro):
    return asyncio.run(coro)


def add_run(conn, rid, started, *, ruleset="R1", exceptions="E1", trigger="manual"):
    conn.execute(
        "INSERT INTO audit_runs (id, started_at, finished_at, trigger, ruleset_hash, "
        "exceptions_hash, device_count, finding_count, exempt_count, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 2, 0, 0, 'done')",
        (rid, started, started, trigger, ruleset, exceptions))
    conn.commit()


def add_finding(conn, run_id, device, rule, *, level="风险提示", source="公司总部", exempt=None):
    conn.execute(
        "INSERT INTO audit_findings (run_id, device_name, rule_id, title, level, source, "
        "exempt_by, exempt_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, device, rule, f"{rule} 标题", level, source,
         "exc-001" if exempt else None,
         json.dumps(exempt, ensure_ascii=False) if exempt else None))
    conn.commit()


ACTIVE = {"status": "active", "exception_id": "exc-001", "approved_by": "张工",
          "reason": "r", "compensating_control": "", "expires_at": "2027-03-19"}
EXPIRED = {**ACTIVE, "status": "expired"}


# ---------------------------------------------------------------- 周聚合

def test_每周取最后一次运行(conn):
    """同一周跑三次 → 只取最后那次（id 最大）的数据。"""
    add_run(conn, 1, "2026-09-14T08:00:00")
    add_run(conn, 2, "2026-09-16T08:00:00")
    add_run(conn, 3, "2026-09-20T08:00:00")          # 该周最后一次
    add_finding(conn, 1, "BJQD1SWI01", "old_rule")
    add_finding(conn, 3, "BJQD1SWI01", "new_rule")

    res = call(audit_api.audit_trends())
    assert res["weeks"] == 1
    p = res["points"][0]
    assert p["week"] == "2026-38" and p["run_id"] == 3
    assert p["total"] == 1 and "new_rule" not in p["counts"]     # 用的是 run 3 的数据


def test_本周无运行则该周不出现(conn):
    add_run(conn, 1, "2026-09-08T08:00:00")     # W37
    add_run(conn, 2, "2026-09-21T08:00:00")     # W39 —— 中间 W38 没有运行
    res = call(audit_api.audit_trends())
    assert [p["week"] for p in res["points"]] == ["2026-37", "2026-39"]


def test_weeks_参数限制点数(conn):
    for i, day in enumerate(["2026-09-08", "2026-09-14", "2026-09-21"], start=1):
        add_run(conn, i, f"{day}T08:00:00")
    assert len(call(audit_api.audit_trends(weeks=2))["points"]) == 2


# ---------------------------------------------------------------- 统计口径

def test_建议数不含生效中例外_过期例外照常计入(conn):
    add_run(conn, 1, "2026-09-20T08:00:00")
    add_finding(conn, 1, "BJQD1SWI01", "r1")                    # 普通建议
    add_finding(conn, 1, "BJQD1SWI01", "r2", exempt=ACTIVE)     # 生效中 → 单列
    add_finding(conn, 1, "BJQD1SWI01", "r3", exempt=EXPIRED)    # 已过期 → 回到建议统计

    p = call(audit_api.audit_trends())["points"][0]
    assert p["total"] == 2 and p["exempt"] == 1
    assert p["counts"]["风险提示"] == 2                          # 拆分里也只有未豁免的
    assert p["by_source"]["公司总部"] == 2


def test_站点过滤(conn):
    add_run(conn, 1, "2026-09-20T08:00:00")
    add_finding(conn, 1, "BJQD1SWI01", "r1")
    add_finding(conn, 1, "ZGND1SWI01", "r1")
    add_finding(conn, 1, "ZGND1SWI01", "r2")

    all_p = call(audit_api.audit_trends())["points"][0]
    bjq = call(audit_api.audit_trends(site="BJQ"))["points"][0]
    assert all_p["total"] == 3 and all_p["devices"] == 2
    assert bjq["total"] == 1 and bjq["devices"] == 1


def test_指纹变化标记(conn):
    add_run(conn, 1, "2026-09-08T08:00:00", ruleset="R1", exceptions="E1")
    add_run(conn, 2, "2026-09-14T08:00:00", ruleset="R2", exceptions="E1")   # 标准变了
    add_run(conn, 3, "2026-09-21T08:00:00", ruleset="R2", exceptions="E2")   # 豁免变了
    pts = call(audit_api.audit_trends())["points"]
    assert pts[0]["ruleset_changed"] is False and pts[0]["exceptions_changed"] is False
    assert pts[1]["ruleset_changed"] is True and pts[1]["exceptions_changed"] is False
    assert pts[2]["ruleset_changed"] is False and pts[2]["exceptions_changed"] is True


# ---------------------------------------------------------------- 收敛/恶化榜

def test_榜缺省基准是周最后两条(conn):
    add_run(conn, 1, "2026-09-14T08:00:00")     # W38
    add_run(conn, 2, "2026-09-20T08:00:00")     # W38 的最后一条（同周）
    add_run(conn, 3, "2026-09-21T08:00:00")     # W39
    # W38 最后一条（run 2）：r1 命中 2 台；W39（run 3）：r1 命中 1 台、r2 新增 1 台
    add_finding(conn, 2, "BJQD1SWI01", "r1")
    add_finding(conn, 2, "ZGND1SWI01", "r1")
    add_finding(conn, 3, "BJQD1SWI01", "r1")
    add_finding(conn, 3, "BJQD1SWI01", "r2")

    res = call(audit_api.audit_trend_diff())
    assert res["from"]["run_id"] == 2 and res["to"]["run_id"] == 3
    assert res["from"]["week"] == "2026-38" and res["to"]["week"] == "2026-39"
    by_rule = {r["rule_id"]: r for r in res["rules"]}
    assert by_rule["r1"]["from_count"] == 2 and by_rule["r1"]["to_count"] == 1
    assert by_rule["r1"]["delta"] == -1                       # 收敛
    assert by_rule["r2"]["from_count"] == 0 and by_rule["r2"]["delta"] == 1   # 恶化
    assert res["converged"] == 1 and res["worsened"] == 1


def test_榜不把豁免算作命中(conn):
    add_run(conn, 1, "2026-09-14T08:00:00")
    add_run(conn, 2, "2026-09-21T08:00:00")
    add_finding(conn, 1, "BJQD1SWI01", "r1")
    add_finding(conn, 1, "ZGND1SWI01", "r1")
    add_finding(conn, 2, "BJQD1SWI01", "r1")
    add_finding(conn, 2, "ZGND1SWI01", "r1", exempt=ACTIVE)   # 第二周被批准例外
    res = call(audit_api.audit_trend_diff())
    r = next(x for x in res["rules"] if x["rule_id"] == "r1")
    assert r["to_count"] == 1 and r["delta"] == -1 and r["exempt_count"] == 1


def test_榜数据不足时给原因不造数(conn):
    add_run(conn, 1, "2026-09-20T08:00:00")
    res = call(audit_api.audit_trend_diff())
    assert res["rules"] == [] and res["from"] is None and "至少两周" in res["reason"]


# ---------------------------------------------------------------- 历史列表

def test_历史列表含例外数与两个指纹(conn):
    add_run(conn, 1, "2026-09-20T08:00:00", ruleset="R9", exceptions="E9")
    runs = call(audit_api.list_runs())["runs"]
    assert runs[0]["exceptions_hash"] == "E9" and "exempt_count" in runs[0]


# ---------------------------------------------------------------- 按规则聚合（by-rule）

def test_按规则聚合带设备名单(conn):
    """反向视图：每条发现命中几台、都是谁（按台数降序、设备名升序）。"""
    add_run(conn, 1, "2026-09-20T08:00:00")
    add_finding(conn, 1, "BJQD1SWI01", "r_ntp")
    add_finding(conn, 1, "ZGND1SWI01", "r_ntp")
    add_finding(conn, 1, "BJQD1SWI01", "r_only_once")
    res = call(audit_api.run_by_rule(1))
    assert res["run_id"] == 1
    assert [r["rule_id"] for r in res["rules"]] == ["r_ntp", "r_only_once"]  # 台数降序
    ntp = res["rules"][0]
    assert ntp["count"] == 2 and ntp["title"] == "r_ntp 标题"
    assert [d["name"] for d in ntp["devices"]] == ["BJQD1SWI01", "ZGND1SWI01"]
    assert ntp["devices"][0]["location"] == "BJQ"


def test_按规则聚合_豁免不计入命中且单列(conn):
    """口径与趋势一致：生效中豁免不数进 count、不进设备名单；过期豁免回到普通统计。"""
    add_run(conn, 1, "2026-09-20T08:00:00")
    add_finding(conn, 1, "BJQD1SWI01", "r1")
    add_finding(conn, 1, "ZGND1SWI01", "r1", exempt=ACTIVE)
    r = call(audit_api.run_by_rule(1))["rules"][0]
    assert r["count"] == 1 and r["exempt_count"] == 1
    assert [d["name"] for d in r["devices"]] == ["BJQD1SWI01"]

    add_finding(conn, 1, "ZGND1SWI01", "r2", exempt=EXPIRED)   # 已过期：回到普通统计
    r2 = next(x for x in call(audit_api.run_by_rule(1))["rules"] if x["rule_id"] == "r2")
    assert r2["count"] == 1 and r2["exempt_count"] == 0


def test_按规则聚合_设备不在册时location为空(conn):
    add_run(conn, 1, "2026-09-20T08:00:00")
    add_finding(conn, 1, "GHOST01", "r1")               # 设备已删/改名
    d = call(audit_api.run_by_rule(1))["rules"][0]["devices"][0]
    assert d["name"] == "GHOST01" and d["location"] == ""


def test_按规则聚合_运行不存在404(conn):
    with pytest.raises(HTTPException) as ei:
        call(audit_api.run_by_rule(999))
    assert ei.value.status_code == 404


def test_明细支持按规则过滤(conn):
    add_run(conn, 1, "2026-09-20T08:00:00")
    add_finding(conn, 1, "BJQD1SWI01", "r1")
    add_finding(conn, 1, "BJQD1SWI01", "r2")
    res = call(audit_api.get_run(1, rule="r2"))
    assert len(res["findings"]) == 1 and res["findings"][0]["rule_id"] == "r2"
