# 端口流量排行：改用「周锚定」累计计数器差值

> 2026-09-14 起稿，2026-09-15 按真机输出与用户确认的周口径重写

## Context

仪表盘「流量排行 Top10」当前取**设备瞬时速率**（Cisco 的 `5 minute input rate`、Aruba 的 interval 均值，5 分钟窗口）。三个问题：

### 问题 1：采样点太窄，是噪音
每次采集只在那一刻前 5 分钟有一个采样点，而采集间隔实测从 **13 分钟到 21 天**不等。用 5 分钟瞬时值代表一周没有意义。

### 问题 2（严重，正在影响生产）：数据挂在错误的端口上

`show interfaces | include rate|load|packets` 输出**不含端口名**，`_enrich_port_details`（`backend/analyzers/performance.py:546`）只能按**索引**对到 `show interface status` 的端口列表。但两者集合不对等：

```
show interfaces 输出   = 173 块 = 157 物理口（含 6 个 FlexStack 堆叠口）+ 16 个 Vlan SVI
show interface status  = 151 行纯物理口
```

跨 18 台 Cisco 设备核实：**11 台交换机无一幸免**，且缺口在**端口序列中段**（`Gi{x}/0/49-50` 之后紧跟 `Gi2/0/1`），缺口之后整体错位 2~6 位，**每台错位量还不一样**。

实测后果（采集 id=675，2026-09-14，DB 权威数据）：

| 端口 | 链路状态 | DB 显示 | 同日手工 `show int counters` |
|---|---|---|---|
| Gi1/0/20 | `notconnect` 未接线 | rx=4.14 tx=1.71（**排第 1**） | **0 / 0** |
| Gi2/0/16 | `notconnect` | rx=3.44 tx=1.29（第 2） | 0 / 0 |
| Gi1/0/21 | `notconnect` | rx=0.97 tx=3.04（第 3） | 0 / 0 |
| Gi1/0/1 | `connected` (Internet-CNC) | **rx=0.00 tx=0.00** | **1.59 TB / 945 GB**（全设备最忙） |

**151 个端口中 Top10 有 7 个是未接线空口；真正的骨干上行口显示 0。**

### 问题 3：口径不符合业务需求

现有的"瞬时速率"无法回答"这一周哪个口搬的流量最多"。业务上需要的是**周流量**，且一周内稳定可对比。

### 目标

改用**周锚定的累计计数器差值**，同时消除索引对齐这一整类问题。

---

## 一、周口径（用户已确认）

```
上周一 09/07  采集A  计数器 = 1000
上周五 09/11  采集B  计数器 = 1500   ← 周中额外采集
本周一 09/14  采集C  计数器 = 2000
本周二 09/15  采集D  计数器 = 2100
```

**规则：周流量 = 本周最早一次采集的读数 − 上周最早一次采集的读数，一周内锁死不变。**

| 采集 | 显示 | 说明 |
|---|---|---|
| 09/14（本周首次） | 2000 − 1000 = **1000** | 完整一周 |
| 09/15（周中） | 2000 − 1000 = **1000** | **不变** |
| 09/21（下周一） | 2100 → … | 用 09/14 的读数做新基线 |

**为什么基线不能用"上一次采集"**：上周五的采集 B 会把基线推到 1500，本周一算出来只剩 `2000 − 1500 = 500`（3 天），**偏小一半**。所以每周必须保住**最早**那次的读数。

**为什么周中采集不改数值**：周流量是"周"级指标，周中再采多少次都不该改变它。这样排行榜在周内稳定，可直接用于周报对比。

**与"配置/端口状态"的区别**：配置、端口状态等**越新越好，新的覆盖旧的**（现有行为不变）；**只有流量计数器**需要按周锚定保留最早读数。

---

## 二、采集命令（全部经真机输出验证）

样本文件在项目根目录（9 份，覆盖四类设备）：

| 设备 | 端口清单 | 流量计数器 |
|---|---|---|
| Cisco 交换机（2960X / IOS-XE） | `show interface status` | **`show int counters`** |
| Cisco 交换机（**C9500**） | 同上 | `show int counters` **+ 排除规则**（见下） |
| **Cisco 路由器** | **`show interfaces description`** | **`show interfaces stats`** |
| Aruba AOS-CX | **`show interface physical`** | **`show interface statistics`** |

### 关键简化：不需要 join 第二个命令

实测端口集合对齐情况：

| 对比 | 结果 |
|---|---|
| C9500：`status` vs `counters` | **58 = 58，完全相同** |
| 2960X：`status` vs `counters` | 151 vs 152（status 多个 `Fa0` 管理口） |
| Aruba：`physical` vs `statistics` | 52 = 52，完全一致 |

