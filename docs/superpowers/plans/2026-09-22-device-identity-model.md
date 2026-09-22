# 设备身份模型 Implementation Plan（Plan 1 / 共 2 份）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让物理成员在库中真正成为一等公民——`devices` 表引入 `kind`（stack/standalone/member）+ 成员行，物理名格式全站统一为 `名字-编号`，硬件变更可检测可留痕。

**Architecture:** 位置身份（名字+IP，stack/standalone 行）持有配置/采集/审计等全部现有数据；物理成员行（member）承载序列号/型号/版本等硬件身份。**配置类外键语义不变**（collections/port_snapshots/alerts/audit_* 仍指向位置行），因此不需要"-1 是主成员"这类隐藏约定。物理名由 `{stack_name}-{member_no}` 物化派生，格式规则只在 `backend/utils/device_identity.py` 一处实现。

**Tech Stack:** Python 3 / FastAPI / SQLite（schema v18）/ pytest；React 18 + MUI + TypeScript（`npx tsc --noEmit` 验证）。

**Spec:** `docs/superpowers/specs/2026-09-22-device-identity-design.md`（务必先读；本计划按它第三节~第八节展开）

## Global Constraints

- `kind` 值域：`stack`（有堆叠/VSF 配置的管理体，哪怕只有 1 个成员）/ `standalone`（单机，自身携带序列号）/ `member`（堆叠成员行，只表示当前占位）。
- 物理名格式：`{stack_name}-{member_no}`，**编号不补零**、跳号原样；成员号优先级：`member_ids`（Aruba VSF / Cisco 成员表第 1 组）> 端口名前缀 > 顺序号兜底。
- 展示名：成员数 ≥2 → 物理名；=1 → 基础名（存储名恒定，均为 `{stack}-{n}`）；单机不加后缀。
- 成员行：`name` 物化派生（`UNIQUE(name)` 覆盖）；**不存 ip**；`location` 继承堆叠；`last_synced` 用于离线判定（30 天规则）。
- 失败保护：本次采集 `serial_number` 为空或 `"未知"` → **不碰成员行、不写变更事件**。
- 成员消失 → 成员行**保留 + 离线标记**（不删除）；删堆叠行 → 成员行级联删除；改名只允许改 stack/standalone 行。
- 查询纪律：禁止新增裸查 `devices`；一律走 `device_dal` 的 `list_managed()` / `list_physical()`。
- **不要用 bash heredoc 写含反引号/花括号的中文内容**（会生成 0 字节怪文件，bug-151 第 8 次）；追加文件一律用 Edit/Write 工具。
- 后端测试：`cd backend && python -m pytest tests/ -q`，必须在 `backend/` 目录下跑。
- 前端改完必须 `cd frontend && npx tsc --noEmit`（vite build 不跑 tsc）；构建 `npm run build` 后 `dist/` 入库。
- 迁移纪律：改 schema 三件套——① 更新 v1 CREATE TABLE ② 写 `_migrate_vN` ③ **递增 `SCHEMA_VERSION`**（当前 17 → 18）。
- 每个任务一个提交，提交信息中文。

## File Structure

- Modify: `backend/storage/database.py` — v18 迁移（devices 三列 + port_snapshots.member_no + device_change_events + device_members.status）
- Create: `backend/utils/device_identity.py` — 物理名/成员号唯一实现
- Modify: `backend/utils/port_names.py` — 新增 `member_no_from_port`（从 topology 迁入）
- Modify: `backend/services/collector_service.py` — Cisco 成员号解析、成员行维护、指纹接线、port member_no
- Create: `backend/analyzers/hardware_change.py` — 硬件指纹与变更事件
- Modify: `backend/storage/device_dal.py` — `list_managed` / `list_physical` / 级联删除 / 改名同步
- Modify: `backend/api/devices.py`、`reports.py`、`stats.py`、`topology.py`、`batch.py`、`logs.py`
- Modify: `backend/storage/lifecycle_dal.py`、`backend/analyzers/compliance/source.py`、`backend/services/log_analyzer.py`、`backend/storage/file_manager.py`
- Modify: `frontend/src/pages/Dashboard.tsx`、`components/topology/PortTopologyCanvas.tsx`、`components/LifecycleCard.tsx`、`services/api.ts`
- Tests: `backend/tests/test_migration_v18.py`、`test_device_identity.py`、`test_hardware_change.py`、`test_member_rows.py`、`test_kind_filters.py`

---

### Task 1: schema v18 + 数据迁移

**Files:**
- Modify: `backend/storage/database.py`（`SCHEMA_VERSION`、`_migrate_v1` 的 devices/port_snapshots CREATE、新增 `_migrate_v18`）
- Test: `backend/tests/test_migration_v18.py`

**Interfaces:**
- Consumes: 无
- Produces: `devices.kind/stack_name/member_no`、`port_snapshots.member_no`、`device_change_events` 表、`device_members.status`

- [ ] **Step 1: 写失败测试**

```python
"""v18 迁移测试：设备身份模型（kind + 成员行）"""
import sqlite3
import pytest
import storage.database as db


@pytest.fixture
def restore_db_path():
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


def test_旧库迁移_堆叠展开成员行(tmp_path, restore_db_path):
    """造一个 v17 库（两台：一台双成员堆叠、一台单机），跑迁移，断言 61 行拆分规则"""
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

    rows = {r[0]: dict(zip(["name", "kind", "stack_name", "member_no", "serial_number"], r[1:]))
            for r in conn.execute(
                "SELECT id, name, kind, stack_name, member_no, serial_number FROM devices")}
    assert rows["TESTD1SWI01"]["kind"] == "stack"
    assert rows["TESTD1SWI01"]["serial_number"] == "SN1, SN2"      # 逗号串保留作缓存
    assert rows["TESTD1SWI01-1"]["kind"] == "member"
    assert rows["TESTD1SWI01-1"]["stack_name"] == "TESTD1SWI01"
    assert rows["TESTD1SWI01-1"]["member_no"] == 1
    assert rows["TESTD1SWI01-1"]["serial_number"] == "SN1"
    assert rows["TESTD1SWI01-2"]["member_no"] == 2
    assert rows["TESTD1SWI02"]["kind"] == "standalone"
    assert "TESTD1SWI02-1" not in rows                             # 单机不建成员行

    db.init_db(str(tmp_path))          # 幂等
    assert conn.execute("SELECT COUNT(*) FROM devices WHERE kind='member'").fetchone()[0] == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_migration_v18.py -q`
