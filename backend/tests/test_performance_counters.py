"""端口累计计数器与端口详情合并测试（PerformanceAnalyzer 接线）

真机样本读 tests/fixtures/；Aruba 的 show interface brief 无样本文件，
用合成表头构造（采集实际用的就是 brief，不是 physical）。
"""
from pathlib import Path

import pytest

from analyzers.counter_parser import parse_aruba_counters
from analyzers.performance import PerformanceAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


def details_of(interface_status: str = "", **kwargs) -> list:
    return PerformanceAnalyzer(interface_status, **kwargs).analyze()["interface_summary"]["details"]


def counter_ports(details: list) -> dict:
    return {d["name"]: (d["in_octets"], d["out_octets"]) for d in details if "in_octets" in d}


# ============================================================
# Cisco 交换机
# ============================================================

def test_交换机_计数器按端口名合并():
    details = details_of(
        interface_status=read_fixture("Cisco 2960x show interfaces status.txt"),
        device_type="cisco_ios",
        counters_raw=read_fixture("Cisco 2960x show interfaces counters.txt"),
        model="WS-C2960X-48FPD-L",
    )
    counters = counter_ports(details)

    assert len(details) == 151          # status 151 口（含管理口 Fa0）
    assert len(counters) == 150         # counters 150 口，全部匹配上
    assert counters["Gi1/0/1"] == (1603759403106, 949050652876)
    # 状态与描述来自 status 命令，流量来自 counters —— 两者按名字对齐
    assert next(d for d in details if d["name"] == "Gi1/0/1")["description"] == "Internet-CNC"


def test_交换机_未被计数器覆盖的端口保留在清单里():
    """Fa0 管理口只在 status 里，没有计数器 —— 不能因此丢掉"""
    details = details_of(
        interface_status=read_fixture("Cisco 2960x show interfaces status.txt"),
        device_type="cisco_ios",
        counters_raw=read_fixture("Cisco 2960x show interfaces counters.txt"),
    )
    fa0 = next(d for d in details if d["name"] == "Fa0")

    assert "in_octets" not in fa0


def test_C9500_排除逻辑口与堆叠口():
    details = details_of(
        interface_status=read_fixture("Cisco 9500 show interfaces status.txt"),
        device_type="cisco_ios",
        counters_raw=read_fixture("Cisco 9500 show interfaces counters.txt"),
        model="C9500-24Y4C",
    )
    counters = counter_ports(details)

    assert len(counters) == 48
    assert not [n for n in counters if n.startswith(("Po", "Hu"))]
    assert counters["Twe1/0/2"] == (16101977364549, 9422674234620)
    # 被排除的口仍在 status 清单里（只是没有流量），面板照常显示
    assert "Po1" in {d["name"] for d in details}


# ============================================================
# Cisco 路由器
# ============================================================

def test_路由器_端口清单来自description且只含父口():
    details = details_of(
        device_type="cisco_ios_router",
        counters_raw=read_fixture("Cisco router show interfaces stats.txt"),
        description_raw=read_fixture("Cisco Router show interfaces descript.txt"),
    )
    names = {d["name"] for d in details}

    assert names == {"Gi0/0/0", "Gi0/0/1", "Gi0/0/2", "Gi0/0/3", "Te0/0/4", "Te0/0/5", "SE0/1/0"}
    assert not [n for n in names if ":" in n]      # 31 个子接口不进清单


def test_路由器_状态与描述来自description():
    """路由器上 show interface status 无输出，状态只能从 description 取"""
    analyzer = PerformanceAnalyzer(
        "",
        device_type="cisco_ios_router",
        counters_raw=read_fixture("Cisco router show interfaces stats.txt"),
        description_raw=read_fixture("Cisco Router show interfaces descript.txt"),
    )
    summary = analyzer.analyze()["interface_summary"]
    details = summary["details"]

    assert summary["up"] == 2 and summary["down"] == 5
    gi1 = next(d for d in details if d["name"] == "Gi0/0/1")
    assert gi1["status"] == "up" and gi1["description"] == "Qorvo-LAN"
    se0 = next(d for d in details if d["name"] == "SE0/1/0")
    assert se0["status"] == "up" and "in_octets" in se0