**计数器命令自带端口名且覆盖完整物理端口集合** —— 流量路径**完全不需要第二个命令参与**，索引对齐那一整类 bug 从根上消失。

### Cisco `show int counters`

两张定宽表（In / Out），自带端口名，64 位累计字节：

```
Port            InOctets    InUcastPkts    InMcastPkts    InBcastPkts
Gi1/0/1    1594904759447     2120751313              0        3968992
...
Port           OutOctets   OutUcastPkts   OutMcastPkts   OutBcastPkts
Gi1/0/1     945495499885     1825370617        3016923        1092747
```

**解析坑**：表头行会**重复出现**（2960X 实测 In 1 次、Out 2 次；C9500 实测 In 1 次、Out 2 次）。用 `mode` 变量记录当前处于哪张表即可天然跳过 —— 比 `performance.py:402-425` 的 `header_lines_seen` 计数法更稳（后者在表头重复超预期时会开始把表头当数据行）。

**C9500 排除规则（用户确认）**：C9500 上这条命令会额外输出逻辑/堆叠口，必须排除：

| 前缀 | 是什么 | 为什么必须排除 |
|---|---|---|
| `Po*` | Port-channel | **计数器是成员口的聚合**，实测 `Po1 InOctets = 3.28e13`。包含它会与成员口**重复计数**，让聚合链路流量虚高 |
| `Hu*` | HundredGigE 堆叠口（如 `Hu2/0/27`） | 跑的是**成员间背板流量**，实测 `Hu1/0/27 = 1.37e13`，会霸榜。不属于边缘流量 |

其他 Cisco 交换机与 Aruba **均无此问题**（2960X 的 counters 只有 Gi/Te，Aruba 的 statistics 只有 `成员/槽位/端口`）。

**排除规则直接写死在解析器里，不做可配置机制**（用户确认）：全网只有**一套 C9500，且今年退休**，不值得为它建配置层。硬编码常量即可：

```python
# C9500 专用：这条命令会额外输出逻辑口与堆叠口，必须排除
# 仅 C9500 需要；2960X / IOS-XE / Aruba 均无此问题
C9500_EXCLUDED_PREFIXES = ("Po", "Hu")   # Po=port-channel(与成员口重复计数)  Hu=HundredGigE 堆叠口
```

判断依据用 `device.platform` 或型号字符串（`C9500`）即可，不需要新增设备属性。

**IOS-XE**：`show int counters` **可用**（用户确认）。

### Cisco 路由器 `show interfaces description` + `show interfaces stats`

路由器上 `show interface status` 返回**空**，改用这两条：

`show interfaces description` —— 端口清单（含 Status / Protocol / Description）：
```
Interface                      Status         Protocol Description
Gi0/0/0                        down           down
Gi0/0/1                        up             up       Qorvo-LAN
Te0/0/4                        down           down
SE0/1/0                        up             up
Se0/1/0:0                      down           down
```

`show interfaces stats` —— 每个接口一个块，**取 `Total` 行的 `Chars In` / `Chars Out`**（= 累计字节）：
```
GigabitEthernet0/0/1
          Switching path    Pkts In   Chars In   Pkts Out  Chars Out
               Processor    5791898  373725508     447324  164775405
             Route cache          0          0          0          0
       Distributed cache    7438944  666209309    2139334  469817868
                   Total   13230842 1039934817    2586658  634593273
```

- 取 `Total` 行而非逐条累加（已验证 `Total` = 三行之和）
- 两份输出**各 39 条，1:1 对应**，但**命名不同，必须归一化**：

| `description` | `stats` |
|---|---|
| `Gi0/0/0` | `GigabitEthernet0/0/0` |
| `Te0/0/4` | `TenGigabitEthernet0/0/4` |
| `SE0/1/0` | `Service-Engine0/1/0` |
| `Se0/1/0:0` | `Serial0/1/0:0` |

**注意大小写**：`SE` = Service-Engine，`Se` = Serial，含义不同 —— 映射表**必须区分大小写**，不能统一 upper/lower。

**子接口排除规则（用户确认）**：串口通道子接口（`Se0/1/0:N`，31 个）**不进排行榜，只算父口** `SE0/1/0`。

```python
# 路由器专用：子接口不进排行榜，只算父口
#   ':' = 串口通道（Serial0/1/0:0）
#   '.' = VLAN 子接口（Gi0/0/0.100）
# 物理口名永不含这两者
def is_subinterface(port_name: str) -> bool:
    return ":" in port_name or "." in port_name
```

**该规则对 `show interfaces description` 与 `show interfaces stats` 两侧都要应用** —— 只在一侧过滤会导致两侧端口集合不一致。实测 39 条里 31 条是子接口，过滤后剩 **8 个父口**。

