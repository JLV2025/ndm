#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
设备清单管理工具
支持：添加、修改、删除设备
"""

import os
import sys
import yaml
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DeviceManager:
    """设备清单管理器"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "devices.yaml")
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

    def list_devices(self):
        """列出所有设备"""
        if not self.devices:
            print("没有配置任何设备")
            return

        print("\n当前设备清单:")
        print("-" * 75)
        print(f"{'序号':<6} {'名称':<12} {'IP 地址':<18} {'位置':<6} {'类型':<12} {'版本':<12}")
        print("-" * 75)
        for i, device in enumerate(self.devices, 1):
            name = device.get("name", "N/A")
            ip = device.get("ip", "N/A")
            loc = device.get("location", "N/A")
            dev_type = device.get("type", "N/A")
            version = device.get("version", "")[:10]
            notes = device.get("notes", "无")[:8]
            print(f"{i:<6} {name:<12} {ip:<18} {loc:<6} {dev_type:<12} {version:<12} {notes}")
        print("-" * 75)

    def add_device(self):
        """添加新设备"""
        print("\n添加新设备:")
        print("=" * 40)

        # 获取设备名称
        while True:
            name = input("设备名称 (例如：CAB-01): ").strip()
            if name and name not in [d.get("name") for d in self.devices]:
                break
            if name in [d.get("name") for d in self.devices]:
                print("设备名称已存在，请重新输入")
            else:
                break

        # 获取 IP
        ip = input("IP 地址 (例如：192.168.1.10): ").strip()

        # 获取设备类型
        print("\n选择设备类型:")
        print("1. cisco_ios    - Cisco IOS/IOS-XE")
        print("2. aruba_osswitch - Aruba OS Switch")
        choice = input("请选择 (1 或 2): ").strip()
        if choice == "1":
            device_type = "cisco_ios"
        elif choice == "2":
            device_type = "aruba_osswitch"
        else:
            device_type = "cisco_ios"

        # 获取平台类型（可选）
        platform = input("平台类型 (可选，例如：cisco_c3725): ").strip() or "cisco_ios"

        # 获取备注（可选）
        notes = input("备注 (可选): ").strip()

        # 获取位置（用于排序和筛选）
        location = input("位置 (例如：BJQ): ").strip() or "N/A"

        # 获取用户名
        username = input("用户名 (例如：admin): ").strip()

        device = {
            "name": name,
            "ip": ip,
            "type": device_type,
            "platform": platform,
            "username": username,
            "notes": notes or "无",
            "location": location or "N/A",
            "version": ""  # 软件版本号，运行时填充
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

        # 获取设备名称
        current_name = device.get("name", "")
        name = input(f"设备名称 [{current_name}]: ").strip()
        if not name:
            name = current_name

        # 获取 IP
        current_ip = device.get("ip", "")
        ip = input(f"IP 地址 [{current_ip}]: ").strip()
        if not ip:
            ip = current_ip

        # 获取设备类型
        current_type = device.get("type", "")
        print("\n选择设备类型:")
        print("1. cisco_ios    - Cisco IOS/IOS-XE")
        print("2. aruba_osswitch - Aruba OS Switch")
        type_choice = input(f"当前：{current_type} | 请选择 (1 或 2，留空保持当前): ").strip()
        if type_choice == "1":
            device_type = "cisco_ios"
        elif type_choice == "2":
            device_type = "aruba_osswitch"
        else:
            device_type = current_type

        # 获取平台类型
        current_platform = device.get("platform", "")
        platform = input(f"平台类型 [{current_platform}]: ").strip()
        if not platform:
            platform = current_platform

        # 获取用户名
        current_username = device.get("username", "")
        username = input(f"用户名 [{current_username}]: ").strip()
        if not username:
            username = current_username

        # 获取备注
        current_notes = device.get("notes", "")
        notes = input(f"备注 [{current_notes}]: ").strip()
        if not notes:
            notes = current_notes

        # 获取位置
        current_location = device.get("location", "")
        location = input(f"位置 [{current_location}]: ").strip()
        if not location:
            location = current_location

        # 获取软件版本（可选）
        current_version = device.get("version", "")
        version = input(f"软件版本 [{current_version}]: ").strip()
        if not version:
            version = current_version

        # 更新设备
        device.update({
            "name": name,
            "ip": ip,
            "type": device_type,
            "platform": platform,
            "username": username,
            "notes": notes or "无",
            "location": location or "N/A",
            "version": version
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

    def update_username(self, index: int, new_username: str):
        """更新设备用户名"""
        if index < 0 or index >= len(self.devices):
            print("无效的设备索引")
            return

        self.devices[index]["username"] = new_username
        self._save()
        print(f"设备 {self.devices[index]['name']} 的用户名已更新")

    def update_device_version(self, index: int, new_version: str):
        """更新设备软件版本"""
        if index < 0 or index >= len(self.devices):
            print("无效的设备索引")
            return

        self.devices[index]["version"] = new_version
        self._save()
        print(f"设备 {self.devices[index]['name']} 的软件版本已更新")

    def run_menu(self):
        """运行交互式菜单"""
        while True:
            print("\n设备清单管理")
            print("=" * 50)
            print("1. 列出设备")
            print("2. 添加设备")
            print("3. 编辑设备")
            print("4. 删除设备")
            print("5. 更新用户名")
            print("6. 更新软件版本")
            print("7. 保存并退出")

            choice = input("\n请选择操作 (1-6): ").strip()

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
                    index = int(input("请输入要编辑的设备序号：").strip()) - 1
                    self.edit_device(index)
                except ValueError:
                    print("无效的输入")
            elif choice == "4":
                if not self.devices:
                    print("没有设备可删除")
                    continue
                self.list_devices()
                try:
                    index = int(input("请输入要删除的设备序号：").strip()) - 1
                    self.delete_device(index)
                except ValueError:
                    print("无效的输入")
            elif choice == "5":
                if not self.devices:
                    print("没有设备可更新")
                    continue
                self.list_devices()
                try:
                    index = int(input("请输入设备序号：").strip()) - 1
                    new_username = input("输入新用户名：").strip()
                    if new_username:
                        self.update_username(index, new_username)
                    else:
                        print("用户名不能为空")
                except ValueError:
                    print("无效的输入")
            elif choice == "6":
                print("退出设备管理")
                break
            elif choice == "7":
                print("退出设备管理")
                break
            else:
                print("无效的选择")


def main():
    """主函数"""
    manager = DeviceManager()
    manager.run_menu()


if __name__ == "__main__":
    main()
