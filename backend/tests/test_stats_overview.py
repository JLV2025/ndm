"""Dashboard 端口统计口径测试 —— Disabled 单独计数

背景：port_stats['disabled'] 曾恒为 0（初始化后从未累加），管理性关闭的端口
（status = 'disabled' / 'admin'）被并进 Down，前端柱状图的 Disabled 段永远是 0。

这里钉住三个桶：up / disabled（管理性关闭）/ down（其余非 up）。
前端「空闲端口」卡片 = down + disabled，即全部非 up 端口。
"""
import asyncio

import pytest

import storage.database as db
from api import stats as stats_api


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """临时库；overview 的设备清单来自 YAML，本测试不关心，置空即可"""
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    monkeypatch.setattr(stats_api, "get_all_devices", lambda: [])
    c = db.get_connection()
    c.execute("INSERT INTO devices (name, ip, type) VALUES ('D1SWI01', '10.0.0.1', 'cisco_ios')")
    c.commit()
    yield c
    c.commit()
    db.close_connection()
    db._db_path = original


def _overview() -> dict:
    return asyncio.run(stats_api.get_overview())


def test_端口统计_Disabled单独计数(conn):
    """disabled 与 admin 都是管理性关闭，单独成桶；其余非 up 才算 Down"""
    cid = conn.execute(
        "INSERT INTO collections (device_id, week, phase, collected_at) "
        "VALUES (1, '2026-38', '1', '2026-09-17T09:00:00')"
    ).lastrowid
    for name, status, up in (
        ("Gi1/0/1", "connected", 1),
        ("Gi1/0/2", "notconnect", 0),
        ("Gi1/0/3", "disabled", 0),
        ("Gi0/1", "admin", 0),
        ("Gi0/2", "err-disabled", 0),
    ):
        conn.execute(
            "INSERT INTO port_snapshots (collection_id, device_id, port_name, status, status_up) "
            "VALUES (?, 1, ?, ?, ?)",
            (cid, name, status, up),
        )
    conn.commit()

    ps = _overview()["port_stats"]

    assert ps["total"] == 5
    assert ps["up"] == 1
    assert ps["disabled"] == 2            # disabled + admin（管理性关闭）
    assert ps["down"] == 2                # notconnect + err-disabled
    assert ps["down"] + ps["disabled"] == 4   # 空闲端口卡片口径 = 全部非 up


def test_端口统计_只取每台设备最新一次采集(conn):
    """旧一次采集的端口不进统计（与流量排序、STP 图同口径）"""
    for week, when, ports in (
        ("2026-37", "2026-09-10T09:00:00", [("Gi1/0/1", "connected", 1)]),
        ("2026-38", "2026-09-17T09:00:00", [("Gi1/0/1", "connected", 1), ("Gi1/0/2", "disabled", 0)]),
    ):
        cid = conn.execute(
            "INSERT INTO collections (device_id, week, phase, collected_at) VALUES (1, ?, '1', ?)",
            (week, when),
        ).lastrowid
        for name, status, up in ports:
            conn.execute(
                "INSERT INTO port_snapshots (collection_id, device_id, port_name, status, status_up) "
                "VALUES (?, 1, ?, ?, ?)",
                (cid, name, status, up),
            )
    conn.commit()

    ps = _overview()["port_stats"]

    assert ps["total"] == 2 and ps["up"] == 1 and ps["disabled"] == 1