### Aruba `show interface physical` + `show interface statistics`

**端口清单改命令**：当前 `base.py:160` 发的是 `show interface brief`，实测它会把 **lag1/lag2/lag49 + 11 个 vlan 接口**一并列出。改用用户确认的 `show interface physical`，实测为 **52 个纯物理口**（无 lag/vlan）。

```
Port        Type           Link    Admin         Speed           Flow-Control          EEE       PoE Power   ...  Port Description
1/1/1       1GbT           up       up       1G       auto      --       off      off      off      0.00             Internet-In
```

**流量**：`show interface statistics`（设备 **6300M / JL659A，AOS-CX 10.10.1070**），单表含 RX/TX 两组列：
```
Interface      RX Bytes        RX Packets   RX Drops   TX Bytes        TX Packets    TX Drops   RX Broadcast   ...
1/1/1      2962913932240      7212765067          0   2069230696219    6289183603          0        56784466   ...
1/1/5    - lag1   28526668166899 ...（LAG 成员标注）
```

| 验证项 | 结果 |
|---|---|
| 表头重复 | **只出现 1 次**（比 Cisco 简单） |
| 独立 lag/vlan 行 | **没有** |
| LAG 成员标注 | `1/1/5 - lag1`，取 `parts[0]`；**`performance.py:437` 已有处理 `- lagN` 的现成逻辑可复用** |
| 端口名格式 | `成员/槽位/端口` |

**两个绝对不能加的修饰参数**：
- **`non-zero`** —— 实测会过滤掉零流量端口（`1/1` 成员 52 口只出 74 行，缺口 15 个）。后果：缺的端口没有基线；**"本轮无流量"与"端口被拔掉"再也无法区分**；`stats.py:78-86` 的 up/down 计数会跳变
- **`human-readable`** —— 会把数值取整成 `1K`/`345M`/`2G`，破坏计数器精度

**解析要点**：**按表头列名建索引，不按固定列位置** —— 列集随 AOS-CX 版本/平台变化（`RX Pause`/`TX Pause` 并非所有型号都有）。

---

## 三、数据模型

### 新增列（`port_snapshots`）

**绝不修改现有 `rx_mbps`/`tx_mbps` 语义** —— `frontend/src/components/devices/FrontPanel.tsx:27` 写了 `util = total_util_pct ?? (rx_mbps + tx_mbps)`，把 mbps 当百分比用，改语义会让它静默出错。

| 列名 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `in_octets` | INTEGER | NULL | 本次采集读到的累计入向字节（64 位）。NULL = 本轮没采到 |
| `out_octets` | INTEGER | NULL | 同上，出向 |

**只存原始读数，不存任何派生值。** 派生值（周流量、平均速率）由 API 按用户选择的**时间窗**在读时计算。

**为什么不预计算 `week_rx_mbps` 等列**：时间窗是**用户可选**的（近 1 周 / 近 1 个月 / 近 3 个月）。预计算列会把窗口写死，每加一档就要加 3 列 + 改 INSERT + 改迁移。存原始读数则任何窗口都能算，窗口增减是纯前端 + 一个查询参数的事。

**为什么用 NULL 而不是 0**：真实输出里全 0 端口大量存在（如 `Gi1/0/4`），`0` 是合法读数。必须区分「读到 0」和「根本没读到」。

**为什么不建独立的"周基准"表**：周基准是 `port_snapshots` 按周取最早派生的，SQL 一句窗口函数就能得到（见第四节）。多一张表就多一处真相和双写一致性问题，而它并不带来性能收益 —— 数据规模见下。

### 规模核实（读时算可行）

| 项 | 实测值 |
|---|---|
| SQLite 版本 | **3.50.4**，窗口函数（≥3.25）支持 ✓ |
| 设备数 | 36 |
| 最新一轮全设备端口快照 | 2076 行（≈58 口/设备） |
| 8 周窗口去重后的基准行数 | ≈ 2076 × 8 = **约 1.6 万行** |

1.6 万行的分组取首尾在 Python 里是毫秒级。**读时算完全可行**，不需要为性能牺牲灵活性。

### 补索引

```sql
CREATE INDEX IF NOT EXISTS idx_collections_device_id ON collections(device_id, id);
```

### 迁移 `_migrate_v10`

`backend/storage/database.py` 三处改动，缺一不可：

- **(a)** `SCHEMA_VERSION`（14 行）9 → 10
- **(b)** `_migrate_v1` 的 `CREATE TABLE`（251-274 行）追加 2 列（不写 DEFAULT）
- **(c)** 新增 `_migrate_v10` 并注册进 `_MIGRATIONS`（465-475 行），照抄 `_migrate_v5/v6/v7/v8` 的幂等范式：

