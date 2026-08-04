"""CDP/LLDP 邻居解析器测试 — 重点：Aruba AP 名识别"""
import pytest

from analyzers.neighbor_parser import (
    AP_NAME_RE,
    DEVICE_NAME_SEARCH_RE,
    _is_ap,
    _is_valid_network_device,
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