def test_路由器_两词Status写法都能解析():
    """Status 列的两词写法会多占一个 token，Protocol 与 Description 都要往后挪：

    IOS-XE（C8300）用 "administratively down"，较老的 ISR（2921/2951）用 "admin down"。
    两者都统一存成 "admin"。真机实测：ISR 上按 'administratively' 判断会让
    description 取到 Protocol 列，变成 desc='down'。
    """
    raw = (
        "BJQD1RTW01#show interfaces description\n"
        "Interface                      Status         Protocol Description\n"
        "Gi0/0/1                        administratively down  down     Qorvo-LAN\n"
        "Gi0/0/2                        admin down     down     WAN_Router\n"
        "Gi0/0/3                        up             up       uplink\n"
    )
    details = details_of(device_type="cisco_ios_router", description_raw=raw)
    by_name = {d["name"]: d for d in details}

    for name, desc in (("Gi0/0/1", "Qorvo-LAN"), ("Gi0/0/2", "WAN_Router")):
        assert by_name[name]["status"] == "admin"
        assert by_name[name]["status_up"] is False
        assert by_name[name]["description"] == desc
    assert by_name["Gi0/0/3"]["status"] == "up"
    assert by_name["Gi0/0/3"]["description"] == "uplink"


def test_路由器_Loopback两侧命名不同仍能对齐():
    """真机实测（ISR 2921/2951）：description 侧叫 Lo1，stats 侧叫 Loopback1。

    不归一化就会变成两条：Lo1 有状态没流量、Loopback1 有流量没状态（被补入）。
    """
    desc = (
        "BJQD1RTW01#show interfaces description\n"
        "Interface                      Status         Protocol Description\n"
        "Lo1                            up             up       Qorvo MGT\n"
    )
    stats = (
        "BJQD1RTW01#show interfaces stats\n"
        "Loopback1\n"
        "          Switching path    Pkts In   Chars In   Pkts Out  Chars Out\n"
        "                   Total        100        800        200       1600\n"
    )
    details = details_of(device_type="cisco_ios_router", description_raw=desc, counters_raw=stats)

    assert len(details) == 1
    assert details[0]["name"] == "Lo1"
    assert details[0]["description"] == "Qorvo MGT"
    assert details[0]["in_octets"] == 800


def test_路由器_没有description时不崩():
    """回退路径：只有空 interface_status，不得抛异常"""
    details = details_of(device_type="cisco_ios_router")
    assert details == []


# ============================================================
# Aruba
# ============================================================

def aruba_brief(port_names) -> str:
    """合成 show interface brief（采集实际用 brief，样本目录里只有 physical）"""
    lines = ["BJDD1SWI01# show interface brief",
             "Port Native Mode Type Enabled Status Speed Description"]
    for i, name in enumerate(port_names, start=1):
        lines.append(f"{name}  4093  access  1GbT  1G  up  1000  port{i}")
    return "\n".join(lines)


def test_Aruba_计数器按端口名合并():
    stats = read_fixture("Aruba show interface statisti.txt")
    names = sorted(parse_aruba_counters(stats), key=lambda n: [int(x) for x in n.split("/")])
    details = details_of(
        interface_status=aruba_brief(names),
        device_type="aruba_aoscx",
        counters_raw=stats,
    )
    counters = counter_ports(details)

    assert len(details) == 52
    assert len(counters) == 52
    assert counters["1/1/1"] == (2962913932240, 2069230696219)


# ============================================================
# 端口清单缺失时的兜底
# ============================================================

def test_端口清单为空时计数器端口仍被保留():
    """端口状态命令失败（返回空）时，流量数据不能凭空消失"""
    details = details_of(
        device_type="cisco_ios",
        counters_raw=read_fixture("Cisco 2960x show interfaces counters.txt"),
    )
    counters = counter_ports(details)

    assert len(counters) == 150
    assert counters["Gi1/0/1"] == (1603759403106, 949050652876)
    # 补入的记录状态未知，但端口名与流量是真的
    assert {d["status"] for d in details} == {"unknown"}


def test_上行口标记来自uplink_ports():
    """流量排行的「上行口优先」排序依赖这个标记。

    注意 API 层逐字段构造 Device 时曾漏掉 uplink_ports，导致全库 is_uplink 恒为 0。
    """
    details = details_of(
        interface_status=read_fixture("Cisco 2960x show interfaces status.txt"),
        device_type="cisco_ios",
        uplink_ports=["Te3/0/1", "Te3/0/2"],
    )
    by_name = {d["name"]: d for d in details}

    assert by_name["Te3/0/1"]["is_uplink"] is True
    assert by_name["Te3/0/2"]["is_uplink"] is True
    assert by_name["Gi1/0/1"]["is_uplink"] is False


def test_没有计数器输出时行为不变():
    """老路径不受影响：不传 counters_raw 时详情里没有计数器字段"""
    details = details_of(
        interface_status=read_fixture("Cisco 2960x show interfaces status.txt"),
        device_type="cisco_ios",
    )

    assert len(details) == 151
    assert not any("in_octets" in d for d in details)
