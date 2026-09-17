"""端口累计计数器解析器测试

fixture 直接读 tests/fixtures/ 下的真机输出文件（不内联），
文件不可复现（需连真机再采），故不修改。
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from analyzers.counter_parser import (
    MIN_SPAN_SEC,
    compute_week_deltas,
    is_excluded_port,
    is_subinterface,
    normalize_port_name,
    parse_aruba_counters,
    parse_cisco_router_stats,
    parse_cisco_switch_counters,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


# 真机样本文件（backend/tests/fixtures/）
CISCO_2960X_COUNTERS = "Cisco 2960x show interfaces counters.txt"
CISCO_9500_COUNTERS = "Cisco 9500 show interfaces counters.txt"
CISCO_ROUTER_STATS = "Cisco router show interfaces stats.txt"
ARUBA_STATISTICS = "Aruba show interface statisti.txt"

C9500_MODEL = "C9500-40X"


# ============================================================
# 端口名归一化
# ============================================================

@pytest.mark.parametrize("full, short", [
    ("GigabitEthernet1/0/1", "Gi1/0/1"),
    ("TenGigabitEthernet0/0/4", "Te0/0/4"),
    ("TwentyFiveGigE1/0/1", "Twe1/0/1"),
    ("HundredGigE2/0/27", "Hu2/0/27"),
    ("FastEthernet0/1", "Fa0/1"),
    ("FortyGigE1/1/1", "Fo1/1/1"),
    ("Loopback1", "Lo1"),
    ("Tunnel0", "Tu0"),
])
def test_归一化_全称转缩写(full, short):
    assert normalize_port_name(full) == short


def test_归一化_Loopback两侧命名必须折到一致():
    """真机实测（ISR 2921/2951）：show interfaces description 给 Lo1，
    show interfaces stats 给 Loopback1 —— 不归一化会出现两个条目，
    一个有状态没流量、一个有流量没状态。"""
    assert normalize_port_name("Loopback1") == normalize_port_name("Lo1") == "Lo1"


def test_归一化_SE与Se不能被混同():
    """SE = Service-Engine，Se = Serial，大小写含义不同"""
    assert normalize_port_name("Service-Engine0/1/0") == "SE0/1/0"
    assert normalize_port_name("Serial0/1/0") == "Se0/1/0"

    # 归一化结果再归一化不得互相串味（幂等）
    assert normalize_port_name("SE0/1/0") == "SE0/1/0"
    assert normalize_port_name("Se0/1/0:0") == "Se0/1/0:0"


def test_归一化_已是缩写则原样返回():
    for name in ("Gi1/0/1", "Te3/0/2", "Po1", "1/1/1", "Twe2/0/24"):
        assert normalize_port_name(name) == name


# ============================================================
# 排除规则
# ============================================================

def test_子接口判定():
    assert is_subinterface("Se0/1/0:0")      # 串口通道
    assert is_subinterface("Gi0/0/0.100")    # VLAN 子接口
    assert not is_subinterface("Se0/1/0")    # 父口
    assert not is_subinterface("Gi1/0/1")


def test_排除规则_Po全平台排除_Hu仅C9500():
    # port-channel 是逻辑口，任何 Cisco 平台都排除（计数器是成员口聚合，重复计入会翻倍）
    assert is_excluded_port("Po1", C9500_MODEL)
    assert is_excluded_port("Po1", "WS-C2960X-48FPD-L")
    assert is_excluded_port("Po1", "")
    assert is_excluded_port("Port-channel1", "")

    # Hu（100G 堆叠口）只在 C9500 上按堆叠口排除；其他平台的 Hu 是真实物理口
    assert is_excluded_port("Hu1/0/27", C9500_MODEL)
    assert not is_excluded_port("Hu1/0/27", "WS-C2960X-48FPD-L")
    assert not is_excluded_port("Hu1/0/27", "")

    # 普通物理口任何型号都不排除
    assert not is_excluded_port("Twe1/0/1", C9500_MODEL)


# ============================================================
# Cisco 交换机 show interfaces counters
# ============================================================

def test_交换机_解析真机样本_2960X():
    counters = parse_cisco_switch_counters(read_fixture(CISCO_2960X_COUNTERS))

    assert len(counters) == 150
    assert counters["Gi1/0/1"] == {"in_octets": 1603759403106, "out_octets": 949050652876}
    # 全 0 端口得 0，而不是缺失
    assert counters["Gi3/0/48"] == {"in_octets": 0, "out_octets": 0}
    # 只有 Gi/Te 物理口
    assert all(n.startswith(("Gi", "Te")) for n in counters)


def test_交换机_解析真机样本_9500_排除逻辑口与堆叠口():
    counters = parse_cisco_switch_counters(read_fixture(CISCO_9500_COUNTERS), C9500_MODEL)

    assert len(counters) == 48
    assert not [n for n in counters if n.startswith("Po")]
    assert not [n for n in counters if n.startswith("Hu")]
    # 大数值（约 16 TB）不丢精度
    assert counters["Twe1/0/2"] == {"in_octets": 16101977364549, "out_octets": 9422674234620}


def test_交换机_非C9500型号只排除Po():
    """Po 全平台排除；Hu 只有在 C9500 上才是堆叠口，换个型号就是真实物理口，须保留"""
    counters = parse_cisco_switch_counters(read_fixture(CISCO_9500_COUNTERS), "WS-C2960X")
    assert len(counters) == 56
    assert "Po1" not in counters
    assert "Hu1/0/27" in counters


def test_交换机_重复表头不干扰取值():
    """2960X 的 In 表头出现 2 次、Out 表头出现 3 次（分屏拆分），值必须仍是 In 归 In"""
    raw = read_fixture(CISCO_2960X_COUNTERS)
    assert raw.count("InOctets") == 2 and raw.count("OutOctets") == 3

    counters = parse_cisco_switch_counters(raw)
    # In / Out 取自各自的表，没有被后出现的表覆盖
    assert counters["Gi1/0/1"]["in_octets"] == 1603759403106
    assert counters["Gi1/0/1"]["out_octets"] == 949050652876


def test_交换机_CRLF行尾():
    raw = (
        "SW#show interfaces counters\r\n"
        "\r\n"
        "Port            InOctets    InUcastPkts\r\n"
        "Gi1/0/1    1603759403106     2136164393\r\n"
        "\r\n"
        "Port           OutOctets   OutUcastPkts\r\n"
        "Gi1/0/1     949050652876     1837049743\r\n"
    )
    assert parse_cisco_switch_counters(raw) == {
        "Gi1/0/1": {"in_octets": 1603759403106, "out_octets": 949050652876}
    }


def test_交换机_只有In表则不出结果():
    """缺一侧无法做差值，该端口不输出"""
    raw = (
        "Port            InOctets    InUcastPkts\n"
        "Gi1/0/1    1603759403106     2136164393\n"
    )
    assert parse_cisco_switch_counters(raw) == {}


def test_交换机_只在一张表出现的端口不输出():
    raw = (
        "Port            InOctets    InUcastPkts\n"
        "Gi1/0/1    1603759403106     2136164393\n"
        "Gi1/0/2     375928042569      808262563\n"
        "Port           OutOctets   OutUcastPkts\n"
        "Gi1/0/1     949050652876     1837049743\n"
    )
    counters = parse_cisco_switch_counters(raw)
    assert set(counters) == {"Gi1/0/1"}


@pytest.mark.parametrize("raw", ["", "   \n  ", "% Invalid input detected at '^' marker."])
def test_交换机_空输入与命令报错返回空字典(raw):
    assert parse_cisco_switch_counters(raw) == {}


# ============================================================
# Cisco 路由器 show interfaces stats
# ============================================================

def test_路由器_解析真机样本():
    stats = parse_cisco_router_stats(read_fixture(CISCO_ROUTER_STATS))

    # 38 个接口节里 31 个是 Se0/1/0:N 子接口，过滤后剩 7 个父口
    assert len(stats) == 7
    assert set(stats) == {"Gi0/0/0", "Gi0/0/1", "Gi0/0/2", "Gi0/0/3", "Te0/0/4", "Te0/0/5", "SE0/1/0"}

    # 取 Total 行（Total = 各 switching path 之和），不是逐行累加
    assert stats["Gi0/0/1"] == {"in_octets": 1039934817, "out_octets": 634593273}
    # 只有出向有流量
    assert stats["SE0/1/0"] == {"in_octets": 0, "out_octets": 109133664}


def test_路由器_归一化后与description侧端口集合一致():
    """两侧必须用同一套归一化 + 同一套子接口过滤，否则端口集合会对不上"""
    from_desc = set()
    for line in read_fixture("Cisco Router show interfaces descript.txt").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3 or parts[0] == "Interface":
            continue
        name = normalize_port_name(parts[0])
        if not is_subinterface(name):
            from_desc.add(name)

    assert from_desc == set(parse_cisco_router_stats(read_fixture(CISCO_ROUTER_STATS)))


@pytest.mark.parametrize("raw", ["", "   \n  ", "% Invalid input detected at '^' marker."])
def test_路由器_空输入与命令报错返回空字典(raw):
    assert parse_cisco_router_stats(raw) == {}


# ============================================================
# Aruba show interface statistics
# ============================================================

def test_Aruba_解析真机样本():
    counters = parse_aruba_counters(read_fixture(ARUBA_STATISTICS))

    assert len(counters) == 52
    assert counters["1/1/1"] == {"in_octets": 2962913932240, "out_octets": 2069230696219}
    assert counters["1/1/52"] == {"in_octets": 0, "out_octets": 0}


def test_Aruba_全零端口得0而非缺失():
    assert parse_aruba_counters(read_fixture(ARUBA_STATISTICS))["1/1/49"] == \
        {"in_octets": 0, "out_octets": 0}


def test_Aruba_行尾列缺失仍能取值():
    """行的尾部列若缺失，只要 RX Bytes / TX Bytes 还在就能取到值"""
    raw = (
        "Interface      RX Bytes   RX Packets   TX Bytes   TX Packets   TX Drops\n"
        "1/1/1           1000000          500     2000000         800        12\n"
        "1/1/2           3000000          600     4000000         900\n"      # 尾部少一列
    )
    assert parse_aruba_counters(raw)["1/1/2"] == {"in_octets": 3000000, "out_octets": 4000000}


def test_Aruba_按表头列名定位而非固定列位置():
    """列集随型号/版本变化（RX Pause / TX Pause 并非所有平台都有）"""
    raw = (
        "Interface      RX Bytes   RX Packets   TX Bytes   TX Packets\n"
        "1/1/1        1000000          500       2000000         800\n"
    )
    assert parse_aruba_counters(raw) == {
        "1/1/1": {"in_octets": 1000000, "out_octets": 2000000}
    }


def test_Aruba_LAG成员标注不干扰():
    """形如 '1/1/5 - lag1' / '1/1/5-lag1' 的行，取的仍是物理口 1/1/5"""
    raw = (
        "Interface      RX Bytes   TX Bytes\n"
        "1/1/5 - lag1    1000000    2000000\n"
    )
    assert parse_aruba_counters(raw) == {"1/1/5": {"in_octets": 1000000, "out_octets": 2000000}}


def test_Aruba_逻辑口行被跳过():
    raw = (
        "Interface      RX Bytes   TX Bytes\n"
        "lag1            1000000    2000000\n"
        "vlan10           500000     600000\n"
        "1/1/1            1000000    2000000\n"
    )
    assert set(parse_aruba_counters(raw)) == {"1/1/1"}


@pytest.mark.parametrize("raw", ["", "   \n  ", "% Invalid input detected at '^' marker."])
def test_Aruba_空输入与命令报错返回空字典(raw):
    assert parse_aruba_counters(raw) == {}


# ============================================================
# 区间流量（周锚定差值）
# ============================================================

T0 = datetime(2026, 9, 7, 9, 0, 0)   # 上周一
WEEK = timedelta(days=7)


def baseline(weeks_ago: int, in_octets: int, out_octets: int, *, device="D1", port="Gi1/0/1"):
    """构造一条周基准读数：weeks_ago=0 表示本周"""
    return {
        "device_id": device,
        "port_name": port,
        "in_octets": in_octets,
        "out_octets": out_octets,
        "collected_at": T0 + (1 - weeks_ago) * WEEK,
    }


def test_区间流量_基本一周():
    rows = [baseline(1, 0, 0), baseline(0, 1000, 2000)]
    result = compute_week_deltas(rows)

    entry = result[("D1", "Gi1/0/1")]
    assert entry["span_sec"] == 7 * 86400
    # 1000 字节 / 7 天
    assert entry["rx_mbps"] == pytest.approx(1000 * 8 / (7 * 86400) / 1e6)
    assert entry["tx_mbps"] == pytest.approx(2000 * 8 / (7 * 86400) / 1e6)


def test_区间流量_输入顺序无关():
    """基准行来自 SQL，顺序不保证；结果必须与顺序无关

    （周中再采几次不影响结果，靠的是「每周只留最早一条基准」这一上游约束，
    在 stats.py 的 ROW_NUMBER 查询里保证。）
    """
    rows = [baseline(1, 0, 0), baseline(0, 1000, 2000)]
    assert compute_week_deltas(rows) == compute_week_deltas(list(reversed(rows)))


def test_区间流量_若误把周中读数当基准结果会偏小():
    """反面用例：说明「取周最早」不是可有可无 —— 用周中读数当基线会少算一截"""
    right = compute_week_deltas([baseline(1, 0, 0), baseline(0, 1000, 0)])
    wrong_rows = [baseline(1, 0, 0), baseline(0, 700, 0)]  # 基线被推到周中
    wrong = compute_week_deltas(wrong_rows)

    assert wrong[("D1", "Gi1/0/1")]["rx_mbps"] < right[("D1", "Gi1/0/1")]["rx_mbps"]


def test_区间流量_多周窗口取首尾():
    """window=4 / 13 只是传入的基准条数不同，算法一律取窗口首尾"""
    # weeks_ago 越小时间越晚，累计读数越大
    rows = [baseline(w, (4 - w) * 1000, (4 - w) * 1000) for w in range(4, -1, -1)]
    entry = compute_week_deltas(rows)[("D1", "Gi1/0/1")]

    assert entry["span_sec"] == 4 * 7 * 86400
    assert entry["rx_mbps"] == pytest.approx(4000 * 8 / (4 * 7 * 86400) / 1e6)


def test_区间流量_窗口内缺采则跨度变大():
    """中间某周采集失败 → 自动跳过，用实际存在的首尾，span_sec 相应变大"""
    rows = [baseline(3, 0, 0), baseline(0, 3000, 0)]  # 缺第 1、2 周
    assert compute_week_deltas(rows)[("D1", "Gi1/0/1")]["span_sec"] == 3 * 7 * 86400


def test_区间流量_只有一条基准则不出结果():
    """首次出现 / 过渡期 —— 窗口内没有可比区间"""
    assert compute_week_deltas([baseline(0, 1000, 2000)]) == {}


def test_区间流量_新端口不按0算():
    """按 0 算会造出虚高假峰值直接冲榜首；首次出现必须给不出结果"""
    result = compute_week_deltas([baseline(0, 10**13, 10**13)])
    assert result == {}


def test_区间流量_计数器重置则该方向无值():
    rows = [baseline(1, 5000, 5000), baseline(0, 100, 200)]  # 读数变小 = 重置
    assert compute_week_deltas(rows) == {}


def test_区间流量_单方向重置不影响另一方向():
    rows = [baseline(1, 5000, 1000), baseline(0, 100, 3000)]
    entry = compute_week_deltas(rows)[("D1", "Gi1/0/1")]

    assert entry["rx_mbps"] is None                      # 入向重置
    assert entry["tx_mbps"] == pytest.approx(2000 * 8 / (7 * 86400) / 1e6)   # 出向仍有效


def test_区间流量_跨度不足则不计算且不抛除零():
    rows = [baseline(1, 0, 0), baseline(1, 1000, 1000)]
    rows[1]["collected_at"] = rows[0]["collected_at"] + timedelta(seconds=MIN_SPAN_SEC - 1)

    assert compute_week_deltas(rows) == {}

    # 零跨度同样不得抛 ZeroDivisionError
    rows[1]["collected_at"] = rows[0]["collected_at"]
    assert compute_week_deltas(rows) == {}


def test_区间流量_读数缺失则该方向无值():
    """in_octets 为 NULL（本轮没采到）不等于读数 0；两方向独立判定"""
    rows = [baseline(1, None, 0), baseline(0, 1000, 0)]
    entry = compute_week_deltas(rows)[("D1", "Gi1/0/1")]

    assert entry["rx_mbps"] is None
    assert entry["tx_mbps"] == 0.0


def test_区间流量_多设备多端口互不干扰():
    rows = [
        baseline(1, 0, 0, device="D1", port="Gi1/0/1"),
        baseline(0, 1000, 0, device="D1", port="Gi1/0/1"),
        baseline(1, 0, 0, device="D1", port="Gi1/0/2"),
        baseline(0, 8000, 0, device="D1", port="Gi1/0/2"),
        baseline(1, 0, 0, device="D2", port="Gi1/0/1"),
        baseline(0, 3000, 0, device="D2", port="Gi1/0/1"),
        baseline(0, 9999, 0, device="D2", port="Gi1/0/9"),   # 只有一条 → 不出现
    ]
    result = compute_week_deltas(rows)

    assert set(result) == {("D1", "Gi1/0/1"), ("D1", "Gi1/0/2"), ("D2", "Gi1/0/1")}
    assert result[("D1", "Gi1/0/2")]["rx_mbps"] > result[("D2", "Gi1/0/1")]["rx_mbps"] \
        > result[("D1", "Gi1/0/1")]["rx_mbps"]


def test_区间流量_时间字段接受ISO字符串():
    rows = [
        baseline(1, 0, 0),
        baseline(0, 1000, 0),
    ]
    for row in rows:
        row["collected_at"] = row["collected_at"].isoformat()

    assert compute_week_deltas(rows)[("D1", "Gi1/0/1")]["span_sec"] == 7 * 86400