Expected: FAIL（`kind` 列不存在）

- [ ] **Step 3: 实现 v18**

`database.py` 顶部 `SCHEMA_VERSION = 18`。v1 的 `devices` CREATE TABLE 增加三列（新库直接有）：

```sql
    kind TEXT NOT NULL DEFAULT 'standalone',   -- stack / standalone / member
    stack_name TEXT DEFAULT '',                -- 成员行：所属堆叠名
    member_no INTEGER,                         -- 成员行：真实成员号
```

v1 的 `port_snapshots` CREATE TABLE 加 `member_no INTEGER,`；`device_members` CREATE TABLE 加 `status TEXT NOT NULL DEFAULT 'active',`。

新增迁移函数（放在 `_migrate_v17` 之后）：

```python
def _migrate_v18(conn: sqlite3.Connection) -> None:
    """Schema v18: 设备身份模型 —— kind + 物理成员行（spec 第三节）

    迁移是**冻结代码**：拆分逻辑不 import 业务模块（collector/utils 会演进，
    迁移必须永远可重放）。规则与 reports._expand_device_members 一致：
    序列号同序 1:1，member_ids 数量一致且全数字才采用真实号，否则顺序号（不补零）。
    """
    # 1) devices 新列（幂等：PRAGMA 检查）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(devices)")}
    if "kind" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN kind TEXT NOT NULL DEFAULT 'standalone'")
    if "stack_name" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN stack_name TEXT DEFAULT ''")
    if "member_no" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN member_no INTEGER")
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_stack_member
                    ON devices(stack_name, member_no) WHERE kind = 'member'""")

    # 2) port_snapshots / device_members 新列
    if "member_no" not in {r[1] for r in conn.execute("PRAGMA table_info(port_snapshots)")}:
        conn.execute("ALTER TABLE port_snapshots ADD COLUMN member_no INTEGER")
    if "status" not in {r[1] for r in conn.execute("PRAGMA table_info(device_members)")}:
        conn.execute("ALTER TABLE device_members ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

    # 3) 变更事件表
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

    # 4) 数据回填：堆叠行 → stack + 成员行
    def _split(raw):
        return [s.strip() for s in (raw or "").split(",") if s.strip()]

    rows = conn.execute(
        "SELECT id, name, ip, type, platform, serial_number, member_ids, model, version, "
        "location, last_synced FROM devices WHERE kind != 'member'").fetchall()
    for r in rows:
        (did, name, ip, dtype, platform, sn_str, mid_str, model_str, version,
         location, last_synced) = r
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
                 models[i] if i < len(models) else "", version or "", location or "", last_synced or ""))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_migration_v18.py tests/test_database_migration.py -q`
Expected: PASS（旧迁移测试也要全绿）

- [ ] **Step 5: 全量回归 + 提交**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 全绿（既有测试若因 devices 出现成员行而失败，说明它们缺少 kind 过滤——这正是 Task 6 要修的，先在此记录，**不要**改测试断言来掩盖）

```bash
git add backend/storage/database.py backend/tests/test_migration_v18.py
git commit -m "身份模型 v18：devices 加 kind/stack_name/member_no，堆叠展开物理成员行"
```

---

### Task 2: device_identity 助手 + 端口→成员号规则迁入 port_names

**Files:**
- Create: `backend/utils/device_identity.py`
- Modify: `backend/utils/port_names.py`（新增 `member_no_from_port`）
- Modify: `backend/api/topology.py:956`（`_member_slot_for_port` 改为委托）
- Test: `backend/tests/test_device_identity.py`

**Interfaces:**
- Consumes: 无
- Produces（后续任务全部依赖这些签名，不得改名）：
  - `device_identity.member_suffixes(serial_count: int, member_ids: str) -> list[str]`
  - `device_identity.physical_name(stack_name: str, suffix: str) -> str`
  - `device_identity.display_name(stack_name: str, suffix: str, member_count: int) -> str`
  - `device_identity.kind_from_config(config_text: str, member_count: int) -> str`
  - `port_names.member_no_from_port(port_name: str, platform: str) -> int | None`

- [ ] **Step 1: 写失败测试**

```python
"""设备身份助手测试（spec 第四节：格式唯一规则）"""
from utils.device_identity import member_suffixes, physical_name, display_name, kind_from_config
from utils.port_names import member_no_from_port


def test_真实成员号优先且不补零():
    assert member_suffixes(3, "1, 3, 4") == ["1", "3", "4"]      # 跳号原样


def test_数量不一致回退顺序号():
    assert member_suffixes(2, "1") == ["1", "2"]
    assert member_suffixes(2, "") == ["1", "2"]


def test_非数字成员号回退顺序号():
    assert member_suffixes(2, "1, 未知") == ["1", "2"]


def test_物理名不补零():
    assert physical_name("SZXD1SWI01", "3") == "SZXD1SWI01-3"


def test_展示名_单成员不加后缀():
    assert display_name("SZXD1SWI01", "1", 1) == "SZXD1SWI01"
    assert display_name("SZXD1SWI01", "1", 3) == "SZXD1SWI01-1"


def test_kind按配置判定():
    assert kind_from_config("vsf member 1\n type jl726b\n", 1) == "stack"      # 1 成员 VSF 仍是 stack
    assert kind_from_config("switch 1 provision ws-c2960x\n", 2) == "stack"
    assert kind_from_config("hostname SWI\ninterface Gi0/1\n", 1) == "standalone"


def test_端口名前缀取成员号():
    assert member_no_from_port("1/1/14", "aruba_aoscx") == 1
    assert member_no_from_port("Gi2/0/1", "cisco_ios") == 2
    assert member_no_from_port("Te1/1/1", "cisco_ios") == 1
    assert member_no_from_port("Po1", "cisco_ios") is None       # 逻辑口
    assert member_no_from_port("lag1", "aruba_aoscx") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_device_identity.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`backend/utils/device_identity.py`：

```python
"""设备身份助手 —— 物理名格式的唯一实现（spec 第四节）

规则：物理名 = f"{stack_name}-{suffix}"，编号不补零、跳号原样；
成员号优先级：member_ids（Aruba VSF / Cisco 成员表）> 端口名前缀（见 port_names）
> 顺序号兜底。顺序号会身份漂移（跳号场景），仅作最后兜底。
"""
import re


