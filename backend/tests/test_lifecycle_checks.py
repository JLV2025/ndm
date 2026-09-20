"""生命周期判定器与「集体性折叠」测试。

三条语义：
  1. EoL / 保修是**资产事实**，判定器不出配置行号（locatable=False）
  2. 「待查」判定看的是"有没有可用的核实信息"：缺项要待查、齐全但陈旧也要待查
  3. 折叠：集体性规则命中 ≥ 阈值（默认 3）折成**一条**网络级条目；不到阈值保持逐台
     （否则几十条"待查"会把真问题淹掉）
"""
import datetime
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from analyzers.compliance import engine, loader, runner  # noqa: E402

NAMING = {"pattern": r"^([A-Z]{2}[A-Z0-9])([DR][1-9])([A-Z]{3})(\d{2})$",
          "site_codes": ["BJQ", "ZGN", "DEZ"], "type_codes": {}}


def make_std(rules):
    return {"meta": {}, "sites": {}, "naming": NAMING, "vlans": {"standard": {}}, "rules": rules}


def rule(**kw):
    base = {"id": "ops_lifecycle_unknown", "title": "生命周期信息待查（型号 EoL 与保修期）",
            "check": "lifecycle_unknown", "level": "需人工判断", "platforms": ["all"],
            "source": "组织规范", "severity": "convention"}
    base.update(kw)
    return base


def days(n: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()


def live(**kw) -> dict:
    """生命周期上下文（与 source.load_lifecycle 同形）。"""
    base = {"device_name": "BJQD1SWI01", "models": ["C9500-48Y4C"], "model_eol": [],
            "serials": [], "extra_rows": []}
    base.update(kw)
    return base


CONFIG = "hostname X\n"


# ---------------------------------------------------------------- EoL

def test_eol_announced_有公告才出且无行号():
    r = rule(id="ops_eol_announced", check="eol_announced", level="风险提示")
    life = live(model_eol=[{"model": "C9500-48Y4C", "end_of_sale": "2025-01-31",
                            "end_of_support": "2030-01-31", "bulletin": "EOL123"}])
    res = engine.analyze("BJQD1SWI01", CONFIG, make_std([r]), lifecycle=life)
    f = res["findings"][0]
    assert "停止销售 2025-01-31" in f["current"] and "停止支持 2030-01-31" in f["current"]
    assert "EOL123" in f["current"]
    assert f["locatable"] is False and f["lines"] == []      # 资产数据没有配置行

    assert engine.analyze("BJQD1SWI01", CONFIG, make_std([r]), lifecycle=live())["findings"] == []


# ---------------------------------------------------------------- 保修

def test_warranty_expired_三态():
    r = rule(id="ops_warranty_expired", check="warranty_expired", level="风险提示",
             params={"warn_days": 90})
    std = make_std([r])

    expired = engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=live(
        serials=[{"serial": "A1", "warranty_end": days(-10)}]))["findings"]
    assert "保修已于" in expired[0]["current"] and "过期" in expired[0]["current"]

    soon = engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=live(
        serials=[{"serial": "A1", "warranty_end": days(30)}]))["findings"]
    assert "剩余 30 天" in soon[0]["current"]

    assert engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=live(
        serials=[{"serial": "A1", "warranty_end": days(400)}]))["findings"] == []
    assert engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=live())["findings"] == []


def test_warranty_expired_逐序列号列全():
    r = rule(id="ops_warranty_expired", check="warranty_expired", level="风险提示")
    res = engine.analyze("BJQD1SWI01", CONFIG, make_std([r]), lifecycle=live(serials=[
        {"serial": "A1", "warranty_end": days(-5)},
        {"serial": "B2", "warranty_end": days(10)}]))
    current = res["findings"][0]["current"]
    assert "A1" in current and "B2" in current


# ---------------------------------------------------------------- 待查