```python
def _migrate_v10(conn):
    """port_snapshots 增加累计计数器原始读数（周流量的计算来源）"""
    for col, col_type in [("in_octets", "INTEGER"), ("out_octets", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE port_snapshots ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在
    # 「按周取最早基准」查询用
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ports_device_port_collection "
        "ON port_snapshots(device_id, port_name, collection_id)"
    )
```

SQLite 无 DEFAULT 的 `ADD COLUMN` 只改元数据、不重写表，几十万行也是瞬间。

**不回填历史数据** —— 历史行没有计数器原值，任何回填都是编造。

---

## 四、流量算法（读时按窗口计算）

**在 API 层算，不在采集时预计算** —— 因为时间窗是用户可选的（见第七节），预计算会把窗口写死。

### 第一步：SQL 取窗口内每周的基准读数

```sql
WITH weekly AS (
  SELECT ps.device_id, ps.port_name, c.week,
         ps.in_octets, ps.out_octets, c.collected_at, c.id AS cid,
         ROW_NUMBER() OVER (
           PARTITION BY ps.device_id, ps.port_name, c.week
           ORDER BY c.collected_at, c.id          -- 每个 ISO 周取【最早】一次
         ) AS rn
  FROM port_snapshots ps
  JOIN collections c ON c.id = ps.collection_id
  WHERE c.phase = '1'
    AND c.week BETWEEN :week_from AND :week_to     -- week 只用于范围筛选
    AND ps.in_octets IS NOT NULL                   -- 采到才算基准
)
SELECT device_id, port_name, week, in_octets, out_octets, collected_at
FROM weekly WHERE rn = 1
```

**排序用 `collected_at` 而不是 `week` 字符串** —— 实测 week 全部两位补零（`2026-23`…`2026-38`）字符串排序安全，但用真实时间戳更稳，不依赖补零约定。

### 第二步：按端口取窗口首尾（Python）

```
对每个 (device_id, port_name)：
    earliest = 窗口中 collected_at 最小的那条基准
    latest   = 窗口中 collected_at 最大的那条基准

    若只有一条基准              → NULL（窗口内没有可比区间）
    Δt = latest.at − earliest.at
    若 Δt <= 0 或 Δt < MIN_SPAN_SEC → NULL
    Δin = latest.in − earliest.in ;  Δout 同理
    若 Δin < 0 或 Δout < 0      → NULL（计数器重置）    【两方向独立判定】
    rx_mbps = Δin × 8 ÷ Δt ÷ 1e6 ;  tx_mbps 同理
    span_sec = Δt
```

### 为什么「一周内锁死」自动成立

`latest` 取的是**当前 ISO 周最早**那次采集，不是"本次采集"。所以本周第 2、3 次采集算出的值与第 1 次**完全相同** —— 这正是已确认的周口径。周中再多采几次，排行榜纹丝不动。

### 窗口的界定

- `week_to` = 当前 ISO 周（`datetime.now().isocalendar()`）
- `week_from` = 当前 ISO 周 − N（N 由前端选择器传入）
- 窗口内某周没有基准（采集失败）→ **自动跳过**，用实际存在的首尾。`span_sec` 会略大于名义周数，UI 用它说明"过去 X 天"

### 边界处理

**计数器重置**：设备重启 / 人工 `clear counters` / 端口 flap 都会让读数变小 → 窗口整体判为无效。`in_octets`/`out_octets` 照常入库，下个窗口自动恢复。

> 已知局限：若重置发生在**窗口中间**，整个窗口会被判无效，即便重置前后各有一段有效数据。改进方向是"重置后重新起算"，属可选优化，先不做（重置是低频事件）。

**为什么新端口不能按 0 算**：端口计数器不是从 0 开始的。一个接服务器、已跑半年的口，第一次被发现时可能已有几十上百 GB，按 0 算会造出虚高假峰值直接冲榜首。首次出现 → `NULL`。

**`MIN_SPAN_SEC`**：暂定 3600 秒，防止异常窗口。

---

## 五、解析器组织

**新文件 `backend/analyzers/counter_parser.py`** —— 纯函数、零依赖，对标已有的 `neighbor_parser.py`。不放 `performance.py`（已 586 行且职责混杂）。

```python
def parse_cisco_switch_counters(raw) -> {端口名: {"in_octets": int, "out_octets": int}}   # show int counters
def parse_cisco_router_stats(raw)   -> {端口名: {"in_octets": int, "out_octets": int}}   # show interfaces stats
def parse_aruba_counters(raw)       -> {端口名: {"in_octets": int, "out_octets": int}}   # show interface statistics

def normalize_port_name(name) -> str   # 全称→缩写：GigabitEthernet1/0/1 → Gi1/0/1
def is_excluded_port(name) -> bool     # Po*/Hu* 排除规则（可配置）

def compute_week_deltas(...) -> {...}  # 周差值，纯函数便于单测
```

