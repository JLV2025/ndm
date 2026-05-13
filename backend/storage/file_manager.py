"""
存储管理模块
- 按周组织数据：YYYY-WW/{device-name}/
- 按设备独立保留最近 N 个周版本
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path


def get_week_dir(base_path: str) -> str:
    """获取当前周的目录名 YYYY-WW"""
    now = datetime.now()
    iso_cal = now.isocalendar()
    return f"{iso_cal[0]}-{iso_cal[1]:02d}"


def get_device_path(base_path: str, device_name: str, week: str) -> str:
    """获取设备数据路径"""
    return os.path.join(base_path, week, device_name)


def create_device_dir(base_path: str, device_name: str, week: str) -> str:
    """创建设备数据目录"""
    device_dir = get_device_path(base_path, device_name, week)
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


def keep_latest_versions_per_device(
    data_root: str,
    device_name: str,
    max_versions: int = 10
) -> list:
    """
    按设备独立保留最近的 N 个周版本

    Args:
        data_root: 数据根目录
        device_name: 设备名称
        max_versions: 保留的最大版本数
    """
    if not os.path.exists(data_root):
        return []

    # 获取该设备的所有周目录
    device_base = os.path.join(data_root, device_name)
    if not os.path.exists(device_base):
        return []

    week_dirs = []
    for d in os.listdir(device_base):
        full_path = os.path.join(device_base, d)
        if os.path.isdir(full_path):
            # 检查是否是 YYYY-WW 格式
            if re.match(r'^\d{4}-\d{2}$', d):
                week_dirs.append(d)

    # 按时间排序（升序）
    week_dirs.sort()

    # 删除过期的周目录
    deleted = []
    while len(week_dirs) > max_versions:
        old_week = week_dirs.pop(0)
        old_path = os.path.join(device_base, old_week)
        shutil.rmtree(old_path)
        deleted.append(old_week)

    return deleted


def cleanup_old_versions(data_root: str, max_versions: int = 10) -> dict:
    """
    清理所有设备的过期版本

    Args:
        data_root: 数据根目录
        max_versions: 保留的最大周数
    """
    deleted = {
        "weeks": [],
        "devices": []
    }

    if not os.path.exists(data_root):
        return deleted

    # 获取所有 YYYY-WW 格式的周目录
    week_dirs = []
    for d in os.listdir(data_root):
        full_path = os.path.join(data_root, d)
        if os.path.isdir(full_path):
            if re.match(r'^\d{4}-\d{2}$', d):
                week_dirs.append(d)

    week_dirs.sort()

    # 保留最近的 N 个周目录
    while len(week_dirs) > max_versions:
        old_week = week_dirs.pop(0)
        old_path = os.path.join(data_root, old_week)
        devices_in_week = [d for d in os.listdir(old_path)
                          if os.path.isdir(os.path.join(old_path, d))]
        deleted["weeks"].append(old_week)
        deleted["devices"].extend(devices_in_week)
        shutil.rmtree(old_path)

    return deleted
