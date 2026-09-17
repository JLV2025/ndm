"""「全部清除」端点测试 —— 批量把未处理告警标记为已处理

口径：过滤条件与 GET /api/alerts 完全一致（页面上看到什么就清除什么）；
已处理的记录不动（resolved_at 保持原值，不被重写）。
"""
import asyncio

import pytest

import storage.database as db
from api import alerts as alerts_api


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.execute("INSERT INTO devices (id, name, ip, type, location) VALUES (1, 'D1SWI01', '10.0.0.1', 'cisco_ios', 'PVG')")
    c.execute("INSERT INTO devices (id, name, ip, type, location) VALUES (2, 'D1SWI02', '10.0.0.2', 'cisco_ios', 'SZX')")
    alerts = [
        # (id, device_id, alert_type, severity, is_read, resolved_at)
        (1, 1, "port_sudden_down", "HIGH", 0, None),
        (2, 1, "config_changed", "INFO", 0, None),
        (3, 1, "port_errors", "WARNING", 1, None),        # 已读未处理
        (4, 2, "port_sudden_down", "CRITICAL", 0, None),
        (5, 2, "device_reboot", "HIGH", 1, "2026-09-01T00:00:00"),   # 已处理
    ]
    for aid, did, atype, sev, is_read, resolved in alerts:
        c.execute(
            "INSERT INTO alerts (id, device_id, alert_type, severity, title, detail, is_read, resolved_at, created_at) "
            "VALUES (?, ?, ?, ?, 't', 'd', ?, ?, '2026-09-17T10:00:00')",
            (aid, did, atype, sev, is_read, resolved),
        )
    c.commit()
    yield c
    c.commit()
    db.close_connection()
    db._db_path = original


def _resolved_ids(conn) -> set:
    return {r["id"] for r in conn.execute("SELECT id FROM alerts WHERE resolved_at IS NOT NULL")}


def test_全部清除_无过滤时清除所有未处理(conn):
    result = asyncio.run(alerts_api.resolve_all_alerts())

    assert result["resolved"] == 4                    # 5 条里 1 条已处理，不动
    assert _resolved_ids(conn) == {1, 2, 3, 4, 5}
    assert all(r["is_read"] == 1 for r in conn.execute("SELECT is_read FROM alerts"))


def test_全部清除_已处理的记录不被重写(conn):
    asyncio.run(alerts_api.resolve_all_alerts())

    row = conn.execute("SELECT resolved_at FROM alerts WHERE id = 5").fetchone()
    assert row["resolved_at"] == "2026-09-01T00:00:00"


def test_全部清除_按设备过滤(conn):
    result = asyncio.run(alerts_api.resolve_all_alerts(device_name="D1SWI02"))

    assert result["resolved"] == 1
    assert _resolved_ids(conn) == {4, 5}


def test_全部清除_按未读过滤(conn):
    """unread_only=True 时只清除未读的未处理告警（已读未处理的那条保留）"""
    result = asyncio.run(alerts_api.resolve_all_alerts(unread_only=True))

    assert result["resolved"] == 3
    assert _resolved_ids(conn) == {1, 2, 4, 5}


def test_全部清除_按类型与级别过滤(conn):
    assert asyncio.run(alerts_api.resolve_all_alerts(alert_type="port_sudden_down"))["resolved"] == 2
    assert _resolved_ids(conn) == {1, 4, 5}


def test_全部清除_再清一次返回0(conn):
    asyncio.run(alerts_api.resolve_all_alerts())
    assert asyncio.run(alerts_api.resolve_all_alerts())["resolved"] == 0