三个平台解析器输出**统一结构** `{端口名: {"in_octets": int, "out_octets": int}}`，下游（差值算法、DB、API、前端）**完全不区分平台**。

**`normalize_port_name` 必须有且区分大小写**（路由器 `SE`=Service-Engine vs `Se`=Serial）：

| 全称 | 缩写 |
|---|---|
| `GigabitEthernet` | `Gi` |
| `TenGigabitEthernet` | `Te` |
| `Serial` | `Se` |
| `Service-Engine` | `SE` |
| `TwentyFiveGigE` | `Twe` |
| `HundredGigE` | `Hu` |
| `FastEthernet` | `Fa` |

---

## 六、接线

**`backend/collectors/base.py`**：
- 新增 `collect_interface_counters()`：
  - `cisco_ios` / `cisco_ios_xe` → `show int counters`
  - `cisco_ios_router` → `show interfaces stats`
  - `aruba_aoscx` → `show interface statistics`
- 新增 `collect_interface_description()`：仅 `cisco_ios_router` 用 `show interfaces description`
- **改** `collect_interface_status()`（`base.py:160`）Aruba 分支：`show interface brief` → **`show interface physical`**
  - **注意**：换命令后 Aruba 的 status 解析列偏移可能变化（现有解析依赖 `brief` 的 `Port / Native VLAN / Mode / Type / Enabled / Status / Speed / Description` 布局），需一并核对 `performance.py` 的 Aruba 分支并用样本文件重新验证

`terminal length 0` 已在 `base.py:94` 会话级下发。

**`backend/analyzers/performance.py`**：
- ctor 加可选参数 `counters_raw=""`、`description_raw=""`（默认值保证现有调用点不破）
- 新增 `_analyze_counters()`，按 device_type 分派
- `_enrich_port_details` 在现有索引逻辑**之后**追加**按名字**合并 —— 这是修正"数据落在错误端口"的关键。老的 `_cisco_block_{i}` 通路保持原样（瞬时值语义不动）

**`backend/services/collector_service.py`**：
- 加采集命令调用 + `total_cmds` 调整
- `_save_to_sqlite` 里算周差值；`rows.append` 与 INSERT 从 19 列扩到 24 列
- **计数器列不要过 `_safe_str`**（会把 `None` 变 `""`）

---

## 七、API 与前端

### API：`/api/stats/overview` 增加 `window` 参数

```
GET /api/stats/overview?window=1     # 近 1 周（默认）
GET /api/stats/overview?window=4     # 近 1 个月
GET /api/stats/overview?window=13    # 近 3 个月
```

- `window` **白名单校验**：`1 / 4 / 13`（周），非法值回落 1
  - `1` = 近 1 周 · `4` = 近 1 个月（28 天）· `13` = 近 3 个月（91 天）
- 按第四节两步算法得到每端口的 `rx_mbps` / `tx_mbps` / `span_sec`
- 排序取 Top10：**`is_uplink DESC, (rx_mbps + tx_mbps) DESC`**
  - 上行口优先，不足 10 条时用普通端口补齐 —— **这是用户确认的预期行为**：目的就是"知道哪些端口流量大"，不该因为上行口只有 4 个就只显示 4 条
  - 后续可扩展：**每台设备各自一个 Top10**（用户提出，不在本次范围）
- 响应逐条带 `rx_mbps` / `tx_mbps` / `span_sec` / `window`

**过渡期显示空白，不做回退（用户确认）**：若窗口内没有任何端口有有效值，排行榜显示空态提示。**不回退到旧的瞬时口径** —— 那批数据正是已知错位的数据，展示它等于把 bug 留在台面上。

因为不做回退，响应**不需要 `source` 字段**，前端也没有"按来源分支取值"的逻辑。

**为什么窗口越长时间越"准"**：计数器差值本身是精确的，但它是"该端口的**典型负载**"的估计。1 周窗口容易被单个异常周带偏（假期、备份周）；**近 1 个月 / 近 3 个月档**把周内波动平均掉，更接近端口的稳态负载。这是给选择器的实际价值。

**`data.py` / `reports.py` 本次不改** —— 它们读的 `rx_mbps/tx_mbps` 语义不变。

### 前端：窗口选择器

`frontend/src/pages/Dashboard.tsx`（`top_traffic` 全仓库只有这一个消费点）：

1. **标题栏加选择器**（MUI `Select` 或 `ToggleButtonGroup`），紧挨 `dashboard.chartTrafficRank` 标题：

