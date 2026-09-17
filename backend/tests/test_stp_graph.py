"""站点级 STP 图构建测试 —— 纯函数 _build_stp_graph（真机样本驱动）

数据来源：PVG 站点 5 台交换机真机样本（backend/tests/fixtures/）。
邻居/LAG 结构按真机库中 PVG 的实际链路构造：
  SWI01(Aruba 6300M 核心) ↔ SWI02/03/04/05 各一条 LAG 上行
  （lag14/15/16/17；对端分别为 lag1 / Po48 / Po48 / Po24）
"""
from pathlib import Path

from analyzers.stp_parser import parse_spanning_tree
from api.topology import _build_stp_graph
from services.collector_service import _build_stp_rows

FIXTURES = Path(__file__).parent / "fixtures"

DEVICES = [
    {"id": "PVGD1SWI01", "label": "PVGD1SWI01", "type": "switch", "tier": "core"},
    {"id": "PVGD1SWI02", "label": "PVGD1SWI02", "type": "switch", "tier": "access"},
    {"id": "PVGD1SWI03", "label": "PVGD1SWI03", "type": "switch", "tier": "access"},
    {"id": "PVGD1SWI04", "label": "PVGD1SWI04", "type": "switch", "tier": "access"},
    {"id": "PVGD1SWI05", "label": "PVGD1SWI05", "type": "switch", "tier": "access"},
]

# 邻居数据（含 LAG 逻辑口 + 物理成员口 + 非交换机邻居，验证过滤与去重）
NEIGHBOR_MAP = {
    "PVGD1SWI01": [
        {"local_port": "lag 14", "neighbor_name": "PVGD1SWI02", "is_logical": 1},
        {"local_port": "lag 15", "neighbor_name": "PVGD1SWI03", "is_logical": 1},
        {"local_port": "lag 16", "neighbor_name": "PVGD1SWI04", "is_logical": 1},
        {"local_port": "lag 17", "neighbor_name": "PVGD1SWI05", "is_logical": 1},
        {"local_port": "1/1/14", "neighbor_name": "PVGD1SWI02", "is_logical": 0},
        {"local_port": "2/1/14", "neighbor_name": "PVGD1SWI02", "is_logical": 0},
        {"local_port": "1/1/2", "neighbor_name": "PVGD1FWL01", "is_logical": 0},  # 非交换机
    ],
    "PVGD1SWI02": [
        {"local_port": "lag 1", "neighbor_name": "PVGD1SWI01", "is_logical": 1},
        {"local_port": "1/1/49", "neighbor_name": "PVGD1SWI01", "is_logical": 0},
        {"local_port": "1/1/50", "neighbor_name": "PVGD1SWI01", "is_logical": 0},
    ],
    "PVGD1SWI03": [
        {"local_port": "Po48", "neighbor_name": "PVGD1SWI01", "is_logical": 1},
        {"local_port": "Gi0/1", "neighbor_name": "PVGD1SWI01", "is_logical": 0},
        {"local_port": "Gi0/2", "neighbor_name": "PVGD1SWI01", "is_logical": 0},
    ],
    "PVGD1SWI04": [
        {"local_port": "Po48", "neighbor_name": "PVGD1SWI01", "is_logical": 1},
        {"local_port": "Gi0/49", "neighbor_name": "PVGD1SWI01", "is_logical": 0},
    ],
    "PVGD1SWI05": [
        {"local_port": "Po24", "neighbor_name": "PVGD1SWI01", "is_logical": 1},
        {"local_port": "Gi1/0/50", "neighbor_name": "PVGD1SWI01", "is_logical": 0},
    ],
}

# 各设备 LAG 的物理成员口（成员口应被隐藏，不单独画线）
LAG_MEMBERS = {
    "PVGD1SWI01": {"1/1/14", "2/1/14", "1/1/15", "2/1/15",
                   "1/1/16", "2/1/16", "1/1/17", "2/1/17"},
    "PVGD1SWI02": {"1/1/49", "1/1/50"},
    "PVGD1SWI03": {"Gi0/1", "Gi0/2"},
    "PVGD1SWI04": {"Gi0/49", "Gi0/50"},
    "PVGD1SWI05": {"Gi1/0/50", "Gi2/0/50"},
}


def _stp_rows_for(name: str) -> list:
    text = (FIXTURES / f"{name} show spanning-tree.txt").read_text(encoding="utf-8", errors="replace")
    return _build_stp_rows(parse_spanning_tree(text, name))


def _graph() -> dict:
    stp_map = {d["id"]: _stp_rows_for(d["id"]) for d in DEVICES}
    return _build_stp_graph(DEVICES, stp_map, NEIGHBOR_MAP, LAG_MEMBERS)


