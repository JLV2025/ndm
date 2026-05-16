"""设备清单管理工具"""

import os
import sys
import yaml
from typing import List, Dict, Optional

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.settings_loader import get_devices_config_path


class DeviceManager:
    """设备清单管理器"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or get_devices_config_path()
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
            }, f, allow_unicode=True, default_flow_style=False, Dumper=yaml.SafeDumper)

    def list_devices(self):
        """列出所有设备"""
        if not self.devices:
            print("没有配置任何设备")
            return

        print("\n当前设备清单:")
        print("-" * 90)
        print(f"{'序号':<6} {'名称':<14} {'IP 地址':<18} {'类型':<15} {'位置':<8} {'备注':<12}")
        print("-" * 90)
        for i, device in enumerate(self.devices, 1):
            name = device.get("name", "N/A")
            ip = device.get("ip", "N/A")
            loc = device.get("location", "N/A")
            dev_type = device.get("type", "N/A")[:12]
            notes = device.get("notes", "无")[:10]
            print(f"{i:<6} {name:<14} {ip:<18} {dev_type:<15} {loc:<8} {notes:<12}")
        print("-" * 90)

    def add_device(self):
        """添加新设备"""
        print("\n添加新设备:")
        print("=" * 40)

        # 获取设备名称
        while True:
            name = input("设备名称：").strip()
            if name and name not in [d.get("name") for d in self.devices]:
                break
            if name in [d.get("name") for d in self.devices]:
                print("设备名称已存在，请重新输入")
            else:
                break

        # 获取 IP
        ip = input("IP 地址：").strip()

        # 获取设备类型
        print("\n选择设备类型:")
        print("1. cisco_ios    - Cisco IOS/IOS-XE")
        print("2. aruba_aoscx - Aruba OS Switch")
        choice = input("请选择 (1 或 2): ").strip()
        if choice == "1":
            device_type = "cisco_ios"
        elif choice == "2":
            device_type = "aruba_aoscx"
        else:
            device_type = "cisco_ios"

        # 获取平台类型
        platform = input("平台类型 (可选): ").strip() or "cisco_ios"

        # 获取备注
        notes = input("备注 (可选): ").strip()

        # 获取位置
        location = input("位置 (例如：BJQ): ").strip() or "N/A"

        device = {
            "name": name,
            "ip": ip,
            "type": device_type,
            "platform": platform,
            "location": location or "N/A",
            "notes": notes or "无",
            "serial_number": "",
            "username": "",
            "password": ""
        }

        self.devices.append(device)
        self._save()
        print(f"\n设备 '{name}' 已添加")

    def edit_device(self, index: int):
        """编辑设备"""
        if index < 0 or index >= len(self.devices):
            print("无效的设备索引")
            return

        device = self.devices[index]
        print(f"\n编辑设备 '{device.get('name')}':")
        print("=" * 40)

        name = input(f"设备名称 [{device.get('name')}]: ").strip()
        if not name:
            name = device.get("name")

        ip = input(f"IP 地址 [{device.get('ip')}]: ").strip()
        if not ip:
            ip = device.get("ip")

        print("\n选择设备类型:")
        print("1. cisco_ios    - Cisco IOS/IOS-XE")
        print("2. aruba_aoscx - Aruba OS Switch")
        type_choice = input(f"当前：{device.get('type')} | 请选择 (1 或 2，留空保持当前): ").strip()
        if type_choice == "1":
            device_type = "cisco_ios"
        elif type_choice == "2":
            device_type = "aruba_aoscx"
        else:
            device_type = device.get("type")

        platform = input(f"平台类型 [{device.get('platform')}]: ").strip()
        notes = input(f"备注 [{device.get('notes')}]: ").strip()
        location = input(f"位置 [{device.get('location')}]: ").strip()

        device.update({
            "name": name,
            "ip": ip,
            "type": device_type,
            "platform": platform or device.get("platform"),
            "notes": notes or device.get("notes"),
            "location": location or device.get("location"),
        })

        self._save()
        print(f"\n设备 '{name}' 已更新")

    def delete_device(self, index: int):
        """删除设备"""
        if index < 0 or index >= len(self.devices):
            print("无效的设备索引")
            return

        device = self.devices[index]
        confirm = input(f"确认删除设备 '{device.get('name')}'? (y/n): ").strip().lower()

        if confirm == "y":
            del self.devices[index]
            self._save()
            print(f"设备 '{device.get('name')}' 已删除")
        else:
            print("取消删除")

    def run_menu(self):
        """运行交互式菜单"""
        while True:
            print("\n设备清单管理")
            print("=" * 50)
            print("1. 列出设备")
            print("2. 添加设备")
            print("3. 编辑设备")
            print("4. 删除设备")
            print("5. 保存并退出")

            choice = input("\n请选择操作 (1-5): ").strip()

            if choice == "1":
                self.list_devices()
            elif choice == "2":
                self.add_device()
            elif choice == "3":
                if not self.devices:
                    print("没有设备可编辑")
                    continue
                self.list_devices()
                try:
                    idx = int(input("请输入要编辑的设备序号：").strip()) - 1
                    self.edit_device(idx)
                except ValueError:
                    print("无效的输入")
            elif choice == "4":
                if not self.devices:
                    print("没有设备可删除")
                    continue
                self.list_devices()
                try:
                    idx = int(input("请输入要删除的设备序号：").strip()) - 1
                    self.delete_device(idx)
                except ValueError:
                    print("无效的输入")
            elif choice == "5":
                print("退出设备管理")
                break
            else:
                print("无效的选择")


def main():
    manager = DeviceManager()
    manager.run_menu()


if __name__ == "__main__":
    main()
