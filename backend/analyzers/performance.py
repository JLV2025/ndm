"""
性能分析模块
- 接口状态分析
- 错误计数统计
- 利用率趋势
"""

import json
from analyzers._helpers import extract_device_name, get_iso_timestamp
import re
from typing import Dict, List, Any
from collections import defaultdict


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self, interface_status: str, config: str = "", device_type: str = ""):
        self.interface_status = interface_status
        self.config = config
        self.device_type = device_type
        self.interface_lines = [l for l in interface_status.splitlines() if l.strip()]

    def analyze(self) -> Dict[str, Any]:
        """执行所有分析"""
        results = {
            "device": extract_device_name(self.config),
            "timestamp": get_iso_timestamp(),
            "interface_summary": self._analyze_interfaces(),
            "errors": self._analyze_errors(),
            "utilization": self._analyze_utilization()
        }
        return results


    def _analyze_interfaces(self) -> Dict[str, Any]:
        """根据设备类型分析接口状态"""
        if not self.interface_lines:
            return {"total": 0, "up": 0, "down": 0, "details": []}

        if self.device_type == "cisco_ios":
            return self._parse_cisco_ios()
        elif self.device_type == "aruba_aoscx":
            return self._parse_aruba()
        else:
            return self._parse_generic()

    def _parse_cisco_ios(self) -> Dict[str, Any]:
        """Cisco IOS show interface status 格式
        Port      Name               Status       Vlan       Duplex Speed Type
        Gi1/0/1                      connected    1          a-full a-1000 10/100/1000BaseTX
        Gi1/0/2   Uplink to Core     notconnect   1          auto   auto   10/100/1000BaseTX
        """
        up_statuses = {"connected", "up"}
        down_statuses = {"notconnect", "disabled", "err-disabled", "down", "inactive", "monitoring"}

        up_count = 0
        down_count = 0
        details = []

        for line in self.interface_lines:
            parts = line.split()
            if len(parts) < 2:
                continue

            # 跳过表头行
            if parts[0].lower() in ("port", "interface"):
                continue

            name = parts[0]
            # Cisco IOS status 通常在位置 1（名称列为空时）或根据内容推断
            # 检查 parts 中是否有已知状态值
            status = parts[1] if len(parts) >= 2 else ""
            found_status = None
            for p in parts[1:5]:
                p_lower = p.lower().rstrip(",")
                if p_lower in up_statuses or p_lower in down_statuses:
                    found_status = p_lower
                    break

            if found_status:
                status = found_status
                if status in up_statuses:
                    up_count += 1
                elif status in down_statuses:
                    down_count += 1
            else:
                # 无法识别状态，仍记录
                status = parts[1]

            details.append({
                "name": name,
                "status": status,
                "status_up": status in up_statuses
            })

        return {
            "total": len(self.interface_lines),
            "up": up_count,
            "down": down_count,
            "details": details[:20]
        }

    def _parse_aruba(self) -> Dict[str, Any]:
        """Aruba show interface brief / show interfaces brief 格式
        Port        Type           Speed    Mode    Status
        1/1/1       1000BASE-T     auto     auto    up

        或 Aruba CX:
        Port        Type           Speed    Mode    Status  Flow Ctrl  MDI
        -------------------------------------------------------------------
        1/1/1       1000BASE-T     auto     auto    up      off        auto

        或 Aruba OS show interfaces brief:
        Status and Counters - Port Status
        Port  Type        ... Status Mode ...
        1     1000BASE-T   ... Up     1000FDx ...
        """
        up_count = 0
        down_count = 0
        details = []
        status_col_index = None

        for line in self.interface_lines:
            parts = line.split()
            if len(parts) < 2:
                continue

            # 检测表头行，找到 Status 列位置
            headers = [p.lower().rstrip(",") for p in parts]
            if "status" in headers:
                status_col_index = headers.index("status")
                continue

            # 跳过分隔线
            if all(c in "- " for c in line.strip()):
                continue

            name = parts[0]
            status = "unknown"

            if status_col_index is not None and status_col_index < len(parts):
                status = parts[status_col_index].lower()
            else:
                # 回退：查找包含 up/down 的部分
                for p in parts[1:]:
                    p_lower = p.lower()
                    if p_lower in ("up", "down", "administratively"):
                        status = p_lower
                        break

            is_up = status == "up"
            if is_up:
                up_count += 1
            elif status in ("down", "administratively"):
                down_count += 1

            details.append({
                "name": name,
                "status": status,
                "status_up": is_up
            })

        return {
            "total": len(self.interface_lines),
            "up": up_count,
            "down": down_count,
            "details": details[:20]
        }

    def _parse_generic(self) -> Dict[str, Any]:
        """通用回退解析"""
        up_count = 0
        down_count = 0
        details = []

        for line in self.interface_lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            if parts[0].lower() in ("port", "interface", "name"):
                continue

            name = parts[0]
            status = "unknown"
            for p in parts[1:]:
                p_lower = p.lower()
                if p_lower in ("up", "connected"):
                    status = p_lower
                    up_count += 1
                    break
                elif p_lower in ("down", "notconnect", "disabled", "err-disabled"):
                    status = p_lower
                    down_count += 1
                    break

            details.append({
                "name": name,
                "status": status,
                "status_up": "up" in status.lower() or "connected" in status.lower()
            })

        return {
            "total": len(self.interface_lines),
            "up": up_count,
            "down": down_count,
            "details": details[:20]
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
