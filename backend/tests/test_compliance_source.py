"""审计数据源测试 —— 重点在三条边界：

1. **采集失败文本必须跳过**：不跳的话整台设备会被判成"配置全缺"，
   一口气报出几十条假问题——最容易毁掉审计可信度的坑。
2. **区分"全文已被保留策略清理"与"从未采集"**：提示文案完全不同。
3. 端口上下文装配：缺哪一路都不影响出结果，只是置信度上不去。
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analyzers.compliance import source  # noqa: E402

SCHEMA = """
CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT, location TEXT, platform TEXT,
                      model TEXT, uplink_ports TEXT);
CREATE TABLE collections (id INTEGER PRIMARY KEY, device_id INTEGER, week TEXT,
                          collected_at TEXT, running_config TEXT, lag_membership TEXT,
                          startup_config TEXT);
CREATE TABLE neighbors (id INTEGER PRIMARY KEY, collection_id INTEGER, local_port TEXT,
                        neighbor_type TEXT);
CREATE TABLE stp_snapshots (id INTEGER PRIMARY KEY, collection_id INTEGER, vlan INTEGER,
                            port_name TEXT, role TEXT);
"""

GOOD_CONFIG = "ArubaOS-CX\nhostname BJQD1SWI01\n" + "!\n" * 600   # 需超过 MIN_CONFIG_LEN


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO devices VALUES (1,'BJQD1SWI01','BJQ','aruba_aoscx','JL659A','[\"1/1/49\"]')")
    conn.execute("INSERT INTO devices VALUES (2,'DEZD1SWI01','DEZ','aruba_aoscx','JL727B',NULL)")
    conn.commit()
    yield conn
    conn.close()


def add_collection(conn, cid, device_id, config, lag=None, week="2026-38", startup=None):
    conn.execute("INSERT INTO collections VALUES (?,?,?,?,?,?,?)",
                 (cid, device_id, week, "2026-09-18T08:00:00", config, lag, startup))
    conn.commit()


# ---------------------------------------------------------------- 配置可用性

def test_missing_device_returns_none(db):
    assert source.load_snapshot(db, "NO_SUCH_DEVICE") is None


def test_never_collected_is_distinguished_from_cleaned(db):
    """从未采集 vs 全文被清理——两者给用户的提示必须不同。"""
    snap = source.load_snapshot(db, "DEZD1SWI01")
    assert snap.usable is False
    assert "从未采集" in snap.reason


def test_cleaned_config_reports_retention_reason(db):
    add_collection(db, 10, 2, None)
    snap = source.load_snapshot(db, "DEZD1SWI01")
    assert snap.usable is False
    assert "保留策略" in snap.reason
    assert snap.collection_id == 10          # 采集记录本身还是要给出


def test_failed_collection_is_skipped(db):
    """采集失败文本必须判为不可用——否则整台设备会被报成"配置全缺"。"""
    add_collection(db, 11, 2, "% 收集失败: 认证失败\n")
    snap = source.load_snapshot(db, "DEZD1SWI01")
    assert snap.usable is False
    assert "采集失败" in snap.reason and "认证失败" in snap.reason


def test_too_short_config_is_rejected(db):
    add_collection(db, 12, 2, "hostname X\n")
    snap = source.load_snapshot(db, "DEZD1SWI01")
    assert snap.usable is False and "过短" in snap.reason


def test_good_config_is_usable_with_stable_hash(db):
    add_collection(db, 13, 1, GOOD_CONFIG)
    snap = source.load_snapshot(db, "BJQD1SWI01")
    assert snap.usable is True and snap.reason == ""
    assert snap.location == "BJQ" and snap.platform == "aruba_aoscx"
    assert snap.config_hash and snap.config_hash == source.load_snapshot(db, "BJQD1SWI01").config_hash
    assert len(snap.config_hash) == 16


def test_latest_collection_wins(db):
    add_collection(db, 20, 1, "% 收集失败: 超时\n")
    add_collection(db, 21, 1, GOOD_CONFIG + "\n! 新版\n")
    snap = source.load_snapshot(db, "BJQD1SWI01")
    assert snap.collection_id == 21 and snap.usable is True


# ---------------------------------------------------------------- 端口上下文

def test_port_context_assembles_all_signals(db):
    add_collection(db, 30, 1, GOOD_CONFIG, lag=json.dumps({"lag 1": ["1/1/49", "1/1/50"]}))
    db.execute("INSERT INTO neighbors VALUES (1,30,'1/1/49','switch')")
    db.execute("INSERT INTO neighbors VALUES (2,30,'1/1/49','switch')")   # 重复源：取第一条即可
    db.execute("INSERT INTO neighbors VALUES (3,30,'1/1/10','server')")
    db.execute("INSERT INTO stp_snapshots VALUES (1,30,1,'1/1/49','root')")
    db.commit()

    ctx = source.load_port_context(db, source.load_snapshot(db, "BJQD1SWI01"))
    assert ctx.neighbor_types == {"1/1/49": "switch", "1/1/10": "server"}
    assert ctx.stp_roles == {"1/1/49": "root"}
    assert ctx.lag_members == {"1/1/49", "1/1/50"}
    assert ctx.uplink_ports == {"1/1/49"}


def test_port_context_survives_bad_json(db):
    """库里存了坏 JSON 不能让整个审计崩掉——上下文只是锦上添花。"""
    add_collection(db, 31, 1, GOOD_CONFIG, lag="{不是合法 json")
    db.execute("UPDATE devices SET uplink_ports = '也不是 json' WHERE id = 1")
    db.commit()
    ctx = source.load_port_context(db, source.load_snapshot(db, "BJQD1SWI01"))
    assert ctx.lag_members == set() and ctx.uplink_ports == set()


def test_load_audit_input_for_missing_device(db):
    assert source.load_audit_input(db, "NO_SUCH_DEVICE") is None


def test_list_audit_inputs_includes_unusable(db):
    """全网快照要把不可用的设备一并带上——它们的 reason 要展示给用户，
    静默跳过会让人以为"这台没问题"。"""
    add_collection(db, 40, 1, GOOD_CONFIG)
    items = source.list_audit_inputs(db)
    assert len(items) == 2
    by_name = {i.snapshot.name: i for i in items}
    assert by_name["BJQD1SWI01"].snapshot.usable is True
    assert by_name["DEZD1SWI01"].snapshot.usable is False
    assert by_name["DEZD1SWI01"].snapshot.reason
