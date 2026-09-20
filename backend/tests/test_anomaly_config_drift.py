"""未保存配置告警测试 —— 重点是**状态型告警的去重与自动消除**。

对比：config_changed 是"事件型"（每次变更一条，累积 258 条是合理的）；
config_drift 是"状态型"—— 只要没人保存它就一直存在。每次都插一条的话，
一周能堆上千条，告警面板直接废掉。

所以这里钉两条行为：
  1. 已有未处理的同类告警 → 不重复新增
  2. running 与 startup 恢复一致 → 自动消除（用户保存完告警自己消失）
"""
import sqlite3
import sys
from pathlib import Path

import pytest

import storage.database as db
from analyzers.anomaly_detector import AnomalyDetector

RUNNING = "Current configuration : 200 bytes\n!\nhostname SWI01\ninterface Gi0/1\n description sw\n!\nend\n"
STARTUP_SAME = "Using 100 out of 200 bytes\n!\nhostname SWI01\ninterface Gi0/1\n description sw\n!\nend\n"
STARTUP_OLD = "Using 100 out of 200 bytes\n!\nhostname SWI01\ninterface Gi0/1\n!\nend\n"


@pytest.fixture
def env(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    conn = db.get_connection()
    conn.execute("INSERT INTO devices (id, name, ip, type) VALUES (1, 'SWI01', '10.0.0.1', 'cisco_ios')")
    conn.commit()
    yield conn
    db.close_connection()
    db._db_path = original


def add_collection(conn, cid, running, startup, week="2026-38"):
    conn.execute(
        "INSERT INTO collections (id, device_id, week, phase, collected_at, "
        "running_config, startup_config) VALUES (?, 1, ?, '1', ?, ?, ?)",
        (cid, week, "2026-09-20T08:00:00", running, startup))
    conn.commit()


def drift_alerts(conn):
    return conn.execute(
        "SELECT id, resolved_at FROM alerts WHERE alert_type='config_drift' ORDER BY id"
    ).fetchall()


def test_drift_alert_created_once(env):
    add_collection(env, 1, RUNNING, STARTUP_OLD)
    d = AnomalyDetector(env)
    assert d.detect_and_save(1, 1, "2026-38") >= 1
    rows = drift_alerts(env)
    assert len(rows) == 1 and rows[0][1] is None

    # 第二次采集仍未保存 → **不重复新增**（否则一周上千条）
    add_collection(env, 2, RUNNING, STARTUP_OLD)
    d.detect_and_save(1, 2, "2026-38")
    assert len(drift_alerts(env)) == 1


def test_drift_alert_auto_resolved_after_save(env):
    """用户保存配置后再采集 → 未保存告警自动消除。
    一个不会自己消失的告警，很快就会被人无视。"""
    add_collection(env, 1, RUNNING, STARTUP_OLD)
    d = AnomalyDetector(env)
    d.detect_and_save(1, 1, "2026-38")
    assert drift_alerts(env)[0][1] is None

    add_collection(env, 2, RUNNING, STARTUP_SAME)     # 保存了
    d.detect_and_save(1, 2, "2026-38")
    rows = drift_alerts(env)
    assert len(rows) == 1 and rows[0][1] is not None  # 被自动 resolve，且没新增


def test_no_drift_alert_when_no_startup_collected(env):
    """没采到 startup 就不判 —— 绝不能因为"没采到"报一条假问题。"""
    add_collection(env, 1, RUNNING, None)
    AnomalyDetector(env).detect_and_save(1, 1, "2026-38")
    assert drift_alerts(env) == []


def test_no_drift_alert_when_configs_match(env):
    add_collection(env, 1, RUNNING, STARTUP_SAME)
    AnomalyDetector(env).detect_and_save(1, 1, "2026-38")
    assert drift_alerts(env) == []


def test_resolve_recovered_drift_is_noop_without_startup(env):
    """采集不到 startup 时不能误消除已有告警（保持现状，等人处理）。"""
    add_collection(env, 1, RUNNING, STARTUP_OLD)
    d = AnomalyDetector(env)
    d.detect_and_save(1, 1, "2026-38")
    add_collection(env, 2, RUNNING, None)
    assert d.resolve_recovered_drift(1, 2) == 0
    assert drift_alerts(env)[0][1] is None


def test_drift_alert_detail_names_sample_lines(env):
    add_collection(env, 1, RUNNING, STARTUP_OLD)
    AnomalyDetector(env).detect_and_save(1, 1, "2026-38")
    import json
    detail = json.loads(env.execute(
        "SELECT detail FROM alerts WHERE alert_type='config_drift'").fetchone()[0])
    assert detail["unsaved_lines"] == 1
    assert "description sw" in detail["sample"][0]
    # 修复建议要来自 remediation_hints（种子按类型补缺，已有库也能拿到）
    hint = env.execute(
        "SELECT suggestion FROM remediation_hints WHERE alert_type='config_drift'").fetchone()
    assert hint and "write memory" in hint[0]