def member_suffixes(serial_count: int, member_ids: str) -> list[str]:
    """成员后缀列表（与序列号同序 1:1）。真实号全为数字且数量一致才采用。"""
    mids = [m.strip() for m in (member_ids or "").split(",") if m.strip()]
    if len(mids) == serial_count and all(m.isdigit() for m in mids):
        return mids
    return [str(i + 1) for i in range(serial_count)]


def physical_name(stack_name: str, suffix: str) -> str:
    return f"{stack_name}-{suffix}"


def display_name(stack_name: str, suffix: str, member_count: int) -> str:
    """展示名：成员数 ≥2 → 物理名；=1 → 基础名（与单机一致）。存储名恒定。"""
    return physical_name(stack_name, suffix) if member_count >= 2 else stack_name


_STACK_CONFIG_RE = re.compile(r'^\s*(vsf\s+member\s+\d+|switch\s+\d+\s)', re.MULTILINE | re.IGNORECASE)


def kind_from_config(config_text: str, member_count: int) -> str:
    """kind 判定按**配置**（有堆叠/VSF 配置即 stack，哪怕只有 1 个成员）。"""
    if _STACK_CONFIG_RE.search(config_text or ""):
        return "stack"
    return "stack" if member_count >= 2 else "standalone"
```

`backend/utils/port_names.py` 追加（函数体从 `api/topology.py::_member_slot_for_port` 原样迁入，改为返回 `int | None`，逻辑口返回 None）：

```python
def member_no_from_port(port_name: str, platform: str) -> int | None:
    """端口名 → 成员号（Aruba `1/1/14` 首段；Cisco `Gi2/0/1` 首个数字段）。
    逻辑口（Po*/Hu*/lag*/vlan*）返回 None。规则迁自 api/topology._member_slot_for_port。"""
```

`api/topology.py` 的 `_member_slot_for_port` 改为一行委托 `member_no_from_port`（保留函数名避免动调用点）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_device_identity.py tests/test_port_names.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/utils/device_identity.py backend/utils/port_names.py backend/api/topology.py backend/tests/test_device_identity.py
git commit -m "身份助手：物理名格式唯一实现 + 端口→成员号规则迁入 port_names"
```

---

### Task 3: Cisco 堆叠成员号解析

**Files:**
- Modify: `backend/services/collector_service.py:218`（`extract_member_ids`）
- Test: `backend/tests/test_member_parser.py`（追加用例）

**Interfaces:**
- Consumes: `_CISCO_MEMBER_TABLE_HEADER/_ROW`（已存在，`_ROW` 第 1 组即 Switch 号，现被丢弃）
- Produces: `extract_member_ids(vsf_output: str = "", version_output: str = "") -> str`（签名向后兼容；调用点需补传 `version_output`）

- [ ] **Step 1: 写失败测试**（追加到 `test_member_parser.py`）

```python
def test_cisco堆叠从成员表取Switch号():
    """成员表第 1 组就是 Switch 号（* 标记主交换机）——之前只取了版本，号码被丢弃"""
    version_output = (
        "Switch Ports Model                     SW Version            SW Image\n"
        "------ ----- -----                     ----------            ----------\n"
        "*    1 52    WS-C2960X-48FPD-L         15.2(4)E8             C2960X-UNIVERSALK9-M\n"
        "     2 52    WS-C2960X-48FPD-L         15.2(4)E8             C2960X-UNIVERSALK9-M\n"
    )
    assert extract_member_ids("", version_output) == "1, 2"


def test_aruba优先于cisco分支():
    vsf = "Member ID                 : 1\nMember ID                 : 3\n"
    version_output = ("Switch Ports Model                     SW Version            SW Image\n"
                      "------ ----- -----                     ----------            ----------\n"
                      "     1 52    WS-C2960X-48FPD-L         15.2(4)E8             C2960X-UNIVERSALK9-M\n")
    assert extract_member_ids(vsf, version_output) == "1, 3"      # 跳号原样


def test_都没有则返回空():
    assert extract_member_ids("", "") == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_member_parser.py -q`
Expected: FAIL（Cisco 用例返回 ""）

- [ ] **Step 3: 实现**（`extract_member_ids` 改为双数据源）