# ---- 节点与分层 ----

def test_节点与分层_根桥在第二层之上():
    graph = _graph()
    nodes = {n["id"]: n for n in graph["nodes"]}

    assert len(nodes) == 5
    assert all(n["has_stp_data"] for n in nodes.values())
    assert all(n["mode"] == "rapid-pvst" for n in nodes.values())

    assert nodes["PVGD1SWI01"]["is_root_bridge"] is True
    assert nodes["PVGD1SWI01"]["layer"] == 1
    for access in ("PVGD1SWI02", "PVGD1SWI03", "PVGD1SWI04", "PVGD1SWI05"):
        assert nodes[access]["is_root_bridge"] is False
        assert nodes[access]["layer"] == 2, access


def test_节点VLAN伪端口摘要():
    nodes = {n["id"]: n for n in _graph()["nodes"]}

    v1_root = next(c for c in nodes["PVGD1SWI01"]["vlans"] if c["vlan"] == 1)
    assert v1_root["is_root"] is True and v1_root["role"] == "root"
    assert v1_root["state"] == "forwarding" and v1_root["port"] is None
    assert v1_root["priority"] == 8192

    v1_access = next(c for c in nodes["PVGD1SWI02"]["vlans"] if c["vlan"] == 1)
    assert v1_access["is_root"] is False
    assert v1_access["role"] == "root" and v1_access["state"] == "forwarding"
    assert v1_access["port"] == "lag1"          # 朝根方向的端口
    assert v1_access["blocked"] is False        # PVG 无阻塞


# ---- 边 ----

def test_边按VLAN成对且方向自上而下():
    graph = _graph()
    layers = {n["id"]: n["layer"] for n in graph["nodes"]}

    for e in graph["edges"]:
        assert layers[e["source"]] <= layers[e["target"]]     # 高层 → 低层
        assert e["source"] != e["target"]

    v1_edge = next(e for e in graph["edges"]
                   if e["source"] == "PVGD1SWI01" and e["target"] == "PVGD1SWI02" and e["vlan"] == 1)
    assert v1_edge["source_port"] == "lag14" and v1_edge["target_port"] == "lag1"
    assert v1_edge["source_role"] == "designated" and v1_edge["target_role"] == "root"
    assert v1_edge["forwarding"] is True


def test_边总数与每对分布():
    """回归锚点：55 条边 = 15(SWI02) + 13(SWI03) + 14(SWI04) + 13(SWI05)

    每对边数 = 两端 VLAN 集合的交集（SWI02 多出本地 VLAN34、SWI04 多出 4092/4093）。
    """
    graph = _graph()
    pairs: dict = {}
    for e in graph["edges"]:
        pairs[(e["source"], e["target"])] = pairs.get((e["source"], e["target"]), 0) + 1

    assert len(graph["edges"]) == 55
    assert pairs == {
        ("PVGD1SWI01", "PVGD1SWI02"): 15,
        ("PVGD1SWI01", "PVGD1SWI03"): 13,
        ("PVGD1SWI01", "PVGD1SWI04"): 14,
        ("PVGD1SWI01", "PVGD1SWI05"): 13,
    }


def test_物理成员口隐藏且无重复边():
    graph = _graph()
    hidden = {"1/1/14", "2/1/14", "1/1/49", "1/1/50",
              "Gi0/1", "Gi0/2", "Gi0/49", "Gi1/0/50"}

    for e in graph["edges"]:
        assert e["source_port"] not in hidden and e["target_port"] not in hidden

    keys = [ (frozenset((e["source"], e["target"])), e["vlan"]) for e in graph["edges"] ]
    assert len(keys) == len(set(keys))          # 每对设备每 VLAN 只有一条边


def test_本地VLAN34不产生跨设备边():
    """VLAN34 是 SWI02/SWI05 各自的本地孤立 VLAN（SWI01 没有）→ 不应有边"""
    graph = _graph()

    assert not any(e["vlan"] == 34 for e in graph["edges"])

    nodes = {n["id"]: n for n in graph["nodes"]}
    for name in ("PVGD1SWI02", "PVGD1SWI05"):
        chip34 = next((c for c in nodes[name]["vlans"] if c["vlan"] == 34), None)
        assert chip34 is not None and chip34["is_root"] is True
        # 本地孤立 VLAN 的根 ≠ 站点级根桥（不能因此抬到第一层）
        assert nodes[name]["is_root_bridge"] is False


def test_非交换机邻居不进图():
    graph = _graph()
    ids = {n["id"] for n in graph["nodes"]}
    assert "PVGD1FWL01" not in ids
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])


def test_根在站点内不触发外部根标记():
    graph = _graph()
    assert graph["root_outside_site"] is False
    assert graph["outside_root_macs"] == []
