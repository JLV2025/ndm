"""自定义报告端点测试 —— 临时库直接调端点函数（HTTP 层之下）

覆盖三张表的共同改造：位置过滤、型号去重、版本一致性比较、带宽只列有流量的端口。
"""
import asyncio

import pytest

import storage.database as db
from api import reports as reports_api

DEVICES = [
    # (name, type, location, model, version)
    ("PVGD1SWI01", "aruba_aoscx", "PVG", "JL658A, JL658A", "FL.10.10.1070"),
    ("PVGD1SWI02", "aruba_aoscx", "PVG", "JL659A", "FL.10.10.1070"),
    ("KORD1SWI01", "aruba_aoscx", "KOR", "JL659A", "FL.10.16.1040"),
    ("BJQD1SWI01", "cisco_ios", "BJQ", "WS-C2960X-48FPD-L", "15.2(4)E8"),
]


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    for i, (name, dtype, loc, model, version) in enumerate(DEVICES, start=1):
        c.execute(
            "INSERT INTO devices (id, name, ip, type, location, model, version, last_synced) "
            "VALUES (?, ?, '10.0.0.1', ?, ?, ?, ?, '2026-09-17T12:00:00')",
            (i, name, dtype, loc, model, version),
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
# 软件版本报告
# ============================================================

def test_软件版本_扁平列表与型号去重(conn):
    data = asyncio.run(reports_api.report_software_versions())

    assert len(data["devices"]) == 4
    pvg01 = next(d for d in data["devices"] if d["name"] == "PVGD1SWI01")
    # 堆叠成员的重复型号在展示字段里已去重
    assert pvg01["model"] == "JL658A"
    assert pvg01["location"] == "PVG"


def test_软件版本_按位置过滤后不一致随之收缩(conn):
    """JL659A 在 PVG 与 KOR 各一台、版本不同 → 全量视图报不一致；只看 PVG 时不再报"""
    all_data = asyncio.run(reports_api.report_software_versions())
    assert all_data["mismatches"] == [
        {"model": "JL659A", "versions": ["FL.10.10.1070", "FL.10.16.1040"]}
    ]

    pvg = asyncio.run(reports_api.report_software_versions(location="PVG"))
    assert [d["name"] for d in pvg["devices"]] == ["PVGD1SWI01", "PVGD1SWI02"]
    assert pvg["mismatches"] == []


def test_软件版本_单台型号不算不一致(conn):
    """只有一台的型号没有比较对象 —— 不能报不一致"""
    data = asyncio.run(reports_api.report_software_versions())
    assert all(m["model"] != "JL658A" for m in data["mismatches"])


# ============================================================
# 设备在线时间
# ============================================================

def test_在线时间_带位置并按位置过滤(conn):
    _add_collection(conn, 1, uptime=100 * 86400)
    _add_collection(conn, 4, uptime=3 * 86400)

    data = asyncio.run(reports_api.report_device_uptime())
    by_name = {d["name"]: d for d in data["devices"]}
    assert by_name["PVGD1SWI01"]["uptime_days"] == 100.0
    assert by_name["PVGD1SWI01"]["location"] == "PVG"
    # 没有采集记录的设备也要在列表里（运行时间为空）
    assert by_name["PVGD1SWI02"]["uptime_days"] is None

    bjq = asyncio.run(reports_api.report_device_uptime(location="BJQ"))
    assert [d["name"] for d in bjq["devices"]] == ["BJQD1SWI01"]


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
    c3 = _add_collection(conn, 3)   # KOR
    _add_port(conn, c1, 1, "1/1/1", 2.0, 0.0, 20.0, 1.0)
    _add_port(conn, c1, 1, "1/1/2", 0.0, 0.0, 0.0, 0.0)        # 无流量 → 不列
    _add_port(conn, c1, 1, "1/1/3", None, None, None, None)      # NULL 利用率不再抛错
    _add_port(conn, c3, 3, "1/1/49", 1.0, 0.5, 300.0, 40.0)      # 吞吐最大 → 第一行

    data = asyncio.run(reports_api.report_bandwidth_summary())

    assert data["count"] == 2
    assert [p["port_name"] for p in data["ports"]] == ["1/1/49", "1/1/1"]
    assert data["ports"][0]["location"] == "KOR"
    assert data["ports"][0]["collected_at"] == "2026-09-17T12:00:00"


def test_带宽_按位置过滤(conn):
    c1 = _add_collection(conn, 1)
    c3 = _add_collection(conn, 3)
    _add_port(conn, c1, 1, "1/1/1", 2.0, 0.0, 20.0, 1.0)
    _add_port(conn, c3, 3, "1/1/49", 1.0, 0.5, 300.0, 40.0)

    data = asyncio.run(reports_api.report_bandwidth_summary(location="PVG"))

    assert [p["device_name"] for p in data["ports"]] == ["PVGD1SWI01"]
