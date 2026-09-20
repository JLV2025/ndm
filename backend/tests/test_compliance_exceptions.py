"""例外登记机制测试 —— 登记表校验 + 豁免判定。

三条语义要钉死：

  1. **过期 = 自动失效**：回到普通建议统计，但仍标注「例外已过期」
     （不能当作没发生过 —— 看报告的人要知道这条偏离现在没人担着）
  2. **撤销 = 软删除**：不参与豁免匹配，但条目保留
     （历史审计里的 exempt_by 要能永远查到出处）
  3. **ruleset_hash 不含例外**：登记例外不能让历史审计看起来"标准变过"

日期一律**相对"今天"构造**（days() 助手），避免测试随时间腐烂——
写死 2027-03-01 的话，到了那天整组用例集体失效。
"""
import datetime
import sys
from pathlib import Path

import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analyzers.compliance import engine, loader  # noqa: E402

SCOPES_YAML = """
sites: {}
naming:
  pattern: '^([A-Z]{2}[A-Z0-9])([DR][1-9])([A-Z]{3})(\\d{2})$'
  site_codes: [BJQ, ZGN, KWJ]
  type_codes: {}
vlans: {standard: {}}
"""

RULES_YAML = """
rules:
  - id: r_community
    title: 不得配置明文团体字
    check: absent_regex
    params: {pattern: '(?mi)^snmp-server community'}
    level: 风险提示
    source: 测试
    severity: vendor
  - id: r_hostname
    title: 配置内应有 hostname
    check: present_regex
    params: {pattern: '(?mi)^hostname'}
    level: 风险提示
    source: 测试
    severity: vendor
"""

CONFIG = "hostname BJQD1SWI01\nsnmp-server community public RO\n"


def days(n: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()


def exc(eid="exc-001", rule_id="r_community", type="device", value="BJQD1SWI01", **kw):
    e = {"id": eid, "rule_id": rule_id,
         "scope": {"type": type} if type == "all" else {"type": type, "value": value},
         "reason": "测试：改造前无法满足",
         "approved_by": "张工",
         "approved_at": days(-30),
         "expires_at": days(180)}
    e.update(kw)
    return e


def std_with(tmp_path, exceptions=None):
    """在临时目录组装最小规则库（两三条规则 + 可选例外表）并加载。"""
    (tmp_path / "_scopes.yaml").write_text(SCOPES_YAML, encoding="utf-8")
    (tmp_path / "org-convention.yaml").write_text(RULES_YAML, encoding="utf-8")
    if exceptions is not None:
        (tmp_path / "_exceptions.yaml").write_text(
            yaml.safe_dump({"exceptions": exceptions}, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
    return loader.load_standard(tmp_path, use_cache=False)


def finding(res, rule_id="r_community"):
    return next((f for f in res["findings"] if f["rule_id"] == rule_id), None)


# ---------------------------------------------------------------- 加载与校验

def test_missing_file_yields_empty_registry(tmp_path):
    """例外表是可选文件：没有它 = 空登记表，不是错误。"""
    std = std_with(tmp_path)
    assert std["exceptions"] == []


def test_valid_exception_loaded_with_source_file(tmp_path):
    std = std_with(tmp_path, [exc()])
    e = std["exceptions"][0]
    assert e["id"] == "exc-001" and e["source_file"] == "_exceptions.yaml"


def test_real_library_exceptions_loadable():
    std = loader.load_standard(use_cache=False)
    assert isinstance(std["exceptions"], list)


def test_unknown_rule_id_rejected(tmp_path):
    """拼错 rule_id 会让豁免静默失效——必须在加载时就报错。"""
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [exc(rule_id="no_such_rule")])
    assert "不在规则库" in str(ei.value)


def test_bad_scope_rejected_all_at_once(tmp_path):
    """三处 scope 问题一次报全（登记表编辑页要一次看到所有错误）。"""
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [
            exc(eid="exc-001", type="weird"),
            exc(eid="exc-002", type="device", value=""),
            exc(eid="exc-003", type="site", value="NOWHERE"),
        ])
    msg = str(ei.value)
    assert "scope.type" in msg and "需要 scope.value" in msg and "不是已知站点码" in msg


def test_all_scope_rejects_value(tmp_path):
    """scope=all 是"全网"，带 value 说明填错了。"""
    e = exc(type="all")
    e["scope"] = {"type": "all", "value": "BJQD1SWI01"}   # 助手会丢掉 all 的 value，这里显式构造
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [e])
    assert "不应填 value" in str(ei.value)


