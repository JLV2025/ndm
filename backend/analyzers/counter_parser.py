"""端口累计计数器解析器

从三类设备的计数器命令输出中提取端口累计字节数（in/out octets 原始读数），
供「周锚定差值」算法计算区间流量。

| 设备 | 命令 | 解析器 |
|---|---|---|
| Cisco 交换机（2960X / IOS-XE / C9500） | ``show interfaces counters`` | parse_cisco_switch_counters |
| Cisco 路由器 | ``show interfaces stats`` | parse_cisco_router_stats |
| Aruba AOS-CX | ``show interface statistics`` | parse_aruba_counters |

三个解析器输出**统一结构**：``{端口名: {"in_octets": int, "out_octets": int}}``，
端口名一律归一化为缩写形式（见 normalize_port_name），下游不区分平台。

只输出原始读数，不做任何派生计算 —— 区间流量由 API 层按用户选择的时间窗在读时算。

设计要点：
- 计数器命令**自带端口名**，因此流量路径完全不依赖 ``show interface status``，
  「按索引对齐端口」那一整类错位 bug 从根上消失。
- 只保留两张表都出现的端口：缺一侧就无法做差值。
- 读数是 64 位累计字节，直接按字符串转 int，不经过浮点，不丢精度。
"""

import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime

# ============================================================
# 端口名归一化
# ============================================================

# 端口名全称 → 缩写
# 必须区分大小写：SE = Service-Engine，Se = Serial，两者含义不同，
# 统一 upper/lower 会把它们混为一谈。
# 各全称互不为前缀，故匹配顺序无关。
_PORT_ABBREV = (
    ("TenGigabitEthernet", "Te"),
    ("TwentyFiveGigE", "Twe"),
    ("GigabitEthernet", "Gi"),
    ("FastEthernet", "Fa"),
    ("HundredGigE", "Hu"),
    ("FortyGigE", "Fo"),
    ("Service-Engine", "SE"),
    ("Serial", "Se"),
)


def normalize_port_name(name: str) -> str:
    """端口名归一化：全称 → 缩写。已是缩写则原样返回（幂等）。

    例：``GigabitEthernet1/0/1`` → ``Gi1/0/1``、``Service-Engine0/1/0`` → ``SE0/1/0``
    """
    name = (name or "").strip()
    for full, short in _PORT_ABBREV:
        if name.startswith(full):
            return short + name[len(full):]
    return name


# ============================================================
# 排除规则
# ============================================================

# C9500 专用：它的 show interfaces counters 会额外输出逻辑口与堆叠口，必须排除。
#   Po* = port-channel，计数器是成员口的聚合，与成员口同时计入会**重复计数**
#   Hu* = HundredGigE 堆叠口（如 Hu2/0/27），跑的是成员间背板流量，不属于边缘流量
# 全网只有一套 C9500 且今年退休，故硬编码，不做可配置层。
# 2960X / IOS-XE / Aruba 的该命令均只输出物理口，无需排除。
C9500_MODEL_MARKER = "C9500"
C9500_EXCLUDED_PREFIXES = ("Po", "Hu")


def is_excluded_port(name: str, model: str = "") -> bool:
    """端口是否属于需要排除的逻辑口 / 堆叠口（见 C9500_EXCLUDED_PREFIXES）"""
    if C9500_MODEL_MARKER not in (model or "").upper():
        return False
    return name.startswith(C9500_EXCLUDED_PREFIXES)


def is_subinterface(port_name: str) -> bool:
    """是否为子接口（路由器专用，只算父口）

    ``:`` = 串口通道子接口（``Serial0/1/0:0``）
    ``.`` = VLAN 子接口（``GigabitEthernet0/0/0.100``）

    物理口名永不含这两者。
    """
    return ":" in port_name or "." in port_name


# ============================================================
# Cisco 交换机：show interfaces counters
# ============================================================

_CISCO_IN_HEADER = "InOctets"
_CISCO_OUT_HEADER = "OutOctets"


