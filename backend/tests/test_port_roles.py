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


def test_when_neighbor_separates_switch_peer_from_three_layer_peer():
    """分两档：对端是交换机（发 BPDU，真风险）vs 三层设备（不发 BPDU，无害）。
    真机实测：现网 21 处命中全部落在三层设备那一档，交换机档 0 处。"""
    switch_rule = dict(BPDU_RULE, id="on_switch",
                       params=dict(BPDU_RULE["params"], when_neighbor=["switch"]))
    infra_rule = dict(BPDU_RULE, id="on_infra", level="可选优化",
                      params=dict(BPDU_RULE["params"], when_neighbor=["sdwan", "router", "firewall"]))
    text = "ArubaOS-CX\nhostname x\ninterface 1/1/49\n    spanning-tree bpdu-guard\n"

    std = std_with(switch_rule)
    assert len(engine.analyze("BJQD1SWI01", text, std,
                              port_context=PortContext(neighbor_types={"1/1/49": "switch"}))["findings"]) == 1
    assert engine.analyze("BJQD1SWI01", text, std,
                          port_context=PortContext(neighbor_types={"1/1/49": "sdwan"}))["findings"] == []

    std2 = std_with(infra_rule)
    assert len(engine.analyze("BJQD1SWI01", text, std2,
                              port_context=PortContext(neighbor_types={"1/1/49": "sdwan"}))["findings"]) == 1
    assert engine.analyze("BJQD1SWI01", text, std2,
                          port_context=PortContext(neighbor_types={"1/1/49": "switch"}))["findings"] == []


def test_stp_root_counts_as_switch_peer():
    """只有 STP 数据、没有 CDP 数据的设备（现网 19/36 台）也必须能命中
    「对端是交换机」类规则 —— 根端口的定义就是朝根桥方向，根桥必然是交换机。"""
    rule = dict(BPDU_RULE, params=dict(BPDU_RULE["params"], when_neighbor=["switch"]))
    text = "ArubaOS-CX\nhostname x\ninterface 1/1/49\n    spanning-tree bpdu-guard\n"
    res = engine.analyze("BJQD1SWI01", text, std_with(rule),
                         port_context=PortContext(stp_roles={"1/1/49": "root"}))
    assert len(res["findings"]) == 1


def test_loader_rejects_bad_when_neighbor(tmp_path):
    (tmp_path / "_scopes.yaml").write_text(
        "sites: {}\nnaming: {pattern: 'x', type_codes: {}}\nvlans: {standard: {}}\n", encoding="utf-8")
    (tmp_path / "org-convention.yaml").write_text(
        "rules:\n"
        "  - id: r1\n    title: t\n    check: command_set\n    level: 改进建议\n"
        "    params: {mode: conflict, when_role: uplink, when_neighbor: switch,\n"
        "             trigger: {label: X, pattern: y}}\n",
        encoding="utf-8")
    with pytest.raises(loader.RuleError) as ei:
        loader.load_standard(tmp_path, use_cache=False)
    assert "when_neighbor 必须是字符串列表" in str(ei.value)


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


# ---------------------------------------------------------------- 上行口推导（采集侧 is_uplink）

def test_上行口推导_STP根端口最精确只认它():
    """多层站点：非核心交换机的上行口 = STP 根端口；此时不看邻居（避免把下行口算进来）。"""
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(
        stp_root_ports={"1/1/49"},
        neighbor_types={"1/1/1": "switch", "1/1/49": "switch", "1/1/10": "sdwan"},
        descriptions={})
    assert out == {"1/1/49": "STP 根端口（朝根桥）"}


def test_上行口推导_单机站点按SDWAN对端():
    """单台设备的站点：没有根端口（本机就是根/没跑 STP）→ 对着 SD-WAN LAN 口的是上行口。"""
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(
        stp_root_ports=set(),
        neighbor_types={"1/1/1": "server", "1/1/48": "sdwan", "1/1/47": "router"},
        descriptions={})
    assert set(out) == {"1/1/48", "1/1/47"}
    assert "sdwan" in out["1/1/48"] and "router" in out["1/1/47"]


