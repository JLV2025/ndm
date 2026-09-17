"""stp_snapshots 落库测试 —— 生成树快照（站点 STP 拓扑图的数据源）

重点：
- 只落参与生成树的端口（Down/Disabled 过滤，见 _build_stp_rows）。
  口径已用真机 summary 交叉验证：落库行数与 `show spanning-tree summary` 的
  「STP Active」列逐一吻合（SWI03=14 / SWI04=32 / SWI05=61）。
- 根/本桥信息与设备级模式随行冗余；跨设备认根靠归一化 MAC（跨厂商可比）。
"""
import sqlite3
from pathlib import Path

import pytest

import storage.database as db
from analyzers.stp_parser import parse_spanning_tree
from services.collector_service import _build_stp_rows, _save_to_sqlite

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def restore_db_path():
    """同 test_port_snapshot_write：换库前必须关掉线程本地连接，避免测试间串数据"""
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


def save(tmp_path, stp_data) -> sqlite3.Connection:
    db.init_db(str(tmp_path))
    _save_to_sqlite(
        device_name="TEST1SWI01", device_ip="10.0.0.1",
        device_type="cisco_ios", device_platform="cisco_ios",
        week="2026-38", collected_at="2026-09-15T09:00:00",
        running_config="", logs_raw="",
        performance_results="{}", validation_results="{}", change_results="{}",
        software_version="15.2", serial_number="FCW1234", device_model="WS-C2960X",
        system_uptime_seconds=None,
        port_details=[], port_errors={},
        neighbors_data=[], boot_history="",
        stp_data=stp_data,
    )
    return db.get_connection()


# ---- _build_stp_rows：解析结果 → 落库行 ----

def test_build_rows_过滤down与disabled端口():
    """SWI01 的 VLAN1 真机 43 个端口里只有 9 个参与生成树（其余是 Down/Disabled 成员口）"""
    result = parse_spanning_tree(_load("PVGD1SWI01 show spanning-tree.txt"), "PVGD1SWI01")
    rows = _build_stp_rows(result)

    assert len(rows) == 111                       # 16 个 VLAN 合计
    vlan1_rows = [r for r in rows if r["vlan"] == 1]
    assert len(vlan1_rows) == 9
    assert all(r["state"] != "down" and r["role"] != "disabled" for r in rows)

    lag14 = next(r for r in vlan1_rows if r["port_name"] == "lag14")
    assert lag14["role"] == "designated" and lag14["state"] == "forwarding"
    assert lag14["cost"] == 2
    assert lag14["is_root"] == 1
    assert lag14["root_mac"] == "9c370806b540"
    assert lag14["bridge_mac"] == "9c370806b540"
    assert lag14["mode"] == "rapid-pvst"


def test_build_rows_行数与summary的STP_Active列吻合():
    """过滤口径的交叉验证：落库行数 == 真机 summary 的「STP Active」"""
    for name, expected in [("PVGD1SWI03", 14), ("PVGD1SWI04", 32), ("PVGD1SWI05", 61)]:
        result = parse_spanning_tree(_load(f"{name} show spanning-tree.txt"), name)
        assert len(_build_stp_rows(result)) == expected, name


def test_build_rows_非根设备带根端口与跨厂商根MAC():
    """SWI02 对 VLAN1：根端口 lag1，根 MAC 与 Aruba 侧（冒号）归一化后一致"""
    result = parse_spanning_tree(_load("PVGD1SWI02 show spanning-tree.txt"), "PVGD1SWI02")
    rows = _build_stp_rows(result)

    lag1 = next(r for r in rows if r["vlan"] == 1 and r["port_name"] == "lag1")
    assert lag1["role"] == "root"
    assert lag1["state"] == "forwarding"
    assert lag1["is_root"] == 0
    assert lag1["root_mac"] == "9c370806b540"     # 跨厂商归一化后的根 MAC
    assert lag1["bridge_mac"] == "4cd58715f580"   # 本机 MAC ≠ 根 MAC


# ---- _save_to_sqlite：落库 ----

def test_stp快照落库(tmp_path, restore_db_path):
    result = parse_spanning_tree(_load("PVGD1SWI05 show spanning-tree.txt"), "PVGD1SWI05")
    rows = _build_stp_rows(result)
    conn = save(tmp_path, rows)

    assert conn.execute("SELECT COUNT(*) FROM stp_snapshots").fetchone()[0] == len(rows) == 61

    row = conn.execute(
        "SELECT vlan, role, state, cost, is_root, root_mac, bridge_mac, mode "
        "FROM stp_snapshots WHERE vlan=1 AND port_name='Po24'"
    ).fetchone()
    assert tuple(row) == (1, "root", "forwarding", 3, 0,
                          "9c370806b540", "f87b20093f00", "rapid-pvst")


def test_stp为空不报错(tmp_path, restore_db_path):
    """路由器等不采集 STP 的设备：stp_data 为 None，落库不报错"""
    conn = save(tmp_path, None)
    assert conn.execute("SELECT COUNT(*) FROM stp_snapshots").fetchone()[0] == 0
