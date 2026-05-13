"""设备管理器"""

import os
import yaml
from typing import Dict, List, Optional


class DeviceManager:
    """设备管理器"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "..", "config", "devices.yaml")
        self.devices: List[Dict] = []
        self._load()

    def _load(self):
        """加载设备清单"""
        if not os.path.exists(self.config_path):
            self.devices = []
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            self.devices = data.get("devices", [])

    def _save(self):
        """保存设备清单"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "devices": self.devices,
                "format_version": "1.0"
            }, f, allow_unicode=True, default_flow_style=False)

    def list_devices(self) -> List[Dict]:
        """列出所有设备"""
        return self.devices.copy()

    def get_device_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取设备"""
        for device in self.devices:
            if device.get("name") == name:
                return device.copy()
        return None

    def add_device(self, device: Dict) -> bool:
        """添加设备"""
        for d in self.devices:
            if d.get("name") == device.get("name"):
                print(f"设备 {device.get('name')} 已存在")
                return False

        self.devices.append(device)
        self._save()
        return True

    def delete_device(self, name: str) -> bool:
        """删除设备"""
        for i, device in enumerate(self.devices):
            if device.get("name") == name:
                del self.devices[i]
                self._save()
                return True
        return False

    def update_device(self, name: str, updates: Dict) -> bool:
        """更新设备"""
        for device in self.devices:
            if device.get("name") == name:
                device.update(updates)
                self._save()
                return True
        return False

    def update_serial_number(self, name: str, serial_number: str) -> bool:
        """更新设备序列号"""
        return self.update_device(name, {"serial_number": serial_number})

    def update_version(self, name: str, version: str) -> bool:
        """更新设备版本"""
        return self.update_device(name, {"version": version})

    def search_devices(self, location: str = None, notes: str = None) -> List[Dict]:
        """搜索设备"""
        result = self.devices.copy()

        if location:
            result = [d for d in result if d.get("location", "").lower() == location.lower()]

        if notes:
            result = [d for d in result if notes.lower() in d.get("notes", "").lower()]

        return result

    def get_all_fields(self) -> List[str]:
        """获取所有可用字段"""
        fields = ["name", "ip", "type", "platform", "location", "notes", "serial_number", "version", "username"]
        return fields