def parse_cisco_switch_counters(raw: str, model: str = "") -> dict:
    """解析 Cisco 交换机 ``show interfaces counters``

    输出为两张定宽表（In / Out），两张表都可能因分屏被拆成多段、**表头重复出现**
    （2960X 实测 In 表头出现 2 次、Out 表头出现 3 次，中间夹空行）。

    用 ``mode`` 记录当前处于哪张表即可天然跳过重复表头 —— 重复表头只会把 mode
    重置为同一个值。这比「统计表头行数」的写法稳，后者在表头重复次数超预期时
    会开始把表头当数据行。

    例::

        Port            InOctets    InUcastPkts    InMcastPkts    InBcastPkts
        Gi1/0/1    1603759403106     2136164393              0        4011728
        ...
        Port           OutOctets   OutUcastPkts   OutMcastPkts   OutBcastPkts
        Gi1/0/1     949050652876     1837049743        3048799        1104308
    """
    if not raw or not raw.strip():
        return {}

    result: dict = {}
    mode = None  # "in" / "out" / None（尚未进入任何一张表）

    for line in raw.splitlines():
        if _CISCO_IN_HEADER in line:
            mode = "in"
            continue
        if _CISCO_OUT_HEADER in line:
            mode = "out"
            continue
        if mode is None:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue
        name, value = parts[0], parts[1]
        if not value.isdigit():
            continue

        name = normalize_port_name(name)
        if is_excluded_port(name, model):
            continue

        result.setdefault(name, {})["in_octets" if mode == "in" else "out_octets"] = int(value)

    # 只保留两张表都出现的端口：缺一侧无法做差值
    return {n: v for n, v in result.items() if "in_octets" in v and "out_octets" in v}


# ============================================================
# Cisco 路由器：show interfaces stats
# ============================================================


def parse_cisco_router_stats(raw: str) -> dict:
    """解析 Cisco 路由器 ``show interfaces stats``

    每个接口一节，节首是**不缩进**的接口全名（如 ``GigabitEthernet0/0/1``），
    节内 ``Total`` 行的 ``Chars In`` / ``Chars Out`` 即累计字节。

    取 ``Total`` 行而不是逐条累加各 switching path —— 已验证 Total 等于各行之和。

    例::

        GigabitEthernet0/0/1
                  Switching path    Pkts In   Chars In   Pkts Out  Chars Out
                       Processor    5791898  373725508     447324  164775405
             Distributed cache    7438944  666209309    2139334  469817868
                           Total   13230842 1039934817    2586658  634593273

    子接口（``Serial0/1/0:N``）只算父口，不在此输出。
    """
    if not raw or not raw.strip():
        return {}

    result: dict = {}
    current = ""

    for line in raw.splitlines():
        if not line.strip():
            continue

        # 节首：不缩进且只有一个 token 的行 = 接口全名
        # （命令回显行如 "BJQD1RTW01#show interfaces stats" 含空格，不会误判）
        if not line[0].isspace() and len(line.split()) == 1:
            current = normalize_port_name(line)
            continue
        if not current:
            continue

        parts = line.split()
        # Total  Pkts In  Chars In  Pkts Out  Chars Out
        if parts[0] != "Total" or len(parts) < 5:
            continue
        if not (parts[2].isdigit() and parts[4].isdigit()):
            continue
        if is_subinterface(current):
            continue

        result[current] = {"in_octets": int(parts[2]), "out_octets": int(parts[4])}

    return result


# ============================================================
# Aruba AOS-CX：show interface statistics
# ============================================================

# AOS-CX 的规范列名，顺序固定。列集随型号 / 版本变化
# （RX Pause / TX Pause 并非所有平台都有），故按表头实际出现的列定位取值下标。
_ARUBA_COLUMNS = (
    "RX Bytes", "RX Packets", "RX Drops",
    "TX Bytes", "TX Packets", "TX Drops",
    "RX Broadcast", "RX Multicast",
    "TX Broadcast", "TX Multicast",
    "RX Pause", "TX Pause",
)

# 物理端口名格式：成员/槽位/端口（如 1/1/1）。lag / vlan 等逻辑口不含此格式。
_ARUBA_PORT_RE = re.compile(r"^\d+(?:/\d+)+$")