```python
def extract_member_ids(vsf_output: str = "", version_output: str = "") -> str:
    """成员号（逗号拼接，与序列号同序 1:1）。

    ① Aruba：show vsf detail 的 `Member ID : N` 行（现有逻辑）；
    ② Cisco：show version 成员表第 1 列（`* 1 52 WS-C2960X...`）——与版本同表，
       此前只取了第 4 组（版本）。不加此源，Cisco 堆叠只能顺序号兜底，
       跳号场景会身份漂移（成员 2 拆走后成员 3 被标成 -2）。
    不去重 —— 与序列号按行序一一对应。
    """
    # ① Aruba VSF（原逻辑）
    members = []
    if vsf_output:
        for line in _strip_ansi(vsf_output).splitlines():
            m = re.search(r'^\s*Member\s+ID\s*:\s*(\d+)', line, re.IGNORECASE)
            if m:
                members.append(m.group(1))
    if members:
        return ", ".join(members)
    # ② Cisco 成员表（复用版本解析的同一表头/行正则）
    if version_output:
        text = _strip_ansi(version_output)
        header = _CISCO_MEMBER_TABLE_HEADER.search(text)
        if header:
            for line in text[header.end():].splitlines():
                m = _CISCO_MEMBER_TABLE_ROW.match(line)
                if m:
                    members.append(m.group(1))
                elif members:
                    break
    return ", ".join(members)
```

调用点（`collect_device` 内）改为 `extract_member_ids(vsf_output, version_output)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_member_parser.py -q`
Expected: PASS（既有用例全绿）

- [ ] **Step 5: 提交**

```bash
git add backend/services/collector_service.py backend/tests/test_member_parser.py
git commit -m "Cisco 堆叠成员号：接上成员表第 1 组（此前被丢弃），顺序号降级为兜底"
```

---

### Task 4: 成员行维护（采集写入路径）

**Files:**
- Modify: `backend/services/collector_service.py`（`_save_to_sqlite` 约 1160-1250 行；新增模块内函数 `_maintain_member_rows`）
- Test: `backend/tests/test_member_rows.py`

**Interfaces:**
- Consumes: `device_identity.member_suffixes/physical_name/kind_from_config`（Task 2）
- Produces: 采集成功后自动 upsert 成员行；返回 `member_row_ids: dict[int, int]`（member_no → device_id，供 Task 5 写事件用）

- [ ] **Step 1: 写失败测试**（模式照抄 `test_member_parser.py` 的 `tmp_path + restore_db_path`）

```python
"""成员行维护测试：成功 upsert / 失败保护 / 离线保留 / 级联删除"""
# 用现有 test_member_parser.py 的 _save 辅助方式（直接调 collector_service._save_to_sqlite，
# 参数：device_name/ip/.../serial_number="SN1, SN2"/member_ids="1, 2"/running_config="vsf member 1\n..."）

def test_堆叠采集后建成员行(tmp_path, restore_db_path):
    ...  # 采集一次 → devices 里 TESTD1SWI01(kind=stack) + TESTD1SWI01-1/-2(kind=member, serial=SN1/SN2)
    #      成员行 ip 必须为 ''、location 继承堆叠、name = f"{stack}-{member_no}"

def test_成员消失保留并离线(tmp_path, restore_db_path):
    ...  # 先 2 成员，再采 1 成员（SN1）→ TESTD1SWI01-2 行仍在且 kind='member'，
    #      last_synced 停在旧时间（用旧值断言）

def test_采集失败不碰成员行(tmp_path, restore_db_path):
    ...  # serial_number="未知" → 成员行不动、无变更事件

def test_单机kind为standalone(tmp_path, restore_db_path):
    ...  # 单机（无堆叠配置、1 序列号）→ kind='standalone'，无成员行

def test_删除堆叠行级联删成员(tmp_path, restore_db_path):
    ...  # dal.delete_device('TESTD1SWI01') → 成员行一并消失
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_member_rows.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 `_maintain_member_rows`**

在 `collector_service.py` 增加（在 `_save_to_sqlite` 的 devices upsert 成功后、`device_members` 档案 upsert 之前调用）：

```python
def _maintain_member_rows(db, device_id: int, device_name: str, serial_number: str,
                          member_ids: str, model_string: str, version: str,
                          location: str, collected_at: str) -> dict[int, int]:
    """成功采集后维护该堆叠的成员行（spec 第五节）。

    - kind：kind_from_config(配置) 决定 stack/standalone（1 成员 VSF 仍是 stack）
    - 新增/更新：upsert by (stack_name, member_no)，name 物化派生
    - 消失成员：**保留行 + 不改 last_synced**（离线由 30 天规则判定）
    - 成员行不存 ip；location 继承堆叠
    返回 {member_no: row_id}（Task 5 记录事件用）。
    """
    serials = [s.strip() for s in serial_number.split(",") if s.strip()]
    suffix_list = member_suffixes(len(serials), member_ids)
    models = [m.strip() for m in (model_string or "").split(",")]
    row_ids: dict[int, int] = {}
    for i, sn in enumerate(serials):
        member_no = int(suffix_list[i]) if suffix_list[i].isdigit() else i + 1
        name = physical_name(device_name, suffix_list[i])
        m_model = models[i] if i < len(models) else (models[-1] if models else "")
        db.execute(
            """INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no,
                                    serial_number, model, version, location, last_synced)
               SELECT ?, '', d.type, d.platform, 'member', ?, ?, ?, ?, ?, ?, ?
               FROM devices d WHERE d.id = ?
               ON CONFLICT(name) DO UPDATE SET
                   serial_number = excluded.serial_number,
                   model = excluded.model,
                   version = excluded.version,
                   location = excluded.location,
                   last_synced = excluded.last_synced""",
            (name, device_name, member_no, sn, m_model, version, location, collected_at, device_id))
        row_ids[member_no] = db.execute("SELECT id FROM devices WHERE name=?", (name,)).fetchone()[0]
    return row_ids
```

调用条件（**失败保护**）：

```python
        if serial_number and serial_number != "未知":
            db.execute("UPDATE devices SET kind=? WHERE id=?",
                       (kind_from_config(running_config or "", len(serials)), device_id))
            if len(serials) >= 2:
                _maintain_member_rows(db, device_id, device_name, serial_number,
                                      member_ids, model_string, version, location, collected_at)
