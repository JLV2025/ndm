"""运行时间解析测试 —— extract_uptime_seconds（Cisco show version / Aruba boot-history）

两个平台的**真实写法**在这里钉住（原文取自 data/ 下的 version.raw 与库里的 boot_history_raw）：

- Cisco 行首是**主机名**，不是 "System"：`SHAD1SWI01 uptime is 1 year, 29 weeks, ...`
  曾因只认 "System uptime is" 导致 18 台 Cisco 全部无运行时间（bug-116）
- Aruba AOS-CX **省略数值为 0 的单位**，days/hrs/mins/secs 四段任意一段都可能缺席：
  `350 days 34 mins 32 secs`（无 hrs）、`180 days 4 hrs 56 secs`（无 mins）
  曾因要求四段齐全导致 BJQD2QIS01 无运行时间（bug-117）
"""
from services.collector_service import (
    extract_uptime_seconds,
    _parse_aruba_uptime,
    _parse_cisco_uptime,
)


# ============================================================
# Cisco：show version
# ============================================================

def test_cisco_行首是主机名():
    """IOS-XE（C9500）真机样本，后面那行 control processor 不能抢匹配"""
    raw = (
        "ROM: IOS-XE ROMMON\n"
        "SHAD1SWI01 uptime is 1 year, 29 weeks, 2 days, 5 hours, 48 minutes\n"
        "Uptime for this control processor is 1 year, 29 weeks, 2 days, 5 hours, 50 minutes\n"
    )
    assert _parse_cisco_uptime(raw) == (365 + 29 * 7 + 2) * 86400 + 5 * 3600 + 48 * 60


def test_cisco_年周小时且缺日():
    """真机样本：KR5D1SWI01 —— 有 years/weeks/hours/minutes，没有 days"""
    raw = "KR5D1SWI01 uptime is 6 years, 27 weeks, 12 hours, 41 minutes\n"
    assert _parse_cisco_uptime(raw) == (6 * 365 + 27 * 7) * 86400 + 12 * 3600 + 41 * 60


def test_cisco_单数单位():
    """1 week / 1 day / 1 hour 的单数写法"""
    raw = "BJQD1RTW01 uptime is 3 days, 16 hours, 28 minutes\n"
    assert _parse_cisco_uptime(raw) == (3 * 86400) + 16 * 3600 + 28 * 60
    assert _parse_cisco_uptime("X uptime is 1 week, 20 hours, 37 minutes\n") == \
        (7 * 86400) + 20 * 3600 + 37 * 60


def test_cisco_无运行时间行返回空():
    assert _parse_cisco_uptime("Cisco IOS Software, Version 15.2\n") is None


# ============================================================
# Aruba：show boot-history
# ============================================================

def test_aruba_缺小时段():
    """BJQD2QIS01 真机样本：0 小时时整段省略"""
    raw = "Index : 2\nCurrent Boot, up for 350 days 34 mins 32 secs\n"
    assert _parse_aruba_uptime(raw) == 350 * 86400 + 34 * 60 + 32


def test_aruba_缺分钟段():
    """真机样本：180 days 4 hrs 56 secs"""
    raw = "Current Boot, up for 180 days 4 hrs 56 secs\n"
    assert _parse_aruba_uptime(raw) == 180 * 86400 + 4 * 3600 + 56


def test_aruba_缺秒段():
    """真机样本：124 days 5 hrs 19 mins"""
    raw = "Current Boot, up for 124 days 5 hrs 19 mins\n"
    assert _parse_aruba_uptime(raw) == 124 * 86400 + 5 * 3600 + 19 * 60


def test_aruba_四段齐全():
    """真机样本：1 days 23 hrs 32 mins 27 secs（AOS-CX 不因数值 1 用单数）"""
    raw = "Current Boot, up for 1 days 23 hrs 32 mins 27 secs\n"
    assert _parse_aruba_uptime(raw) == 86400 + 23 * 3600 + 32 * 60 + 27


def test_aruba_无CurrentBoot行返回空():
    assert _parse_aruba_uptime("Management module\n\nIndex : 0\n") is None


# ============================================================
# 分派逻辑
# ============================================================

def test_分派_Cisco取version_Aruba取boot_history():
    version = "SW1 uptime is 2 days, 3 hours, 4 minutes\n"
    boot = "Current Boot, up for 5 days 6 hrs 7 mins 8 secs\n"

    assert extract_uptime_seconds(version, boot, "cisco_ios") == 2 * 86400 + 3 * 3600 + 4 * 60
    assert extract_uptime_seconds(version, boot, "cisco_ios_router") == 2 * 86400 + 3 * 3600 + 4 * 60
    assert extract_uptime_seconds(version, boot, "aruba_aoscx") == 5 * 86400 + 6 * 3600 + 7 * 60 + 8


def test_分派_数据缺失返回空():
    assert extract_uptime_seconds("", "", "cisco_ios") is None
    assert extract_uptime_seconds("", "", "aruba_aoscx") is None