```
流量排行 Top 10    [近 1 周 ▾]        ← 近1周 / 近1个月 / 近3个月
```

2. `window` 存入 state，变化时重新 `fetch('/api/stats/overview?window=N')`
3. 类型加 `rx_mbps` / `tx_mbps` / `span_sec` / `window` / `source`
4. 图表映射：直接用 `rx_mbps` / `tx_mbps`。`<Bar dataKey="rx"/tx>` 不改
5. tooltip 加 `formatter`，数值后附实际区间长度（`fmtDuration(span_sec)` → `7 天` / `21 天`）
6. `trafficChartData.length === 0` 时显示空态

### i18n（`zh.ts` + `en.ts` 成对新增）

| key | zh | en |
|---|---|---|
| `dashboard.trafficWindow` | `统计区间` | `Window` |
| `dashboard.trafficWindow1` | `近 1 周` | `Last week` |
| `dashboard.trafficWindow4` | `近 1 个月` | `Last month` |
| `dashboard.trafficWindow13` | `近 3 个月` | `Last 3 months` |
| `dashboard.trafficNoData` | `暂无区间流量数据（需至少两次跨周采集）` | `No interval data yet` |
| `dashboard.trafficIntervalAvg` | `{span}区间平均` | `Average over {span}` |
| `dashboard.trafficNeedTwoCollections` | `需至少两次采集后才能计算区间流量` | `Requires at least two collections` |
| `common.days` | `天` | `d` |

**注意** `frontend/src/i18n/index.tsx:6` 的 `TFunc` **不支持插值**，沿用项目已有的 `.replace('{xxx}', ...)` 写法（见 `DeviceDetail.tsx:483`）。

---

## 八、建议一并修复瞬时速率路径（同根因，可解耦单独提交）

索引错位不只污染排行榜 —— **Cisco 的瞬时 `rx_mbps`/`tx_mbps` 本身也是错位的**，而 `FrontPanel.tsx:27` 用它当利用率百分比、以 80 为阈值变色。**前端端口面板的告警颜色当前也是错的。**

修法与计数器无关：把 Cisco 利用率命令从

```
show interfaces | include rate|load|packets     # 输出无端口名
```
改为
```
show interfaces | include ^[A-Za-z]|rate|bytes  # 第0列 = 接口名行
```

已用真实 raw 文件逐行验证：接口名行在第 0 列，其余行都有前导空格，`^[A-Za-z]` 只捞接口名行。解析改为按名匹配后，`_enrich_port_details` 的索引对齐即可弃用。

---

## 九、测试

**新建 `backend/tests/test_counter_parser.py`**。fixture **直接读 `backend/tests/fixtures/` 下的 9 份真机输出**（不内联）：

| fixture | 来源 |
|---|---|
| Cisco 交换机 counters | `Cisco 2960x show interfaces counters.txt`、`Cisco 9500 show interfaces counters.txt` |
| Cisco 路由器 stats | `Cisco router show interfaces stats.txt` + `Cisco Router show interfaces descript.txt` |
| Aruba statistics | `Aruba show interface statisti.txt` + `Aruba show interface physical.txt` |

**必须覆盖的特征**：**重复表头**（Cisco 两表各 ≥2 次，中间夹空行）、**C9500 的 `Po1`/`Hu*` 必须被排除**、全 0 端口得 `0` 而非 None、大数值不丢精度、`% Invalid input` → `{}`、空输入 → `{}`、只有 In 表 → `{}`、只在一个表出现的端口不输出、`\r\n` 行尾。

**命名归一化用例**：`GigabitEthernet1/0/1`→`Gi1/0/1`、`Service-Engine0/1/0`→`SE0/1/0`、`Serial0/1/0:0`→`Se0/1/0:0`（**验证 SE/Se 不被混同**）。

**窗口算法用例**（纯函数，手写基准序列，不依赖采集）：

| 用例 | 断言 |
|---|---|
| `window=1` 基本 | 本周最早 − 上周最早 |
| **周中第二次采集结果与第一次完全相同** | **核心断言** —— 周口径锁死的唯一保证 |
| 上周五多采一次 | 结果不变（基线取上周**最早**，不是最后一次） |
| `window=4` | 本周最早 − 4 周前最早（近 1 个月档） |
| `window=13` | 本周最早 − 13 周前最早（近 3 个月档） |
| 窗口内某周缺采 | 用实际存在的首尾，`span_sec` 相应变大 |
| 窗口内只有一条基准 | → NULL |
| 首次出现（窗口内无历史） | → NULL |
| 计数器重置（latest < earliest） | → NULL |
| 单方向重置 | 该方向 NULL，另一方向仍有值 |
| `Δt < MIN_SPAN_SEC` | → NULL（**不得 ZeroDivisionError**） |