def test_lifecycle_unknown_四态():
    r = rule(collective=True, params={"stale_days": 365})
    std = make_std([r])

    nothing = engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=live())["findings"]
    assert "型号 EoL、保修期" in nothing[0]["current"]

    partial = engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=live(
        model_eol=[{"model": "X", "end_of_sale": "2025-01-01"}]))["findings"]
    assert "尚未登记：保修期" in partial[0]["current"]

    complete = live(model_eol=[{"model": "X", "end_of_sale": "2025-01-01",
                                "fetched_at": days(-10)}],
                    serials=[{"serial": "A1", "warranty_end": days(400),
                              "verified_at": days(-10)}])
    assert engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=complete)["findings"] == []

    stale = live(model_eol=[{"model": "X", "end_of_sale": "2025-01-01",
                             "fetched_at": days(-400)}],
                 serials=[{"serial": "A1", "warranty_end": days(400),
                           "verified_at": days(-400)}])
    f = engine.analyze("BJQD1SWI01", CONFIG, std, lifecycle=stale)["findings"]
    assert "已超过 365 天" in f[0]["current"]


# ---------------------------------------------------------------- 集体性折叠

def pair(dev, rule_id="ops_lifecycle_unknown"):
    return (dev, {"rule_id": rule_id, "title": "生命周期信息待查（型号 EoL 与保修期）",
                  "level": "需人工判断", "detail": "尚未登记"})


def test_折叠_达到阈值合成一条():
    std = make_std([rule(collective=True), rule(id="other", check="absent_regex")])
    pairs = [pair("A"), pair("B"), pair("C"), pair("D", rule_id="other")]
    out = engine.collapse_collective(pairs, std)

    assert len(out) == 2                                  # 3 台折叠成 1 条 + 非集体规则 1 条
    agg = next(f for n, f in out if n == "全网")
    assert agg["device_count"] == 3 and agg["devices"] == ["A", "B", "C"]
    assert "（3 台）" in agg["title"] and agg["collective"] is True
    assert agg["locatable"] is False and agg["lines"] == []
    assert [n for n, _ in out if n != "全网"] == ["D"]      # 非集体规则不受影响


def test_折叠_不到阈值保持逐台():
    std = make_std([rule(collective=True)])
    out = engine.collapse_collective([pair("A"), pair("B")], std)
    assert [n for n, _ in out] == ["A", "B"]


def test_折叠_阈值可由规则参数调整():
    std = make_std([rule(collective=True, params={"collective_threshold": 2})])
    out = engine.collapse_collective([pair("A"), pair("B")], std)
    assert out[0][0] == "全网" and out[0][1]["device_count"] == 2


def test_非集体规则永不折叠():
    std = make_std([rule(id="ops_eol_announced", check="eol_announced", level="风险提示")])
    pairs = [("A", {"rule_id": "ops_eol_announced"}), ("B", {"rule_id": "ops_eol_announced"}),
             ("C", {"rule_id": "ops_eol_announced"})]
    out = engine.collapse_collective(pairs, std)
    assert [n for n, _ in out] == ["A", "B", "C"]


# ---------------------------------------------------------------- 全量审计集成

@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    cfg = "hostname X\n" + "!\n" * 600
    for i, (name, loc) in enumerate([("BJQD1SWI01", "BJQ"), ("ZGND1SWI02", "ZGN"),
                                     ("DEZD1SWI01", "DEZ")], start=1):
        c.execute("INSERT INTO devices (id, name, ip, type, location) VALUES (?,?,?,?,?)",
                  (i, name, f"10.0.0.{i}", "aruba_aoscx", loc))
        c.execute("INSERT INTO collections (id, device_id, week, collected_at, running_config) "
                  "VALUES (?,?,?,?,?)", (10 + i, i, "2026-38", "2026-09-20T08:00:00", cfg))
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def test_全量审计把待查折叠成一条(conn):
    """三台都没登记生命周期 → audit_findings 里只应有一条 ops_lifecycle_unknown（全网级）。"""
    std = loader.load_standard(use_cache=False)
    res = runner.run_full_audit(conn, std, trigger="manual")
    rows = conn.execute(
        "SELECT device_name, device_id, title FROM audit_findings "
        "WHERE rule_id = 'ops_lifecycle_unknown'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "全网" and rows[0][1] is None      # 网络级条目没有单台设备
    assert "3 台" in rows[0][2]
    assert res["finding_count"] >= 1


def test_真实规则库加载三条生命周期规则():
    std = loader.load_standard(use_cache=False)
    ids = {r["id"]: r for r in std["rules"]}
    assert ids["ops_lifecycle_unknown"]["collective"] is True
    assert ids["ops_lifecycle_unknown"]["level"] == "需人工判断"
    assert ids["ops_eol_announced"]["level"] == "风险提示"
    assert ids["ops_warranty_expired"]["params"]["warn_days"] == 90
