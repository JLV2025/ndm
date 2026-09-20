"""端口角色推断测试 —— 让「BPDU Guard 不该配在上行口」这类端口级规则可信。

核心原则：**只在 high 置信时下结论**，低置信降级为「需人工判断」。
宁可说"我拿不准"，也不要瞎报警——一个资深专家最忌讳的就是瞎报警。
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analyzers.compliance import engine, loader  # noqa: E402
from analyzers.compliance.parser import parse_device  # noqa: E402
from analyzers.compliance.port_roles import (  # noqa: E402
    PortContext, build_port_roles, infer_port_role)

NAMING = {"pattern": r"^([A-Z]{2}[A-Z0-9])([DR][1-9])([A-Z]{3})(\d{2})$",
          "site_codes": ["BJQ"], "type_codes": {"SWI": "交换机"}, "core_dc_codes": ["R1"]}


# ---------------------------------------------------------------- 单端口推断

def test_stp_root_port_is_high_confidence_uplink():
    pr = infer_port_role("1/1/49", stp_role="root")
    assert pr.role == "uplink" and pr.confidence == "high"
    assert "根端口" in pr.reasons[0]


def test_switch_neighbor_is_high_confidence_uplink():
    pr = infer_port_role("1/1/49", neighbor_type="switch")
    assert pr.role == "uplink" and pr.confidence == "high"
    assert infer_port_role("Gi0/1", neighbor_type="firewall").confidence == "high"
    assert infer_port_role("Gi0/1", neighbor_type="router").confidence == "high"
    assert infer_port_role("Gi0/1", neighbor_type="sdwan").confidence == "high"


def test_terminal_neighbor_is_access():
    pr = infer_port_role("1/1/5", neighbor_type="server", config_hint="access")
    assert pr.role == "access" and pr.confidence == "medium"
    assert infer_port_role("1/1/6", neighbor_type="AP").role == "access"


def test_lag_member_and_uplink_list_are_uplink_evidence():
    assert infer_port_role("1/1/51", in_lag=True).role == "uplink"
    assert infer_port_role("1/1/51", in_lag=True).confidence == "medium"
    assert infer_port_role("Te3/0/1", in_uplink_list=True).role == "uplink"


def test_config_hint_alone_is_not_high_confidence():
    """只有 vlan trunk 这一个信号时不能算高置信——AP 端口也会是 trunk。"""
    pr = infer_port_role("1/1/10", config_hint="trunk")
    assert pr.role == "uplink" and pr.confidence == "medium"


def test_no_signal_is_unknown():
    pr = infer_port_role("1/1/2")
    assert pr.role == "unknown" and pr.confidence == "low"
    assert not pr.is_confident


def test_infrastructure_neighbor_wins_over_weak_config_hint():
    """真机案例（BJDD1SWI01 1/1/2）：对端 CDP 报出的是 SD-WAN 路由器，
    但该口的配置是 vlan access（SD-WAN 的 LAN 口本就落在某个 access VLAN 上）。
    对端是基础设施属硬证据，不能被"配置形态"这个弱提示降级——
    否则真实的上行口会被降成"拿不准"，反而制造噪声。"""
    pr = infer_port_role("1/1/2", neighbor_type="sdwan", config_hint="access")
    assert pr.role == "uplink" and pr.confidence == "high"
    assert "sdwan" in pr.reasons[0]


def test_config_hint_used_only_when_no_stronger_signal():
    """没有邻居/生成树证据时，配置形态才作为第二档依据。"""
    assert infer_port_role("1/1/2", config_hint="trunk").confidence == "medium"
    assert infer_port_role("1/1/2", config_hint="access").role == "access"


def test_description_keywords_are_low_confidence():
    pr = infer_port_role("1/1/20", description="UPLINK to core")
    assert pr.role == "uplink" and pr.confidence == "low"


# ---------------------------------------------------------------- 整机角色表

CFG = """hostname BJQD1SWI01
interface 1/1/1
    no shutdown
    vlan access 16
interface 1/1/49
    no shutdown
    description UPLINK
    vlan trunk native 255
    vlan trunk allowed all
