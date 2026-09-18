"""堆叠成员级解析测试 —— 编号 / 序列号 / 版本 / ROM / 运行时间

真机样本（backend/tests/fixtures/，CRLF 原样）：
- `Cisco 2960x stack show version.txt` —— SZXD1SWI01（2960X 三成员堆叠）
- `Aruba 6300 vsf detail.txt`        —— BJQD1SWI01（6300M 双成员 VSF）

关键事实：堆叠整机共享一个软件镜像 —— 只有 classic IOS 堆叠的 `show version`
成员表逐成员给出软件版本；Aruba VSF 的成员级版本只有 ROM Version。
"""
from pathlib import Path

import pytest

import storage.database as db
from services.collector_service import (
    _is_svl_device,
    _parse_uptime_phrase,
    _save_to_sqlite,
    extract_member_ids,
    extract_member_rom_versions,
    extract_member_uptimes,
    extract_member_versions,
    extract_serial_number,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


CISCO_STACK = "Cisco 2960x stack show version.txt"
ARUBA_VSF = "Aruba 6300 vsf detail.txt"
CISCO_SVL = "Cisco 9500 svl uptime.txt"


# ============================================================
# 成员版本
# ============================================================

def test_cisco堆叠_成员表逐成员给出版本():
    versions = extract_member_versions(read_fixture(CISCO_STACK))
    assert versions == "15.2(4)E8, 15.2(4)E8, 15.2(4)E8"


def test_cisco堆叠_升级未完成时成员版本不同():
    """一个成员已重启进新镜像、另一个还在跑旧版本 —— 唯一值得报警的场景"""
    raw = (
        "SW1 uptime is 1 day, 2 hours, 3 minutes\n"
        "Switch Ports Model                     SW Version            SW Image\n"
        "------ ----- -----                     ----------            ----------\n"
        "*    1 52    WS-C2960X-48FPD-L         15.2(4)E8             C2960X-UNIVERSALK9-M\n"
        "     2 52    WS-C2960X-48LPD-L         15.2(4)E5             C2960X-UNIVERSALK9-M\n"
    )
    assert extract_member_versions(raw) == "15.2(4)E8, 15.2(4)E5"


def test_无成员表返回空():
    """Aruba VSF / IOS-XE 堆叠 / 单机：没有成员版本表 → 空串（由报告侧用整机版本填充）"""
    assert extract_member_versions(read_fixture(ARUBA_VSF)) == ""
    assert extract_member_versions("SHAD1SWI01 uptime is 1 year, 2 weeks, 3 days\n") == ""
    assert extract_member_versions("") == ""


# ============================================================
# 成员 ROM 版本（Aruba VSF）
# ============================================================

def test_aruba_vsf_成员ROM版本():
    assert extract_member_rom_versions(read_fixture(ARUBA_VSF)) == "FL.01.11.0001, FL.01.11.0001"


def test_aruba_vsf_ROM版本不一致():
    """升级引导时逐个成员更新 —— 成员 ROM 版本可能不同"""
    raw = (
        "Member ID                            : 1\n"
        "\tROM Version                  : FL.01.11.0002\n"
        "Member ID                            : 2\n"
        "\tROM Version                  : FL.01.11.0001\n"
    )
    assert extract_member_rom_versions(raw) == "FL.01.11.0002, FL.01.11.0001"


def test_非vsf没有ROM版本():
    assert extract_member_rom_versions("") == ""
    assert extract_member_rom_versions("SHAD1SWI01 uptime is 1 day\n") == ""


def test_cisco_从BOOTLDR行取ROM版本_按成员数复制():
    """Cisco 只上报主交换机的引导版本（成员段无该字段）→ 复制到每个成员行"""
    roms = extract_member_rom_versions(version_output=read_fixture(CISCO_STACK), member_count=3)
    assert roms == "15.2(4r)E3, 15.2(4r)E3, 15.2(4r)E3"


def test_cisco_老IOS的ROM行带版本():
    raw = "ROM: System Bootstrap, Version 12.2(44)SE6, RELEASE SOFTWARE (fc1)\n"
    assert extract_member_rom_versions(version_output=raw, member_count=1) == "12.2(44)SE6"


def test_cisco_BOOTLDR优先于ROM行():
    raw = (
        "ROM: System Bootstrap, Version 12.2(44)SE6, RELEASE SOFTWARE (fc1)\n"
        "BOOTLDR: C2960X Boot Loader (C2960X-HBOOT-M) Version 15.2(4r)E3, RELEASE SOFTWARE (fc4)\n"
    )
    assert extract_member_rom_versions(version_output=raw, member_count=2) == "15.2(4r)E3, 15.2(4r)E3"


def test_cisco_ROM行无版本号时为空():
    """真机 2960X 的 ROM 行是「Bootstrap program is ...」（无版本），版本在 BOOTLDR 行"""
    raw = "ROM: Bootstrap program is C2960X boot loader\n"
    assert extract_member_rom_versions(version_output=raw, member_count=2) == ""


def test_aruba成员ROM优先于cisco分支():
    vsf = "Member ID                            : 1\n\tROM Version                  : FL.01.11.0002\n"
    roms = extract_member_rom_versions(vsf, "BOOTLDR: x Version 1.2.3, RELEASE\n", member_count=2)
    assert roms == "FL.01.11.0002"


# ============================================================
# 成员运行时间
# ============================================================

def test_时长短语_支持缺段与单复数():
    assert _parse_uptime_phrase("1 year, 29 weeks, 2 days, 5 hours, 48 minutes") == \
        365 * 86400 + 29 * 7 * 86400 + 2 * 86400 + 5 * 3600 + 48 * 60
    assert _parse_uptime_phrase("350 days 34 mins 32 secs") == 350 * 86400 + 34 * 60 + 32
    assert _parse_uptime_phrase("180 days 4 hrs 56 secs") == 180 * 86400 + 4 * 3600 + 56
    # Aruba 的「不足一分钟」不贡献数值，但小时段要算
    assert _parse_uptime_phrase("89 weeks, 1 day, 21 hours under a minute") == \
        89 * 7 * 86400 + 86400 + 21 * 3600
    assert _parse_uptime_phrase("no numbers here") is None


def test_cisco堆叠_成员运行时间_主交换机取设备级():
    uptimes = [int(v) for v in extract_member_uptimes(version_output=read_fixture(CISCO_STACK)).split(", ")]

    assert len(uptimes) == 3
    # 1 号成员 = 设备级 `<主机名> uptime is 9 weeks, 3 days, 5 hours, 52 minutes`
    assert uptimes[0] == 9 * 7 * 86400 + 3 * 86400 + 5 * 3600 + 52 * 60
    # 2/3 号成员来自各自成员段的 `Switch Uptime : ... (54 minutes)`
    assert uptimes[1] == 9 * 7 * 86400 + 3 * 86400 + 5 * 3600 + 54 * 60
    assert uptimes[1] == uptimes[2]


def test_aruba_vsf_成员运行时间():
    uptimes = [int(v) for v in extract_member_uptimes(vsf_output=read_fixture(ARUBA_VSF)).split(", ")]

    assert len(uptimes) == 2
    assert uptimes[0] == 89 * 7 * 86400 + 86400 + 21 * 3600 + 2 * 60   # ...21 hours, 2 minutes
    assert uptimes[1] == 89 * 7 * 86400 + 86400 + 21 * 3600            # ...21 hours under a minute


def test_单机没有成员运行时间():
    """只有一个值（非堆叠）不返回 —— 单机运行时间由设备级字段负责"""
    assert extract_member_uptimes(version_output="SW1 uptime is 3 days, 4 hours, 5 minutes\n") == ""
    assert extract_member_uptimes() == ""


# ============================================================
# C9500 StackWise Virtual 特例（onboard logging 取成员运行时间）
# ============================================================

def test_c9500_svl_成员运行时间():
    """两段 Current uptime：顺序 = active、standby（真机样本 SHAD1SWI01）"""
    uptimes = [int(v) for v in extract_member_uptimes(svl_output=read_fixture(CISCO_SVL)).split(", ")]

    assert len(uptimes) == 2
    assert uptimes[0] == 365 * 86400 + 40 * 7 * 86400 + 4 * 86400 + 23 * 3600 + 6 * 60   # active
    assert uptimes[1] == 365 * 86400 + 40 * 7 * 86400 + 4 * 86400 + 23 * 3600 + 5 * 60   # standby


def test_c9500_只有一段时不返回():
    """单机 C9500 没有 standby 段 → 返回空，由报告侧回退设备级运行时间"""
    raw = "Current uptime          :  1  years  40  weeks  4  days  23 hours  6  minutes\n"
    assert extract_member_uptimes(svl_output=raw) == ""


def test_c9500特例判定按型号():
    assert _is_svl_device("C9500-24Y4C, C9500-24Y4C") is True
    assert _is_svl_device("C9200L-24P-4G") is False
    assert _is_svl_device("") is False


# ============================================================
# 成员三元组落库（device_members 档案 + devices 成员列）
# ============================================================

@pytest.fixture
def restore_db_path():
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


def save(tmp_path, **overrides):
    """以 Cisco 双成员堆叠为默认场景写一次采集（member_ids 为空 —— 与真机一致）"""
    params = dict(
        device_name="SZXD1SWI01", device_ip="10.0.0.1",
        device_type="cisco_ios", device_platform="cisco_ios",
        week="2026-38", collected_at="2026-09-17T09:00:00",
        running_config="", logs_raw="",
        performance_results="{}", validation_results="{}", change_results="{}",
        software_version="15.2(4)E8", serial_number="FCW2129B3TR, FCW2126A49Z",
        device_model="WS-C2960X-48FPD-L, WS-C2960X-48LPD-L",
        system_uptime_seconds=5723520,
        port_details=[], port_errors={}, neighbors_data=[], boot_history="",
        member_versions="15.2(4)E8, 15.2(4)E5",
        member_uptimes="5723520, 5723640",
    )
    params.update(overrides)
    db.init_db(str(tmp_path))
    _save_to_sqlite(**params)
    return db.get_connection()


def test_cisco堆叠成员全部进入物理档案(tmp_path, restore_db_path):
    """member_ids 为空（Cisco 没有 Member ID）也要逐成员建档 —— 曾经 zip 空列表导致一条都不进"""
    conn = save(tmp_path)

    rows = {
        r["serial_number"]: (r["last_member"], r["version"])
        for r in conn.execute("SELECT serial_number, last_member, version FROM device_members")
    }
    assert rows == {
        "FCW2129B3TR": ("1", "15.2(4)E8"),   # 成员自己的版本
        "FCW2126A49Z": ("2", "15.2(4)E5"),
    }


def test_成员版本与运行时间落库(tmp_path, restore_db_path):
    conn = save(tmp_path)

    row = conn.execute(
        "SELECT member_versions, member_uptimes, member_rom_versions FROM devices WHERE name='SZXD1SWI01'"
    ).fetchone()
    assert row["member_versions"] == "15.2(4)E8, 15.2(4)E5"
    assert row["member_uptimes"] == "5723520, 5723640"
    assert row["member_rom_versions"] == ""


def test_aruba成员用真实MemberID建档(tmp_path, restore_db_path):
    conn = save(
        tmp_path,
        device_name="BJQD1SWI01", device_type="aruba_aoscx", device_platform="aruba_aoscx",
        serial_number="SG30LMQ17K, SG30LMQ108",
        device_model="JL659A, JL659A",
        software_version="FL.10.10.1070",
        member_ids="1, 2",
        member_versions="",                       # VSF 整堆叠共享镜像 → 无成员级版本
        member_rom_versions="FL.01.11.0001, FL.01.11.0001",
        member_uptimes="53989320, 53989200",
    )

    rows = {
        r["serial_number"]: (r["last_member"], r["version"])
        for r in conn.execute("SELECT serial_number, last_member, version FROM device_members")
    }
    assert rows == {
        "SG30LMQ17K": ("1", "FL.10.10.1070"),   # 无成员级版本 → 退回整机版本
        "SG30LMQ108": ("2", "FL.10.10.1070"),
    }


def test_重复采集不覆盖已有成员数据(tmp_path, restore_db_path):
    """本轮解析失败（空串）时保留上一轮的值，不能把成员数据清空"""
    conn = save(tmp_path)
    save(tmp_path, member_versions="", member_uptimes="", member_rom_versions="")

    row = conn.execute(
        "SELECT member_versions, member_uptimes FROM devices WHERE name='SZXD1SWI01'"
    ).fetchone()
    assert row["member_versions"] == "15.2(4)E8, 15.2(4)E5"
    assert row["member_uptimes"] == "5723520, 5723640"


def test_单机也建档一次(tmp_path, restore_db_path):
    conn = save(
        tmp_path,
        device_name="BJQD1RTW01", device_type="cisco_ios_router",
        serial_number="FCZ1234", device_model="C8300-1N1S-4T2X",
        member_ids="", member_versions="", member_uptimes="",
    )

    rows = list(conn.execute("SELECT serial_number, last_member FROM device_members"))
    assert [(r["serial_number"], r["last_member"]) for r in rows] == [("FCZ1234", "1")]
