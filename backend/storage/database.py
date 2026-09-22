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
SCHEMA_VERSION = 18

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

    # YAML → SQLite 迁移（启动时自动执行，幂等）
    _migrate_yaml_if_needed(data_root)
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
    """种子：修复建议映射表

    **按 alert_type 补缺**而不是"表非空就跳过"：后者会让以后新增的告警类型
    永远进不了已有库（老库的 count 早就 > 0 了）。
    """
    if not _table_exists(conn, "remediation_hints"):
        return

    hints = [
        (
            "device_reboot",
            "设备发生重启。建议：1) 检查 show logging 中重启时间前后的日志 "
            "2) 检查电源/温控状态 3) 若为 crash，收集 crashinfo 并联系 TAC",
        ),
        (
            "port_sudden_down",
            "端口当前为DOWN，上周是UP的。建议：1) 检查远端设备是否正常运行 "
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
        (
            "config_drift",
            "设备运行配置与启动配置不一致 —— 有改动没保存，设备重启后会全部丢失。"
            "建议：1) 确认这些改动是否为计划内、已完成验证的 2) 在设备上执行 "
            "write memory（Aruba CX 用 write memory）保存 3) 保存后再采集一次，告警会自动消除",
        ),
    ]
    existing = {r[0] for r in conn.execute("SELECT DISTINCT alert_type FROM remediation_hints")}
    missing = [h for h in hints if h[0] not in existing]
    if missing:
        conn.executemany(
            "INSERT INTO remediation_hints (alert_type, suggestion) VALUES (?, ?)", missing)
        print(f"[数据库] 种子数据: 补充 {len(missing)} 条修复建议")


def _migrate_yaml_if_needed(data_root: str) -> None:
    """启动时自动从 devices.yaml 迁移数据到 SQLite（仅运行一次）"""
    try:
        from pathlib import Path
        yaml_path = Path(data_root).parent / "config" / "devices.yaml"
        if not yaml_path.exists():
            return

        conn = _create_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        finally:
            conn.close()

        # 仅当 SQLite 中无设备数据时才执行迁移
        if count > 0:
            return

        print("[数据库] 检测到 YAML 设备数据，正在迁移到 SQLite...")
        from storage.device_dal import migrate_from_yaml
        n = migrate_from_yaml(str(yaml_path))
        print(f"[数据库] YAML→SQLite 迁移完成: {n} 台设备")
    except Exception as e:
        print(f"[数据库] YAML 迁移跳过: {e}")


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
            -- v18 起：设备身份模型。stack/standalone = 位置行（持有 IP 与配置类数据）；
            -- member = 物理成员行（name 物化派生 {stack_name}-{member_no}，不存 ip）
            kind TEXT NOT NULL DEFAULT 'standalone',
            stack_name TEXT DEFAULT '',
            member_no INTEGER,
            serial_number TEXT DEFAULT '',
            member_versions TEXT DEFAULT '',
            member_rom_versions TEXT DEFAULT '',
            member_uptimes TEXT DEFAULT '',
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
            -- v10 起：累计计数器原始读数（64 位），区间流量的计算来源。
            -- 不写 DEFAULT —— NULL 必须与「读到 0」区分：NULL = 本轮没采到。
            in_octets INTEGER,
            out_octets INTEGER,
            -- v18 起：端口所属成员号（写入时由端口名前缀解析；逻辑口 Po/Hu/lag 为 NULL）
            member_no INTEGER,
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
            neighbor_port TEXT DEFAULT '',
            source TEXT DEFAULT 'cdp',
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE INDEX IF NOT EXISTS idx_neighbors_device
            ON neighbors(device_id, collection_id);

        -- 生成树快照（一行 = 设备 × VLAN × 参与 STP 的端口；根/本桥信息按行冗余）
        CREATE TABLE IF NOT EXISTS stp_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            vlan INTEGER NOT NULL,
            port_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '',
            cost INTEGER,
            port_priority INTEGER,
            is_root INTEGER NOT NULL DEFAULT 0,
            root_priority INTEGER,
            root_mac TEXT DEFAULT '',
            bridge_priority INTEGER,
            bridge_mac TEXT DEFAULT '',
            mode TEXT DEFAULT '',
            FOREIGN KEY (collection_id) REFERENCES collections(id),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        );
        CREATE INDEX IF NOT EXISTS idx_stp_device_collection
            ON stp_snapshots(device_id, collection_id);
        CREATE INDEX IF NOT EXISTS idx_stp_device_vlan
            ON stp_snapshots(device_id, vlan);

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


