"""配置收集 API 路由"""

import asyncio
import json
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict
import os
import subprocess
import platform
import socket
from utils.settings_loader import load_settings
from storage.device_dal import get_device_by_name

router = APIRouter()


@router.get("/progress/{device_name}")
async def get_collect_progress(device_name: str) -> dict:
    """查询设备收集进度（前端轮询用——保留兼容，SSE 端点 /progress/stream/{device_name} 为首选）"""
    from services.collector_service import get_collection_progress
    progress = get_collection_progress(device_name)
    if progress is None:
        return {"step": "idle", "error": "", "progress": 0, "cmd_done": 0, "total_cmds": 0}
    return {
        "step": progress.get("step", "unknown"),
        "error": progress.get("error", ""),
        "progress": progress.get("progress", 0),
        "cmd_done": progress.get("cmd_done", 0),
        "total_cmds": progress.get("total_cmds", 0),
    }


@router.get("/progress/stream/{device_name}")
async def stream_collect_progress(device_name: str):
    """SSE 实时推送设备收集进度（替代轮询）"""
    from services.collector_service import get_collection_progress

    async def event_stream():
        last_state = ""
        while True:
            progress = get_collection_progress(device_name)
            step = progress.get("step", "idle") if progress else "idle"
            error = progress.get("error", "") if progress else ""
            pct = progress.get("progress", 0) if progress else 0

            # 在步骤变化或进度数值变化时推送
            payload = json.dumps(
                {"step": step, "error": error, "progress": pct},
                ensure_ascii=False
            )
            state_key = f"{step}:{pct:.1f}:{error}"
            if state_key != last_state:
                last_state = state_key
                yield f"data: {payload}\n\n"

            # complete 或 failed → 推送最后一次后断开
            if step in ("complete", "failed"):
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _ping_blocking(ip: str, sys_name: str) -> Dict:
    """同步 Ping 逻辑，由 asyncio.to_thread 调度，避免阻塞事件循环"""
    if sys_name == "windows":
        cmd = ["ping", "-n", "1", "-w", "2000", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "2", ip]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    reachable = result.returncode == 0

    if not reachable:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            tcp_result = sock.connect_ex((ip, 22))
            sock.close()
            if tcp_result == 0:
                return {
                    "reachable": True,
                    "ip": ip,
                    "detail": "设备可达（Ping 被拦截，但 TCP 22 端口开放）"
                }
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass

    return {
        "reachable": reachable,
        "ip": ip,
        "detail": "设备可达" if reachable else f"设备不可达（Ping {ip} 失败）"
    }


@router.post("/ping/{device_name}")
async def ping_device(device_name: str) -> Dict:
    """Ping 设备 IP 检查可达性"""
    device = get_device_by_name(device_name)
    if not device:
        raise HTTPException(status_code=404, detail=f"设备 '{device_name}' 不存在")

    ip = device.get("ip", "")
    if not ip:
        return {"reachable": False, "error": "设备未配置 IP 地址"}

    try:
        sys_name = platform.system().lower()
        return await asyncio.to_thread(_ping_blocking, ip, sys_name)
    except subprocess.TimeoutExpired:
        return {"reachable": False, "ip": ip, "detail": f"Ping 超时（{ip}）"}
    except Exception as e:
        print(f"Ping 异常 ({ip}): {e}")
        return {"reachable": False, "ip": ip, "detail": "Ping 检测失败"}


@router.post("/{device_name}")
async def collect_config(
    device_name: str,
    username: str = Form(...),
    password: str = Form(...)
) -> Dict:
    """收集设备配置 — SSH 登录交换机获取 running-config 等数据"""
    # 查找设备信息
    device = get_device_by_name(device_name)
    if not device:
        raise HTTPException(status_code=404, detail=f"设备 '{device_name}' 不存在")

    print(f"[收集] 设备={device_name}, 用户名={username}")

    try:
        from services.collector_service import collect_device
        from utils.settings_loader import load_settings
        from models.devices import Device

        # 将 dict 转为 Device 对象
        device_obj = Device(
            name=device.get("name", device_name),
            ip=device.get("ip", ""),
            device_type=device.get("type", "cisco_ios"),
        )
        device_obj.platform = device.get("platform") or ""
        device_obj.location = device.get("location") or ""
        device_obj.notes = device.get("notes") or ""
        device_obj.serial_number = device.get("serial_number") or ""
        device_obj.username = device.get("username") or ""

        settings = load_settings()
        result = await asyncio.to_thread(collect_device, device_obj, username, password, settings)

        if result["status"] == "failed":
            return {
                "success": False,
                "result": result,
                "detail": result.get("error", "收集失败")
            }

        return {
            "success": True,
            "result": result
        }
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"模块导入失败: {str(e)}")
    except Exception as e:
        print(f"收集过程出错: {e}")
        raise HTTPException(status_code=500, detail="收集过程出错，请稍后重试")


