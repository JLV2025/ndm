"""采集后自动审计（去抖）测试。

四条要点：
  1. **去抖**：批次内连续采集 → 只跑一轮（而不是每台一轮）
  2. **开关**：run_after_collect=false → 不跑
  3. **失败隔离**：审计抛任何异常都不上升（采集不能被拖累）
  4. **设置读不到**：不跑、不抛
"""
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from services import audit_scheduler as scheduler  # noqa: E402
from analyzers.compliance import runner  # noqa: E402


@pytest.fixture
def env(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    conn = db.get_connection()
    yield conn
    # 清掉可能还在跑的定时器，避免线程泄漏到下一个测试
    if scheduler._timer is not None:
        scheduler._timer.cancel()
    scheduler._timer = None
    db.close_connection()
    db._db_path = original


def wait_for_runs(conn, n=1, timeout=3.0) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout:
        count = conn.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0]
        if count >= n:
            return count
        time.sleep(0.05)
    return conn.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0]


def test_连续采集只跑一轮(env, monkeypatch):
    """模拟一批三台设备依次采集成功 —— 去抖后只应产生一轮审计。"""
    monkeypatch.setattr(scheduler, "_settings", lambda: {"post_collect_delay": 0.15})
    assert scheduler.schedule_post_collect_audit() is True
    assert scheduler.schedule_post_collect_audit() is True
    assert scheduler.schedule_post_collect_audit() is True

    assert wait_for_runs(env) == 1
    time.sleep(0.4)                      # 再等一会，确认没有第二、第三轮
    assert env.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0] == 1
    row = env.execute("SELECT trigger, status FROM audit_runs").fetchone()
    assert row[0] == "post_collect" and row[1] == "done"


def test_开关关闭则不跑(env, monkeypatch):
    monkeypatch.setattr(scheduler, "_settings", lambda: {"run_after_collect": False})
    assert scheduler.schedule_post_collect_audit(delay=0.05) is False
    time.sleep(0.3)
    assert env.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0] == 0


def test_审计失败不上升(env, monkeypatch):
    """执行器抛异常时，_run 必须吞掉（采集链路不能被审计拖垮）。"""
    def boom(*a, **k):
        raise RuntimeError("模拟审计崩溃")

    monkeypatch.setattr(runner, "run_full_audit", boom)
    scheduler._run()                     # 不得抛异常
    assert env.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0] == 0


def test_设置读不到则跳过(env, monkeypatch):
    def broken():
        raise FileNotFoundError("settings.yaml 不存在")

    monkeypatch.setattr(scheduler, "_settings", broken)
    assert scheduler.schedule_post_collect_audit() is False
    time.sleep(0.2)
    assert env.execute("SELECT COUNT(*) FROM audit_runs").fetchone()[0] == 0
