"""配置保存服务"""

import os
import json
from datetime import datetime
from typing import Dict


class ConfigSaver:
    """配置保存器"""

    def __init__(self, data_root: str, device_name: str, week: str):
        self.data_root = data_root
        self.device_name = device_name
        self.week = week
        self.device_dir = os.path.join(data_root, device_name, week)
        os.makedirs(self.device_dir, exist_ok=True)

    def save_config(
        self,
        running_config: str,
        startup_config: str,
        logs: str,
        interface_status: str,
        version_info: str,
        interface_utilization: str
    ) -> None:
        """保存原始配置"""
        with open(os.path.join(self.device_dir, "running-config.raw"), "w", encoding="utf-8") as f:
            f.write(running_config)

        with open(os.path.join(self.device_dir, "startup-config.raw"), "w", encoding="utf-8") as f:
            f.write(startup_config)

        with open(os.path.join(self.device_dir, "logs.raw"), "w", encoding="utf-8") as f:
            f.write(logs)

        with open(os.path.join(self.device_dir, "interface-status.raw"), "w", encoding="utf-8") as f:
            f.write(interface_status)

        with open(os.path.join(self.device_dir, "version.raw"), "w", encoding="utf-8") as f:
            f.write(version_info)

        with open(os.path.join(self.device_dir, "interface-utilization.raw"), "w", encoding="utf-8") as f:
            f.write(interface_utilization)

    def save_analysis(
        self,
        validation_results: str,
        performance_results: str,
        change_results: str
    ) -> None:
        """保存分析结果"""
        with open(os.path.join(self.device_dir, "validation.json"), "w", encoding="utf-8") as f:
            f.write(validation_results)

        with open(os.path.join(self.device_dir, "performance.json"), "w", encoding="utf-8") as f:
            f.write(performance_results)

        with open(os.path.join(self.device_dir, "change.json"), "w", encoding="utf-8") as f:
            f.write(change_results)

    def save_summary(self, summary: str) -> None:
        """保存摘要"""
        with open(os.path.join(self.device_dir, "summary.txt"), "w", encoding="utf-8") as f:
            f.write(summary)

    def get_summary(self) -> Dict:
        """获取摘要信息"""
        summary_path = os.path.join(self.device_dir, "summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                return {"content": f.read()}
        return {}
