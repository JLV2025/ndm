"""设备清单管理工具 — SQLite 数据源"""

import os
import sys
import yaml

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage import init_db
from storage.device_dal import (
    get_all_devices,
    get_device_by_name,
    create_device,
    update_device,
    delete_device,
    device_exists,
)

# 初始化数据库
_data_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
init_db(_data_root)


class DeviceManager:
    """设备清单管理器"""

    def __init__(self):
        self._devices_cache: list = []

    def _refresh(self):
        self._devices_cache = get_all_devices()

    @property
    def devices(self):
        self._refresh()
        return self._devices_cache

    def export_yaml(self, yaml_path: str = None):
        """导出设备清单到 YAML（备份）"""
        if yaml_path is None:
            cfg_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config",
            )
            yaml_path = os.path.join(cfg_dir, "devices.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"devices": self.devices, "format_version": "1.0"},
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                Dumper=yaml.SafeDumper,
            )
        print(f"已导出 {len(self.devices)} 台设备到 {yaml_path}")

    def list_devices(self):
        """列出所有设备"""
        devs = self.devices
        if not devs:
            print("没有配置任何设备")
            return

        print("\n当前设备清单:")
        print("-" * 90)
        print(f"{'序号':<6} {'名称':<14} {'IP 地址':<18} {'类型':<15} {'位置':<8} {'备注':<12}")
        print("-" * 90)
        for i, d in enumerate(devs, 1):
            name = d.get("name", "N/A")
            ip = d.get("ip", "N/A")
            loc = d.get("location", "N/A")
            dev_type = d.get("type", "N/A")[:12]
            notes = d.get("notes", "无")[:10]
            print(f"{i:<6} {name:<14} {ip:<18} {dev_type:<15} {loc:<8} {notes:<12}")
        print("-" * 90)

    def add_device(self):
        """添加新设备"""
        print("\n添加新设备:")
        print("=" * 40)

        while True:
            name = input("设备名称：").strip()
            if name and not device_exists(name):
                break
            if device_exists(name):
                print("设备名称已存在，请重新输入")

        ip = input("IP 地址：").strip()
        print("\n选择设备类型:")
        print("1. cisco_ios    - Cisco IOS/IOS-XE")
        print("2. aruba_aoscx - Aruba OS Switch")
        choice = input("请选择 (1 或 2): ").strip()
        device_type = "cisco_ios" if choice != "2" else "aruba_aoscx"
        platform = input("平台类型 (可选): ").strip() or "cisco_ios"
        notes = input("备注 (可选): ").strip()
        location = input("位置 (例如：BJQ): ").strip() or "N/A"

        device = {
            "name": name, "ip": ip, "type": device_type,
            "platform": platform, "location": location or "N/A",
            "notes": notes or "无",
        }
        create_device(device)
        print(f"\n设备 '{name}' 已添加")

    def edit_device(self, index: int):
        """编辑设备"""
        devs = self.devices
        if index < 0 or index >= len(devs):
            print("无效的设备索引")
            return

        d = devs[index]
        name = d["name"]
        print(f"\n编辑设备 '{name}':")
        print("=" * 40)

        new_name = input(f"设备名称 [{name}]: ").strip()
        ip = input(f"IP 地址 [{d.get('ip')}]: ").strip()
        print(f"\n当前类型: {d.get('type')}")
        print("1. cisco_ios    2. aruba_aoscx")
        tc = input("请选择 (留空保持当前): ").strip()
        notes = input(f"备注 [{d.get('notes', '')}]: ").strip()
        location = input(f"位置 [{d.get('location', '')}]: ").strip()

        updates = {}
        if new_name:
            updates["name"] = new_name
        if ip:
            updates["ip"] = ip
        if tc == "1":
            updates["type"] = "cisco_ios"
        elif tc == "2":
            updates["type"] = "aruba_aoscx"
        if notes:
            updates["notes"] = notes
        if location:
            updates["location"] = location

        if updates:
            update_device(name, updates)
            print(f"\n设备 '{name}' 已更新")

    def delete_device(self, index: int):
        """删除设备"""
        devs = self.devices
        if index < 0 or index >= len(devs):
            print("无效的设备索引")
            return
        name = devs[index]["name"]
        confirm = input(f"确认删除设备 '{name}'？(y/n): ").strip().lower()
        if confirm == "y":
            delete_device(name)
            print(f"设备 '{name}' 已删除")


def main():
    manager = DeviceManager()

    while True:
        print("\n" + "=" * 60)
        print("设备管理工具")
        print("=" * 60)
        print("1. 列出所有设备")
        print("2. 添加设备")
        print("3. 编辑设备")
        print("4. 删除设备")
        print("5. 导出到 YAML（备份）")
        print("6. 退出")
        print("=" * 60)
        choice = input("请选择操作 (1/2/3/4/5/6): ").strip()

        if choice == "1":
            manager.list_devices()
        elif choice == "2":
            manager.add_device()
        elif choice == "3":
            manager.list_devices()
            try:
                idx = int(input("请输入要编辑的设备序号: ").strip()) - 1
                manager.edit_device(idx)
            except ValueError:
                print("无效的输入")
        elif choice == "4":
            manager.list_devices()
            try:
                idx = int(input("请输入要删除的设备序号: ").strip()) - 1
                manager.delete_device(idx)
            except ValueError:
                print("无效的输入")
        elif choice == "5":
            manager.export_yaml()
        elif choice == "6":
            print("再见！")
            break
        else:
            print("无效的选择")


if __name__ == "__main__":
    main()
