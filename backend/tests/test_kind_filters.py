"""kind 过滤纪律测试：成员行不得混入管理体视角（每类页面防漏网）。

spec 第八节：devices 查询收敛到 device_dal 的两个入口
（list_managed / list_physical），禁止新代码裸查 devices。
"""
import asyncio

import pytest
from fastapi import HTTPException

import storage.database as db
from storage import device_dal


@pytest.fixture
def restore_db_path():
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


@pytest.fixture
def seeded(tmp_path, restore_db_path):
    """1 堆叠（2 成员）+ 1 单机"""
    db.init_db(str(tmp_path))
    conn = db.get_connection()
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind) "
                 "VALUES ('STACK1', '10.0.0.1', 'aruba_aoscx', 'aruba_aoscx', 'stack')")
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind) "
                 "VALUES ('SINGLE1', '10.0.0.2', 'cisco_ios', 'cisco_ios', 'standalone')")
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no, serial_number) "
                 "VALUES ('STACK1-1', '', 'aruba_aoscx', 'aruba_aoscx', 'member', 'STACK1', 1, 'SN1')")
    conn.execute("INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no, serial_number) "
                 "VALUES ('STACK1-2', '', 'aruba_aoscx', 'aruba_aoscx', 'member', 'STACK1', 2, 'SN2')")
    conn.commit()
    return conn


def test_list_managed_只含管理体(seeded):
    assert [d["name"] for d in device_dal.list_managed()] == ["SINGLE1", "STACK1"]


def test_list_physical_含成员与单机(seeded):
    assert [d["name"] for d in device_dal.list_physical()] == ["SINGLE1", "STACK1-1", "STACK1-2"]


def test_get_all_devices_语义为管理体(seeded):
    """兼容别名：既有调用点（采集/审计/拓扑扫描）要的就是管理体清单"""
    assert [d["name"] for d in device_dal.get_all_devices()] == ["SINGLE1", "STACK1"]


def test_删除堆叠级联删成员(seeded):
    assert device_dal.delete_device("STACK1") is True
    assert [r["name"] for r in seeded.execute("SELECT name FROM devices")] == ["SINGLE1"]


def test_成员行不可单独删除(seeded):
    """成员是堆叠的一部分——删它要在堆叠行上做（错误信息给出堆叠名）"""
    with pytest.raises(ValueError, match="堆叠成员"):
        device_dal.delete_device("STACK1-2")


def test_改名级联成员行与档案(seeded):
    """改堆叠名 → 成员行 name/stack_name 跟随；档案表 last_device 同步
    （否则下次采集会把改名误报成"调拨"）"""
    seeded.execute("INSERT INTO device_members (serial_number, last_device, last_member) "
                   "VALUES ('SN1', 'STACK1', '1')")
    seeded.commit()

    assert device_dal.update_device("STACK1", {"name": "STACK9"}) is True

    names = [r["name"] for r in seeded.execute("SELECT name FROM devices ORDER BY name")]
    assert names == ["SINGLE1", "STACK9", "STACK9-1", "STACK9-2"]
    row = seeded.execute("SELECT stack_name, member_no FROM devices WHERE name='STACK9-1'").fetchone()
    assert row["stack_name"] == "STACK9" and row["member_no"] == 1
    assert seeded.execute(
        "SELECT last_device FROM device_members WHERE serial_number='SN1'"
    ).fetchone()["last_device"] == "STACK9"


# ============================================================
# 按名入口拒绝成员行（spec 第八节：成员不可采集/执行/查日志/单台审计）
# ============================================================

def test_成员拒绝文案(seeded):
    assert device_dal.member_reject_message("STACK1-2") == \
        "STACK1-2 是堆叠成员，请对堆叠 STACK1 操作"
    assert device_dal.member_reject_message("STACK1") == ""
    assert device_dal.member_reject_message("不存在") == ""


def test_采集与Ping拒绝成员(seeded):
    """collector 两个按名入口在碰设备/建进度前就拒绝"""
    from api import collector as collector_api

    with pytest.raises(HTTPException) as e:
        asyncio.run(collector_api.ping_device("STACK1-2"))
    assert e.value.status_code == 400 and "堆叠成员" in e.value.detail

    with pytest.raises(HTTPException) as e:
        asyncio.run(collector_api.collect_config("STACK1-2", username="u", password="p"))
    assert e.value.status_code == 400 and "堆叠成员" in e.value.detail


def test_批量执行拒绝成员(seeded):
    from api import batch as batch_api

    with pytest.raises(HTTPException) as e:
        asyncio.run(batch_api.execute(
            device_name="STACK1-2", username="u", password="p",
            text="show version", batch_id="b1"))
    assert e.value.status_code == 400 and "堆叠成员" in e.value.detail


def test_审计源不含成员行(seeded):
    """扫描类查询（全量审计输入）只遍历管理体"""
    from analyzers.compliance import source

    assert [i.snapshot.name for i in source.list_audit_inputs(seeded)] == ["SINGLE1", "STACK1"]
