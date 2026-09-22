"""设备列表 API 测试：managed / physical 两个视图（HTTP 层之下直接调端点函数）。

managed 是操作类页面的默认（设备管理/采集/画图选设备）；
physical 供仪表盘清单等展示类页面（成员行 + 单机，ip 从堆叠行带出）。
"""
import asyncio

import pytest

import storage.database as db
from api import devices as devices_api


@pytest.fixture
def seeded(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    conn = db.get_connection()
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind) "
                 "VALUES ('STACK1', '10.0.0.1', 'aruba_aoscx', 'aruba_aoscx', 'stack')")
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind) "
                 "VALUES ('SINGLE1', '10.0.0.2', 'cisco_ios', 'cisco_ios', 'standalone')")
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no, "
                 "serial_number, model) "
                 "VALUES ('STACK1-1', '', 'aruba_aoscx', 'aruba_aoscx', 'member', 'STACK1', 1, "
                 "'SN1', 'JL727B')")
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no, "
                 "serial_number, model) "
                 "VALUES ('STACK1-2', '', 'aruba_aoscx', 'aruba_aoscx', 'member', 'STACK1', 2, "
                 "'SN2', 'JL727B')")
    conn.commit()
    yield conn
    db.close_connection()
    db._db_path = original


def test_managed视图默认不含成员(seeded):
    rows = asyncio.run(devices_api.list_devices())
    assert [r["name"] for r in rows] == ["SINGLE1", "STACK1"]


def test_physical视图含成员且补ip(seeded):
    rows = asyncio.run(devices_api.list_devices(view="physical"))
    by_name = {r["name"]: r for r in rows}
    assert set(by_name) == {"SINGLE1", "STACK1-1", "STACK1-2"}
    assert by_name["STACK1-1"]["ip"] == "10.0.0.1"        # 从堆叠行带出
    assert by_name["STACK1-1"]["stack_name"] == "STACK1"
    assert by_name["STACK1-1"]["member_no"] == 1
    assert by_name["STACK1-1"]["serial_number"] == "SN1"
    assert by_name["SINGLE1"]["ip"] == "10.0.0.2"         # 单机自身 ip 不动
    assert by_name["SINGLE1"]["kind"] == "standalone"