**迁移测试**：临时库跑两次 `_migrate_v10`，断言幂等且 `PRAGMA table_info` 含 5 个新列。

---

## 十、验证方法

1. **解析器离线验证（不需要设备）**：对 9 份样本文件跑解析器，断言端口数与集合、排除规则生效、值与文件逐行吻合。
2. **端到端**：对 `SZXD1SWI01`（Cisco 交换机）、`BJQD1SWI01`（Aruba）、`BJQD1RTW01`（路由器）各连采两次，确认第二次 `week_*` 有值。
3. **周口径验证**（核心）：同周内连采三次，确认三次请求 `window=1` 得到的排行榜**完全相同**。
4. **窗口切换 + 错位消除验证**：`window=13` 与 `window=1` 数值不同、且换榜更少（单周异常被平均掉）；排行榜端口用 `status` 交叉核对，**不应再出现 `notconnect`**，且真实的骨干上行口（如 `Gi1/0/1` Internet-CNC）应在榜上。
5. **现有功能不受影响**：`FrontPanel` 利用率百分比、`Reports` 带宽汇总、告警页仍正常。
6. **迁移前备份** `data/ndm.db`。

---

## 十一、待确认事项

已解决：

1. ~~C9500 排除规则~~ —— 写死 `Po*`/`Hu*`，不做配置层（全网一套且今年退休）
2. ~~窗口档位~~ —— **3 档：`1 / 4 / 13` 周**（近 1 周 / 近 1 个月 / 近 3 个月）
3. ~~路由器子接口~~ —— **只算父口**，排除含 `:` 或 `.` 的子接口（39 条 → 8 个父口）

已解决：

1. ~~C9500 排除规则~~ —— 写死 `Po*`/`Hu*`，不做配置层（全网一套且今年退休）
2. ~~窗口档位~~ —— **3 档：`1 / 4 / 13` 周**（近 1 周 / 近 1 个月 / 近 3 个月）
3. ~~路由器子接口~~ —— **只算父口**，排除含 `:` 或 `.` 的子接口（39 条 → 8 个父口）
4. ~~过渡期口径~~ —— **显示空白**，不回退旧瞬时口径
5. ~~`is_uplink` 排序~~ —— 保留 `is_uplink DESC`，普通端口补齐 Top10 是预期行为
6. ~~Aruba status 核对~~ —— 同意核对，实现时用样本文件验证

待处理：

7. **`MIN_SPAN_SEC` 取值**（暂定 3600 秒）。
8. ~~数据保留策略与 13 周窗口冲突~~ —— **已解决**，见「十一之二」的分层保留规则。

---

## 十一之二、数据保留与归档（用户已确认）

**现状**：`config/settings.yaml` 配了 `max_versions: 10`，但 `keep_latest_versions_per_device` / `cleanup_old_versions`（`backend/storage/file_manager.py:33/76`）**全仓库零调用点** —— 从未生效。实际 DB 16 周（2026-23~2026-38）、设备周目录 13~14 个。

**存储压力实测（确认"压力不大"）**：

| 项 | 每周 | 每年 |
|---|---|---|
| `collections.running_config`（34.4 KB/份） | ~1.5 MB | ~76 MB |
| `device_logs`（72,162 行） | ~0.9 MB | ~47 MB |
| `port_snapshots`（39,147 行） | ~0.24 MB | ~13 MB |
| **合计** | | **~140 MB/年** |

**所以归档的动机是可查看性，不是省空间** —— 设计取向是"能不删就不删，只把粒度放粗"。

### 分层保留规则

| 对象 | 位置 | 规则 |
|---|---|---|
| **配置文本文件** | `data/{设备}/{YYYY-WW}/running-config.raw` | 最近 **16 周**按周保留；更早的**按月收缩** —— 该月**最后一个**版本移入月目录，该月其余版本删除 |
| **月归档目录** | `data/{设备}/archive/{YYYY}-M{MM}/running-config.raw` | 例 `2026-M09`。`archive/` 前缀 + `M` 标识**双重隔离**，避免被周目录逻辑误读 |
| **DB `collections.running_config`** | DB 列 | 只留最近 **2 次**采集的全文，更早的置 NULL |
| **DB `device_logs`** | DB 表 | 只留最近 **2 次**采集的日志 |
| `port_snapshots` / `neighbors` / `collections` 其余列 | DB | 保留 **16 周**（13 周窗口 + 余量） |
| `config_changes` / `validation_results` / `alerts` | DB | 保留（是结果不是原文，量小） |

**为什么 DB 配置只留 2 次**：变更检测（`config_changes`）只用"上一次采集"的 config，2 次足够；且按**记录数**而非时间，不受采集间隔不均影响。

