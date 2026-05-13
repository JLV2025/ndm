"""
性能分析模块
- 接口状态分析
- 错误计数统计
- 利用率趋势
"""

import json
import re
from typing import Dict, List, Any
from collections import defaultdict


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self, interface_status: str, config: str = ""):
        self.interface_status = interface_status
        self.config = config
        self.interface_lines = [l for l in interface_status.splitlines() if l.strip()]

    def analyze(self) -> Dict[str, Any]:
        """执行所有分析"""
        results = {
            "device": self._get_device_name(),
            "timestamp": self._get_timestamp(),
            "interface_summary": self._analyze_interfaces(),
            "errors": self._analyze_errors(),
            "utilization": self._analyze_utilization()
        }
        return results

    def _get_device_name(self) -> str:
        """获取设备名"""
        for pattern in [r"^Router\s+(.+)", r"^Switch\s+(.+)"]:
            match = re.search(pattern, self.config, re.MULTILINE)
            if match:
                return match.group(1)
        return "unknown"

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def _analyze_interfaces(self) -> Dict[str, Any]:
        """分析接口"""
        if not self.interface_lines:
            return {
                "total": 0,
                "up": 0,
                "down": 0,
                "details": []
            }

        up_count = 0
        down_count = 0
        details = []

        # Cisco 输出格式：Gi0/1      up              up              1000Mb/s  Full  1000Mb/s
        # Aruba 输出格式类似
        for line in self.interface_lines:
            parts = line.split()
            # 至少需要 2 个部分（接口名和状态）
            if len(parts) >= 2:
                name = parts[0]
                status = parts[1]

                if "up" in status and "down" not in status:
                    up_count += 1
                elif "down" in status:
                    down_count += 1

                details.append({
                    "name": name,
                    "status": status,
                    "status_up": "up" in status and "down" not in status
                })

        return {
            "total": len(self.interface_lines),
            "up": up_count,
            "down": down_count,
            "details": details[:20]  # 只显示前 20 个
        }

    def _analyze_errors(self) -> Dict[str, Any]:
        """分析错误"""
        error_counts = defaultdict(int)

        for line in self.interface_lines:
            if "err-disabled" in line.lower():
                error_counts["err-disabled"] += 1
            if "discards" in line.lower():
                error_counts["discards"] += 1
            if "dropped" in line.lower():
                error_counts["dropped"] += 1
            if "overruns" in line.lower():
                error_counts["overruns"] += 1

        return dict(error_counts)

    def _analyze_utilization(self) -> Dict[str, Any]:
        """分析利用率（从配置中估算）"""
        utilization = {}

        # 从配置中提取接口负载信息
        load_matches = re.findall(r"load\s+average\s+:\s+\S+\s+(\d+\.?\d*)", self.config)
        if load_matches:
            utilization["load_averages"] = load_matches[:10]

        # 从配置中提取带宽信息
        bandwidth_info = re.findall(r"Bandwidth\s+(\d+)", self.config)
        if bandwidth_info:
            utilization["bandwidth_range"] = {
                "min": min(bandwidth_info),
                "max": max(bandwidth_info)
            }

        return utilization