```

（`kind` 判定用本次采集的 running_config；`running_config` 为 None 时传 `""`。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_member_rows.py tests/test_member_parser.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/services/collector_service.py backend/tests/test_member_rows.py
git commit -m "成员行维护：采集后 upsert/离线保留/失败保护，kind 按配置判定"
```

---

### Task 5: 硬件指纹与变更事件

**Files:**
- Create: `backend/analyzers/hardware_change.py`
- Modify: `backend/services/collector_service.py`（`_save_to_sqlite` 接线：更新**前**读旧行建 prev 指纹）
- Test: `backend/tests/test_hardware_change.py`

**Interfaces:**
- Consumes: Task 1 的 `device_change_events` 表、Task 4 的成员行
- Produces：
  - `hardware_change.compute_fingerprint(platform: str, model_str: str, serial_str: str, kind: str) -> dict`
  - `hardware_change.diff_fingerprints(prev: dict | None, cur: dict) -> dict | None`（返回 `{"kind": ..., "detail": ...}`）
  - `hardware_change.record_event(conn, device_id: int, event: dict, detected_at: str, movements: list[dict]) -> None`

- [ ] **Step 1: 写失败测试**

```python
"""硬件变更检测测试（spec 第六节六情形 + 零交集整机更换 + 调拨）"""
from analyzers.hardware_change import compute_fingerprint, diff_fingerprints


def fp(platform, models, serials, kind="stack"):
    return compute_fingerprint(platform, ",".join(models), ",".join(serials), kind)


def test_无变化():
    a = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    assert diff_fingerprints(a, a) is None


def test_成员新增():
    prev = fp("aruba_aoscx", ["JL727B"], ["SN1"])
    cur = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    ev = diff_fingerprints(prev, cur)
    assert ev["kind"] == "member_added" and "SN2" in ev["detail"]


def test_成员减少():
    prev = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    cur = fp("aruba_aoscx", ["JL727B"], ["SN1"])
    assert diff_fingerprints(prev, cur)["kind"] == "member_removed"


def test_成员更换_部分交集同槽位新SN():
    prev = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    cur = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN3"])
    ev = diff_fingerprints(prev, cur)
    assert ev["kind"] == "member_replaced" and "SN3" in ev["detail"] and "SN2" in ev["detail"]


def test_整机更换_零交集():
    """Cisco 单机 → Aruba VSF 双机：平台/型号全变、SN 零交集"""
    prev = fp("cisco_ios", ["WS-C2960X-48FPD-L"], ["FCW1"], kind="standalone")
    cur = fp("aruba_aoscx", ["JL726B", "JL727B"], ["SG1", "CN2"])
    ev = diff_fingerprints(prev, cur)
    assert ev["kind"] == "full_replacement" and "cisco_ios" in ev["detail"] and "aruba_aoscx" in ev["detail"]


def test_形态变化_standalone到一成员stack():
    prev = fp("aruba_aoscx", ["JL659A"], ["SN1"], kind="standalone")
    cur = fp("aruba_aoscx", ["JL659A"], ["SN1"], kind="stack")
    assert diff_fingerprints(prev, cur)["kind"] == "form_change"


def test_首次采集无事件():
    assert diff_fingerprints(None, fp("aruba_aoscx", ["JL727B"], ["SN1"])) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_hardware_change.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

```python
"""硬件变更检测 —— 指纹 diff 与事件（spec 第六节）

只做确定性集合比较（"什么变了"）；不做策略（"该怎么办"）——整机级变化
只记录、只提示，历史全留，由人工备注（意图不自动化）。
"""
import json


def compute_fingerprint(platform: str, model_str: str, serial_str: str, kind: str) -> dict:
    models = sorted({m.strip() for m in (model_str or "").split(",") if m.strip()})
    serials = sorted({s.strip() for s in (serial_str or "").split(",") if s.strip()})
    return {"platform": platform or "", "models": models, "serials": serials,
            "member_count": len(serials), "kind": kind or ""}


def diff_fingerprints(prev: dict | None, cur: dict) -> dict | None:
    """六情形判定；优先级：整机更换 > 形态变化 > 成员级变化。无变化/首次采集 → None"""
    if prev is None:
        return None
    if prev == cur:
        return None
    old, new = set(prev["serials"]), set(cur["serials"])
    # 整机更换：平台或型号族变化，或 SN 零交集
    if prev["platform"] != cur["platform"] or not (old & new) or \
            (prev["models"] and cur["models"] and prev["models"] != cur["models"]):
        return {"kind": "full_replacement",
                "detail": json.dumps({"platform": [prev["platform"], cur["platform"]],
                                      "models": [prev["models"], cur["models"]],
                                      "serials": [sorted(old), sorted(new)]}, ensure_ascii=False)}
    if prev["kind"] != cur["kind"]:
        return {"kind": "form_change",
                "detail": json.dumps({"kind": [prev["kind"], cur["kind"]]}, ensure_ascii=False)}
    if new > old:
        return {"kind": "member_added",
                "detail": json.dumps({"added": sorted(new - old)}, ensure_ascii=False)}
    if old > new:
        return {"kind": "member_removed",
                "detail": json.dumps({"removed": sorted(old - new)}, ensure_ascii=False)}
    if old == new:
        return {"kind": "member_reordered", "detail": "{}"}
    return {"kind": "member_replaced",
            "detail": json.dumps({"out": sorted(old - new), "in": sorted(new - old)},
                                 ensure_ascii=False)}


def record_event(conn, device_id: int, event: dict, detected_at: str,
                 movements: list[dict] | None = None) -> None:
    """写变更事件；movements = [{serial, from_device}]（调拨，来自 device_members.last_device 变化）"""
    detail = event.get("detail") or ""
    if movements:
        detail = json.dumps({"diff": detail, "movements": movements}, ensure_ascii=False)
    conn.execute(
        "INSERT INTO device_change_events (device_id, detected_at, kind, detail) VALUES (?,?,?,?)",
        (device_id, detected_at, event["kind"], detail))
