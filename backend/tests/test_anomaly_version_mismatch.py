"""异常检测：堆叠成员版本不一致告警

规则（与「软件版本报告」同口径）：**只比同一台设备内部的堆叠成员**；
跨设备同型号版本不同是正常的分站点差异，不报警。
"""
import pytest

import storage.database as db
from analyzers.anomaly_detector import AnomalyDetector


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.commit()
    yield c
    c.commit()
    db.close_connection()
    db._db_path = original


def add_device(conn, device_id: int, name: str, model: str, version: str,
               member_versions: str = "", member_rom_versions: str = "") -> None:
    conn.execute(
        "INSERT INTO devices (id, name, ip, type, model, version, member_versions, member_rom_versions) "
        "VALUES (?, ?, '10.0.0.1', 'cisco_ios', ?, ?, ?, ?)",
        (device_id, name, model, version, member_versions, member_rom_versions),
    )
    conn.commit()


def check(conn, device_id: int):
    return AnomalyDetector(conn)._check_version_mismatch(device_id, collection_id=1)


def test_成员版本一致不报警(conn):
    add_device(conn, 1, "SZXD1SWI01", "WS-C2960X", "15.2(4)E8",
               member_versions="15.2(4)E8, 15.2(4)E8, 15.2(4)E8")

    assert check(conn, 1) == []


def test_成员版本不一致报警(conn):
    add_device(conn, 1, "SZXD1SWI01", "WS-C2960X", "15.2(4)E8",
               member_versions="15.2(4)E8, 15.2(4)E5, 15.2(4)E8")

    alerts = check(conn, 1)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["alert_type"] == "version_mismatch"
    assert alert["title"] == "SZXD1SWI01 堆叠成员版本不一致"
    assert alert["detail"]["member_versions"] == ["15.2(4)E5", "15.2(4)E8"]


def test_跨设备同型号版本不同不报警(conn):
    """两台 JL659A 在不同站点跑不同版本 —— 正常，不报警"""
    add_device(conn, 1, "BJQD1SWI01", "JL659A", "FL.10.10.1070")
    add_device(conn, 2, "KORD1SWI01", "JL659A", "FL.10.16.1040")

    assert check(conn, 1) == []
    assert check(conn, 2) == []


def test_成员ROM版本不一致也报警(conn):
    """Aruba VSF 软件版本整堆叠共享，成员级唯一可比的是 ROM 版本"""
    add_device(conn, 1, "BJQD1SWI01", "JL659A", "FL.10.10.1070",
               member_rom_versions="FL.01.11.0002, FL.01.11.0001")

    alerts = check(conn, 1)

    assert len(alerts) == 1
    assert alerts[0]["detail"]["member_rom_versions"] == ["FL.01.11.0001", "FL.01.11.0002"]
    assert "ROM 版本" in alerts[0]["detail"]["summary"]


def test_非堆叠设备不报警(conn):
    add_device(conn, 1, "BJQD1RTW01", "C8300-1N1S-4T2X", "17.09.04a")

    assert check(conn, 1) == []
