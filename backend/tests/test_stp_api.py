"""STP 端点集成测试 —— 临时库 + 真机样本 → 完整 JSON（HTTP 层之下）

链路：fixtures（真机输出）→ stp_parser → stp_snapshots 落库 → 端点函数
覆盖：交换机过滤（路由器排除）、分层、成边、模式一致性、根信息。
"""
import asyncio
from pathlib import Path

import pytest

import storage.database as db
from analyzers.stp_parser import parse_spanning_tree
from api.topology import get_location_stp_topology
from services.collector_service import _build_stp_rows

FIXTURES = Path(__file__).parent / "fixtures"

# (name, driver_type, notes) —— 路由器不进图
DEVICE_ROWS = [
    ("PVGD1SWI01", "aruba_aoscx", "Core Switch"),
    ("PVGD1SWI02", "aruba_aoscx", "Access Switch"),
    ("PVGD1SWI03", "cisco_ios", "Cascade Switch"),
    ("PVGD1SWI04", "cisco_ios", "Cascade Switch"),
    ("PVGD1SWI05", "cisco_ios", "Cascade Switch"),
    ("PVGD1RTW01", "cisco_ios_router", "Voice Gateway"),
]

NEIGHBORS = {
    "PVGD1SWI01": [
        ("lag 14", "PVGD1SWI02", 1), ("lag 15", "PVGD1SWI03", 1),
        ("lag 16", "PVGD1SWI04", 1), ("lag 17", "PVGD1SWI05", 1),
        ("1/1/14", "PVGD1SWI02", 0), ("1/1/2", "PVGD1FWL01", 0),
    ],
    "PVGD1SWI02": [("lag 1", "PVGD1SWI01", 1), ("1/1/49", "PVGD1SWI01", 0)],
    "PVGD1SWI03": [("Po48", "PVGD1SWI01", 1), ("Gi0/1", "PVGD1SWI01", 0)],
    "PVGD1SWI04": [("Po48", "PVGD1SWI01", 1), ("Gi0/49", "PVGD1SWI01", 0)],
    "PVGD1SWI05": [("Po24", "PVGD1SWI01", 1), ("Gi1/0/50", "PVGD1SWI01", 0)],
}


@pytest.fixture
def restore_db_path():
    """换库前必须关掉线程本地连接，避免测试间串数据"""
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


def _load(name: str) -> str:
    return (FIXTURES / f"{name} show spanning-tree.txt").read_text(encoding="utf-8", errors="replace")


def _seed(tmp_path) -> None:
    """把 5 台 PVG 交换机的真机样本灌进临时库（含采集会话与邻居链路）"""
    db.init_db(str(tmp_path))
    conn = db.get_connection()

    for name, driver, notes in DEVICE_ROWS:
        conn.execute(
            "INSERT INTO devices (name, ip, type, platform, location, notes) VALUES (?, ?, ?, ?, 'PVG', ?)",
            (name, "10.0.0.1", driver, driver, notes),
        )

    for name, _, _ in DEVICE_ROWS[:5]:
        device_id = conn.execute("SELECT id FROM devices WHERE name = ?", (name,)).fetchone()["id"]
        conn.execute(
            "INSERT INTO collections (device_id, week, phase, collected_at) VALUES (?, '2026-38', '1', '2026-09-17T09:00:00')",
            (device_id,),
        )
        collection_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for local_port, neighbor_name, is_logical in NEIGHBORS.get(name, []):
            conn.execute(
                "INSERT INTO neighbors (collection_id, device_id, local_port, neighbor_name, source, is_logical) "
                "VALUES (?, ?, ?, ?, 'cdp', ?)",
                (collection_id, device_id, local_port, neighbor_name, is_logical),
            )

        rows = _build_stp_rows(parse_spanning_tree(_load(name), name))
        for r in rows:
            conn.execute(
                "INSERT INTO stp_snapshots (collection_id, device_id, vlan, port_name, role, state, "
                "cost, port_priority, is_root, root_priority, root_mac, bridge_priority, bridge_mac, mode) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (collection_id, device_id, r["vlan"], r["port_name"], r["role"], r["state"],
                 r["cost"], r["port_priority"], 1 if r["is_root"] else 0, r["root_priority"],
                 r["root_mac"], r["bridge_priority"], r["bridge_mac"], r["mode"]),
            )
    conn.commit()


def test_端点返回完整PVG图(tmp_path, restore_db_path):
    _seed(tmp_path)

    result = asyncio.run(get_location_stp_topology("PVG"))

    # 结构
    assert result["location"] == "PVG"
    nodes = {n["id"]: n for n in result["nodes"]}
    assert set(nodes) == {"PVGD1SWI01", "PVGD1SWI02", "PVGD1SWI03", "PVGD1SWI04", "PVGD1SWI05"}
    assert "PVGD1RTW01" not in nodes          # 路由器不进图（不跑 STP）
    assert len(result["edges"]) == 55         # 15 + 13 + 14 + 13
    assert result["summary"] == {
        "node_count": 5, "edge_count": 55, "vlan_count": 19,
        "vlans": sorted(result["summary"]["vlans"]),
    }

    # 分层与根桥
    assert nodes["PVGD1SWI01"]["is_root_bridge"] is True
    assert nodes["PVGD1SWI01"]["layer"] == 1
    assert all(nodes[n]["layer"] == 2 for n in nodes if n != "PVGD1SWI01")

    # 模式一致性与根信息
    assert result["mode_check"]["consistent"] is True
    assert result["mode_check"]["families"] == ["rapid-pvst"]
    assert set(result["mode_check"]["modes"]) == set(nodes)
    assert result["root_outside_site"] is False
    assert result["outside_root_macs"] == []

    # 边方向与内容抽查（VLAN1：SWI01 lag14 → SWI02 lag1）
    v1 = next(e for e in result["edges"]
              if e["source"] == "PVGD1SWI01" and e["target"] == "PVGD1SWI02" and e["vlan"] == 1)
    assert v1["source_port"] == "lag14" and v1["target_port"] == "lag1"
    assert v1["forwarding"] is True


def test_端点_模式不一致时给出告警数据(tmp_path, restore_db_path):
    """把 SWI05 的 mode 改成 pvst（模拟混用）→ consistent=False 且列明各设备模式"""
    _seed(tmp_path)
    conn = db.get_connection()
    conn.execute("UPDATE stp_snapshots SET mode='pvst' WHERE device_id = (SELECT id FROM devices WHERE name='PVGD1SWI05')")
    conn.commit()

    result = asyncio.run(get_location_stp_topology("PVG"))

    assert result["mode_check"]["consistent"] is False
    assert result["mode_check"]["families"] == ["pvst", "rapid-pvst"]
    assert result["mode_check"]["modes"]["PVGD1SWI05"] == "pvst"
    assert result["mode_check"]["modes"]["PVGD1SWI01"] == "rapid-pvst"


def test_端点_未知location报404(tmp_path, restore_db_path):
    from fastapi import HTTPException

    _seed(tmp_path)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_location_stp_topology("XXX"))
    assert exc.value.status_code == 404