def test_missing_required_fields_rejected(tmp_path):
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [exc(reason="", approved_by="")])
    msg = str(ei.value)
    assert "reason" in msg and "approved_by" in msg


def test_bad_dates_rejected(tmp_path):
    """格式坏 + 到期早于批准，两类都要拦。"""
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [
            exc(eid="exc-001", expires_at="2027/03/01"),
            exc(eid="exc-002", rule_id="r_hostname", approved_at=days(0), expires_at=days(-10)),
        ])
    msg = str(ei.value)
    assert "YYYY-MM-DD" in msg and "晚于" in msg


def test_duplicate_exception_id_rejected(tmp_path):
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [exc(eid="exc-001"),
                            exc(eid="exc-001", rule_id="r_hostname")])
    assert "例外 id 重复" in str(ei.value)


def test_bad_id_format_rejected(tmp_path):
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [exc(eid="EXC1")])
    assert "exc-NNN" in str(ei.value)


def test_duplicate_scope_registration_rejected(tmp_path):
    """同一 (rule_id, scope) 登记两条 → 哪条生效说不清。"""
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [exc(eid="exc-001"), exc(eid="exc-002")])
    assert "重复登记" in str(ei.value)


def test_revoked_block_validated(tmp_path):
    with pytest.raises(loader.RuleError) as ei:
        std_with(tmp_path, [exc(revoked={"at": days(-5)})])   # 缺 by / reason
    msg = str(ei.value)
    assert "revoked" in msg and "by" in msg and "reason" in msg


# ---------------------------------------------------------------- 指纹

def test_ruleset_hash_ignores_exceptions_and_exceptions_hash_tracks_them(tmp_path):
    std_no = std_with(tmp_path)
    rules_hash = loader.ruleset_hash(std_no)

    std_yes = std_with(tmp_path, [exc()])
    assert loader.ruleset_hash(std_yes) == rules_hash          # 登记例外 ≠ 标准变了
    assert loader.exceptions_hash(std_yes) != loader.exceptions_hash(std_no)

    # 顺序不敏感（与 ruleset_hash 同规格：按 id 排序后再算）
    a = std_with(tmp_path, [exc(), exc(eid="exc-002", rule_id="r_hostname")])
    b = std_with(tmp_path, [exc(eid="exc-002", rule_id="r_hostname"), exc()])
    assert loader.exceptions_hash(a) == loader.exceptions_hash(b)


# ---------------------------------------------------------------- 豁免判定

def test_active_exception_marks_finding_and_excludes_from_counts(tmp_path):
    std = std_with(tmp_path, [exc()])
    res = engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ")
    f = finding(res)
    assert f is not None
    assert f["exempt"]["status"] == "active"
    assert f["exempt"]["exception_id"] == "exc-001"
    assert f["exempt"]["approved_by"] == "张工"
    assert res["counts"]["风险提示"] == 0     # 不计入建议统计
    assert res["exempt_count"] == 1           # 单列一类


def test_no_exception_keeps_phase1_behaviour(tmp_path):
    """向后兼容：没有例外表时，结果与一期逐字段一致（不出现 exempt 键）。"""
    std = std_with(tmp_path)
    res = engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ")
    f = finding(res)
    assert "exempt" not in f
    assert res["counts"]["风险提示"] == 1 and res["exempt_count"] == 0


