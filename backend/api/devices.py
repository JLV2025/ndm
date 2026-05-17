"""设备管理 API 路由"""

from fastapi import APIRouter, HTTPException, Form, File, UploadFile
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional
import os
import yaml
import json
import re
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
        if v and v not in ['cisco_ios', 'cisco_ios_xe', 'aruba_aoscx']:
            raise ValueError('不支持的设备类型，仅支持 cisco_ios / cisco_ios_xe / aruba_aoscx')
        return v


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    type: Optional[str] = None
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
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
        if v and v not in ['cisco_ios', 'cisco_ios_xe', 'aruba_aoscx']:
            raise ValueError('不支持的设备类型，仅支持 cisco_ios / cisco_ios_xe / aruba_aoscx')
        return v


class DeviceResponse(BaseModel):
    name: str
    ip: str
    type: str
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
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
