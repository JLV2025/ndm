"""成员行维护测试（spec 第五节）：成功 upsert / 失败保护 / 离线保留。

成员行 = 槽位身份（name 物化派生 {堆叠名}-{成员号}）；消失成员保留行、
last_synced 停在旧值（离线由 30 天规则判定，不自动删）。
"""
from pathlib import Path

import pytest

import storage.database as db
from services.collector_service import _save_to_sqlite


@pytest.fixture
def restore_db_path():
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


def save(tmp_path, **overrides):
    """以 Aruba VSF 双成员为默认场景写一次采集（配置里带 vsf member 段）"""
    params = dict(
        device_name="SZXD1SWI01", device_ip="10.0.0.1",
        device_type="aruba_aoscx", device_platform="aruba_aoscx",
        week="2026-38", collected_at="2026-09-17T09:00:00",
        running_config="vsf member 1\n type jl726b\nvsf member 2\n type jl726b\n",
        logs_raw="",
        performance_results="{}", validation_results="{}", change_results="{}",
        software_version="ML.10.16.1020", serial_number="SN1, SN2",
        device_model="JL726B, JL726B",
        system_uptime_seconds=1000,
        port_details=[], port_errors={}, neighbors_data=[], boot_history="",
        member_ids="1, 2",
    )
    params.update(overrides)
    db.init_db(str(tmp_path))
    _save_to_sqlite(**params)
    return db.get_connection()


def test_堆叠采集后建成员行(tmp_path, restore_db_path):
    conn = save(tmp_path)

    rows = {r["name"]: dict(r) for r in conn.execute(
        "SELECT name, kind, stack_name, member_no, serial_number, ip, location "
        "FROM devices WHERE kind='member' ORDER BY member_no")}
    assert set(rows) == {"SZXD1SWI01-1", "SZXD1SWI01-2"}
    assert rows["SZXD1SWI01-1"]["stack_name"] == "SZXD1SWI01"
    assert rows["SZXD1SWI01-1"]["member_no"] == 1
    assert rows["SZXD1SWI01-1"]["serial_number"] == "SN1"
    assert rows["SZXD1SWI01-1"]["ip"] == ""            # 成员行不存 ip（共享堆叠管理 IP）
    # 位置行 kind=stack（配置里有 vsf member 段）
    assert conn.execute(
        "SELECT kind FROM devices WHERE name='SZXD1SWI01'").fetchone()["kind"] == "stack"

    # location 从位置行继承
    conn.execute("UPDATE devices SET location='SZX' WHERE name='SZXD1SWI01'")
    conn.commit()
    save(tmp_path, collected_at="2026-09-18T09:00:00")
    assert conn.execute(
        "SELECT DISTINCT location FROM devices WHERE kind='member'").fetchone()["location"] == "SZX"


def test_成员消失保留并离线(tmp_path, restore_db_path):
    save(tmp_path)                                     # 先 2 成员
    conn = save(tmp_path, collected_at="2026-09-18T09:00:00",
                serial_number="SN1", device_model="JL726B", member_ids="1")

    rows = {r["name"]: r["last_synced"] for r in conn.execute(
        "SELECT name, last_synced FROM devices WHERE kind='member'")}
    assert rows["SZXD1SWI01-1"] == "2026-09-18T09:00:00"   # 本次更新
    assert rows["SZXD1SWI01-2"] == "2026-09-17T09:00:00"   # 保留 + 陈旧（离线判定用）


def test_采集失败不碰成员行(tmp_path, restore_db_path):
    save(tmp_path)
    conn = save(tmp_path, collected_at="2026-09-18T09:00:00",
                serial_number="未知", device_model="未知", member_ids="")

    rows = {r["name"]: r["last_synced"] for r in conn.execute(
        "SELECT name, last_synced FROM devices WHERE kind='member'")}
    assert set(rows) == {"SZXD1SWI01-1", "SZXD1SWI01-2"}
    assert all(ts == "2026-09-17T09:00:00" for ts in rows.values())   # 全部未被触碰


def test_单机kind为standalone(tmp_path, restore_db_path):
    conn = save(tmp_path, device_name="PVGD1SWI03",
                running_config="hostname PVGD1SWI03\n",
                serial_number="SN9", device_model="JL659A", member_ids="")

    assert conn.execute(
        "SELECT kind FROM devices WHERE name='PVGD1SWI03'").fetchone()["kind"] == "standalone"
    assert conn.execute("SELECT COUNT(*) FROM devices WHERE kind='member'").fetchone()[0] == 0