def test_site_scope_matches_only_that_site(tmp_path):
    std = std_with(tmp_path, [exc(type="site", value="BJQ")])
    assert finding(engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ"))["exempt"]["status"] == "active"
    assert "exempt" not in finding(engine.analyze("BJQD1SWI01", CONFIG, std, site="ZGN"))


def test_device_scope_beats_site_scope(tmp_path):
    """最具体者优先：设备级与站点级同时命中时，设备级生效。"""
    std = std_with(tmp_path, [
        exc(eid="exc-001", type="site", value="BJQ", approved_by="站点批准人"),
        exc(eid="exc-002", type="device", value="BJQD1SWI01", approved_by="设备批准人"),
    ])
    f = finding(engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ"))
    assert f["exempt"]["exception_id"] == "exc-002"
    assert f["exempt"]["approved_by"] == "设备批准人"


def test_all_scope_matches_every_device(tmp_path):
    std = std_with(tmp_path, [exc(type="all")])
    f = finding(engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ"))
    assert f["exempt"]["status"] == "active"


def test_expired_exception_annotates_but_does_not_exempt(tmp_path):
    """到期即自动失效：回到普通统计，但标注「已过期」提醒复核。"""
    std = std_with(tmp_path, [exc(expires_at=days(-1))])
    res = engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ")
    f = finding(res)
    assert f["exempt"]["status"] == "expired"
    assert res["counts"]["风险提示"] == 1     # 回到普通统计
    assert res["exempt_count"] == 0


def test_expiring_soon_still_exempts(tmp_path):
    """即将到期（30 天内）仍然豁免——到期日当天之前都算数。"""
    std = std_with(tmp_path, [exc(expires_at=days(10))])
    res = engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ")
    assert finding(res)["exempt"]["status"] == "expiring"
    assert res["counts"]["风险提示"] == 0 and res["exempt_count"] == 1


def test_revoked_exception_is_ignored(tmp_path):
    """撤销 = 恢复原状：不豁免、不标注（历史审计里查得到）。"""
    std = std_with(tmp_path, [exc(revoked={"at": days(-5), "by": "李工", "reason": "已整改"})])
    res = engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ")
    f = finding(res)
    assert "exempt" not in f
    assert res["counts"]["风险提示"] == 1


def test_revoked_device_falls_back_to_active_site(tmp_path):
    """设备级被撤销后，站点级例外应重新生效（撤销条目不参与匹配，而不是整条规则失效）。"""
    std = std_with(tmp_path, [
        exc(eid="exc-001", type="site", value="BJQ"),
        exc(eid="exc-002", type="device", value="BJQD1SWI01",
            revoked={"at": days(-5), "by": "李工", "reason": "已整改"}),
    ])
    f = finding(engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ"))
    assert f["exempt"]["exception_id"] == "exc-001"


def test_expired_device_exception_falls_back_to_valid_site(tmp_path):
    """设备级过期、站点级仍生效 → 应当用站点级豁免。
    （写成"过期就标注"太容易，会让仍然有效的站点级例外失效。）"""
    std = std_with(tmp_path, [
        exc(eid="exc-001", type="site", value="BJQ"),
        exc(eid="exc-002", type="device", value="BJQD1SWI01", expires_at=days(-1)),
    ])
    f = finding(engine.analyze("BJQD1SWI01", CONFIG, std, site="BJQ"))
    assert f["exempt"]["exception_id"] == "exc-001"
    assert f["exempt"]["status"] == "active"


def test_exception_status_derivation():
    """状态推导的边界：30 天整算即将到期，31 天外算生效中，撤销压过一切。"""
    today = datetime.date(2026, 9, 20)
    base = {"id": "exc-001", "rule_id": "r", "reason": "r", "approved_by": "a",
            "approved_at": "2026-01-01"}
    assert engine.exception_status({**base, "expires_at": "2026-10-20"}, today) == "expiring"
    assert engine.exception_status({**base, "expires_at": "2026-10-21"}, today) == "active"
    assert engine.exception_status({**base, "expires_at": "2026-09-19"}, today) == "expired"
    assert engine.exception_status(
        {**base, "expires_at": "2027-01-01",
         "revoked": {"at": "2026-09-01", "by": "b", "reason": "r"}}, today) == "revoked"
