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
    assert {"exceptions_hash", "exempt_count"} <= table_columns(conn, "audit_runs")        # v15：例外
    assert {"exempt_by", "exempt_json"} <= table_columns(conn, "audit_findings")           # v15：豁免快照
    assert {"model", "end_of_sale", "end_of_support", "bulletin_url", "source"} \
        <= table_columns(conn, "eol_models")                                               # v16：EoL 型号缓存
    assert {"device_name", "serial", "warranty_end", "source", "verified_at"} \
        <= table_columns(conn, "device_lifecycle")                                         # v16：逐序列号保修


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


# ---- v15：例外登记的落库列 ----

V14_AUDIT_TABLES = """
    CREATE TABLE audit_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT,
        trigger TEXT NOT NULL DEFAULT 'manual', ruleset_hash TEXT, ruleset_version INTEGER,
        device_count INTEGER DEFAULT 0, finding_count INTEGER DEFAULT 0, status TEXT DEFAULT 'running'
    );
    CREATE TABLE audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, device_id INTEGER,
        device_name TEXT, collection_id INTEGER, week TEXT, rule_id TEXT NOT NULL, level TEXT,
        source TEXT, severity TEXT, title TEXT, detail TEXT, current_text TEXT, fix_text TEXT,
        why_text TEXT, note_text TEXT, evidence_json TEXT, lines_json TEXT, missing_json TEXT,
        controls_json TEXT, config_hash TEXT, ruleset_hash TEXT, created_at TEXT
    );
"""


def test_v15可重复执行():
    """ALTER TABLE 重复加同名列会抛 OperationalError，由 except 吞掉（迁移幂等）"""
    conn = sqlite3.connect(":memory:")
    conn.executescript(V14_AUDIT_TABLES)

    db._migrate_v15(conn)
    db._migrate_v15(conn)  # 不得抛异常

    assert {"exempt_by", "exempt_json"} <= table_columns(conn, "audit_findings")
    assert {"exceptions_hash", "exempt_count"} <= table_columns(conn, "audit_runs")
    fin_idx = {row[1] for row in conn.execute("PRAGMA index_list(audit_findings)")}
    assert "idx_audit_findings_exempt" in fin_idx


def test_v14老库升级到v15补列且旧审计数据保留():
    """升级路径：老库里的审计结果照常保留，新列为 NULL / 默认值，**不回填**。"""
    conn = sqlite3.connect(":memory:")
    conn.executescript(V14_AUDIT_TABLES)
    conn.execute("INSERT INTO audit_runs (started_at, finding_count) VALUES ('2026-09-19', 3)")
    conn.execute("INSERT INTO audit_findings (run_id, rule_id, level, title) "
                 "VALUES (1, 'r1', '风险提示', '旧记录')")

    db._migrate_v15(conn)

    assert conn.execute("SELECT finding_count, exceptions_hash, exempt_count "
                        "FROM audit_runs").fetchone() == (3, None, 0)
    assert conn.execute("SELECT rule_id, title, exempt_by, exempt_json "
                        "FROM audit_findings").fetchone() == ("r1", "旧记录", None, None)


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


# ---- v16：设备生命周期两张表 ----

def test_v16可重复执行():
    """CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS —— 重复执行不抛异常。"""
    conn = sqlite3.connect(":memory:")

    db._migrate_v16(conn)
    db._migrate_v16(conn)

    assert {"model", "description", "end_of_sale", "end_of_support", "announcement",
            "bulletin", "bulletin_url", "source", "fetched_at", "updated_by", "note"} \
        <= table_columns(conn, "eol_models")
    assert {"device_name", "serial", "model", "warranty_end", "note", "source",
            "verified_at", "verified_by", "updated_at"} <= table_columns(conn, "device_lifecycle")
    idx = {row[1] for row in conn.execute("PRAGMA index_list(device_lifecycle)")}
    assert "idx_device_lifecycle_device" in idx and "idx_device_lifecycle_serial" in idx


def test_v16同设备同序列号唯一():
    """(device_name, serial) 唯一约束 —— upsert 语义靠它（堆叠逐成员一行）。"""
    conn = sqlite3.connect(":memory:")
    db._migrate_v16(conn)
    conn.execute("INSERT INTO device_lifecycle (device_name, serial, warranty_end) "
                 "VALUES ('BJQD1SWI01', 'SG30LMQ17K', '2028-05-01')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO device_lifecycle (device_name, serial) "
                     "VALUES ('BJQD1SWI01', 'SG30LMQ17K')")
    # 不同序列号（堆叠另一成员）可以共存
    conn.execute("INSERT INTO device_lifecycle (device_name, serial) "
                 "VALUES ('BJQD1SWI01', 'SG30LMQ108')")
    assert conn.execute("SELECT COUNT(*) FROM device_lifecycle").fetchone()[0] == 2


def test_v15老库升级到v16只加表不动既有数据():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE audit_runs (id INTEGER PRIMARY KEY, started_at TEXT)")
    conn.execute("INSERT INTO audit_runs VALUES (1, '2026-09-20T10:00:00')")

    db._migrate_v16(conn)

    assert conn.execute("SELECT started_at FROM audit_runs").fetchone()[0] == "2026-09-20T10:00:00"
    assert table_columns(conn, "device_lifecycle")


# ---- v17：批量命令执行两张表 ----

def test_v17可重复执行():
    """CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS —— 重复执行不抛异常。"""
    conn = sqlite3.connect(":memory:")

    db._migrate_v17(conn)
    db._migrate_v17(conn)

    assert {"batch_id", "created_at", "username", "mode", "save_config",
            "command_text", "device_count", "note"} <= table_columns(conn, "batch_runs")
    assert {"batch_id", "device_name", "status", "output", "error",
            "started_at", "finished_at"} <= table_columns(conn, "batch_results")
    idx = {row[1] for row in conn.execute("PRAGMA index_list(batch_results)")}
    assert "idx_batch_results_batch" in idx


def test_v17批次内同设备唯一():
    """(batch_id, device_name) 唯一 —— 同一台重复写结果时是约束错误而不是重复行。"""
    conn = sqlite3.connect(":memory:")
    db._migrate_v17(conn)
    conn.execute("INSERT INTO batch_results (batch_id, device_name, status) "
                 "VALUES ('b1', 'BJQD1SWI01', 'success')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO batch_results (batch_id, device_name, status) "
                     "VALUES ('b1', 'BJQD1SWI01', 'failed')")
    # 不同批次 / 不同设备可以共存
    conn.execute("INSERT INTO batch_results (batch_id, device_name, status) "
                 "VALUES ('b2', 'BJQD1SWI01', 'success')")
    conn.execute("INSERT INTO batch_results (batch_id, device_name, status) "
                 "VALUES ('b1', 'ZGND1SWI01', 'success')")
    assert conn.execute("SELECT COUNT(*) FROM batch_results").fetchone()[0] == 3


def test_v16老库升级到v17只加表不动既有数据():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE device_lifecycle (id INTEGER PRIMARY KEY, device_name TEXT)")
    conn.execute("INSERT INTO device_lifecycle VALUES (1, 'BJQD1SWI01')")

    db._migrate_v17(conn)

    assert conn.execute("SELECT device_name FROM device_lifecycle").fetchone()[0] == "BJQD1SWI01"
    assert table_columns(conn, "batch_runs") and table_columns(conn, "batch_results")
