"""批量命令执行 API —— 预检 / 单台执行 / 历史留痕。

编排在**前端**（与采集同一模式：逐台调 execute 端点、实时进度、可中断），
服务端只负责"一台"：预检兜底 → 连接执行（线程外，SSH 是阻塞 IO）→ 落库留痕。

凭据纪律：用户名密码只在本次请求内使用，**绝不入库 / 进日志**
（`batch_runs.username` 记操作者账号用于留痕；密码不落任何表）。
"""
from __future__ import annotations

import asyncio
import datetime
import sqlite3

from fastapi import APIRouter, Form, HTTPException
from pydantic import BaseModel

router = APIRouter()

from services import batch_exec  # noqa: E402
from storage.database import get_connection as _get_db  # noqa: E402


class CheckBody(BaseModel):
    text: str = ""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


@router.post("/api/batch/check")
async def check(body: CheckBody):
    """命令预检（前端预览用）：拆行 → 黑名单三态。回显解析后的命令列表。"""
    commands = batch_exec.split_commands(body.text)
    return {"commands": commands, **batch_exec.check_commands(commands)}


@router.post("/api/batch/execute")
async def execute(
    device_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    text: str = Form(...),
    mode: str = Form("show"),
    save: str = Form("0"),
    batch_id: str = Form(...),
    total: int = Form(0),
    note: str = Form(""),
):
    """对单台设备执行命令。每次调用写一条结果行 —— 同一台重复执行覆盖（前端重试不产生重复）。"""
    db = _get_db()
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT name, ip, type, platform FROM devices WHERE name = ?",
                     (device_name,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"设备 '{device_name}' 不存在")

    commands = batch_exec.split_commands(text)
    if not commands:
        raise HTTPException(status_code=400, detail="命令为空")
    if mode not in ("show", "config"):
        raise HTTPException(status_code=400, detail=f"未知模式：{mode}")
    if not batch_id.strip():
        raise HTTPException(status_code=400, detail="缺少 batch_id")
    save_flag = save in ("1", "true", "True")

    # 首台到达时建批次行（命令全文只存这一份；后续台次 DO NOTHING 不覆盖）
    db.execute(
        "INSERT INTO batch_runs (batch_id, created_at, username, mode, save_config, "
        "command_text, device_count, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(batch_id) DO NOTHING",
        (batch_id.strip(), _now(), username, mode, 1 if save_flag else 0, text,
         max(0, total), note))
    db.commit()

    from models.devices import Device
    from utils.settings_loader import load_settings

    device = Device(name=row["name"], ip=row["ip"], device_type=row["type"] or "cisco_ios")
    device.platform = row["platform"] or ""

    started = _now()
    # SSH 是阻塞 IO —— 进线程；**库操作留在主线程**（SQLite 连接不能跨线程，既有教训）
    result = await asyncio.to_thread(
        batch_exec.execute_on_device, device, username, password, commands,
        mode, save_flag, load_settings())

    db.execute(
        "INSERT INTO batch_results (batch_id, device_name, status, output, error, "
        "started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(batch_id, device_name) DO UPDATE SET "
        "status=excluded.status, output=excluded.output, error=excluded.error, "
        "finished_at=excluded.finished_at",
        (batch_id.strip(), device_name, result["status"], result.get("output", ""),
         result.get("error", ""), started, _now()))
    db.commit()
    return {"device": device_name, **result}


@router.get("/api/batch/history")
async def history(limit: int = 20):
    """批次列表（含每批成功 / 失败统计）。"""
    db = _get_db()
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT r.*, "
        "(SELECT COUNT(*) FROM batch_results x WHERE x.batch_id = r.batch_id "
        " AND x.status = 'success') AS success_count, "
        "(SELECT COUNT(*) FROM batch_results x WHERE x.batch_id = r.batch_id "
        " AND x.status IN ('failed', 'blocked')) AS failed_count, "
        "(SELECT COUNT(*) FROM batch_results x WHERE x.batch_id = r.batch_id) AS done_count "
        "FROM batch_runs r ORDER BY r.id DESC LIMIT ?",
        (max(1, min(limit, 100)),)).fetchall()
    return {"batches": [dict(r) for r in rows]}


@router.get("/api/batch/history/{batch_id}")
async def history_detail(batch_id: str):
    """批次详情：命令全文 + 每台结果（含输出）。"""
    db = _get_db()
    db.row_factory = sqlite3.Row
    run = db.execute("SELECT * FROM batch_runs WHERE batch_id = ?", (batch_id,)).fetchone()
    if run is None:
        raise HTTPException(status_code=404, detail=f"批次不存在：{batch_id}")
    results = db.execute(
        "SELECT device_name, status, output, error, started_at, finished_at "
        "FROM batch_results WHERE batch_id = ? ORDER BY id", (batch_id,)).fetchall()
    return {"batch": dict(run), "results": [dict(r) for r in results]}


@router.delete("/api/batch/history/{batch_id}")
async def delete_history(batch_id: str):
    """删除一个批次及其全部结果（留痕数据由用户自行管理）。"""
    db = _get_db()
    n = db.execute("DELETE FROM batch_results WHERE batch_id = ?", (batch_id,)).rowcount
    db.execute("DELETE FROM batch_runs WHERE batch_id = ?", (batch_id,))
    db.commit()
    return {"deleted": batch_id, "results": n}
