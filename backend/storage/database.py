"""
SQLite 数据库管理模块
- WAL 模式连接管理
- Schema 初始化与迁移
- 单例连接池
"""

import os
import sqlite3
import threading
from pathlib import Path

# 当前 Schema 版本（每次 schema 变更递增）
SCHEMA_VERSION = 3

# 线程本地存储 —— 每个线程持有自己的连接
_local = threading.local()

# 数据库文件路径（模块初始化时设定）
_db_path: str = ""


def init_db(data_root: str = "./data") -> str:
    """初始化数据库：设定路径、建表、迁移、种子数据

    幂等 —— 多次调用不会破坏已有数据。
    返回数据库文件路径。
    """
    global _db_path
    if not os.path.isabs(data_root):
        data_root = os.path.abspath(data_root)
    os.makedirs(data_root, exist_ok=True)
    _db_path = os.path.join(data_root, "ndm.db")

    conn = _create_connection()
    try:
        _ensure_schema_version_table(conn)
        _run_migrations(conn)
        _seed_data(conn)
    finally:
        conn.close()
    return _db_path


def get_connection() -> sqlite3.Connection:
    """获取当前线程的数据库连接（自动创建 + WAL 模式）

    每个线程独立连接，线程安全。
    """
    conn = getattr(_local, "connection", None)
    if conn is None:
        conn = _create_connection()
        _local.connection = conn
    return conn


def close_connection() -> None:
    """关闭当前线程的数据库连接"""
    conn = getattr(_local, "connection", None)
    if conn is not None:
        conn.close()
        _local.connection = None


# ================================================================
# 内部实现
# ================================================================


def _create_connection() -> sqlite3.Connection:
    """创建 SQLite 连接（WAL 模式，外键约束）"""
    if not _db_path:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    conn = sqlite3.connect(_db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """检查表是否存在"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """建 schema 版本追踪表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)


def _current_version(conn: sqlite3.Connection) -> int:
    """查询当前 schema 版本"""
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] if row and row[0] is not None else 0


def _run_migrations(conn: sqlite3.Connection) -> None:
    """按需执行增量迁移"""
    current = _current_version(conn)

    for version in range(current + 1, SCHEMA_VERSION + 1):
        migrator = _MIGRATIONS.get(version)
        if migrator:
            migrator(conn)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (version,)
        )
        print(f"[数据库] 迁移 v{version} 完成")
    conn.commit()


def _seed_data(conn: sqlite3.Connection) -> None:
    """写入种子数据（仅当表为空时）"""
    _seed_remediation_hints(conn)
    conn.commit()


def _seed_remediation_hints(conn: sqlite3.Connection) -> None:
    """种子：修复建议映射表"""
    if not _table_exists(conn, "remediation_hints"):
        return
    count = conn.execute("SELECT COUNT(*) FROM remediation_hints").fetchone()[0]
    if count > 0:
        return

    hints = [
        (
            "device_reboot",
            "设备发生重启。建议：1) 检查 show logging 中重启时间前后的日志 "
            "2) 检查电源/温控状态 3) 若为 crash，收集 crashinfo 并联系 TAC",
        ),
        (
            "port_sudden_down",
            "端口突然 DOWN。建议：1) 检查远端设备是否正常运行 "
            "2) 检查光模块/光纤/线缆物理连接 3) 检查 spanning-tree 拓扑是否有变更 "
            "4) 检查端口错误计数器",
        ),
        (
            "port_errors",
            "端口出现错误。建议：1) 若是 err-disabled，检查 errdisable recovery 配置 "
            "2) 检查光模块兼容性 3) 检查线缆是否损坏 4) 查看对应日志定位根因",
        ),
        (
            "config_changed",
            "配置发生变更。建议：1) 检查变更内容是否为计划内操作 "
            "2) 若为未授权变更，排查操作记录 3) 确认变更后设备运行正常",
        ),
        (
            "topology_changed",
            "拓扑连接发生变更。建议：1) 确认是否有设备上下线 "
            "2) 检查新设备配置是否正确 3) 更新网络拓扑文档",
        ),
        (
            "version_mismatch",
            "同型号设备存在版本不一致。建议：1) 确认各版本 Release Notes 中的已知问题 "
            "2) 制定统一升级计划 3) 优先升级存在安全漏洞的旧版本",
        ),
        (
            "high_utilization",
            "端口带宽利用率过高。建议：1) 确认是否为业务高峰期正常使用 "
            "2) 检查是否存在异常流量 3) 考虑负载均衡或扩容",
        ),
    ]
    conn.executemany(
        "INSERT INTO remediation_hints (alert_type, suggestion) VALUES (?, ?)",
        hints,
    )
    print(f"[数据库] 种子数据: {len(hints)} 条修复建议已写入")