**为什么周数不一致（16 周 vs 2 次）**：流量窗口需要 13 周的历史计数器，所以 `port_snapshots` 要留 16 周；配置全文只在对比时用一次，留 2 次即可。两者目的不同，不必强行统一。

**"取月末"与流量"取周初"方向相反但都对**：配置是**状态快照**，月末那份最能代表该月状态；流量是**累计值**，需要最早作基线。不是矛盾。

### 三条关键约束

1. **周目录识别必须用严格正则 `^\d{4}-\d{2}$`** —— 否则 `2026-M09` 可能被当作周目录参与清理
2. **归档是不可逆删除** —— 该月非末周的配置会被**永久删除**。实现时必须提供 `--dry-run`，先在真库上列出将删除的清单再执行
3. **归档在采集时触发** —— 每次采集后检查，但只有确实存在 >16 周的周目录时才执行动作（检查是列目录级别，代价可忽略）

> 注意：`utils/storage.py`（README/CLAUDE.md 提到的路径）与 `backend/storage/file_manager.py`（实际实现）**不是同一处**，实现时别改错文件。
>
> `max_versions` 配置项由本方案取代（语义从"周数"变成分层规则），实施时同步更新注释或移除。

---

## 十一之三、邻接数据现状（与本次任务无关，供参考）

用户问到邻居关系是否落在逻辑端口上。核实结论：

**有，共 272 条**，且已用 `neighbors.is_logical` 标记，无漏网（未标记的行里没有 lag/Po/Vlan 命名的）。

**但存在重复记录与写法不统一**。`KR3D1SWI01` 最新一次采集里，到同一邻居 `KR3R1SWI01` 有 **3 条**：

```
Gi1/1/2  [cdp] -> KR3R1SWI01   is_logical=0   ← 物理成员口
Po1      [cdp] -> KR3R1SWI01   is_logical=1   ← 逻辑口
po 1     [cdp] -> KR3R1SWI01   is_logical=1   ← 同一个口，另一种写法
```

`local_port` 写法混用：`Po1` / `po 1` / `lag 1` / `lag1`（Cisco 用 `Po`，Aruba 用 `lag`，空格与大小写不一致）。拓扑图上会**重复画线**。

**结论**：`is_logical` 标记本身是可靠的，问题在 `local_port` 未归一化。属既有问题，**不在本次流量改造范围**，建议单独开单。

---

## 十二、实施顺序

**Phase A —— 现在就能做，不依赖任何设备确认**

| 步骤 | 产出 |
|---|---|
| A1 | `backend/analyzers/counter_parser.py` —— 三个平台解析器 + 归一化 + 排除规则（**格式均已用真机输出确认**） |
| A2 | `backend/tests/test_counter_parser.py`（9 份样本文件作 fixture） |
| A3 | `database.py` v10 迁移 |
| A4 | `base.py` 三个采集方法 + Aruba status 改 `show interface physical` |
| A5 | `performance.py` 接线 |
| A6 | `collector_service.py` 接线（命令 + `total_cmds` + INSERT 从 19 列扩到 **21 列**）。**不做任何派生计算** —— 只写原始读数 |
| A7 | `stats.py`：`window` 参数 + 两步窗口算法 + Top10 |
| A8 | 前端 `Dashboard.tsx` + 窗口选择器 + 类型 + i18n |
| A9 | **保留与归档**：分层规则 + 严格正则识别周目录 + `--dry-run` + 采集时触发（与 A5~A8 互不依赖，可并行） |
| A10 | 端到端验证（三类设备） |

A1~A4 互不依赖可并行。A1/A2 风险最低，最先落地。

**Phase B —— 待确认后处理**：上述「待确认事项」1、2、3、6 均只影响单个解析分支或常量，改动隔离。

---

## 附：样本文件清单

已归置到 **`backend/tests/fixtures/`**（9 份，共约 90 KB）：

```
backend/tests/fixtures/
├── Cisco 9500 show interfaces status.txt
├── Cisco 9500 show interfaces counters.txt
├── Cisco 2960x show interfaces status.txt
├── Cisco 2960x show interfaces counters.txt
├── Cisco Router show interfaces descript.txt
├── Cisco router show interfaces stats.txt
├── Aruba show interface physical.txt
├── Aruba show interface utilizat.txt
└── Aruba show interface statisti.txt
```

**注意**：`.gitignore:69` 有 `*.txt`，这些样本**当前未被 git 跟踪**。它们**不可复现**（需要真机才能再采），建议给 `backend/tests/fixtures/*.txt` 加一条 `!` 例外纳入版本控制 —— 否则 A2 的测试换台机器就跑不了。

A2 **直接读这些文件**构造 fixture，不要内联几百行进测试代码。
