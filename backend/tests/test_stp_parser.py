"""stp_parser 测试 — 两个平台的真机样本（backend/tests/fixtures/）

样本来源：PVG 站点 5 台交换机的 `show spanning-tree` 真机输出（2026-09-17）
- Aruba AOS-CX（RPVST）：PVGD1SWI01（全 VLAN 根桥）、PVGD1SWI02（非根 + VLAN34 本地根）
- Cisco 2960X（rapid-pvst）：PVGD1SWI03、PVGD1SWI04（VLAN4092/4093 本地根）、PVGD1SWI05
样本文件为 CRLF 行尾（真机原样），解析器需正确处理
"""
from pathlib import Path

from analyzers.stp_parser import (
    normalize_mac,
    normalize_mode,
    parse_spanning_tree,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


# ---- Aruba AOS-CX ----

def test_aruba_root_device_swi01():
    """SWI01 是全部 16 个 VLAN 的根（Designated 端口 + This bridge is the root）"""
    result = parse_spanning_tree(_load("PVGD1SWI01 show spanning-tree.txt"), "PVGD1SWI01")

    assert result.mode == "rapid-pvst"     # RPVST 归入 rapid-pvst 族（与 Cisco 互通）
    assert result.mode_raw == "RPVST"
    assert len(result.vlans) == 16
    assert sorted(result.vlans) == [1, 2, 5, 8, 9, 16, 30, 31, 32, 33, 37, 196, 212, 213, 254, 255]

    vlan1 = result.vlans[1]
    assert vlan1.is_root is True
    assert vlan1.root_priority == 8192
    assert vlan1.root_mac == "9c370806b540"
    assert vlan1.bridge_mac == "9c370806b540"
    assert vlan1.root_port is None          # 根桥没有根端口
    assert len(vlan1.ports) == 43           # 含 Disabled/Down 端口（原始真相全保留）

    lag14 = next(p for p in vlan1.ports if p.name == "lag14")
    assert lag14.role == "designated"
    assert lag14.state == "forwarding"
    assert lag14.cost == 2
    assert any(p.state == "down" for p in vlan1.ports)   # 下联成员口如实保留


def test_aruba_non_root_swi02():
    """SWI02 对 VLAN1 非根：根 MAC 指向 SWI01，根端口是 lag1（cost 2000）"""
    result = parse_spanning_tree(_load("PVGD1SWI02 show spanning-tree.txt"), "PVGD1SWI02")

    assert result.mode == "rapid-pvst"
    vlan1 = result.vlans[1]
    assert vlan1.is_root is False
    assert vlan1.root_mac == "9c370806b540"      # 与 SWI01 的桥 MAC 相同 → 同一棵树
    assert vlan1.bridge_mac == "4cd58715f580"    # 本机 MAC ≠ 根 MAC
    assert vlan1.root_port == "lag1"

    lag1 = next(p for p in vlan1.ports if p.name == "lag1")
    assert lag1.role == "root"
    assert lag1.state == "forwarding"
    assert lag1.cost == 2000


def test_aruba_local_root_vlan34_swi02():
    """VLAN34 是 SWI02 的本地孤立 VLAN（自己就是根，Priority 32768）"""
    result = parse_spanning_tree(_load("PVGD1SWI02 show spanning-tree.txt"), "PVGD1SWI02")

    vlan34 = result.vlans[34]
    assert vlan34.is_root is True
    assert vlan34.root_priority == 32768
    assert vlan34.root_mac == "4cd58715f580"
    assert vlan34.root_port is None

    port_1_1_47 = next(p for p in vlan34.ports if p.name == "1/1/47")
    assert port_1_1_47.role == "designated"
    assert port_1_1_47.state == "forwarding"


# ---- Cisco IOS ----

def test_cisco_access_swi05():
    """SWI05：根在 SWI01（mac 跨厂商格式归一化后一致），根端口 Po24，优先级含 sys-id-ext"""
    result = parse_spanning_tree(_load("PVGD1SWI05 show spanning-tree.txt"), "PVGD1SWI05")

    assert result.mode == "rapid-pvst"     # 块内 `enabled protocol rstp`
    assert result.mode_raw == "rstp"
    assert len(result.vlans) == 14

    vlan1 = result.vlans[1]
    assert vlan1.is_root is False
    assert vlan1.root_priority == 8193            # 8192 + sys-id-ext 1（Cisco 显示口径）
    assert vlan1.root_mac == "9c370806b540"      # Cisco 点号 `9c37.0806.b540` → 归一化
    assert vlan1.bridge_mac == "f87b20093f00"
    assert vlan1.root_port == "Po24"

    po24 = next(p for p in vlan1.ports if p.name == "Po24")
    assert po24.role == "root"
    assert po24.state == "forwarding"
    assert po24.cost == 3
    assert po24.port_priority == 128              # Prio.Nbr `128.640` → 取 128

    # 访问口（VLAN2 里含 Gi1/0/42）
    vlan2 = result.vlans[2]
    gi42 = next(p for p in vlan2.ports if p.name == "Gi1/0/42")
    assert gi42.role == "designated"
    assert gi42.state == "forwarding"
    assert gi42.cost == 4


def test_cisco_local_root_swi04():
    """SWI04 是 VLAN4092/4093 的本地根（This bridge is the root）"""
    result = parse_spanning_tree(_load("PVGD1SWI04 show spanning-tree.txt"), "PVGD1SWI04")

    assert len(result.vlans) == 16                # 含 VLAN4092/4093
    vlan4092 = result.vlans[4092]
    assert vlan4092.is_root is True
    assert vlan4092.root_priority == 36860        # 32768 + 4092
    assert vlan4092.bridge_mac == "002156c9ed00"
    assert vlan4092.root_port is None


def test_cisco_swi03_vlan_count():
    """SWI03：13 个 VLAN，模式同为 rapid-pvst"""
    result = parse_spanning_tree(_load("PVGD1SWI03 show spanning-tree.txt"), "PVGD1SWI03")

    assert result.mode == "rapid-pvst"
    assert len(result.vlans) == 13


def test_cross_vendor_same_root():
    """跨厂商认根：Aruba 的根 MAC 与 Cisco 看到的根 MAC 归一化后一致"""
    aruba = parse_spanning_tree(_load("PVGD1SWI01 show spanning-tree.txt"), "PVGD1SWI01")
    cisco = parse_spanning_tree(_load("PVGD1SWI05 show spanning-tree.txt"), "PVGD1SWI05")

    assert aruba.vlans[1].root_mac == cisco.vlans[1].root_mac == "9c370806b540"


# ---- 边界与工具函数 ----

def test_empty_and_error_input():
    """空文本 / 命令回显错误 → 空结果，不抛异常"""
    for text in ("", "% 收集失败: timeout", "% Invalid input detected at '^' marker.\n"):
        result = parse_spanning_tree(text, "X")
        assert result.vlans == {}
        assert result.mode == ""


def test_normalize_helpers():
    assert normalize_mac("9c:37:08:06:b5:40") == "9c370806b540"
    assert normalize_mac("9c37.0806.b540") == "9c370806b540"
    assert normalize_mode("RPVST") == "rapid-pvst"
    assert normalize_mode("rapid-pvst") == "rapid-pvst"
    assert normalize_mode("ieee") == "pvst"
    assert normalize_mode("MSTP") == "mstp"
