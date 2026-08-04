"""CDP/LLDP 邻居解析器测试 — 重点：Aruba AP 名识别"""
import pytest

from analyzers.neighbor_parser import (
    AP_NAME_RE,
    DEVICE_NAME_SEARCH_RE,
    _is_ap,
    _is_valid_network_device,
)
from analyzers.neighbor_parser import (
    parse_cdp_cisco, parse_lldp_cisco, parse_cdp_aruba,
    parse_lldp_aruba, parse_lldp_aruba_detail,
)


# ---- AP_NAME_RE ----

def test_ap_name_re_matches_standard():
    """标准 AP 名: 3位site + 点 + location + AP + 编号 + 点 + 4位MAC"""
    assert AP_NAME_RE.fullmatch("SZX.F11AP2.7C5F")


def test_ap_name_re_site_with_digit():
    """site code 含数字（KR3）也能匹配"""
    assert AP_NAME_RE.fullmatch("KR3.F11AP2.7C5F")


def test_ap_name_re_lowercase_mac():
    """MAC 小写也能匹配"""
    assert AP_NAME_RE.fullmatch("SZX.F11AP2.7c5f")


def test_ap_name_re_rejects_standard_device():
    """标准交换机名不是 AP 名"""
    assert not AP_NAME_RE.fullmatch("PVGD1SWI02")


def test_ap_name_re_rejects_old_ap_prefix():
    """旧式 AP 前缀名（AP-xxx）不属于新 AP 名格式"""
    assert not AP_NAME_RE.fullmatch("AP-515-LAB")


# ---- _is_ap ----

def test_is_ap():
    assert _is_ap("SZX.F11AP2.7C5F")
    assert not _is_ap("PVGD1SWI02")
    assert not _is_ap("AP-515-LAB")
    assert not _is_ap("")


# ---- _is_valid_network_device（放行 AP 名） ----

def test_is_valid_network_device_accepts_ap():
    assert _is_valid_network_device("SZX.F11AP2.7C5F")


def test_is_valid_network_device_still_accepts_standard():
    assert _is_valid_network_device("PVGD1SWI02")
    assert _is_valid_network_device("GTSPEKESX01")


# ---- DEVICE_NAME_SEARCH_RE（输出行中能搜到 AP 名） ----

def test_search_re_finds_ap_in_lldp_line():
    """LLDP 行中能捕获 AP 名（带域名后缀时只捕获 AP 名本身）"""
    m = DEVICE_NAME_SEARCH_RE.search("SZX.F11AP2.7C5F Gi1/0/14 120 AP Aruba 515")
    assert m and m.group(1) == "SZX.F11AP2.7C5F"


def test_search_re_ap_with_domain_suffix():
    m = DEVICE_NAME_SEARCH_RE.search("SZX.F11AP2.7C5F.corp.com  Gi1/0/14")
    assert m and m.group(1) == "SZX.F11AP2.7C5F"


def test_search_re_does_not_mangle_standard_line():
    """标准设备名行行为不变"""
    m = DEVICE_NAME_SEARCH_RE.search("BJQD1RTW01.corp.com  Gi0/0/1")
    assert m and m.group(1) == "BJQD1RTW01"


# ---- 5 个解析器：AP 保留为端点条目，其他端点照旧跳过 ----

def test_lldp_aruba_keeps_ap_and_skips_phone():
    """AP 保留为端点条目；Phone 端点照旧跳过"""
    text = """LOCAL-PORT  CHASSIS-ID         PORT-ID  PORT-DESC  TTL  SYS-NAME
1/1/14      8c:44:a5:2c:2c:10  1/1/14   AP          120  SZX.F11AP2.7C5F
1/1/15      8c:44:a5:2c:2c:11  1/1/15   IPPHONE     120  Phone-101"""
    entries = parse_lldp_aruba(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


def test_lldp_aruba_detail_keeps_ap():
    text = """LLDP Neighbor Information

Port                           : 1/1/14
Neighbor System-Name           : SZX.F11AP2.7C5F
Neighbor System-Description    : Aruba 515 (RW5) ArubaOS 10.x
Neighbor Port-ID               : 1/1/14
Neighbor Port-Desc             : AP
"""
    entries = parse_lldp_aruba_detail(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


def test_cdp_aruba_keeps_ap():
    text = """Port        Device ID                Platform                 Capability
1/1/6       BJQD1RTW01.corp.com      cisco C8300-1N1S-4T2X    IRS
1/1/14      SZX.F11AP2.7C5F          Aruba 515                AP
"""
    entries = parse_cdp_aruba(text)
    assert len(entries) == 2
    ap = [e for e in entries if e.neighbor_name == "SZX.F11AP2.7C5F"][0]
    assert ap.neighbor_type == "AP"


def test_cdp_cisco_keeps_ap():
    text = """Device ID              Local Intrfce  Holdtme  Capability  Platform  Port ID
SZX.F11AP2.7C5F        Gi1/0/14       135      AP          Aruba 515  Gi1/0/14
"""
    entries = parse_cdp_cisco(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


def test_lldp_cisco_keeps_ap():
    text = """Device ID           Local Intf  Hold-time  Capability  Port ID
SZX.F11AP2.7C5F     Gi1/0/14    120        AP          Gi1/0/14
"""
    entries = parse_lldp_cisco(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


def test_cdp_cisco_standard_device_unchanged():
    """标准交换机行为不变"""
    text = """Device ID              Local Intrfce  Holdtme  Capability  Platform  Port ID
BJQD1SWI02             Gi1/0/1        135      S          WS-C2960X  Gi1/0/1
"""
    entries = parse_cdp_cisco(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "BJQD1SWI02"
    assert entries[0].neighbor_type == "switch"
