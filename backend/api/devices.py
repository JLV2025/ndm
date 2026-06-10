"""设备管理 API 路由"""

from fastapi import APIRouter, HTTPException, Form, File, UploadFile
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional
import os
import yaml
import json
import re
import csv
import io
from utils.settings_loader import get_devices_config_path

router = APIRouter()


class DeviceCreate(BaseModel):
    name: str
    ip: str
    type: str = "cisco_ios"
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    uplink_ports: Optional[List[str]] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证设备名称 - 防止路径遍历和非法字符"""
        if not v or not isinstance(v, str):
            raise ValueError('设备名称不能为空')
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('设备名称包含非法字符')
        if not re.match(r'^[a-zA-Z0-9_\-\d]+$', v):
            raise ValueError('设备名称只能包含字母、数字、下划线和连字符')
        if len(v) > 100:
            raise ValueError('设备名称过长')
        return v

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """验证 IP 地址格式"""
        if not v or not isinstance(v, str):
            raise ValueError('IP 地址不能为空')
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, v):
            raise ValueError('无效的 IP 地址格式')
        # 验证 IP 地址是否合法
        parts = v.split('.')
        for part in parts:
            if int(part) > 255:
                raise ValueError('无效的 IP 地址')
        return v

    @field_validator('type', 'platform')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证设备类型（platform 可为空）"""
        if v and v not in ['cisco_ios', 'cisco_ios_xe', 'cisco_ios_router', 'aruba_aoscx']:
            raise ValueError('不支持的设备类型，仅支持 cisco_ios / cisco_ios_xe / cisco_ios_router / aruba_aoscx')
        return v


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    type: Optional[str] = None
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    uplink_ports: Optional[List[str]] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """验证设备名称"""
        if v is not None:
            if not isinstance(v, str):
                raise ValueError('设备名称必须为字符串')
            if '..' in v or '/' in v or '\\' in v:
                raise ValueError('设备名称包含非法字符')
            if not re.match(r'^[a-zA-Z0-9_\-\d]+$', v):
                raise ValueError('设备名称只能包含字母、数字、下划线和连字符')
        return v

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        """验证 IP 地址格式"""
        if v is not None:
            if not isinstance(v, str):
                raise ValueError('IP 地址必须为字符串')
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if not re.match(ip_pattern, v):
                raise ValueError('无效的 IP 地址格式')
            parts = v.split('.')
            for part in parts:
                if int(part) > 255:
                    raise ValueError('无效的 IP 地址')
        return v

    @field_validator('type', 'platform')
    @classmethod
    def validate_type_update(cls, v: Optional[str]) -> Optional[str]:
        """验证设备类型（platform 可为空）"""
        if v and v not in ['cisco_ios', 'cisco_ios_xe', 'cisco_ios_router', 'aruba_aoscx']:
            raise ValueError('不支持的设备类型，仅支持 cisco_ios / cisco_ios_xe / cisco_ios_router / aruba_aoscx')
        return v


class DeviceResponse(BaseModel):
    name: str
    ip: str
    type: str
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    last_synced: Optional[str] = None
    username: Optional[str] = None
    uplink_ports: Optional[list] = None


class DevicesConfig(BaseModel):
    devices: List[dict]


def load_devices_from_yaml() -> List[dict]:
    """从 YAML 文件加载设备列表"""
    config_path = get_devices_config_path()
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("devices", [])
    except Exception as e:
        print(f"读取设备配置失败：{e}")
        return []


def save_device_to_yaml(device: dict):
    """将设备保存到 YAML 文件"""
    config_path = get_devices_config_path()

    if not os.path.exists(config_path):
        # 创建新的配置
        data = {"devices": [device]}
    else:
        # 加载现有配置
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"读取设备配置失败：{e}")
            data = {"devices": [device]}
        if "devices" not in data:
            data["devices"] = []

    # 更新或添加设备
    device_list = data.get("devices", [])
    for i, d in enumerate(device_list):
        if d.get("name") == device.get("name"):
            # 更新现有设备
            device_list[i] = device
            break
    else:
        # 添加新设备
        device_list.append(device)

    # 保存文件
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, Dumper=yaml.SafeDumper)
    except Exception as e:
        print(f"保存设备配置失败：{e}")
        raise

    return True


def delete_device_from_yaml(device_name: str) -> bool:
    """从 YAML 文件中删除设备"""
    config_path = get_devices_config_path()
    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except Exception as e:
                print(f"读取 YAML 失败：{e}")
                return False

        device_list = data.get("devices", [])
        original_len = len(device_list)
        data["devices"] = [d for d in device_list if d.get("name") != device_name]

        if len(data["devices"]) < original_len:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, Dumper=yaml.SafeDumper)
            return True
        return False
    except Exception as e:
        print(f"删除设备配置失败：{e}")
        return False


@router.get("/")
async def list_devices():
    """获取设备列表"""
    devices = load_devices_from_yaml()
    result = []
    for d in devices:
        result.append(DeviceResponse(**d).model_dump())
    return result


# CSV 列名映射（CSV header -> YAML 字段名）
CSV_COLUMN_MAP = {
    "name": "name",
    "ip": "ip",
    "type": "type",
    "platform": "platform",
    "location": "location",
    "notes": "notes",
    "uplink_ports": "uplink_ports",
}

