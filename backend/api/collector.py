"""配置收集 API 路由"""

from fastapi import APIRouter, Form, HTTPException
from typing import Dict, List
from pydantic import BaseModel
import os
import yaml
import subprocess
import platform
import socket
from utils.settings_loader import get_devices_config_path, load_settings

router = APIRouter()


@router.get("/progress/{device_name}")
async def get_collect_progress(device_name: str) -> dict:
    """查询设备收集进度（前端轮询用）"""
    from services.collector_service import get_collection_progress
    progress = get_collection_progress(device_name)
    if progress is None:
        return {"step": "idle", "error": ""}
    return {"step": progress.get("step", "unknown"), "error": progress.get("error", "")}


class BatchCollectRequest(BaseModel):
    devices: List[str]
    username: str
    password: str


@router.post("/ping/{device_name}")
async def ping_device(device_name: str) -> Dict:
    """Ping 设备 IP 检查可达性"""
    device = find_device_by_name(device_name)
    if not device:
        raise HTTPException(status_code=404, detail=f"设备 '{device_name}' 不存在")

    ip = device.get("ip", "")
    if not ip:
        return {"reachable": False, "error": "设备未配置 IP 地址"}

    try:
        # Windows: ping -n 1 -w 2000; Linux/Mac: ping -c 1 -W 2
        sys = platform.system().lower()
        if sys == "windows":
            cmd = ["ping", "-n", "1", "-w", "2000", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "2", ip]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        reachable = result.returncode == 0
        # 如果 Ping 失败，再尝试 TCP 22 端口检测（防火墙可能禁 ICMP）
        if not reachable:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                tcp_result = sock.connect_ex((ip, 22))
                sock.close()
                if tcp_result == 0:
                    reachable = True
                    return {
                        "reachable": True,
                        "ip": ip,
                        "detail": f"设备可达（Ping 被拦截，但 TCP 22 端口开放）"
                    }
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass

        return {
            "reachable": reachable,
            "ip": ip,
            "detail": "设备可达" if reachable else f"设备不可达（Ping {ip} 失败）"
        }
    except subprocess.TimeoutExpired:
        return {"reachable": False, "ip": ip, "detail": f"Ping 超时（{ip}）"}
    except Exception as e:
        print(f"Ping 异常 ({ip}): {e}")
        return {"reachable": False, "ip": ip, "detail": "Ping 检测失败"}


def find_device_by_name(device_name: str) -> dict | None:
    """查找设备配置"""
    config_path = get_devices_config_path()
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for device in data.get("devices", []):
        if device.get("name") == device_name:
            return device
    return None


@router.post("/batch")
async def collect_batch(request: BatchCollectRequest) -> Dict:
    """批量收集多台设备配置"""
    from services.collector_service import collect_device
    from utils.settings_loader import load_settings
    from models.devices import Device

    results = []
    settings = load_settings()

    for device_name in request.devices:
        device = find_device_by_name(device_name)
        if not device:
            results.append({
                "device": device_name,
                "status": "failed",
                "error": f"设备 '{device_name}' 不存在"
            })
            continue

        try:
            device_obj = Device(
                name=device.get("name", device_name),
                ip=device.get("ip", ""),
                device_type=device.get("type", "cisco_ios"),
            )
            device_obj.platform = device.get("platform") or ""
            device_obj.location = device.get("location") or ""

            result = collect_device(device_obj, request.username, request.password, settings)
            result["device"] = device_name
            results.append(result)
        except Exception as e:
            results.append({
                "device": device_name,
                "status": "failed",
                "error": str(e)
            })

    return {
        "success": True,
        "total": len(request.devices),
        "success_count": sum(1 for r in results if r.get("status") == "success"),
        "failed_count": sum(1 for r in results if r.get("status") != "success"),
        "results": results
    }


@router.post("/{device_name}")
async def collect_config(
    device_name: str,
    username: str = Form(...),
    password: str = Form(...)
) -> Dict:
    """收集设备配置 — SSH 登录交换机获取 running-config 等数据"""
    # 查找设备信息
    device = find_device_by_name(device_name)
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
        result = collect_device(device_obj, username, password, settings)

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


class Phase2Request(BaseModel):
    triggers: List[str] = []
    port_name: str = ""
    username: str = ""
    password: str = ""


@router.post("/phase2/{device_name}")
async def collect_phase2(device_name: str, request: Phase2Request) -> Dict:
    """Phase 2 深度收集——针对已检测到的异常进行深度诊断"""
    device = find_device_by_name(device_name)
    if not device:
        raise HTTPException(status_code=404, detail=f"设备 '{device_name}' 不存在")

    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="请提供设备凭据")

    try:
        from services.collector_service import run_phase2_collection
        settings = load_settings()
        result = run_phase2_collection(
            device_name=device_name,
            triggers=request.triggers,
            username=request.username,
            password=request.password,
            settings=settings,
            port_name=request.port_name,
        )
        return {"success": result.get("status") == "success", "result": result}
    except Exception as e:
        print(f"Phase 2 收集出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))