def parse_aruba_counters(raw: str) -> dict:
    """解析 Aruba AOS-CX ``show interface statistics``

    单表含 RX / TX 两组列，表头只出现一次。

    **按表头中列名的先后顺序定位取值下标**，不依赖固定列位置 —— 列集随型号 / 版本变化。
    端口名之后只接受整数 token，因此 LAG 成员标注（``1/1/5 - lag1``）会被自然跳过，
    取到的仍是物理口 ``1/1/5``。

    行尾列缺失（终端宽度截断）时按 ``zip`` 截断处理，只要 RX Bytes / TX Bytes 还在
    就能正常取值。

    两个**绝对不能加**的命令修饰参数：
    - ``non-zero``  会过滤掉零流量端口 → 缺基线的端口无法与「端口被拔掉」区分
    - ``human-readable``  会把数值取整成 ``1K``/``2G`` → 破坏计数器精度
    """
    if not raw or not raw.strip():
        return {}

    result: dict = {}
    columns: list = []  # [(列名, 该列名在表头文本中的字符位置)]，按位置升序 = 取值顺序

    for line in raw.splitlines():
        if "Interface" in line and "RX Bytes" in line and "TX Bytes" in line:
            found = [(name, line.find(name)) for name in _ARUBA_COLUMNS]
            columns = sorted((c for c in found if c[1] >= 0), key=lambda c: c[1])
            continue
        if not columns:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        name = parts[0].split("-")[0]  # 兼容 "1/1/5-lag1" 这种无空格写法
        if not _ARUBA_PORT_RE.match(name):
            continue

        values = [int(t) for t in parts[1:] if t.isdigit()]
        row = dict(zip((c[0] for c in columns), values))

        in_octets = row.get("RX Bytes")
        out_octets = row.get("TX Bytes")
        if in_octets is None or out_octets is None:
            continue

        result[name] = {"in_octets": in_octets, "out_octets": out_octets}

    return result


# ============================================================
# 区间流量：按窗口首尾基准求差
# ============================================================

# 区间过短（例如同一分钟内连采两次）时不计算，避免噪声与除零
MIN_SPAN_SEC = 3600


def _field(row, name: str):
    """取字段值：dict / sqlite3.Row / 普通对象都支持"""
    try:
        return row[name]
    except (TypeError, KeyError, IndexError):
        return getattr(row, name, None)


def _as_datetime(value):
    """把 collected_at 归一化为 datetime：接受 datetime 或 ISO 字符串，失败返回 None"""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_int(value):
    """转 int，失败返回 None（None 表示「本轮没采到」，与读数 0 区分）"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compute_week_deltas(baselines, min_span_sec: int = MIN_SPAN_SEC) -> dict:
    """按端口取窗口首尾基准，算区间平均速率

    ``baselines`` 为「窗口内每周最早一次采集」的基准行，每项含
    ``device_id`` / ``port_name`` / ``in_octets`` / ``out_octets`` / ``collected_at``
    （顺序不限；同一端口允许多条，每周一条）。

    因为每周只留**最早**一条基准，取窗口内 ``collected_at`` 最大的那条即是
    「本周最早读数」，所以**同一周内重复调用结果完全相同** —— 这正是周口径锁死。

    返回 ``{(device_id, port_name): {"rx_mbps", "tx_mbps", "span_sec"}}``：

    - 单位 Mbps，``span_sec`` 为两端真实间隔秒数（窗口内有周缺采时会大于名义周数）
    - 计数器重置（``end < start``）→ 该方向为 ``None``，**两方向独立判定**
    - 窗口内只有一条基准（首次出现 / 只有一周有数据）→ 该端口不出现
    - 间隔小于 ``min_span_sec`` → 该端口不出现（不得 ZeroDivisionError）
    - 两个方向都无效的端口不出现

    新端口**不按 0 算**：计数器不是从 0 开始的，一个已跑半年的端口首次被发现时
    可能已有几十上百 GB，按 0 算会造出虚高假峰值直接冲榜首。
    """
    grouped = defaultdict(list)
    for row in baselines:
        ts = _as_datetime(_field(row, "collected_at"))
        if ts is None:
            continue
        grouped[(_field(row, "device_id"), _field(row, "port_name"))].append((ts, row))

    out: dict = {}
    for key, rows in grouped.items():
        if len(rows) < 2:
            continue  # 窗口内没有可比区间

        rows.sort(key=lambda item: item[0])
        (t0, first), (t1, last) = rows[0], rows[-1]

        try:
            span = int((t1 - t0).total_seconds())
        except TypeError:
            continue  # 时区感知与朴素时间混用，无法相减
        if span < min_span_sec:
            continue

        entry: dict = {}
        for field, column in (("rx_mbps", "in_octets"), ("tx_mbps", "out_octets")):
            start = _as_int(_field(first, column))
            end = _as_int(_field(last, column))
            if start is None or end is None or end < start:
                entry[field] = None  # 读数缺失或计数器重置
                continue
            entry[field] = (end - start) * 8 / span / 1e6

        if entry["rx_mbps"] is None and entry["tx_mbps"] is None:
            continue

        entry["span_sec"] = span
        out[key] = entry

    return out
