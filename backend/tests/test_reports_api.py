"""自定义报告端点测试 —— 临时库直接调端点函数（HTTP 层之下）

覆盖两张表的共同改造：位置过滤、按物理成员展开、成员级版本一致性、带宽只列有流量的端口。
（「设备在线时间」报告已删除 —— 内容与设备运行状态报告重复，2026-09-18 用户定案）
"""
import asyncio

import pytest

import storage.database as db
from api import reports as reports_api

# (name, type, location, model, version, serial_number, member_ids,
#  member_versions, member_rom_versions, member_uptimes)
DEVICES = [
    # 单机：与下面的 JL659A 堆叠同型号、版本不同 —— 跨设备差异**不应**报警
    ("PVGD1SWI02", "aruba_aoscx", "PVG", "JL659A", "FL.10.10.1070", "", "", "", "", ""),
    ("KORD1SWI01", "aruba_aoscx", "KOR", "JL659A", "FL.10.16.1040", "", "", "", "", ""),
    # Cisco 三成员堆叠：成员 2 的软件版本与其余不同（升级未完成）
    ("SZXD1SWI01", "cisco_ios", "SZX",
     "WS-C2960X-48FPD-L, WS-C2960X-48LPD-L, WS-C2960X-48LPD-L", "15.2(4)E8",
     "FCW2129B3TR, FCW2126A49Z, FCW2126A49U", "",
     "15.2(4)E8, 15.2(4)E5, 15.2(4)E8", "", "5723520, 5723640, 5723640"),
    # Aruba 双成员 VSF：软件版本整堆叠共享，但成员 ROM 版本不同
    ("PVGD1SWI01", "aruba_aoscx", "PVG", "JL658A, JL658A", "FL.10.10.1070",
     "SG41LMP093, SG41LMP0B7", "1, 2", "", "FL.01.11.0002, FL.01.11.0001", "53989320, 53989200"),
]


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    for i, row in enumerate(DEVICES, start=1):
        name, dtype, loc, model, version, serial, mids, mver, mrom, mupt = row
        c.execute(
            "INSERT INTO devices (id, name, ip, type, location, model, version, last_synced, "
            "serial_number, member_ids, member_versions, member_rom_versions, member_uptimes) "
            "VALUES (?, ?, '10.0.0.1', ?, ?, ?, ?, '2026-09-17T12:00:00', ?, ?, ?, ?, ?)",
            (i, name, dtype, loc, model, version, serial, mids, mver, mrom, mupt),
        )
    c.commit()
    yield c
    c.commit()
    db.close_connection()
    db._db_path = original


def _add_collection(conn, device_id: int, collected_at: str = "2026-09-17T12:00:00",
                    uptime: int | None = None, version: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO collections (device_id, week, phase, collected_at, system_uptime_seconds, software_version) "
        "VALUES (?, '2026-38', '1', ?, ?, ?)",
        (device_id, collected_at, uptime, version),
    )
    conn.commit()
    return cur.lastrowid


# ============================================================
# 软件版本报告（按物理成员展开）
# ============================================================

def test_软件版本_堆叠拆成物理成员行(conn):
    data = asyncio.run(reports_api.report_software_versions())
    by_name = {d["name"]: d for d in data["devices"]}

    # Cisco 三成员：顺序号做后缀，各自序列号 / 型号 / 版本
    assert by_name["SZXD1SWI01-1"]["serial"] == "FCW2129B3TR"
    assert by_name["SZXD1SWI01-1"]["model"] == "WS-C2960X-48FPD-L"
    assert by_name["SZXD1SWI01-2"]["version"] == "15.2(4)E5"
    assert by_name["SZXD1SWI01-3"]["model"] == "WS-C2960X-48LPD-L"
    assert by_name["SZXD1SWI01-1"]["device"] == "SZXD1SWI01"

    # Aruba VSF：真实 Member ID 做后缀，成员无软件版本 → 用整堆叠版本填充
    assert by_name["PVGD1SWI01-1"]["serial"] == "SG41LMP093"
    assert by_name["PVGD1SWI01-1"]["version"] == "FL.10.10.1070"
    assert by_name["PVGD1SWI01-2"]["rom_version"] == "FL.01.11.0001"

    # 单机不拆：名称不带后缀
    assert by_name["PVGD1SWI02"]["name"] == "PVGD1SWI02"


def test_软件版本_成员运行时间(conn):
    """成员级运行时间进报告（Cisco 主交换机取设备级那行）"""
    data = asyncio.run(reports_api.report_software_versions())
    by_name = {d["name"]: d for d in data["devices"]}

    assert by_name["SZXD1SWI01-1"]["uptime_days"] == round(5723520 / 86400, 1)
    assert by_name["PVGD1SWI01-2"]["uptime_days"] == round(53989200 / 86400, 1)


def test_软件版本_跨设备同型号版本不同不报警(conn):
    """PVGD1SWI02 与 KORD1SWI01 同型号（JL659A）版本不同 —— 这是正常的分站点差异"""
    data = asyncio.run(reports_api.report_software_versions())

    assert all(m["device"] not in ("PVGD1SWI02", "KORD1SWI01") for m in data["mismatches"])
    assert all("model" not in m for m in data["mismatches"])


