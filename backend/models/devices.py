"""设备数据模型"""

import os
import yaml
import hashlib
import base64
import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from enum import Enum


class Device:
    """设备模型"""

    def __init__(self, name: str, ip: str, device_type: str = "cisco_ios"):
        self.name = name
        self.ip = ip
        self.type = device_type
        self.platform = ""
        self.location = ""
        self.notes = ""
        self.serial_number = ""
        self.username = ""
        self.password = ""

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "ip": self.ip,
            "type": self.type,
            "platform": self.platform,
            "location": self.location,
            "notes": self.notes,
            "serial_number": self.serial_number,
            "username": self.username,
            "password": self.password
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Device":
        """从字典创建"""
        device = cls(
            name=data.get("name", ""),
            ip=data.get("ip", ""),
            device_type=data.get("type", "cisco_ios")
        )
        device.platform = data.get("platform", "")
        device.location = data.get("location", "")
        device.notes = data.get("notes", "")
        device.serial_number = data.get("serial_number", "")
        device.username = data.get("username", "")
        device.password = data.get("password", "")
        return device


class DeviceList:
    """设备列表管理"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.devices: List[Device] = []
        self._load()

    def _load(self):
        """加载设备列表"""
        if not os.path.exists(self.config_path):
            self.devices = []
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            for device_data in data.get("devices", []):
                self.devices.append(Device.from_dict(device_data))

    def _save(self):
        """保存设备列表"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "devices": [d.to_dict() for d in self.devices],
                "format_version": "1.0"
            }, f, allow_unicode=True, default_flow_style=False)

    def list_devices(self) -> List[Device]:
        """返回设备列表"""
        return self.devices

    def get_device_by_name(self, name: str) -> Optional[Device]:
        """根据名称获取设备"""
        for device in self.devices:
            if device.name == name:
                return device
        return None

    def add_device(self, device: Device):
        """添加设备"""
        for d in self.devices:
            if d.name == device.name:
                print(f"设备 {device.name} 已存在")
                return
        self.devices.append(device)
        self._save()

    def remove_device(self, name: str) -> bool:
        """删除设备"""
        for i, device in enumerate(self.devices):
            if device.name == name:
                del self.devices[i]
                self._save()
                return True
        return False

    def update_device(self, name: str, updates: Dict):
        """更新设备"""
        for device in self.devices:
            if device.name == name:
                device.__dict__.update(updates)
                self._save()
                return True
        return False