# 模板 CSV 内容
CSV_TEMPLATE = "name,ip,type,platform,location,notes,uplink_ports\r\nSWI01,192.168.1.1,aruba_aoscx,aruba_aoscx,DC1,Core Switch,\"1/1/49,1/1/50\"\r\nSWI02,192.168.1.2,cisco_ios,cisco_ios_xe,DC1,Access Switch,\"Te1/0/1,Te1/0/2\"\r\n"


@router.get("/batch-import/template")
async def download_import_template():
    """下载 CSV 导入模板"""
    from fastapi.responses import Response
    return Response(
        content=CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=NDM_Device_Import_Template.csv"}
    )


@router.post("/batch-import")
async def batch_import_devices(file: UploadFile = File(...)):
    """批量导入设备（CSV 格式）"""
    # 读取并解析 CSV
    try:
        content = await file.read()
        text = content.decode("utf-8-sig")  # 兼容 BOM
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 解析失败：{str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV 文件为空")

    # 获取已有设备名集合（用于重名检测）
    existing_devices = {d.get("name", "") for d in load_devices_from_yaml()}

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, row in enumerate(rows):
        row_num = idx + 2  # CSV 行号（第1行是 header）
        # 规范化行数据：去除空白
        row_data = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

        name = row_data.get("name", "")
        ip = row_data.get("ip", "")
        dev_type = row_data.get("type", "")
        platform = row_data.get("platform", "")
        location = row_data.get("location", "")
        notes = row_data.get("notes", "")
        uplink_raw = row_data.get("uplink_ports", "")

        # 校验必填字段
        errors = []
        if not name:
            errors.append("设备名称为空")
        elif not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
            errors.append("设备名称包含非法字符")
        if not ip:
            errors.append("IP 地址为空")
        elif not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            errors.append("IP 地址格式无效")
        else:
            parts = ip.split('.')
            if any(int(p) > 255 for p in parts):
                errors.append("IP 地址值无效")
        if not dev_type:
            errors.append("设备类型为空")
        elif dev_type not in ['cisco_ios', 'cisco_ios_xe', 'cisco_ios_router', 'aruba_aoscx']:
            errors.append(f"不支持的设备类型：{dev_type}")

        if errors:
            results.append({"row": row_num, "name": name or "(空)", "status": "failed", "errors": errors})
            failed_count += 1
            continue

        # 重名检测
        if name in existing_devices:
            results.append({"row": row_num, "name": name, "status": "skipped", "errors": ["设备名称已存在"]})
            skipped_count += 1
            continue

        # 解析 uplink_ports（逗号分隔 -> 列表）
        uplink_ports = None
        if uplink_raw:
            uplink_ports = [p.strip() for p in uplink_raw.replace("，", ",").split(",") if p.strip()]

        # 构建设备字典
        device_dict = {
            "name": name,
            "ip": ip,
            "type": dev_type,
            "platform": platform or None,
            "location": location or None,
            "notes": notes or None,
            "uplink_ports": uplink_ports,
        }

        # 剔除 None 值字段
        device_dict = {k: v for k, v in device_dict.items() if v is not None}

        try:
            if not save_device_to_yaml(device_dict):
                results.append({"row": row_num, "name": name, "status": "failed", "errors": ["保存设备失败"]})
                failed_count += 1
            else:
                results.append({"row": row_num, "name": name, "status": "success", "errors": []})
                success_count += 1
                existing_devices.add(name)  # 更新重名检测集合
        except Exception as e:
            results.append({"row": row_num, "name": name, "status": "failed", "errors": [str(e)]})
            failed_count += 1

    return {
        "success": True,
        "total": len(rows),
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "results": results,
    }


@router.get("/{name}")
async def get_device(name: str):
    """获取单个设备详情"""
    devices = load_devices_from_yaml()
    for device in devices:
        if device.get("name") == name:
            return DeviceResponse(**device).model_dump()
    raise HTTPException(status_code=404, detail="设备不存在")


@router.post("/")
async def add_device(device: DeviceCreate):
    """添加设备"""
    # 检查设备名是否已存在
    devices = load_devices_from_yaml()
    for d in devices:
        if d.get("name") == device.name:
            raise HTTPException(status_code=400, detail="设备名称已存在")

    # 转换为字典并添加 ID
    device_dict = device.model_dump()
    if not save_device_to_yaml(device_dict):
        raise HTTPException(status_code=500, detail="保存设备失败")

    return {"success": True, "message": "设备添加成功", "device": device_dict}


@router.delete("/{name}")
async def delete_device(name: str):
    """删除设备"""
    if not delete_device_from_yaml(name):
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"success": True, "message": "设备删除成功"}


@router.patch("/{name}")
async def update_device(name: str, device: DeviceUpdate):
    """更新设备"""
    # 检查设备是否存在
    devices = load_devices_from_yaml()
    device_list = [d for d in devices if d.get("name") == name]

    if not device_list:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 更新字段
    for d in device_list:
        for key, value in device.model_dump().items():
            if value is not None:
                d[key] = value

    # 保存更新
    if not save_device_to_yaml(d):
        raise HTTPException(status_code=500, detail="保存设备失败")

    return {"success": True, "message": "设备更新成功", "device": d}