def test_软件版本_成员软件版本不一致报警(conn):
    """同一个堆叠内部成员版本不同 → 报警（升级未完成的信号）"""
    data = asyncio.run(reports_api.report_software_versions())
    szx = next(m for m in data["mismatches"] if m["device"] == "SZXD1SWI01")

    assert szx["versions"] == ["15.2(4)E5", "15.2(4)E8"]
    assert [m["name"] for m in szx["members"]] == ["SZXD1SWI01-1", "SZXD1SWI01-2", "SZXD1SWI01-3"]


def test_软件版本_成员ROM版本不一致报警(conn):
    data = asyncio.run(reports_api.report_software_versions())
    pvg = next(m for m in data["mismatches"] if m["device"] == "PVGD1SWI01")

    assert pvg["rom_versions"] == ["FL.01.11.0001", "FL.01.11.0002"]
    assert pvg["versions"] == ["FL.10.10.1070"]   # 软件版本仍是整堆叠一致


def test_软件版本_单机运行时间回退设备级(conn):
    """单机设备没有成员段 → 用设备级（最新一次采集）运行时间，不能留空"""
    _add_collection(conn, 1, uptime=100 * 86400)   # PVGD1SWI02 单机

    data = asyncio.run(reports_api.report_software_versions())
    by_name = {d["name"]: d for d in data["devices"]}

    assert by_name["PVGD1SWI02"]["uptime_days"] == 100.0
    # 有成员级数据的堆叠不受影响，仍用成员自己的值
    assert by_name["SZXD1SWI01-1"]["uptime_days"] == round(5723520 / 86400, 1)


def test_软件版本_多成员无成员级数据不回退设备级(conn):
    """设备级运行时间只代表主/活动成员 —— 不能复制给堆叠里的每一台"""
    conn.execute(
        "INSERT INTO devices (id, name, ip, type, location, model, version, serial_number) "
        "VALUES (9, 'SHAD1SWI01', '10.0.0.9', 'cisco_ios', 'SHA', 'C9500-24Y4C, C9500-24Y4C', "
        "'16.09.03', 'CAT2322L0L4, CAT2319L3WX')"
    )
    conn.commit()
    _add_collection(conn, 9, uptime=56153340)      # 双成员 SVL：无成员级运行时间

    data = asyncio.run(reports_api.report_software_versions(location="SHA"))
    by_name = {d["name"]: d for d in data["devices"]}

    assert by_name["SHAD1SWI01-1"]["uptime_days"] is None
    assert by_name["SHAD1SWI01-2"]["uptime_days"] is None


def test_软件版本_按位置过滤(conn):
    data = asyncio.run(reports_api.report_software_versions(location="PVG"))

    assert sorted(d["name"] for d in data["devices"]) == ["PVGD1SWI01-1", "PVGD1SWI01-2", "PVGD1SWI02"]
    assert [m["device"] for m in data["mismatches"]] == ["PVGD1SWI01"]


# ============================================================
# 带宽利用率汇总
# ============================================================

def _add_port(conn, cid: int, device_id: int, port: str,
              rx_util: float | None, tx_util: float | None,
              rx_mbps: float | None = None, tx_mbps: float | None = None):
    conn.execute(
        "INSERT INTO port_snapshots (collection_id, device_id, port_name, status, status_up, "
        "rx_util_pct, tx_util_pct, rx_mbps, tx_mbps) VALUES (?, ?, ?, 'up', 1, ?, ?, ?, ?)",
        (cid, device_id, port, rx_util, tx_util, rx_mbps, tx_mbps),
    )
    conn.commit()


def test_带宽_只列有流量的端口且按吞吐降序(conn):
    c1 = _add_collection(conn, 1)   # PVG
    c3 = _add_collection(conn, 3)   # SZX
    _add_port(conn, c1, 1, "1/1/1", 2.0, 0.0, 20.0, 1.0)
    _add_port(conn, c1, 1, "1/1/2", 0.0, 0.0, 0.0, 0.0)        # 无流量 → 不列
    _add_port(conn, c1, 1, "1/1/3", None, None, None, None)      # NULL 利用率不再抛错
    _add_port(conn, c3, 3, "1/1/49", 1.0, 0.5, 300.0, 40.0)      # 吞吐最大 → 第一行

    data = asyncio.run(reports_api.report_bandwidth_summary())

    assert data["count"] == 2
    assert [p["port_name"] for p in data["ports"]] == ["1/1/49", "1/1/1"]
    assert data["ports"][0]["location"] == "SZX"
    assert data["ports"][0]["collected_at"] == "2026-09-17T12:00:00"


def test_带宽_按位置过滤(conn):
    c1 = _add_collection(conn, 1)
    c3 = _add_collection(conn, 3)
    _add_port(conn, c1, 1, "1/1/1", 2.0, 0.0, 20.0, 1.0)
    _add_port(conn, c3, 3, "1/1/49", 1.0, 0.5, 300.0, 40.0)

    data = asyncio.run(reports_api.report_bandwidth_summary(location="PVG"))

    assert [p["device_name"] for p in data["ports"]] == ["PVGD1SWI02"]
