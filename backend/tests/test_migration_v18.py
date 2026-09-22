"""v18 迁移测试：设备身份模型（kind + 物理成员行）"""
import sqlite3

import pytest

import storage.database as db


@pytest.fixture
def restore_db_path():
    """init_db 会改模块级 _db_path；用完还原，避免污染同进程的其他测试"""
    original = db._db_path
    yield
    db._db_path = original


def table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_全新库包含身份列(tmp_path, restore_db_path):
    db_path = db.init_db(str(tmp_path))
    conn = sqlite3.connect(db_path)

    assert db.SCHEMA_VERSION == 18
    assert {"kind", "stack_name", "member_no"} <= table_columns(conn, "devices")
    assert "member_no" in table_columns(conn, "port_snapshots")
    assert "status" in table_columns(conn, "device_members")
    assert {"device_id", "detected_at", "kind", "detail", "note", "annotated_by"} \
        <= table_columns(conn, "device_change_events")


def test_回填_堆叠展开成员行_单机不展开(tmp_path, restore_db_path):
    """设备已入库但还没拆成员行的库：跑 v18 后按序列号同序 1:1 展开"""
    db_path = db.init_db(str(tmp_path))
    conn = sqlite3.connect(db_path)
    conn.execute("""INSERT INTO devices (name, ip, type, platform, serial_number, member_ids, model, version)
                    VALUES ('TESTD1SWI01', '10.0.0.1', 'aruba_aoscx', 'aruba_aoscx',
                            'SN1, SN2', '1, 2', 'JL659A, JL659A', 'ML.10.16.1020')""")
    conn.execute("""INSERT INTO devices (name, ip, type, platform, serial_number, model, version)
                    VALUES ('TESTD1SWI02', '10.0.0.2', 'cisco_ios', 'cisco_ios',
                            'SN3', 'WS-C2960X', '15.2(4)E8')""")
    conn.execute("DELETE FROM schema_version WHERE version = 18")
    conn.commit()
    conn.close()

    db.init_db(str(tmp_path))          # 触发 v18
    conn = sqlite3.connect(db_path)

    cols = ["kind", "stack_name", "member_no", "serial_number"]
    rows = {r[0]: dict(zip(cols, r[1:]))
            for r in conn.execute(f"SELECT name, {', '.join(cols)} FROM devices")}
    assert rows["TESTD1SWI01"]["kind"] == "stack"
    assert rows["TESTD1SWI01"]["serial_number"] == "SN1, SN2"      # 逗号串保留作缓存
    assert rows["TESTD1SWI01-1"]["kind"] == "member"
    assert rows["TESTD1SWI01-1"]["stack_name"] == "TESTD1SWI01"
    assert rows["TESTD1SWI01-1"]["member_no"] == 1
    assert rows["TESTD1SWI01-1"]["serial_number"] == "SN1"
    assert rows["TESTD1SWI01-2"]["member_no"] == 2
    assert rows["TESTD1SWI02"]["kind"] == "standalone"
    assert "TESTD1SWI02-1" not in rows                             # 单机不建成员行

    db.init_db(str(tmp_path))          # 幂等：再跑一次不重复建行
    assert conn.execute("SELECT COUNT(*) FROM devices WHERE kind='member'").fetchone()[0] == 2


def test_从v17风格旧表迁移_走ALTER路径(tmp_path, restore_db_path):
    """手工造 v17 风格旧表（无新列），验证 ALTER 补齐 + member_ids 为空时顺序号回退"""
    db_path = str(tmp_path / "ndm.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);
        INSERT INTO schema_version (version) VALUES (17);
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, ip TEXT NOT NULL,
            type TEXT NOT NULL, platform TEXT DEFAULT '', serial_number TEXT DEFAULT '',
            member_ids TEXT DEFAULT '', model TEXT DEFAULT '', version TEXT DEFAULT '',
            location TEXT DEFAULT '', last_synced TEXT DEFAULT '');
        CREATE TABLE port_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT);
        CREATE TABLE device_members (serial_number TEXT PRIMARY KEY);
        INSERT INTO devices (name, ip, type, platform, serial_number, member_ids, model)
            VALUES ('OLDD1SWI01', '10.9.9.9', 'aruba_aoscx', 'aruba_aoscx',
                    'A1, A2', '', 'JL659A, JL659A');
    """)
    conn.commit()
    conn.close()

    db.init_db(str(tmp_path))
    conn = sqlite3.connect(db_path)

    assert {"kind", "stack_name", "member_no"} <= table_columns(conn, "devices")
    assert conn.execute(
        "SELECT kind FROM devices WHERE name='OLDD1SWI01'").fetchone()[0] == "stack"
    members = conn.execute(
        "SELECT name, member_no FROM devices WHERE stack_name='OLDD1SWI01' ORDER BY member_no").fetchall()
    assert members == [("OLDD1SWI01-1", 1), ("OLDD1SWI01-2", 2)]   # 无真实号 → 顺序号