def _migrate_v4(conn: sqlite3.Connection) -> None:
    """Schema v4: 更新 port_sudden_down 修复建议文本"""
    conn.execute(
        "UPDATE remediation_hints SET suggestion = ? WHERE alert_type = 'port_sudden_down'",
        (
            "端口当前为DOWN，上周是UP的。建议：1) 检查远端设备是否正常运行 "
            "2) 检查光模块/光纤/线缆物理连接 3) 检查 spanning-tree 拓扑是否有变更 "
            "4) 检查端口错误计数器",
        ),
    )


def _migrate_v5(conn: sqlite3.Connection) -> None:
    """Schema v5: devices 表添加 notes / uplink_ports / username 列"""
    for col, col_type in [
        ("notes", "TEXT DEFAULT ''"),
        ("uplink_ports", "TEXT DEFAULT ''"),
        ("username", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE devices ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在


def _migrate_v6(conn: sqlite3.Connection) -> None:
    """Schema v6: neighbors 表添加 neighbor_port 列"""
    try:
        conn.execute("ALTER TABLE neighbors ADD COLUMN neighbor_port TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 列已存在


def _migrate_v7(conn: sqlite3.Connection) -> None:
    """Schema v7: neighbors 表添加 is_logical 列 + collections 表添加 lag_membership 列"""
    try:
        conn.execute("ALTER TABLE neighbors ADD COLUMN is_logical INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE collections ADD COLUMN lag_membership TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass


def _migrate_v8(conn: sqlite3.Connection) -> None:
    """Schema v8: devices 表添加 member_ids 列（VSF 成员 ID，逗号拼接，与序列号 1:1）"""
    try:
        conn.execute("ALTER TABLE devices ADD COLUMN member_ids TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 列已存在


def _migrate_v9(conn: sqlite3.Connection) -> None:
    """Schema v9: 建 device_members 物理设备档案表（序列号主键，收集时 upsert，永不删除）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_members (
            serial_number TEXT PRIMARY KEY,
            model TEXT DEFAULT '',
            version TEXT DEFAULT '',
            last_device TEXT DEFAULT '',
            last_member TEXT DEFAULT '',
            last_seen TEXT DEFAULT '',
            -- v18 起：active 在用 / spare 备件在库 / retired 已报废（人工标注，系统不猜）
            status TEXT NOT NULL DEFAULT 'active',
            first_seen TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)


def _migrate_v10(conn: sqlite3.Connection) -> None:
    """Schema v10: port_snapshots 增加累计计数器原始读数（区间流量的计算来源）

    只存原始读数，不存派生值 —— 区间流量由 API 按用户选择的时间窗在读时计算，
    预计算会把窗口写死，每加一档就要加列 + 改 INSERT + 改迁移。

    不回填历史数据：历史行没有计数器原值，任何回填都是编造。

    SQLite 无 DEFAULT 的 ADD COLUMN 只改元数据、不重写表，几十万行也是瞬间。
    """
    for column in ("in_octets", "out_octets"):
        try:
            conn.execute(f"ALTER TABLE port_snapshots ADD COLUMN {column} INTEGER")
        except sqlite3.OperationalError:
            pass  # 列已存在（新建库已由 _migrate_v1 建好）

    # 「按周取最早基准」查询按 (device_id, port_name) 分区、按 collected_at 排序
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ports_device_port_collection "
        "ON port_snapshots(device_id, port_name, collection_id)"
    )


def _migrate_v11(conn: sqlite3.Connection) -> None:
    """Schema v11: 建 stp_snapshots 生成树快照表（站点 STP 拓扑图的数据源）

    一行 = 设备 × VLAN × 端口，只存参与生成树的端口（解析层已过滤 Down/Disabled）。
    根/本桥信息（is_root / root_* / bridge_*）与设备级模式（mode）按行冗余：
    查询简单（无需 join 汇总表），单轮量级约 1 万行，SQLite 毫无压力。
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stp_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            device_id INTEGER NOT NULL,
            vlan INTEGER NOT NULL,
            port_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '',
            cost INTEGER,
            port_priority INTEGER,
            is_root INTEGER NOT NULL DEFAULT 0,
            root_priority INTEGER,
            root_mac TEXT DEFAULT '',
            bridge_priority INTEGER,
            bridge_mac TEXT DEFAULT '',
            mode TEXT DEFAULT '',
            FOREIGN KEY (collection_id) REFERENCES collections(id),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stp_device_collection "
        "ON stp_snapshots(device_id, collection_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stp_device_vlan "
        "ON stp_snapshots(device_id, vlan)"
    )


def _migrate_v12(conn: sqlite3.Connection) -> None:
    """Schema v12: devices 表添加堆叠成员版本列（逗号拼接，与序列号同序 1:1）

    - member_versions：成员级**软件**版本 —— 只有 classic IOS 堆叠（2960X 等）的
      show version 成员表逐成员给出；IOS-XE 堆叠与 Aruba VSF 整堆叠共享镜像，
      此列为空，由报告侧用整机版本填充
    - member_rom_versions：Aruba VSF 成员级 ROM 版本（show vsf detail）——
      成员级唯一逐成员给出的版本；升级引导时逐个成员更新，可能出现不一致
    - member_uptimes：成员级运行时间（秒，逗号拼接）—— Cisco 用各成员段里的
      ``Switch Uptime``（1 号成员用设备级 uptime），Aruba 用成员段里的 ``Uptime``。
      成员级重启（堆叠里单台重启）是设备级 uptime 看不出来的故障信号

    三列都与序列号同序对齐（非堆叠时为空串）。不回填历史数据：
    show version / show vsf 原文未入库，任何回填都是编造。
    """
    for column in ("member_versions", "member_rom_versions", "member_uptimes"):
        try:
            conn.execute(f"ALTER TABLE devices ADD COLUMN {column} TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # 列已存在（新建库已由 _migrate_v1 建好）


def _migrate_v13(conn: sqlite3.Connection) -> None:
    """Schema v13: 配置审计结果两张表。

    - audit_runs：一次审计（单台按需审计不落库；全量审计落一行），趋势分析的基座
    - audit_findings：该次审计的每条发现

    **为什么证据要自包含**（evidence_json / current_text / 各 *_text 都存全文）：
    collections.running_config 按保留策略**只留最近 2 次**采集的全文，
    若发现只存 collection_id 引用，过两周配置被清理后证据就成了空指针——
    而审计记录是要长期留档给审计用的。

    **为什么不建"规则状态表"**：规则的启停直接写回 YAML 的 enabled 字段，
    YAML 保持唯一权威（与用户定案一致）。

    device_name / ruleset_hash 为冗余列：设备可能改名或删除，审计证据要能独立还原当时的情形。
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at      TEXT NOT NULL,
            finished_at     TEXT,
            trigger         TEXT NOT NULL DEFAULT 'manual',
            ruleset_hash    TEXT,
            ruleset_version INTEGER,
            device_count    INTEGER DEFAULT 0,
            finding_count   INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS audit_findings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        INTEGER NOT NULL,
            device_id     INTEGER,
            device_name   TEXT,
            collection_id INTEGER,
            week          TEXT,
            rule_id       TEXT NOT NULL,
            level         TEXT,
            source        TEXT,
            severity      TEXT,
            title         TEXT,
            detail        TEXT,
            current_text  TEXT,
            fix_text      TEXT,
            why_text      TEXT,
            note_text     TEXT,
            evidence_json TEXT,
            lines_json    TEXT,
            missing_json  TEXT,
            controls_json TEXT,
            config_hash   TEXT,
            ruleset_hash  TEXT,
            created_at    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_findings_run_level
            ON audit_findings(run_id, level);
        CREATE INDEX IF NOT EXISTS idx_audit_findings_device_rule
            ON audit_findings(device_id, rule_id);
    """)
    # trigger 取值约定：manual（手动全量）/ scheduled（计划任务）/ post_collect（采集后自动跑）
    # status 取值约定：running / done / failed


def _migrate_v14(conn: sqlite3.Connection) -> None:
    """Schema v14: collections 增加 startup_config 列。

    用途：与 running_config 比对，发现「改了但没保存」——设备重启会丢配置。

    **保留策略与 running_config 一致**（`retention.CONFIG_KEEP=2`，更早置 NULL）：
    两份配置的差异只在"当下"有意义，不需要长期历史。

    刻意**不给 startup 存周文件历史**：配置文本本身按周存一年是 62 MB，
    而 startup 变化极少（只在有人 save 时），52 份里 51 份是重复副本。
    文件层只在设备目录下留一份最新的 startup-config.raw（覆盖写）。
    """
    try:
        conn.execute("ALTER TABLE collections ADD COLUMN startup_config TEXT")
    except sqlite3.OperationalError:
        pass  # 列已存在


def _migrate_v15(conn: sqlite3.Connection) -> None:
    """Schema v15: 例外登记的落库列。

    - audit_findings.exempt_by：命中豁免时记例外 id（加索引，便于按例外反查影响面）
    - audit_findings.exempt_json：**当时的快照**（批准人/依据/到期日/状态）——
      历史审计要能回答"那次审计时它被谁批的豁免"，不能只存 id 再去 YAML 里现查
      （例外条目后来可能被改过或撤销）
    - audit_runs.exceptions_hash：那次审计用的例外集指纹 —— 趋势分析要能区分
      "标准变了"与"豁免变了"（ruleset_hash 不含例外，两者各自有指纹）
    - audit_runs.exempt_count：豁免条数（省得趋势页每次去 findings 里数）
    """
    for ddl in (
        "ALTER TABLE audit_findings ADD COLUMN exempt_by TEXT",
        "ALTER TABLE audit_findings ADD COLUMN exempt_json TEXT",
        "ALTER TABLE audit_runs ADD COLUMN exceptions_hash TEXT",
        "ALTER TABLE audit_runs ADD COLUMN exempt_count INTEGER DEFAULT 0",
        "CREATE INDEX IF NOT EXISTS idx_audit_findings_exempt ON audit_findings(exempt_by)",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # 列/索引已存在（迁移幂等）


def _migrate_v16(conn: sqlite3.Connection) -> None:
    """Schema v16: 设备生命周期两张表（EoL 型号缓存 + 逐序列号保修登记）。

    **为什么进库而不是 YAML**（与例外机制相反）：例外是"决策记录"（谁批的、到期复核），
    需要 git 追溯；EoL / 保修是**设备事实数据** —— 随 API 刷新而变、条数多（全网友 ≈50 个序列号）、
    且需要"手工值不被自动刷新覆盖"的语义，所以进库 + 页面编辑。

    device_name 冗余存名字（而不是只存 device_id）：设备改名/删除后记录仍可追溯 ——
    与 audit_findings 的做法一致。
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS eol_models (
            model          TEXT PRIMARY KEY,   -- 型号（Cisco PID / Aruba 型号号）
            description    TEXT,
            end_of_sale    TEXT,               -- YYYY-MM-DD
            end_of_support TEXT,               -- LastDateOfSupport
            announcement   TEXT,
            bulletin       TEXT,
            bulletin_url   TEXT,
            source         TEXT,               -- api（Cisco EoX）| manual
            fetched_at     TEXT,
            updated_by     TEXT,
            note           TEXT
        );

        CREATE TABLE IF NOT EXISTS device_lifecycle (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            device_name  TEXT NOT NULL,
            serial       TEXT NOT NULL DEFAULT '',   -- 堆叠设备逐成员一行
            model        TEXT,
            warranty_end TEXT,                       -- YYYY-MM-DD（保修，不是服务合同）
            note         TEXT,
            source       TEXT,                       -- manual | api
            verified_at  TEXT,                       -- 何时核实的（陈旧判定用）
            verified_by  TEXT,
            updated_at   TEXT,
            UNIQUE(device_name, serial)
        );
        CREATE INDEX IF NOT EXISTS idx_device_lifecycle_device ON device_lifecycle(device_name);
        CREATE INDEX IF NOT EXISTS idx_device_lifecycle_serial ON device_lifecycle(serial);
    """)


def _migrate_v17(conn: sqlite3.Connection) -> None:
    """Schema v17: 批量命令执行两张表（批次 + 逐台结果）。

    **为什么落库**：批量对生产设备执行命令需要留痕（谁 / 何时 / 哪台 / 什么命令 / 结果），
    这是变更追溯的底账。命令全文只存批次一份（逐台结果不重复存）；
    **凭据绝不入库**（用户名可以留痕，密码绝不落盘 —— 与全局纪律一致）。

    batch_id 由前端生成（uuid）：执行是前端逐台调端点（与采集同一编排模式），
    首台到达时 upsert 批次行，因此服务端无"批次生命周期"概念，只有 append。
    status 取值：success | failed | blocked（服务端黑名单兜底拦截）| skipped（用户中途停止）。
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS batch_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id     TEXT UNIQUE NOT NULL,   -- 前端生成的 uuid
            created_at   TEXT NOT NULL,
            username     TEXT,                   -- 操作者（登录设备用的账号；密码绝不落库）
            mode         TEXT,                   -- show（查询）| config（配置）
            save_config  INTEGER NOT NULL DEFAULT 0,  -- 配置模式下是否执行 write memory
            command_text TEXT,                   -- 命令全文（多行），只存这一份
            device_count INTEGER NOT NULL DEFAULT 0,  -- 计划执行台数
            note         TEXT                    -- 来源备注（如"来自审计发现"）
        );

        CREATE TABLE IF NOT EXISTS batch_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id    TEXT NOT NULL,
            device_name TEXT NOT NULL,
            status      TEXT NOT NULL,           -- success | failed | blocked | skipped
            output      TEXT DEFAULT '',         -- 命令输出（不截断）
            error       TEXT DEFAULT '',
            started_at  TEXT,
            finished_at TEXT,
            UNIQUE(batch_id, device_name)
        );
        CREATE INDEX IF NOT EXISTS idx_batch_results_batch ON batch_results(batch_id);
    """)


def _migrate_v18(conn: sqlite3.Connection) -> None:
    """Schema v18: 设备身份模型 —— kind + 物理成员行（spec 第三节）

    迁移是**冻结代码**：拆分逻辑不 import 业务模块（collector/utils 会演进，
    迁移必须永远可重放）。规则与 reports._expand_device_members 一致：
    序列号同序 1:1，member_ids 数量一致且全数字才采用真实号，否则顺序号（不补零）。

    逐表判存在再动：老库升级测试会手工造只含单表的旧库（如只有 port_snapshots），
    缺表必须跳过而不是炸掉整条迁移链。
    """
    # 1) devices：新列 + 成员行回填
    if _table_exists(conn, "devices"):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(devices)")}
        if "kind" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN kind TEXT NOT NULL DEFAULT 'standalone'")
        if "stack_name" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN stack_name TEXT DEFAULT ''")
        if "member_no" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN member_no INTEGER")
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_stack_member
                        ON devices(stack_name, member_no) WHERE kind = 'member'""")

        # 回填只对"完整" devices 表有意义：老库升级测试会造缺列的最小桩
        needed = {"id", "name", "ip", "type", "platform", "serial_number", "member_ids",
                  "model", "version", "location", "last_synced"}
        if needed <= cols:
            _v18_backfill_member_rows(conn)

    # 2) port_snapshots / device_members 新列
    if _table_exists(conn, "port_snapshots") and \
            "member_no" not in {r[1] for r in conn.execute("PRAGMA table_info(port_snapshots)")}:
        conn.execute("ALTER TABLE port_snapshots ADD COLUMN member_no INTEGER")
    if _table_exists(conn, "device_members") and \
            "status" not in {r[1] for r in conn.execute("PRAGMA table_info(device_members)")}:
        conn.execute("ALTER TABLE device_members ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

    # 3) 变更事件表（硬件指纹 diff 的结果记录，spec 第六节）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_change_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL REFERENCES devices(id),
            detected_at TEXT NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT DEFAULT '',
            note TEXT DEFAULT '',
            annotated_by TEXT DEFAULT ''
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_change_events_device "
                 "ON device_change_events(device_id, detected_at)")


def _v18_backfill_member_rows(conn: sqlite3.Connection) -> None:
    """v18 数据回填：堆叠行 → kind='stack' + 成员行（幂等：按 name 存在性跳过）"""
    def _split(raw: str) -> list[str]:
        return [s.strip() for s in (raw or "").split(",") if s.strip()]

    rows = conn.execute(
        "SELECT id, name, ip, type, platform, serial_number, member_ids, model, version, "
        "location, last_synced FROM devices WHERE kind != 'member'").fetchall()
    for (did, name, ip, dtype, platform, sn_str, mid_str, model_str, version,
         location, last_synced) in rows:
        serials = _split(sn_str)
        if len(serials) < 2:
            continue                                    # 单机保持 standalone
        conn.execute("UPDATE devices SET kind='stack' WHERE id=?", (did,))
        mids = _split(mid_str)
        use_real = len(mids) == len(serials) and all(m.isdigit() for m in mids)
        models = _split(model_str) or [""] * len(serials)
        for i, sn in enumerate(serials):
            suffix = mids[i] if use_real else str(i + 1)
            member_name = f"{name}-{suffix}"
            if conn.execute("SELECT 1 FROM devices WHERE name=?", (member_name,)).fetchone():
                continue                                # 幂等
            conn.execute(
                "INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no, "
                "serial_number, model, version, location, last_synced) "
                "VALUES (?, '', ?, ?, 'member', ?, ?, ?, ?, ?, ?, ?)",
                (member_name, dtype, platform, name, int(suffix), sn,
                 models[i] if i < len(models) else "", version or "", location or "",
                 last_synced or ""))


# 迁移注册表
_MIGRATIONS = {
    1: _migrate_v1,
    2: _migrate_v2,
    3: _migrate_v3,
    4: _migrate_v4,
    5: _migrate_v5,
    6: _migrate_v6,
    7: _migrate_v7,
    8: _migrate_v8,
    9: _migrate_v9,
    10: _migrate_v10,
    11: _migrate_v11,
    12: _migrate_v12,
    13: _migrate_v13,
    14: _migrate_v14,
    15: _migrate_v15,
    16: _migrate_v16,
    17: _migrate_v17,
    18: _migrate_v18,
}
