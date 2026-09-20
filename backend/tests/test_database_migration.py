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

    assert max_version(conn) == db.SCHEMA_VERSION
    assert "startup_config" in table_columns(conn, "collections")   # v14：与 running 比对用
    assert {"in_octets", "out_octets"} <= table_columns(conn, "port_snapshots")
    assert {"vlan", "port_name", "role", "state", "is_root", "mode"} <= table_columns(conn, "stp_snapshots")
    assert {"started_at", "trigger", "ruleset_hash", "device_count", "finding_count"} <= table_columns(conn, "audit_runs")
    assert {"run_id", "rule_id", "level", "evidence_json", "config_hash"} <= table_columns(conn, "audit_findings")


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

    assert max_version(conn) == db.SCHEMA_VERSION
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

    assert max_version(conn) == db.SCHEMA_VERSION
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "stp_snapshots" in tables

    row = conn.execute("SELECT port_name, in_octets FROM port_snapshots").fetchone()
    assert row[0] == "Gi1/0/1" and row[1] == 0   # 0 是合法读数，不能被迁移改动


# ---- v13：配置审计结果表 ----

def test_v13可重复执行():
    """audit_runs / audit_findings 建表迁移必须幂等（IF NOT EXISTS）"""
    conn = sqlite3.connect(":memory:")

    db._migrate_v13(conn)
    db._migrate_v13(conn)  # 不得抛异常

    assert {"started_at", "finished_at", "trigger", "ruleset_hash", "ruleset_version",
            "device_count", "finding_count", "status"} <= table_columns(conn, "audit_runs")
    assert {"run_id", "device_id", "device_name", "collection_id", "week", "rule_id",
            "level", "source", "severity", "title", "detail", "current_text", "fix_text",
            "why_text", "note_text", "evidence_json", "lines_json", "missing_json",
            "controls_json", "config_hash", "ruleset_hash", "created_at"} \
        <= table_columns(conn, "audit_findings")

    fin_idx = {row[1] for row in conn.execute("PRAGMA index_list(audit_findings)")}
    assert "idx_audit_findings_run_level" in fin_idx
    assert "idx_audit_findings_device_rule" in fin_idx


def test_v13从零建库后审计表可用():
    """新库直接跑全部迁移后，审计结果能正常落库并查回来。"""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, "
                 "applied_at TEXT DEFAULT (datetime('now')))")

    db._run_migrations(conn)

    assert max_version(conn) == db.SCHEMA_VERSION >= 13
    conn.execute("INSERT INTO audit_runs (started_at, trigger, ruleset_hash, device_count, "
                 "finding_count, status) VALUES ('2026-09-20T10:00:00', 'manual', 'abc123', 36, 1, 'done')")
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO audit_findings (run_id, device_id, device_name, rule_id, level, source, "
        "severity, title, evidence_json, lines_json, config_hash, created_at) "
        "VALUES (?, 1, 'BJQD1SWI01', 'hq_cs_snmpv3_user', '强烈建议', '公司总部', 'shall', "
        "'未配置 SNMPv3 用户', '[{\"line\": 3, \"text\": \"snmp-server group X v3 priv\"}]', "
        "'[3]', 'deadbeef', '2026-09-20T10:00:01')", (run_id,))

    row = conn.execute(
        "SELECT device_name, rule_id, severity, evidence_json FROM audit_findings "
        "WHERE run_id = ?", (run_id,)).fetchone()
    assert row[0] == "BJQD1SWI01" and row[1] == "hq_cs_snmpv3_user"
    assert row[2] == "shall" and '"line": 3' in row[3]


def test_v12老库升级到v13只加审计表不动既有数据():
    """升级路径：老库只跑 v13，既有业务表与数据不受影响。"""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, "
                 "applied_at TEXT DEFAULT (datetime('now')))")
    conn.execute("INSERT INTO schema_version (version) VALUES (12)")
    conn.execute("CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO devices (id, name) VALUES (1, 'BJQD1SWI01')")

    db._run_migrations(conn)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"audit_runs", "audit_findings"} <= tables
    assert conn.execute("SELECT name FROM devices WHERE id = 1").fetchone()[0] == "BJQD1SWI01"