```

接线（`_save_to_sqlite`，**在 devices upsert 之前**读旧行）：

```python
        prev_row = db.execute(
            "SELECT platform, model, serial_number, kind FROM devices WHERE id=?",
            (device_id,)).fetchone()
        prev_fp = compute_fingerprint(*prev_row) if prev_row else None
        # ...（原有 upsert / 成员行维护）...
        if serial_number and serial_number != "未知":
            cur_fp = compute_fingerprint(platform, model_string, serial_number,
                                         kind_from_config(running_config or "", len(serials)))
            ev = diff_fingerprints(prev_fp, cur_fp)
            if ev:
                record_event(db, device_id, ev, collected_at, movements=_detect_movements(...))
```

调拨检测：在 `device_members` upsert 循环里，**先查** `SELECT last_device FROM device_members WHERE serial_number=?`，若存在且 `!= device_name` → 记 `{"serial": sn, "from_device": old_last_device}`（去向=当前设备）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_hardware_change.py tests/test_member_rows.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/analyzers/hardware_change.py backend/services/collector_service.py backend/tests/test_hardware_change.py
git commit -m "硬件变更检测：指纹 diff 六情形 + 变更事件 + 调拨记录"
```

---

### Task 6: device_dal 收敛（kind 过滤的唯一入口）

**Files:**
- Modify: `backend/storage/device_dal.py`
- Test: `backend/tests/test_kind_filters.py`

**Interfaces:**
- Consumes: Task 1 schema
- Produces：
  - `device_dal.list_managed(kind: str = "") -> list[dict]`（kind IN ('stack','standalone')）
  - `device_dal.list_physical() -> list[dict]`（kind IN ('member','standalone')）
  - `device_dal.get_all_devices()` **改为 `list_managed` 的别名**（既有调用点自动获得正确语义）
  - `device_dal.rename_device(old, new)`：改 stack 名时同步成员行 `stack_name` 与 `name`
  - `device_dal.delete_device(name)`：删 stack → 级联删成员行；**kind='member' 直接抛 ValueError**

- [ ] **Step 1: 写失败测试**

```python
"""kind 过滤纪律测试：成员行不得混入管理体清单（每类页面防漏网）"""
# 建库后插入：1 stack + 2 member + 1 standalone
# 断言：
#   list_managed()      → 2 台（stack + standalone），不含 member
#   list_physical()     → 3 台（2 member + standalone）
#   get_all_devices()   → 同 list_managed
#   delete_device('stack 名')     → member 行一并消失
#   delete_device('成员名')       → ValueError
#   rename_device('STACK','NEW')  → NEW-1 / NEW-2 出现且 stack_name 更新
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_kind_filters.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**（`get_all_devices` 保持函数名，内部改走 managed 语义；其余新函数按 Interfaces 实现）

- [ ] **Step 4: 跑测试 + 全量回归**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS（Task 1 记录过的失败点应在此任务后消除）

- [ ] **Step 5: 提交**

```bash
git add backend/storage/device_dal.py backend/tests/test_kind_filters.py
git commit -m "device_dal 收敛：list_managed/list_physical 唯一入口，改名/删除按 kind 规则"
```

---

### Task 7: 成员行不可采集/执行/查日志（按名入口拒绝）

**Files:**
- Modify: `backend/api/batch.py:54`、`backend/api/logs.py:134,208`、`backend/services/collector_service.py:937,1219,1717`、`backend/services/log_analyzer.py:43,48`、`backend/storage/file_manager.py:193`、`backend/analyzers/compliance/source.py:77,129`
- Test: `backend/tests/test_kind_filters.py`（追加）

**Interfaces:**
- Consumes: Task 6
- Produces: 成员行名字打到任何"按名"入口 → `HTTPException(400, "SZXD1SWI01-1 是堆叠成员，请对堆叠 SZXD1SWI01 操作")`；location 扫描 / 文件清理 / 审计源只遍历管理体。

- [ ] **Step 1: 写失败测试**：`POST /api/collect/{成员名}` 与批量执行同一断言 400；`_scan_device_neighbors()` 返回的 key 不含成员名。
- [ ] **Step 2: 跑测试确认失败** — Run: `cd backend && python -m pytest tests/test_kind_filters.py -q`
- [ ] **Step 3: 实现**：在按名取设备的位置统一加 `kind='member'` 拒绝（错误文案含堆叠名，从 `stack_name` 取）；三处扫描类查询加 `WHERE d.kind != 'member'`。
- [ ] **Step 4: 跑测试确认通过** — Run: `cd backend && python -m pytest tests/ -q`
- [ ] **Step 5: 提交**

```bash
git add backend/api/batch.py backend/api/logs.py backend/services/collector_service.py \
        backend/services/log_analyzer.py backend/storage/file_manager.py \
        backend/analyzers/compliance/source.py backend/tests/test_kind_filters.py
