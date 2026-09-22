"""port_snapshots 落库测试 —— 重点：累计计数器列（in_octets / out_octets）

NULL 与读数 0 必须可区分：0 是合法读数（空端口大量存在），NULL 表示「本轮没采到」。
"""
import sqlite3

import pytest

import storage.database as db
from services.collector_service import _save_to_sqlite


@pytest.fixture
def restore_db_path():
    """init_db 会改模块级 _db_path；且 get_connection() 的线程本地连接会一直指向旧库，
    换库前必须关掉，否则测试之间会串数据。"""
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


def save(tmp_path, port_details) -> sqlite3.Connection:
    db.init_db(str(tmp_path))
    _save_to_sqlite(
        device_name="TEST1SWI01", device_ip="10.0.0.1",
        device_type="cisco_ios", device_platform="cisco_ios",
        week="2026-38", collected_at="2026-09-15T09:00:00",
        running_config="", logs_raw="",
        performance_results="{}", validation_results="{}", change_results="{}",
        software_version="15.2", serial_number="FCW1234", device_model="WS-C2960X",
        system_uptime_seconds=None,
        port_details=port_details, port_errors={},
        neighbors_data=[], boot_history="",
    )
    return db.get_connection()


def test_计数器读数落库(tmp_path, restore_db_path):
    conn = save(tmp_path, [
        {"name": "Gi1/0/1", "status": "connected", "status_up": True,
         "in_octets": 1603759403106, "out_octets": 949050652876},
    ])

    row = conn.execute("SELECT in_octets, out_octets FROM port_snapshots WHERE port_name='Gi1/0/1'").fetchone()
    assert tuple(row) == (1603759403106, 949050652876)


def test_读数0与没采到必须区分(tmp_path, restore_db_path):
    """0 是合法读数；None（本轮没采到）入库为 NULL。_safe_str 会把 None 变 ''，不能用在这里"""
    conn = save(tmp_path, [
        {"name": "Gi1/0/1", "status": "notconnect", "status_up": False,
         "in_octets": 0, "out_octets": 0},
        {"name": "Gi1/0/2", "status": "notconnect", "status_up": False},
    ])

    rows = dict(conn.execute("SELECT port_name, in_octets FROM port_snapshots"))
    assert rows["Gi1/0/1"] == 0
    assert rows["Gi1/0/2"] is None


def test_端口成员号落库_逻辑口为空(tmp_path, restore_db_path):
    """端口→成员号（2026-09-22 身份模型）：Aruba/Cisco 首个数字段即成员号；
    逻辑口（Po/Hu/lag）为 NULL —— 它们不属于任何物理成员"""
    conn = save(tmp_path, [
        {"name": "Gi2/0/1", "status": "connected", "status_up": True},
        {"name": "2/1/1", "status": "connected", "status_up": True},
        {"name": "Tw1/0/2", "status": "connected", "status_up": True},
        {"name": "Po1", "status": "connected", "status_up": True},
        {"name": "Hu1/0/27", "status": "connected", "status_up": True},
    ])

    rows = dict(conn.execute("SELECT port_name, member_no FROM port_snapshots"))
    assert rows["Gi2/0/1"] == 2
    assert rows["2/1/1"] == 2
    assert rows["Tw1/0/2"] == 1
    assert rows["Po1"] is None
    assert rows["Hu1/0/27"] is None


def test_大数据不丢精度(tmp_path, restore_db_path):
    """64 位累计字节（约 16 TB）用 INTEGER 存，不能变浮点"""
    conn = save(tmp_path, [
        {"name": "Twe1/0/2", "status": "connected", "status_up": True,
         "in_octets": 16101977364549, "out_octets": 9422674234620},
    ])

    row = conn.execute("SELECT in_octets, out_octets FROM port_snapshots WHERE port_name='Twe1/0/2'").fetchone()
    assert tuple(row) == (16101977364549, 9422674234620)


def test_原有19列不受影响(tmp_path, restore_db_path):
    """计数器是新加的列，老的端口字段与列数不能变"""
    conn = save(tmp_path, [
        {"name": "Gi1/0/1", "status": "connected", "status_up": True,
         "speed": "1000", "mode": "access", "type": "10/100/1000BaseTX",
         "description": "Internet-CNC", "native_vlan": "4093", "is_uplink": True,
         "rx_mbps": 4.5, "tx_mbps": 1.25, "rx_util_pct": 3.0, "tx_util_pct": 1.0,
         "rx_pps": 100, "tx_pps": 50, "rxload": 10, "txload": 20,
         "in_octets": 100, "out_octets": 200},
    ])

    row = conn.execute("""
        SELECT port_name, status, status_up, speed, mode, port_type, description,
               native_vlan, is_uplink, rx_mbps, tx_mbps, rx_util_pct, tx_util_pct,
               rx_pps, tx_pps, rxload, txload
        FROM port_snapshots WHERE port_name='Gi1/0/1'
    """).fetchone()

    assert tuple(row) == ("Gi1/0/1", "connected", 1, "1000", "access", "10/100/1000BaseTX",
                          "Internet-CNC", "4093", 1, 4.5, 1.25, 3.0, 1.0, 100, 50, 10, 20)


def test_端口详情为空时不报错(tmp_path, restore_db_path):
    conn = save(tmp_path, [])
    assert conn.execute("SELECT COUNT(*) FROM port_snapshots").fetchone()[0] == 0