"""


def test_build_port_roles_maps_normalized_names():
    dev = parse_device("BJQD1SWI01", CFG, NAMING)
    ctx = PortContext(stp_roles={"1/1/49": "root"}, neighbor_types={"1/1/1": "server"})
    roles = build_port_roles(dev, ctx)
    assert roles["1/1/49"].role == "uplink" and roles["1/1/49"].confidence == "high"
    assert roles["1/1/1"].role == "access"


def test_build_port_roles_normalizes_long_cisco_names():
    dev = parse_device("BJQD1SWI01", "hostname x\ninterface GigabitEthernet1/1/2\n    vlan access 16\n", NAMING)
    ctx = PortContext(neighbor_types={"Gi1/1/2": "switch"})
    roles = build_port_roles(dev, ctx)
    assert "Gi1/1/2" in roles and roles["Gi1/1/2"].role == "uplink"


def test_port_context_from_lag_membership():
    ctx = PortContext.from_lag_membership({"lag 1": ["1/1/51", "2/1/51"], "po 3": ["Gi1/0/1"]})
    assert ctx.lag_members == {"1/1/51", "2/1/51", "Gi1/0/1"}
    assert PortContext.from_lag_membership(None).lag_members == set()


# ---------------------------------------------------------------- 角色化冲突判定

BPDU_RULE = {
    "id": "cs_bpduguard_not_uplink", "title": "BPDU Guard 未配在上行口",
    "check": "command_set", "level": "强烈建议", "platforms": ["cx"],
    "source": "厂商基线", "severity": "vendor",
    "params": {"mode": "conflict", "scope": "block", "when_role": "uplink",
               "trigger": {"label": "BPDU Guard", "pattern": r"spanning-tree bpdu-guard"}},
}


def std_with(rule):
    return {"meta": {}, "sites": {"exempt_vlan_address": []}, "naming": NAMING,
            "vlans": {"standard": {}}, "rules": [rule]}


def test_bpduguard_on_confident_uplink_is_flagged():
    text = ("ArubaOS-CX\nhostname x\ninterface 1/1/49\n    no shutdown\n"
            "    spanning-tree bpdu-guard\n")
    ctx = PortContext(neighbor_types={"1/1/49": "switch"})
    res = engine.analyze("BJQD1SWI01", text, std_with(BPDU_RULE), port_context=ctx)
    f = res["findings"][0]
    assert f["check_kind"] == "conflict" and f["level"] == "强烈建议"
    assert "1/1/49 是上行口" in f["detail"]
    assert f["lines"] == [5]


def test_bpduguard_on_access_port_is_silent():
    text = ("ArubaOS-CX\nhostname x\ninterface 1/1/1\n    no shutdown\n"
            "    vlan access 16\n    spanning-tree bpdu-guard\n")
    ctx = PortContext(neighbor_types={"1/1/1": "server"})
    assert engine.analyze("BJQD1SWI01", text, std_with(BPDU_RULE),
                          port_context=ctx)["findings"] == []


def test_low_confidence_degrades_to_manual_review():
    """有上行倾向但证据不够硬（只有 vlan trunk allowed all）时不下结论，聚合成一条「需人工判断」。"""
    text = ("ArubaOS-CX\nhostname x\ninterface 1/1/49\n"
            "    vlan trunk allowed all\n    spanning-tree bpdu-guard\n")
    res = engine.analyze("BJQD1SWI01", text, std_with(BPDU_RULE))   # 不给邻居/生成树上下文
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f["level"] == "需人工判断"
    assert "疑似上行" in f["detail"] and "1/1/49" in f["detail"]
    assert f["locatable"] is False


def test_unknown_role_ports_are_not_listed():
    """完全判断不出的端口**不进**"拿不准"清单。

    真机教训：现网 214 处 `vlan trunk allowed <列举>` 其实是电话口，
    没有邻居数据时会被判成 unknown。把它们泼进报告，只会淹掉真问题。"""
    text = "ArubaOS-CX\nhostname x\ninterface 1/1/9\n    spanning-tree bpdu-guard\n"
    assert engine.analyze("BJQD1SWI01", text, std_with(BPDU_RULE))["findings"] == []


def test_manual_review_is_suppressed_when_a_real_finding_exists():
    """已经指出了真问题就不再叠加"还有几个拿不准"，避免噪声。"""
    text = ("ArubaOS-CX\nhostname x\n"
            "interface 1/1/49\n    spanning-tree bpdu-guard\n"
            "interface 1/1/50\n    spanning-tree bpdu-guard\n")
    ctx = PortContext(neighbor_types={"1/1/49": "switch"})   # 只确定 1/1/49
    res = engine.analyze("BJQD1SWI01", text, std_with(BPDU_RULE), port_context=ctx)
    assert len(res["findings"]) == 1
    assert res["findings"][0]["level"] == "强烈建议"


def test_port_roles_returned_in_result():
    text = "ArubaOS-CX\nhostname x\ninterface 1/1/49\n    spanning-tree bpdu-guard\n"
    ctx = PortContext(neighbor_types={"1/1/49": "switch"})
    res = engine.analyze("BJQD1SWI01", text, std_with(BPDU_RULE), port_context=ctx)
    assert res["port_roles"]["1/1/49"]["role"] == "uplink"
    assert res["port_roles"]["1/1/49"]["confidence"] == "high"


def test_loader_validates_when_role_value(tmp_path):
    (tmp_path / "_scopes.yaml").write_text(
        "sites: {}\nnaming: {pattern: 'x', type_codes: {}}\nvlans: {standard: {}}\n", encoding="utf-8")
    (tmp_path / "org-convention.yaml").write_text(
        "rules:\n"
        "  - id: r1\n    title: t\n    check: command_set\n    level: 改进建议\n"
        "    params: {mode: conflict, trigger: {label: X, pattern: y}}\n"
        "  - id: r2\n    title: t\n    check: command_set\n    level: 改进建议\n"
        "    params: {mode: conflict, when_role: sideways, trigger: {label: X, pattern: y}}\n",
        encoding="utf-8")
    with pytest.raises(loader.RuleError) as ei:
        loader.load_standard(tmp_path, use_cache=False)
    msg = str(ei.value)
    assert "需要 params.forbidden 或 params.when_role 之一" in msg
    assert "when_role 只能是" in msg