git commit -m "kind 过滤清扫：成员行拒绝采集/执行/日志入口，扫描类查询排除成员行"
```

---

### Task 8: 设备清单 API 返回物理行 + Dashboard 切换

**Files:**
- Modify: `backend/api/devices.py`（列表端点增加 `view=physical|managed` 参数，默认 physical；响应含 `kind/stack_name/member_no/serial_number`）
- Modify: `frontend/src/pages/Dashboard.tsx:208-239`（删除本地展开 useMemo，直接消费 API 行）
- Modify: `frontend/src/components/devices/deviceUtils.ts`（`memberSuffixes` 若无调用方则删除）
- Test: `backend/tests/test_devices_api.py`（若不存在则新建）

**Interfaces:**
- Consumes: Task 6 `list_physical()`
- Produces: `GET /api/devices?view=physical` → 物理行数组（member 行带 `stack_name`/`member_no`；standalone 行自身带 serial）

- [ ] **Step 1: 写失败测试**：断言 physical 视图 3 行（2 member + 1 standalone），member 行 `ip` 为空且前端可从 stack 行补；managed 视图 2 行。
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现**：后端按 `view` 走 `list_physical/list_managed`，物理视图每行补 `ip`（从 stack 行带出，spec：成员行不存 ip、API 返回时带出）；前端 Dashboard 删除展开逻辑，表格主键改用 `name`（物理名已由 API 给出）。
- [ ] **Step 4: 验证**：`cd backend && python -m pytest tests/test_devices_api.py -q`；`cd frontend && npx tsc --noEmit`；`npm run build`。
- [ ] **Step 5: 提交**

```bash
git add backend/api/devices.py backend/tests/test_devices_api.py frontend/src/pages/Dashboard.tsx frontend/src/components/devices/deviceUtils.ts frontend/dist
git commit -m "设备清单：API 直接返回物理行（view=physical），Dashboard 删除前端展开"
```

---

### Task 9: 软件版本报告改读成员行

**Files:**
- Modify: `backend/api/reports.py:17-132`（`_expand_device_members` 退役；`report_software_versions` 直接 SELECT member + standalone 行）
- Test: `backend/tests/test_reports_api.py`（改断言：数据源为行，不再展开）

**Interfaces:**
- Consumes: Task 6 `list_physical()` / 直接 SQL `WHERE kind IN ('member','standalone')`
- Produces: 响应结构不变（`devices[{name, serial, model, version, rom_version, uptime_days, member_count, ...}]`），`name` 用 `display_name` 规则（1 成员堆叠 → 基础名）

- [ ] **Step 1: 写失败测试**：断言响应行来自成员行——`devices[].name` 含 `-1`/`-2` 且每行 `serial` 是单值；**测试数据里 1 成员堆叠行的 `name` 应是基础名**（`display_name` 规则）。
- [ ] **Step 2: 跑测试确认失败** — Run: `cd backend && python -m pytest tests/test_reports_api.py -q`
- [ ] **Step 3: 实现**：`report_software_versions` 改查物理行（`_expand_device_members` 删除）：

```python
    rows = db.execute(
        """SELECT d.id, d.name, d.kind, d.stack_name, d.member_no, d.serial_number,
                  d.model, d.version, d.location, d.last_synced,
                  c.system_uptime_seconds AS device_uptime_seconds,
                  (SELECT COUNT(*) FROM devices m
                   WHERE m.kind='member' AND m.stack_name = d.stack_name) AS member_count
           FROM devices d
           LEFT JOIN collections c ON c.device_id = d.id
               AND c.id = (SELECT MAX(c2.id) FROM collections c2
                           WHERE c2.device_id = d.id AND c2.phase = '1')
           WHERE d.kind IN ('member', 'standalone')
             AND d.version != '' AND d.version != '未知'
           ORDER BY d.model, d.name""").fetchall()
```

装配时：`display_name` 走 `device_identity.display_name(stack_name, member_no, member_count)`；单机 `member_count=1` → 原名。**`uptime_days` 的成员级回退契约原样保留**（单机回退设备级 uptime；多成员拿不到成员级保持空——成员行的 version 已含成员级版本，uptime 从 `member_uptimes` 拆分迁移进成员行时未迁移，此处若需要成员级 uptime 由 Task 1 迁移回填的 `member_uptimes` 缓存列补齐，行为与现状一致）。
- [ ] **Step 4: 跑测试确认通过** — `cd backend && python -m pytest tests/test_reports_api.py -q`
- [ ] **Step 5: 提交**

```bash
git add backend/api/reports.py backend/tests/test_reports_api.py
git commit -m "软件版本报告：直接读物理成员行，删除展示层展开"
```

---

### Task 10: 生命周期数据层改物理视角 + 保修卡物理名

**Files:**
- Modify: `backend/storage/lifecycle_dal.py:55,59,74,93,98,108`（`list_device_serials`/`overview`/`serial_index` 面向物理行）
- Modify: `frontend/src/components/LifecycleCard.tsx`（每行序列号旁显示物理名）
- Test: `backend/tests/test_lifecycle_dal.py`（追加）

**Interfaces:**
- Consumes: Task 6
- Produces: `get_device_lifecycle(conn, name)` 返回的 `serials` 每项增加 `physical_name` 字段（`display_name` 规则）；`overview()` 面向物理设备逐行（member + standalone）

- [ ] **Step 1-5**：TDD 循环 + `cd backend && python -m pytest tests/test_lifecycle_dal.py tests/test_lifecycle_api.py -q` + `npx tsc --noEmit` + 提交（`git commit -m "生命周期数据层改物理视角，保修卡显示物理名"`）。`extra_rows` 机制（登记过但当前采集不到的 SN 仍显示）必须保持。

---

### Task 11: 拓扑格式统一

**Files:**
- Modify: `backend/api/topology.py:977-1024`（`_expand_physical_devices` 后缀改走 `device_identity.member_suffixes`，回退号从固定两位 `-01` 改为不补零 `-1`；"是否堆叠"判定优先用成员行存在性）
- Modify: `frontend/src/components/topology/PortTopologyCanvas.tsx:266-269,658`（显示标签 `(Member 1)` → `-1`；内部节点 ID `-M1` 不动）
- Test: `backend/tests/test_stp_graph.py` 相邻的拓扑测试（若无则新建 `test_topology_members.py`）

**Interfaces:**
- Consumes: Task 2
- Produces: 多设备拓扑节点 `label = "PVGD1SWI05-1"`（Cisco 回退号不补零）；端口连接图成员标签 `PVGD1SWI05-1`

- [ ] **Step 1: 写失败测试**：`_expand_physical_devices` 对 2 成员 Cisco 堆叠返回 `expanded_name == ["PVGD1SWI05-1", "PVGD1SWI05-2"]`（旧行为是 `-01/-02`）。
- [ ] **Step 2: 跑测试确认失败** — Run: `cd backend && python -m pytest tests/ -q -k "topology or stp"`
- [ ] **Step 3: 实现**（`topology.py:1005-1014` 替换为助手调用）：

```python
        from utils.device_identity import member_suffixes
        suffix_list = member_suffixes(len(sn_list), mid_str)
        for i, s in enumerate(sn_list):
            d = dict(dev)
            d["expanded_name"] = f"{dev['name']}-{suffix_list[i]}"
