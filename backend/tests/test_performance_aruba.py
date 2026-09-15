"""Aruba show interface brief 解析测试

重点：lag 逻辑口必须被过滤（端口面板与流量排行都只看物理口），
同时 Native VLAN 与「模式」(access/trunk) 必须保留 —— 这两列是
show interface brief 独有、show interface physical 没有的。
"""
from analyzers.performance import PerformanceAnalyzer

HEADER = "Port Native Mode Type Enabled Status Speed Description"

BRIEF = f"""BJDD1SWI01# show interface brief
{HEADER}
1/1/1      4093  access  1GbT  1G  up    1000  Internet-In
1/1/2      1     access  1GbT  1G  down  --    --
lag1       4093  trunk   1GbT  --  up    --    to-core
lag49      4093  trunk   1GbT  --  up    --    to-core
vlan10     4093  access  --    --  up    --    --
"""


def analyze(raw: str):
    return PerformanceAnalyzer(raw, "", "aruba_aoscx").analyze()["interface_summary"]


def test_lag逻辑口被过滤():
    summary = analyze(BRIEF)
    names = [d["name"] for d in summary["details"]]

    assert names == ["1/1/1", "1/1/2"]


def test_vlan接口仍被过滤():
    assert not [d for d in analyze(BRIEF)["details"] if d["name"].startswith("vlan")]


def test_模式与NativeVLAN被保留():
    """这两列只有 show interface brief 有，换命令会丢 —— 前端 3 处在显示「模式」"""
    detail = analyze(BRIEF)["details"][0]

    assert detail["mode"] == "access"
    assert detail["native_vlan"] == "4093"


def test_updown计数不含lag():
    summary = analyze(BRIEF)

    assert summary["total"] == 2
    assert summary["up"] == 1
    assert summary["down"] == 1