# ================================================================
# 迁移定义
# ================================================================


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Schema v1: 初始建表"""
    conn.executescript("""
        -- 设备字典
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            ip TEXT NOT NULL,
            type TEXT NOT NULL,
            platform TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            model TEXT DEFAULT '',
            version TEXT DEFAULT '',
            location TEXT DEFAULT '',
            last_synced TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- 采集会话
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL REFERENCES devices(id),
            week TEXT NOT NULL,
            phase TEXT NOT NULL DEFAULT '1',
            collected_at TEXT NOT NULL,
            software_version TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            model TEXT DEFAULT '',
            system_uptime_seconds INTEGER,
            running_config TEXT,
            running_config_lines INTEGER DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        );
        CREATE INDEX IF NOT EXISTS idx_collections_device_week
            ON collections(device_id, week);

        -- 端口快照
        CREATE TABLE IF NOT EXISTS port_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            port_name TEXT NOT NULL,
            status TEXT NOT NULL,
            status_up INTEGER NOT NULL DEFAULT 0,
            speed TEXT DEFAULT '',
            mode TEXT DEFAULT '',
            port_type TEXT DEFAULT '',
            description TEXT DEFAULT '',
            native_vlan TEXT DEFAULT '',
            is_uplink INTEGER NOT NULL DEFAULT 0,
            rx_mbps REAL DEFAULT 0,
            tx_mbps REAL DEFAULT 0,
            rx_util_pct REAL DEFAULT 0,
            tx_util_pct REAL DEFAULT 0,
            rx_pps INTEGER DEFAULT 0,
            tx_pps INTEGER DEFAULT 0,
            rxload INTEGER DEFAULT 0,
            txload INTEGER DEFAULT 0,
            FOREIGN KEY (collection_id) REFERENCES collections(id),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        );
        CREATE INDEX IF NOT EXISTS idx_ports_device_collection
            ON port_snapshots(device_id, collection_id);
        CREATE INDEX IF NOT EXISTS idx_ports_status
            ON port_snapshots(device_id, status_up);

        -- 端口错误
        CREATE TABLE IF NOT EXISTS port_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            port_name TEXT NOT NULL,
            error_type TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE INDEX IF NOT EXISTS idx_errors_device
            ON port_errors(device_id, collection_id);

        -- 邻居关系
        CREATE TABLE IF NOT EXISTS neighbors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            local_port TEXT NOT NULL,
            neighbor_name TEXT NOT NULL,
            neighbor_type TEXT DEFAULT '',
            neighbor_platform TEXT DEFAULT '',
            neighbor_desc TEXT DEFAULT '',
            source TEXT DEFAULT 'cdp',
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE INDEX IF NOT EXISTS idx_neighbors_device
            ON neighbors(device_id, collection_id);

        -- 配置变更记录
        CREATE TABLE IF NOT EXISTS config_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            detected_at TEXT NOT NULL,
            has_changes INTEGER NOT NULL DEFAULT 0,
            added_lines INTEGER DEFAULT 0,
            removed_lines INTEGER DEFAULT 0,
            change_summary TEXT DEFAULT '',
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );

        -- 配置验证结果
        CREATE TABLE IF NOT EXISTS validation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            errors_count INTEGER DEFAULT 0,
            warnings_count INTEGER DEFAULT 0,
            info_count INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );

        -- 设备日志
        CREATE TABLE IF NOT EXISTS device_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            log_timestamp TEXT,
            severity TEXT DEFAULT '',
            facility TEXT DEFAULT '',
            message TEXT NOT NULL,
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE INDEX IF NOT EXISTS idx_logs_device_time
            ON device_logs(device_id, log_timestamp);

        -- 告警
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            collection_id INTEGER REFERENCES collections(id),
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'WARNING',
            title TEXT NOT NULL,
            detail TEXT DEFAULT '',
            suggestion TEXT DEFAULT '',
            is_read INTEGER NOT NULL DEFAULT 0,
            resolved_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_unread
            ON alerts(device_id, is_read, created_at);

        -- 修复建议映射表
        CREATE TABLE IF NOT EXISTS remediation_hints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            keyword TEXT DEFAULT '',
            suggestion TEXT NOT NULL,
            reference_url TEXT DEFAULT ''
        );
    """)


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Schema v2: 添加 collection_id 前导索引（异常检测查询优化）"""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_ports_collection
            ON port_snapshots(collection_id);
        CREATE INDEX IF NOT EXISTS idx_neighbors_collection
            ON neighbors(collection_id);
        CREATE INDEX IF NOT EXISTS idx_errors_collection
            ON port_errors(collection_id);
    """)


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """Schema v3: collections 表添加 boot_history_raw 列"""
    conn.execute("ALTER TABLE collections ADD COLUMN boot_history_raw TEXT DEFAULT ''")


# 迁移注册表
_MIGRATIONS = {
    1: _migrate_v1,
    2: _migrate_v2,
    3: _migrate_v3,
}