```
前端 `PortTopologyCanvas.tsx:266-269` 的 `formatMemberLabel` 改为返回 `-N` 形式（`PVGD1SWI01-M1` → `PVGD1SWI01-1`）；`:658` 的 label 模板同步。内部节点 ID `-M${m}`（:456）**不动**（用户不可见，减少改动面）。
- [ ] **Step 4: 验证**：`cd backend && python -m pytest tests/ -q -k "topology or stp"`；`cd frontend && npx tsc --noEmit`
- [ ] **Step 5: 提交**

```bash
git add backend/api/topology.py frontend/src/components/topology/PortTopologyCanvas.tsx backend/tests
git commit -m "拓扑统一物理名 -N：多设备拓扑回退号不补零，端口连接图标签对齐"
```

---

### Task 12: port_snapshots.member_no 落库

**Files:**
- Modify: `backend/services/collector_service.py`（写端口快照处：`member_no_from_port(port_name, platform)`，逻辑口 NULL）
- Modify: `backend/api/topology.py`（端口→成员分配优先用 `member_no` 列，保留名前缀回退）
- Test: `backend/tests/test_port_snapshot_write.py`（追加）

**Interfaces:**
- Consumes: Task 2 `member_no_from_port`
- Produces: `port_snapshots.member_no`（写入；历史回填：迁移不强制，API 查询按"列有值用列、无值回退前缀解析"）

- [ ] **Step 1-5**：TDD 循环 + `cd backend && python -m pytest tests/test_port_snapshot_write.py -q` + 提交（`git commit -m "端口快照落库 member_no，画图/成员端口查询直接化"`）

---

### Task 13: 统计双口径（管理设备 / 物理交换机）

**Files:**
- Modify: `backend/api/stats.py`（概览增加 `managed_count` 与 `physical_count` 两个字段）
- Modify: `frontend/src/pages/Dashboard.tsx`（两个口径分别显示）
- Test: `backend/tests/test_stats_overview.py`（追加断言：managed_count=2, physical_count=3 的夹具）

- [ ] **Step 1: 写失败测试**：夹具 = 1 stack + 2 member + 1 standalone → 断言 `managed_count == 2`、`physical_count == 3`。
- [ ] **Step 2: 跑测试确认失败** — Run: `cd backend && python -m pytest tests/test_stats_overview.py -q`
- [ ] **Step 3: 实现**（`stats.py` 概览端点）：

```python
    managed_count = conn.execute(
        "SELECT COUNT(*) FROM devices WHERE kind IN ('stack','standalone')").fetchone()[0]
    physical_count = conn.execute(
        "SELECT COUNT(*) FROM devices WHERE kind IN ('member','standalone')").fetchone()[0]
```

前端 Dashboard 概览卡显示两个口径（如「管理设备 36 · 物理交换机 49」），i18n 加 key。
- [ ] **Step 4: 验证**：`cd backend && python -m pytest tests/test_stats_overview.py -q`；`cd frontend && npx tsc --noEmit`
- [ ] **Step 5: 提交**

```bash
git add backend/api/stats.py frontend/src/pages/Dashboard.tsx frontend/src/i18n frontend/dist
git commit -m "统计双口径：管理设备与物理交换机分别计数"
```

---

### Task 14: 收尾与验收

**Files:**
- Modify: `.wolf/anatomy.md`、`.wolf/cerebrum.md`（新模块条目 + 本次定案）
- Test: 全量

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest tests/ -q`；`cd frontend && npx tsc --noEmit && npm run build`
Expected: 全绿

- [ ] **Step 2: 验收清单**（对照 spec 第十一节逐条勾）
  1. 物理设备视图（清单/版本报告/拓扑）全部来自成员行，**展示层无展开代码**（grep：`memberSuffixes`、`_expand_device_members` 无生产调用）；
  2. 物理名格式全站一致（抽查：跳号 VSF、Cisco 回退、1 成员）；
  3. 成员增减/更换/整机换代有事件记录（造一次假采集验证）；
  4. 管理设备 36 / 物理交换机 49 两口径可查（生产库实测）；
  5. 采集失败（serial="未知"）不破坏成员行（复现 KORD1SWI02 场景验证）。

- [ ] **Step 3: 文档与狼记**

更新 `.wolf/anatomy.md`（`device_identity.py`、`hardware_change.py` 两个新文件条目）与 `.wolf/cerebrum.md`（Decision Log：身份模型落地；Do-Not-Repeat：已有一条 heredoc 教训，确认在册）。

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "身份模型收尾：验收清单通过，狼记更新"
```

---

## Self-Review 记录（计划自检）

- **Spec 覆盖**：第三节 → T1；第四节 → T2/T3/T11；第五节 → T4/T12；第六节 → T5；第七节 → T8/T9/T10/T13；第八节 → T6/T7；迁移与回滚 → T1；两步实施 → 第二步项（`member_*` 逗号串退役、前端清理残件）已并入 T8/T14，时代分界 UI 归 Plan 2 之后另排。
- **类型一致性**：`member_suffixes(serial_count, member_ids)` 在 T2 定义，T4/T11 消费，签名一致；`compute_fingerprint(platform, model_str, serial_str, kind)` 与 T5 接线一致。
- **已知取舍**：T4 的 kind 判定用 running_config 正则（`vsf member N` / `switch N`）——IOS-XE 堆叠是否有成员表需真机样本验证（spec 第十节），若样本显示无成员表，回退路径为端口名前缀（T2 已提供）。
