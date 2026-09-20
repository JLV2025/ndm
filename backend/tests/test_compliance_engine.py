"""配置审计引擎测试 —— 解析、判定器、站点作用域、行号契约。

重点覆盖移植时改动的行为（见 docs/superpowers/plans/2026-09-18-compliance-audit.md §二）：
  - split("\\n") 的行号口径（配置以换行结尾时不能错位）
  - exempt_sites 支持多个分组名（netstd 原实现只读第一个，会静默失效）
  - 命名类判定 line 为 None 且 locatable=False
  - VLAN 名称判定定位到 name 行（而非 vlan 行）
  - 显式站点优先于设备名解析
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analyzers.compliance import engine, loader  # noqa: E402
from analyzers.compliance.parser import parse_device  # noqa: E402

NAMING = {
    "pattern": r"^([A-Z]{2}[A-Z0-9])([DR][1-9])([A-Z]{3})(\d{2})$",
    "site_codes": ["BJQ", "ZGN", "KWJ", "BJD"],
    "type_codes": {"SWI": "交换机", "RTW": "路由器", "QIS": "QI Lab Switch"},
    "known_name_exceptions": ["test_device"],
    "core_dc_codes": ["R1"],
}
SITES = {
    "osat": ["KWJ"],
    "special": ["BJD"],
    "qorvo_standard": ["BJQ", "ZGN"],
    "exempt_vlan_address": ["KWJ", "BJD"],
}
VLANS = {"standard": {1: "Default LAN", 16: "PC/Data Clients", 255: "LAN Switch"}}


def make_std(rules):
    return {"meta": {}, "sites": SITES, "naming": NAMING, "vlans": VLANS, "rules": rules}


def rule(**kw):
    base = {"id": "r1", "title": "t", "check": "present_regex", "level": "改进建议",
            "platforms": ["all"], "source": "测试", "severity": "vendor"}
    base.update(kw)
    return base


# ---------------------------------------------------------------- 解析与行号

def test_lines_use_split_newline_not_splitlines():
    """配置以换行结尾时，split("\\n") 会多出一个尾部空元素——行数差 1，但**索引必须对齐**。
    前端渲染同一份文本，若这边用 splitlines 就会整体错位一行。"""
    text = "hostname A\nvlan 16\n    name Data\n"
    dev = parse_device("BJQD1SWI01", text, NAMING)
    assert dev.lines == ["hostname A", "vlan 16", "    name Data", ""]

    text_no_eol = "hostname A\nvlan 16\n    name Data"
    dev2 = parse_device("BJQD1SWI01", text_no_eol, NAMING)
    assert dev2.lines == ["hostname A", "vlan 16", "    name Data"]


def test_vlan_name_line_points_to_name_statement():
    text = "vlan 16\n    name Qorvo-Data\n"
    dev = parse_device("BJQD1SWI01", text, NAMING)
    assert dev.vlans[16]["line"] == 1        # vlan 语句所在行
    assert dev.vlans[16]["name_line"] == 2   # name 语句所在行
    assert dev.vlans[16]["name"] == "Qorvo-Data"


def test_interface_block_records_end_line():
    text = "interface 1/1/1\n    no shutdown\n    vlan access 16\ninterface 1/1/2\n    no shutdown\n"
    dev = parse_device("BJQD1SWI01", text, NAMING)
    assert len(dev.if_blocks) == 2
    assert dev.if_blocks[0]["line"] == 1 and dev.if_blocks[0]["end"] == 3
    assert dev.if_blocks[1]["line"] == 4 and dev.if_blocks[1]["end"] == 5


# ---------------------------------------------------------------- 站点作用域

def test_explicit_site_overrides_name_derived():
    """NDM 以 devices.location 为准；设备名不规范的设备也要能命中站点规则。"""
    dev = parse_device("NOTANAME", "hostname x", NAMING, site="ZGN")
    assert dev.site == "ZGN" and dev.site_source == "location"

    dev2 = parse_device("BJQD1SWI01", "hostname x", NAMING)
    assert dev2.site == "BJQ" and dev2.site_source == "name"


def test_only_sites_limits_rule_to_listed_sites():
    # present_regex 未命中 → 出建议；规则限定 ZGN，故只有 ZGN 的设备会命中
    r = rule(id="zgn_only", only_sites=["ZGN"],
             check="present_regex", params={"pattern": "never-match"})
    std = make_std([r])
    assert len(engine.analyze("ZGND1SWI01", "hostname x", std)["findings"]) == 1
    assert len(engine.analyze("BJQD1SWI01", "hostname x", std)["findings"]) == 0


def test_exempt_sites_expands_every_group_name():
    """netstd 原实现只读 exempt[0]，写第二个分组会静默失效——这里必须两个都生效。"""
    r = rule(id="ex", check="present_regex", params={"pattern": "never-match"},
             exempt_sites=["osat", "special"])
    std = make_std([r])
    assert len(engine.analyze("KWJD1SWI01", "hostname x", std)["findings"]) == 0   # osat 组豁免
    assert len(engine.analyze("BJDD1SWI01", "hostname x", std)["findings"]) == 0   # special 组豁免
    assert len(engine.analyze("BJQD1SWI01", "hostname x", std)["findings"]) == 1   # 未豁免 → 出建议


def test_exempt_sites_accepts_literal_site_code():
    r = rule(id="ex2", check="present_regex", params={"pattern": "never-match"},
             exempt_sites=["ZGN"])
    std = make_std([r])
    assert len(engine.analyze("ZGND1SWI01", "hostname x", std)["findings"]) == 0
    assert len(engine.analyze("BJQD1SWI01", "hostname x", std)["findings"]) == 1


def test_platform_scope():
    r = rule(id="cxonly", platforms=["cx"], check="present_regex", params={"pattern": "never"})
    std = make_std([r])
    assert len(engine.analyze("BJQD1SWI01", "ArubaOS-CX\nhostname x", std)["findings"]) == 1
    assert len(engine.analyze("BJQD1SWI01", "version 15.2\nhostname x", std)["findings"]) == 0


# ---------------------------------------------------------------- 证据与行号契约

def test_absent_regex_finding_carries_lines_and_locatable():
    r = rule(id="telnet", check="absent_regex", params={"pattern": r"(?mi)^\s*telnet\s+server"})
    text = "ArubaOS-CX\nhostname x\ntelnet server vrf default\n"
    res = engine.analyze("BJQD1SWI01", text, make_std([r]))
    f = res["findings"][0]
    assert f["lines"] == [3]
    assert f["locatable"] is True
    assert f["evidence"][0]["text"].strip() == "telnet server vrf default"


def test_naming_findings_are_not_locatable():
    """设备名/hostname 类问题不落在配置文件的某一行，line 必须是 None（netstd 用 0，会与真实行号 1 混淆）。"""
    r = rule(id="nm", check="device_name_format")
    res = engine.analyze("bad-name", "hostname x", make_std([r]))
    f = res["findings"][0]
    assert f["evidence"][0]["line"] is None
    assert f["lines"] == []
    assert f["locatable"] is False


def test_present_regex_missing_gives_placeholder_evidence():
    r = rule(id="miss", check="present_regex", params={"pattern": "never-match"})
    f = engine.analyze("BJQD1SWI01", "hostname x", make_std([r]))["findings"][0]
    assert f["current"] == "(未配置)"
    assert f["locatable"] is False


def test_vlan_name_finding_locates_name_line():
    r = rule(id="vp", check="vlan_name_pure")
    text = "vlan 16\n    name 10.1.16.0_Data\n"
    f = engine.analyze("BJQD1SWI01", text, make_std([r]))["findings"][0]
    assert f["lines"] == [2]          # 指向 name 行，不是 vlan 行
    assert "名称内嵌网段" in f["evidence"][0]["text"]


def test_findings_sorted_by_level_then_rule_id():
    rules = [
        rule(id="b_improve", level="改进建议", check="present_regex", params={"pattern": "never"}),
        rule(id="a_strong", level="强烈建议", check="present_regex", params={"pattern": "never"}),
        rule(id="c_risk", level="风险提示", check="present_regex", params={"pattern": "never"}),
    ]
    res = engine.analyze("BJQD1SWI01", "hostname x", make_std(rules))
    assert [f["rule_id"] for f in res["findings"]] == ["a_strong", "c_risk", "b_improve"]


# ---------------------------------------------------------------- 规则库

def test_real_rule_library_loads_and_validates():
    std = loader.load_standard()
    assert len(std["rules"]) >= 26
    assert "_scopes.yaml" not in std["rule_files"]          # 共用段不算规则文件
    assert all(r.get("source_file") for r in std["rules"])   # 每条都注入了来源文件
    ids = [r["id"] for r in std["rules"]]
    assert len(ids) == len(set(ids))                          # id 不重复


def test_ruleset_hash_is_stable_and_content_sensitive():
    std = loader.load_standard(use_cache=False)
    h1 = loader.ruleset_hash(std)
    h2 = loader.ruleset_hash(loader.load_standard(use_cache=False))
    assert h1 == h2
    mutated = dict(std)
    mutated["rules"] = std["rules"] + [rule(id="brand_new", severity="shall")]
    assert loader.ruleset_hash(mutated) != h1


def test_loader_rejects_unknown_check(tmp_path):
    (tmp_path / "_scopes.yaml").write_text(
        "sites: {}\nnaming: {pattern: 'x', type_codes: {}}\nvlans: {standard: {}}\n", encoding="utf-8")
    (tmp_path / "org-convention.yaml").write_text(
        "rules:\n  - id: bad\n    title: t\n    check: no_such_check\n    level: 改进建议\n",
        encoding="utf-8")
    with pytest.raises(loader.RuleError) as ei:
        loader.load_standard(tmp_path, use_cache=False)
    assert "未知判定器" in str(ei.value)


def test_loader_reports_all_errors_at_once(tmp_path):
    """规则编辑页要一次看到全部问题，不能改一个报一个。"""
    (tmp_path / "_scopes.yaml").write_text(
        "sites: {}\nnaming: {pattern: 'x', type_codes: {}}\nvlans: {standard: {}}\n", encoding="utf-8")
    (tmp_path / "org-convention.yaml").write_text(
        "rules:\n"
        "  - id: r1\n    title: t\n    check: no_such_check\n    level: 改进建议\n"
        "  - id: r2\n    title: t\n    check: present_regex\n    level: 不存在的档位\n",
        encoding="utf-8")
    with pytest.raises(loader.RuleError) as ei:
        loader.load_standard(tmp_path, use_cache=False)
    msg = str(ei.value)
    assert "未知判定器" in msg and "不在" in msg


# ---------------------------------------------------------------- 组合判定器

CISCO_SNMP = "version 15.2\nhostname SWI\nsnmp-server group GRP-SNMP-V3 v3 priv\n"


def test_command_set_all_of_names_the_missing_item():
    """真机场景：现网 Cisco 18/18 都配了 SNMPv3 group、0 台配 user —— 必须点名缺"用户"。"""
    r = rule(id="cs_snmpv3", check="command_set", params={
        "mode": "all_of",
        "group": "SNMPv3 三件套",
        "items": [
            {"label": "服务器组", "pattern": r"(?mi)^snmp-server group"},
            {"label": "用户", "pattern": r"(?mi)^snmp-server user"},
        ],
    })
    f = engine.analyze("BJQD1SWI01", CISCO_SNMP, make_std([r]))["findings"][0]
    assert f["check_kind"] == "all_of"
    assert f["satisfied"] == ["服务器组"]
    assert f["missing"] == ["用户"]
    assert "已配 1/2" in f["detail"]
    assert f["lines"] == [3]          # 指向已配的那条，便于对照


def test_command_set_all_of_silent_when_complete():
    r = rule(id="cs_ok", check="command_set", params={
        "mode": "all_of", "group": "G",
        "items": [{"label": "a", "pattern": "hostname"}, {"label": "b", "pattern": "version"}]})
    assert engine.analyze("BJQD1SWI01", CISCO_SNMP, make_std([r]))["findings"] == []


def test_command_set_requires_only_fires_when_trigger_present():
    r = rule(id="dai", check="command_set", params={
        "mode": "requires",
        "trigger": {"label": "动态 ARP 检测", "pattern": r"(?mi)^ip arp inspection"},
        "required": [{"label": "DHCP snooping", "pattern": r"(?mi)^ip dhcp snooping"}],
    })
    std = make_std([r])
    # 没配 DAI → 不该提示缺 DHCP snooping
    assert engine.analyze("BJQD1SWI01", CISCO_SNMP, std)["findings"] == []
    # 配了 DAI 但没配 snooping → 提示
    text = CISCO_SNMP + "ip arp inspection vlan 16\n"
    f = engine.analyze("BJQD1SWI01", text, std)["findings"][0]
    assert f["check_kind"] == "requires" and f["missing"] == ["DHCP snooping"]
    assert f["lines"] == [4]


def test_command_set_requires_satisfied_is_silent():
    r = rule(id="dai2", check="command_set", params={
        "mode": "requires",
        "trigger": {"label": "DAI", "pattern": r"(?mi)^ip arp inspection"},
        "required": [{"label": "snooping", "pattern": r"(?mi)^ip dhcp snooping"}]})
    text = CISCO_SNMP + "ip arp inspection vlan 16\nip dhcp snooping\n"
    assert engine.analyze("BJQD1SWI01", text, make_std([r]))["findings"] == []


def test_command_set_conflict_is_scoped_to_one_block():
    """conflict 默认按接口块判定：同一口上冲突才报，不同口各配各的不报。"""
    r = rule(id="conf", check="command_set", params={
        "mode": "conflict", "scope": "block",
        "trigger": {"label": "BPDU Guard", "pattern": r"spanning-tree bpdu-guard"},
        "forbidden": [{"label": "root-guard", "pattern": r"spanning-tree root-guard"}],
    })
    std = make_std([r])
    same_block = "hostname x\ninterface 1/1/1\n    spanning-tree bpdu-guard\n    spanning-tree root-guard\n"
    diff_block = ("hostname x\ninterface 1/1/1\n    spanning-tree bpdu-guard\n"
                  "interface 1/1/2\n    spanning-tree root-guard\n")
    assert len(engine.analyze("BJQD1SWI01", same_block, std)["findings"]) == 1
    assert engine.analyze("BJQD1SWI01", diff_block, std)["findings"] == []


def test_command_set_conflict_evidence_includes_block_header():
    r = rule(id="conf2", check="command_set", params={
        "mode": "conflict", "scope": "block",
        "trigger": {"label": "X", "pattern": "aaa"},
        "forbidden": [{"label": "Y", "pattern": "bbb"}]})
    text = "hostname x\ninterface 1/1/5\n    aaa\n    bbb\n"
    f = engine.analyze("BJQD1SWI01", text, make_std([r]))["findings"][0]
    assert f["evidence"][0]["text"] == "interface 1/1/5"
    assert f["lines"] == [2, 3, 4]


def test_command_set_global_scope_catches_cross_section_conflict():
    r = rule(id="conf3", check="command_set", params={
        "mode": "conflict",
        "trigger": {"label": "A", "pattern": r"(?mi)^aaa new-model"},
        "forbidden": [{"label": "B", "pattern": r"(?mi)^no aaa new-model"}]})
    text = "version 15.2\naaa new-model\n!\nno aaa new-model\n"
    assert len(engine.analyze("BJQD1SWI01", text, make_std([r]))["findings"]) == 1


def test_loader_validates_command_set_params(tmp_path):
    (tmp_path / "_scopes.yaml").write_text(
        "sites: {}\nnaming: {pattern: 'x', type_codes: {}}\nvlans: {standard: {}}\n", encoding="utf-8")
    (tmp_path / "org-convention.yaml").write_text(
        "rules:\n"
        "  - id: bad_mode\n    title: t\n    check: command_set\n    level: 改进建议\n"
        "    params: {mode: nope}\n"
        "  - id: no_items\n    title: t\n    check: command_set\n    level: 改进建议\n"
        "    params: {mode: all_of}\n"
        "  - id: no_trigger\n    title: t\n    check: command_set\n    level: 改进建议\n"
        "    params: {mode: requires, required: [{label: a, pattern: b}]}\n",
        encoding="utf-8")
    with pytest.raises(loader.RuleError) as ei:
        loader.load_standard(tmp_path, use_cache=False)
    msg = str(ei.value)
    assert "mode 必须是" in msg and "需要 params.items" in msg and "需要 params.trigger.pattern" in msg
