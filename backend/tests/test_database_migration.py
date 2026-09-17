"""数据库迁移测试（重点 v10 计数器列 / v11 生成树快照表）"""
import sqlite3

import pytest

import storage.database as db


@pytest.fixture
def restore_db_path():
    """init_db 会改模块级 _db_path；用完还原，避免污染同进程的其他测试"""
    original = db._db_path
    yield
    db._db_path = original


def table_columns(conn: sqlite3.Connection, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def max_version(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]


def test_全新库包含计数器列且版本为最新(tmp_path, restore_db_path):
    db_path = db.init_db(str(tmp_path))
    conn = sqlite3.connect(db_path)

    assert max_version(conn) == db.SCHEMA_VERSION == 12
    assert {"in_octets", "out_octets"} <= table_columns(conn, "port_snapshots")
    assert {"vlan", "port_name", "role", "state", "is_root", "mode"} <= table_columns(conn, "stp_snapshots")


def test_迁移幂等_重复init不报错也不改变结构(tmp_path, restore_db_path):
    db_path = db.init_db(str(tmp_path))
    before = table_columns(sqlite3.connect(db_path), "port_snapshots")

    db.init_db(str(tmp_path))  # 第二次
    conn = sqlite3.connect(db_path)

    assert table_columns(conn, "port_snapshots") == before
    assert conn.execute("SELECT COUNT(*) FROM schema_version WHERE version=11").fetchone()[0] == 1


V9_TABLE = """
    CREATE TABLE port_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection_id INTEGER NOT NULL,
        device_id INTEGER NOT NULL,
        port_name TEXT NOT NULL
    )
"""


def test_v10可重复执行():
    """迁移必须幂等 —— ALTER TABLE 重复加同名列会抛 OperationalError，由 except 吞掉"""
    conn = sqlite3.connect(":memory:")
    conn.execute(V9_TABLE)

    db._migrate_v10(conn)
    db._migrate_v10(conn)  # 不得抛异常

    assert {"in_octets", "out_octets"} <= table_columns(conn, "port_snapshots")


def test_v9老库升级到v10补上计数器列且旧数据保留():
    """升级路径：老库只跑 v10，历史行照常保留，计数器列为 NULL（不回填）"""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("INSERT INTO schema_version (version) VALUES (9)")
    # v10 之前的 port_snapshots（无计数器列）
    conn.execute("""
        CREATE TABLE port_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            port_name TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO port_snapshots (collection_id, device_id, port_name, status) "
        "VALUES (1, 1, 'Gi1/0/1', 'connected')"
    )

    db._run_migrations(conn)

    assert max_version(conn) == 12
    assert {"in_octets", "out_octets"} <= table_columns(conn, "port_snapshots")

    row = conn.execute("SELECT port_name, status, in_octets, out_octets FROM port_snapshots").fetchone()
    assert row[0] == "Gi1/0/1" and row[1] == "connected"
    assert row[2] is None and row[3] is None  # 不回填历史数据


def test_计数器列无默认值_NULL与读数0必须可区分():
    """0 是合法读数（空端口大量存在），NULL 表示「本轮没采到」，两者不能混同"""
    conn = sqlite3.connect(":memory:")
    conn.execute(V9_TABLE)
    db._migrate_v10(conn)

    defaults = {row[1]: row[4] for row in conn.execute("PRAGMA table_info(port_snapshots)")}
    assert defaults["in_octets"] is None and defaults["out_octets"] is None

    conn.execute(
        "INSERT INTO port_snapshots (collection_id, device_id, port_name, in_octets) "
        "VALUES (1, 1, 'Gi1/0/1', 0)"
    )
    conn.execute(
        "INSERT INTO port_snapshots (collection_id, device_id, port_name) VALUES (1, 1, 'Gi1/0/2')"
    )
    rows = dict(conn.execute("SELECT port_name, in_octets FROM port_snapshots"))

    assert rows["Gi1/0/1"] == 0
    assert rows["Gi1/0/2"] is None


def test_基准查询索引已建立():
    conn = sqlite3.connect(":memory:")
    conn.execute(V9_TABLE)

    db._migrate_v10(conn)
    db._migrate_v10(conn)  # IF NOT EXISTS，重复执行不报错

    # PRAGMA index_list 列序为 (seq, name, unique, origin, partial)
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(port_snapshots)")}
    assert "idx_ports_device_port_collection" in indexes


# ---- v11：生成树快照表 ----

def test_v11可重复执行():
    """stp_snapshots 建表迁移必须幂等（IF NOT EXISTS）"""
    conn = sqlite3.connect(":memory:")

    db._migrate_v11(conn)
    db._migrate_v11(conn)  # 不得抛异常

    assert {"vlan", "port_name", "role", "state", "cost", "port_priority",
            "is_root", "root_mac", "bridge_mac", "mode"} <= table_columns(conn, "stp_snapshots")
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(stp_snapshots)")}
    assert {"idx_stp_device_collection", "idx_stp_device_vlan"} <= indexes


def test_v10老库升级到v11补上生成树表且旧数据保留():
    """升级路径：老库只跑 v11，port_snapshots 历史行照常保留"""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("INSERT INTO schema_version (version) VALUES (10)")
    conn.execute("""
        CREATE TABLE port_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            port_name TEXT NOT NULL,
            in_octets INTEGER
        )
    """)
    conn.execute(
        "INSERT INTO port_snapshots (collection_id, device_id, port_name, in_octets) "
        "VALUES (1, 1, 'Gi1/0/1', 0)"
    )

    db._run_migrations(conn)

    assert max_version(conn) == 12
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "stp_snapshots" in tables

    row = conn.execute("SELECT port_name, in_octets FROM port_snapshots").fetchone()
    assert row[0] == "Gi1/0/1" and row[1] == 0   # 0 是合法读数，不能被迁移改动