def test_上行口推导_核心交换机不被误标():
    """核心交换机没有根端口，且朝下的口对端也是交换机 —— 绝不能标成上行。"""
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(
        stp_root_ports=set(),
        neighbor_types={"1/1/1": "switch", "1/1/2": "switch", "1/1/24": "switch"},
        descriptions={})
    assert out == {}


def test_上行口推导_描述关键词兜底():
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(
        stp_root_ports=None, neighbor_types={},
        descriptions={"Gi1/0/1": "Uplink to core", "Gi1/0/2": "to SDWAN",
                      "Gi1/0/3": "PC-Data", "Gi1/0/4": "TO_FW"})
    assert set(out) == {"Gi1/0/1", "Gi1/0/2", "Gi1/0/4"}
    assert "PC-Data" not in out


def test_上行口推导_手工指定始终并入():
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(stp_root_ports={"1/1/49"}, neighbor_types={},
                              descriptions={}, manual=["1/1/1", "1/1/49"])
    assert out["1/1/1"] == "手工指定（devices.uplink_ports）"
    assert out["1/1/49"] == "手工指定（devices.uplink_ports）"    # 手工覆盖推导理由


def test_上行口推导_什么信号都没有就不标():
    from analyzers.compliance.port_roles import derive_uplink_ports
    assert derive_uplink_ports() == {}


def test_上行口推导_聚合口展开成物理成员():
    """STP 根端口是 LAG（Po1/lag49）时必须展开 —— is_uplink 标在物理口上、流量也统计在物理口。"""
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(stp_root_ports={"Po1"}, lag_members={"po 1": ["Gi1/1/1", "Gi1/1/2"]})
    assert set(out) == {"Gi1/1/1", "Gi1/1/2"}
    assert all("LAG 成员" in why for why in out.values())


def test_上行口推导_手工指定的聚合口也展开():
    from analyzers.compliance.port_roles import derive_uplink_ports
    out = derive_uplink_ports(manual=["lag49"], lag_members={"lag 49": ["1/1/49", "1/1/50"]})
    assert set(out) == {"1/1/49", "1/1/50"}


def test_上行口推导_没有成员数据时保留聚合口本身():
    """拿不到成员关系时不要把标记丢掉 —— 总比什么都不标好（前端只渲染物理口，聚合名无害）。"""
    from analyzers.compliance.port_roles import derive_uplink_ports
    assert derive_uplink_ports(stp_root_ports={"Po9"}, lag_members={}) == {"Po9": "STP 根端口（朝根桥）"}


# ---------------------------------------------------------------- LAG 成员解析（采集侧共用）

def test_解析LAG成员_aruba格式():
    from services.collector_service import _parse_lag_members
    raw = "Aggregate name   : lag49\nInterfaces       : 1/1/49 2/1/49\n\n" \
          "Aggregate name   : lag1\nInterfaces       : 1/1/5 2/1/5\n"
    assert _parse_lag_members(raw) == {"lag 49": ["1/1/49", "2/1/49"], "lag 1": ["1/1/5", "2/1/5"]}


def test_解析LAG成员_cisco格式键名归一():
    from services.collector_service import _parse_lag_members
    raw = "Group  Port-channel  Protocol    Ports\n" \
          "1      Po1(SD)        LACP        Gi1/1/1(P)  Gi1/1/2(P)\n"
    out = _parse_lag_members(raw)
    assert "po 1" in out and out["po 1"] == ["Gi1/1/1", "Gi1/1/2"]


def test_解析LAG成员_空输入与坏输入不抛():
    from services.collector_service import _parse_lag_members
    assert _parse_lag_members("") == {} and _parse_lag_members(None) == {}
    assert _parse_lag_members("随便一段无关输出\n没有匹配格式") == {}
