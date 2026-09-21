"""批量执行 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）+ 假 SSH 连接。

重点三条契约：
  1. **留痕**：首台到达建批次行（命令全文只存一份）、每台写结果行、重复执行同台**覆盖**不重复
  2. **服务端兜底**：危险命令在 API 层就被拒（blocked），根本不尝试连接设备
  3. **凭据绝不落库**：两表结构里没有任何密码列（只留操作者 username）
"""
import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from api import batch as batch_api  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.row_factory = sqlite3.Row
    c.execute("INSERT INTO devices (id, name, ip, type, platform) "
              "VALUES (1, 'BJQD1SWI01', '10.0.0.1', 'aruba_aoscx', 'aruba_aoscx')")
    c.execute("INSERT INTO devices (id, name, ip, type, platform) "
              "VALUES (2, 'ZGND1SWI01', '10.0.0.2', 'cisco_ios', 'cisco_ios')")
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def call(coro):
    return asyncio.run(coro)


class FakeConn:
    """最小假 DeviceConnection（netmiko 层由同一对象兼任）。"""
    calls: list = []

    def __init__(self, config):
        self.config = config
        self.connection = self
        self.secret = ""

    def connect(self, u, p):
        FakeConn.calls.append(("connect", self.config["name"]))
        return True

    def check_enable_mode(self):
        return True

    def send_config_set(self, cmds, read_timeout=None):
        FakeConn.calls.append(("config_set", list(cmds)))
        return "config applied"

    def send_command(self, cmd, read_timeout=None):
        FakeConn.calls.append(("cmd", cmd))
        return f"output of {cmd}"

    def disconnect(self):
        FakeConn.calls.append(("disconnect",))


@pytest.fixture
def fake_ssh(monkeypatch):
    FakeConn.calls = []
    monkeypatch.setattr("collectors.base.DeviceConnection", FakeConn)
    return FakeConn


def exec_kwargs(**over):
    kw = dict(device_name="BJQD1SWI01", username="admin", password="pw",
              text="show clock", mode="show", save="0",
              batch_id="b-test-1", total=2, note="来自审计发现")
    kw.update(over)
    return kw


# ---------------------------------------------------------------- 预检

def test_check端点三态(conn):
    res = call(batch_api.check(batch_api.CheckBody(text="show clock\nreload\nno vlan 16")))
    assert res["commands"] == ["show clock", "reload", "no vlan 16"]
    assert [b["cmd"] for b in res["blocked"]] == ["reload"]
    assert [w["cmd"] for w in res["warnings"]] == ["no vlan 16"]


# ---------------------------------------------------------------- 执行与留痕

def test_execute首台建批次行并写结果(conn, fake_ssh):
    res = call(batch_api.execute(**exec_kwargs()))
    assert res["status"] == "success" and "output of show clock" in res["output"]

    run = conn.execute("SELECT * FROM batch_runs WHERE batch_id='b-test-1'").fetchone()
    assert run["username"] == "admin" and run["device_count"] == 2
    assert run["note"] == "来自审计发现"
    r = conn.execute("SELECT * FROM batch_results WHERE batch_id='b-test-1'").fetchone()
    assert r["device_name"] == "BJQD1SWI01" and r["status"] == "success"
    assert "output of show clock" in r["output"]
    assert ("disconnect",) in fake_ssh.calls


def test_execute第二台不重建批次行(conn, fake_ssh):
    call(batch_api.execute(**exec_kwargs()))
    call(batch_api.execute(**exec_kwargs(device_name="ZGND1SWI01", text="show version")))
    assert conn.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM batch_results").fetchone()[0] == 2
    # 命令全文只存首台那次的（DO NOTHING 不覆盖）
    run = conn.execute("SELECT command_text FROM batch_runs").fetchone()
    assert run["command_text"] == "show clock"


def test_execute重复执行同台覆盖不重复(conn, fake_ssh):
    call(batch_api.execute(**exec_kwargs()))
    call(batch_api.execute(**exec_kwargs(text="show version")))    # 重试/重跑
    rows = conn.execute("SELECT * FROM batch_results WHERE batch_id='b-test-1'").fetchall()
    assert len(rows) == 1 and "output of show version" in rows[0]["output"]


def test_execute危险命令直接blocked且不连接(conn, fake_ssh):
    res = call(batch_api.execute(**exec_kwargs(text="reload")))
    assert res["status"] == "blocked" and "拦截" in res["error"]
    assert fake_ssh.calls == []                                    # 根本没连设备
    # 结果也要留痕（谁在何时试过执行危险命令）
    r = conn.execute("SELECT status FROM batch_results").fetchone()
    assert r["status"] == "blocked"


def test_execute参数校验(conn, fake_ssh):
    with pytest.raises(HTTPException) as ei:
        call(batch_api.execute(**exec_kwargs(device_name="NOPE")))
    assert ei.value.status_code == 404
    with pytest.raises(HTTPException) as ei:
        call(batch_api.execute(**exec_kwargs(text="\n! 只有注释\n")))
    assert ei.value.status_code == 400
    with pytest.raises(HTTPException) as ei:
        call(batch_api.execute(**exec_kwargs(mode="yolo")))
    assert ei.value.status_code == 400
    with pytest.raises(HTTPException) as ei:
        call(batch_api.execute(**exec_kwargs(batch_id="  ")))
    assert ei.value.status_code == 400


def test_config模式保存选项落库(conn, fake_ssh):
    call(batch_api.execute(**exec_kwargs(text="vlan 16", mode="config", save="1")))
    run = conn.execute("SELECT mode, save_config FROM batch_runs").fetchone()
    assert run["mode"] == "config" and run["save_config"] == 1
    assert ("cmd", "write memory") in fake_ssh.calls


def test_凭据绝不落库(conn):
    """两表结构里没有任何密码列 —— 这是纪律的结构性保证，不靠自觉。"""
    for table in ("batch_runs", "batch_results"):
        cols = {r[1].lower() for r in conn.execute(f"PRAGMA table_info({table})")}
        assert not any("password" in c or "secret" in c for c in cols), f"{table} 混进了凭据列"


# ---------------------------------------------------------------- 历史

def test_history统计与详情(conn, fake_ssh):
    call(batch_api.execute(**exec_kwargs()))
    call(batch_api.execute(**exec_kwargs(device_name="ZGND1SWI01", text="reload")))
    batches = call(batch_api.history())["batches"]
    assert len(batches) == 1
    b = batches[0]
    assert b["success_count"] == 1 and b["failed_count"] == 1 and b["done_count"] == 2

    detail = call(batch_api.history_detail("b-test-1"))
    assert detail["batch"]["batch_id"] == "b-test-1"
    assert {r["device_name"] for r in detail["results"]} == {"BJQD1SWI01", "ZGND1SWI01"}
    out = next(r["output"] for r in detail["results"] if r["device_name"] == "BJQD1SWI01")
    assert "output of show clock" in out

    with pytest.raises(HTTPException) as ei:
        call(batch_api.history_detail("nope"))
    assert ei.value.status_code == 404


def test_delete批次(conn, fake_ssh):
    call(batch_api.execute(**exec_kwargs()))
    res = call(batch_api.delete_history("b-test-1"))
    assert res["results"] == 1
    assert conn.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM batch_results").fetchone()[0] == 0
