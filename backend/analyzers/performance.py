"""
性能分析模块
- 接口状态分析
- 错误计数统计
- 利用率解析
"""

import json
import re
from analyzers._helpers import extract_device_name, get_iso_timestamp
from typing import Dict, List, Any, Optional
from collections import defaultdict


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self, interface_status: str, config: str = "", device_type: str = "",
                 interface_utilization: str = "", uplink_ports: Optional[List[str]] = None):
        self.interface_status = interface_status
        self.config = config
        self.device_type = device_type
        self.interface_utilization = interface_utilization
        self.uplink_ports = set(uplink_ports or [])
        self.interface_lines = [l for l in interface_status.splitlines() if l.strip()]

    def analyze(self) -> Dict[str, Any]:
        """执行所有分析"""
        interface_summary = self._analyze_interfaces()
        utilization_data = self._analyze_utilization()
        details = interface_summary.get("details", [])
        self._enrich_port_details(details, utilization_data)

        results = {
            "device": extract_device_name(self.config),
            "timestamp": get_iso_timestamp(),
            "interface_summary": interface_summary,
            "errors": self._analyze_errors(),
            "utilization": self._build_utilization_summary(details)
        }
        return results

    # =========================================================================
    # 接口状态解析
    # =========================================================================

    def _analyze_interfaces(self) -> Dict[str, Any]:
        """根据设备类型分析接口状态"""
        if not self.interface_lines:
            return {"total": 0, "up": 0, "down": 0, "details": []}

        if self.device_type == "cisco_ios_router":
            return self._parse_cisco_ios_router()
        elif self.device_type == "cisco_ios":
            return self._parse_cisco_ios()
        elif self.device_type == "aruba_aoscx":
            return self._parse_aruba_cx()
        else:
            return self._parse_generic()

    def _parse_cisco_interface_status(self, skip_prefixes: tuple[str, ...], speed_offset: int) -> Dict[str, Any]:
        """Cisco IOS show interface status 通用解析

        speed_offset: Status 列到 Speed 列的偏移（路由器5列格式=1，交换机7列格式=3）
        skip_prefixes: 跳过的接口名前缀（如 ("vlan", "loopback")）
        """
        up_statuses = {"connected", "up"}
        down_statuses = {"notconnect", "disabled", "err-disabled", "down", "inactive", "monitoring", "admin"}

        up_count = 0
        down_count = 0
        details = []

        for line in self.interface_lines:
            parts = line.split()
            if len(parts) < 2:
                continue

            if parts[0].lower() in ("port", "interface"):
                continue

            name = parts[0]
            if any(name.lower().startswith(p) for p in skip_prefixes):
                continue

            # 找到 Status 列位置（通过关键字匹配）
            status_pos = None
            found_status = None
            for i, p in enumerate(parts[1:], start=1):
                p_lower = p.lower().rstrip(",")
                if p_lower in up_statuses or p_lower in down_statuses:
                    status_pos = i
                    found_status = p_lower
                    break

            if not found_status:
                found_status = parts[1] if len(parts) > 1 else "unknown"
                status_pos = 1

            # 描述: Port 之后、Status 之前的所有字段
            if status_pos > 2:
                description = " ".join(parts[1:status_pos])
            elif status_pos == 2:
                description = parts[1] if parts[1] != found_status else None
            else:
                description = None

            # Speed 按偏移量取列
            speed_raw = parts[status_pos + speed_offset] if status_pos + speed_offset < len(parts) else None
            speed = self._normalize_cisco_speed(speed_raw)

            # Type: Speed 的下一列
            port_type = parts[status_pos + speed_offset + 1] if status_pos + speed_offset + 1 < len(parts) else None

            is_up = found_status in up_statuses
            if is_up:
                up_count += 1
            elif found_status.lower() in down_statuses:
                down_count += 1

            details.append(self._build_port_detail(name, found_status, is_up, speed, None, port_type, description))

        return {"total": len(details), "up": up_count, "down": down_count, "details": details}

    def _parse_cisco_ios(self) -> Dict[str, Any]:
        """Cisco IOS 交换机 show interface status（7 列格式）

        列: Port  Name  Status  Vlan  Duplex  Speed  Type
        """
        return self._parse_cisco_interface_status(
            skip_prefixes=("vlan", "loopback"),
            speed_offset=3,
        )

    def _parse_cisco_ios_router(self) -> Dict[str, Any]:
        """Cisco IOS 路由器 show interface status（5 列格式）

        列: Port  Name  Status  Speed  Type
        """
        return self._parse_cisco_interface_status(
            skip_prefixes=("service-engine",),
            speed_offset=1,
        )

    @staticmethod
    def _normalize_cisco_speed(raw: Optional[str]) -> Optional[str]:
        """规范化Cisco speed值: a-1000→1000, 10G→10000, auto/Not Present→None"""
        if not raw:
            return None
        raw = raw.rstrip(",")
        # a-1000 → 1000, a-100 → 100
        m = re.match(r'^a-(\d+)$', raw)
        if m:
            return m.group(1)
        # 10G → 10000
        m = re.match(r'^(\d+)G$', raw)
        if m:
            return str(int(m.group(1)) * 1000)
        # 纯数字
        if raw.isdigit():
            return raw
        # auto, Not Present, -- 等
        if raw.lower() in ("auto", "not present", "--", ""):
            return None
        return raw

    def _parse_aruba_cx(self) -> Dict[str, Any]:
        """Aruba CX show interface brief

        列: Port | Native_VLAN | Mode | Type | Enabled | Status | [Reason] | Speed | Description
        Reason列在status=up时为空，导致后续列向左偏移。
        策略：找到Status列后，如果下一列为非纯数字文本则跳过。
        """
        up_count = 0
        down_count = 0
        disabled_count = 0
        details = []
        header_parsed = False
        col_index = {}

        for line in self.interface_lines:
            parts = line.split()
            if len(parts) < 2:
                continue

            if all(c in "- " for c in line.strip()):
                continue

            headers_lower = [p.lower().rstrip(",") for p in parts]

            if not header_parsed:
                if "status" in headers_lower and ("port" in headers_lower or "interface" in headers_lower):
                    for i, h in enumerate(headers_lower):
                        if h in ("port",):
                            col_index["port"] = i
                        elif h in ("vlan", "native"):
                            col_index["native_vlan"] = i
                        elif h in ("mode",):
                            col_index["mode"] = i
                        elif h in ("type",):
                            col_index["type"] = i
                        elif h in ("enabled",):
                            col_index["enabled"] = i
                        elif h in ("status",):
                            col_index["status"] = i
                        elif h in ("speed",):
                            col_index["speed"] = i
                        elif h in ("description",):
                            col_index["description"] = i
                    header_parsed = True
                continue

            if parts[0].lower().startswith("vlan") or parts[0].lower().startswith("loopback"):
                continue

            name = parts[0]

            # 通过header索引取列
            def _col(key):
                idx = col_index.get(key)
                return parts[idx] if idx is not None and idx < len(parts) else None

            # status 始终在 header 定义的索引处
            status = _col("status")
            if status is None:
                for p in parts[1:]:
                    pl = p.lower()
                    if pl in ("up", "down", "administratively"):
                        status = pl
                        break
                if status is None:
                    status = "unknown"

            status_lower = status.lower() if status else "unknown"
            is_up = status_lower == "up"

            if is_up:
                up_count += 1
            elif status_lower in ("down", "administratively"):
                if status_lower == "administratively":
                    disabled_count += 1
                else:
                    down_count += 1

            # 提取 speed/mode/type/description
            # 找到 status 的实际位置（可能不等于 header 索引）
            status_pos = None
            for i, p in enumerate(parts):
                if p.lower() == status_lower:
                    status_pos = i
                    break

            # speed: Description总是最后一列，speed在Description之前
            # 从后向前扫描，找到第一个匹配数字或"--"的字段
            speed = None
            for i in range(len(parts) - 1, status_pos, -1):
                p = parts[i]
                if re.match(r'^[\d,]+$', p) or p == '--':
                    speed = p
                    break

            # 如果header索引的speed有效则优先使用
            header_speed = _col("speed")
            if header_speed and re.match(r'^[\d,]+$', header_speed):
                speed = header_speed

            mode = _col("mode")
            port_type = _col("type")
            desc = None
            # 描述通常在最后
            if len(parts) > 6:
                last = parts[-1]
                if last not in (speed, mode, port_type):
                    desc = last

            native_vlan = _col("native_vlan")

            detail = self._build_port_detail(
                name, status_lower, is_up, speed, mode, port_type, desc,
                native_vlan=native_vlan
            )
            details.append(detail)

        return {
            "total": len(details),
            "up": up_count,
            "down": down_count + disabled_count,
            "details": details
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

            is_up = "up" in status.lower() or "connected" in status.lower()
            details.append(self._build_port_detail(name, status, is_up))

        return {"total": len(details), "up": up_count, "down": down_count, "details": details}

    # =========================================================================
    # 端口详情构建
    # =========================================================================

    def _build_port_detail(self, name: str, status: str, is_up: bool,
                           speed: Optional[str] = None, mode: Optional[str] = None,
                           port_type: Optional[str] = None, description: Optional[str] = None,
                           native_vlan: Optional[str] = None) -> Dict[str, Any]:
        """构建单个端口详情"""
        is_uplink = name in self.uplink_ports

        detail = {
            "name": name,
            "status": status,
            "status_up": is_up,
            "is_uplink": is_uplink,
        }
        if speed is not None and speed != "--":
            detail["speed"] = speed
        if mode is not None and mode != "--":
            detail["mode"] = mode
        if port_type is not None and port_type != "--":
            detail["type"] = port_type
        if description is not None and description != "--":
            detail["description"] = description.strip()
        if native_vlan is not None and native_vlan != "--":
            detail["native_vlan"] = native_vlan

        return detail

    # =========================================================================
    # 错误分析
    # =========================================================================

    def _analyze_errors(self) -> Dict[str, Any]:
        """分析接口错误"""
        error_counts = defaultdict(int)
        error_ports = defaultdict(list)

        for line in self.interface_lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            port_name = parts[0]

            line_lower = line.lower()
            if "err-disabled" in line_lower:
                error_counts["err-disabled"] += 1
                error_ports["err-disabled"].append(port_name)
            if "discards" in line_lower:
                error_counts["discards"] += 1
                error_ports["discards"].append(port_name)
            if "dropped" in line_lower:
                error_counts["dropped"] += 1
                error_ports["dropped"].append(port_name)
            if "overruns" in line_lower:
                error_counts["overruns"] += 1
                error_ports["overruns"].append(port_name)

        return {"counts": dict(error_counts), "ports": dict(error_ports)}

    # =========================================================================
    # 利用率解析
    # =========================================================================

    def _analyze_utilization(self) -> Dict[str, Dict[str, Any]]:
        """解析 interface-utilization.raw 获取每端口流量数据

        Returns:
            { port_name: { rx_mbps, tx_mbps, total_mbps, rx_util_pct, ... } }
        """
        if not self.interface_utilization:
            return {}

        if self.device_type == "aruba_aoscx":
            return self._parse_aruba_utilization()
        if self.device_type in ("cisco_ios", "cisco_ios_router"):
            return self._parse_cisco_utilization()
        return {}

    def _parse_aruba_utilization(self) -> Dict[str, Dict[str, Any]]:
        """解析 Aruba CX show interface utilization 表格"""
        result = {}
        header_lines_seen = 0

        for line in self.interface_utilization.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # 跳过分隔线
            if all(c in "- " for c in stripped):
                continue

            # 检测并跳过表头行（跨两行: "RX|TX|Total" + "Mbps|KPkt/s|Util%"）
            if header_lines_seen < 2:
                is_header = (
                    ("RX" in stripped and "TX" in stripped) or
                    ("Mbps" in stripped and "Util%" in stripped) or
                    ("Interface" in stripped and "Interval" in stripped)
                )
                if is_header:
                    header_lines_seen += 1
                    continue

            parts = stripped.split()
            if len(parts) < 11:
                continue

            # 端口名：第一个字段，最多跟一个 LAG 标记
            # 如: "1/1/1" 或 "1/1/5" + "- lag1" 格式（parts[0]="1/1/5", parts[1]="-", parts[2]="lag1"）
            port_name = parts[0]
            data_offset = 1

            # 处理 "1/1/5  - lag1" 格式：跳过 "-" 和 "lagN" 标记
            if len(parts) > 2 and parts[1] == "-" and parts[2].startswith("lag"):
                port_name = parts[0]  # 主端口名
                data_offset = 3

            data = parts[data_offset:]

            # 至少需要: interval, rx_mbps, rx_kpps, rx_util, tx_mbps, tx_kpps, tx_util, total_mbps, total_kpps, total_util
            if len(data) < 10:
                continue

            try:
                result[port_name] = {
                    "interval_sec": int(data[0]),
                    "rx_mbps": float(data[1]),
                    "rx_kpps": float(data[2]),
                    "rx_util_pct": float(data[3]),
                    "tx_mbps": float(data[4]),
                    "tx_kpps": float(data[5]),
                    "tx_util_pct": float(data[6]),
                    "total_mbps": float(data[7]),
                    "total_kpps": float(data[8]),
                    "total_util_pct": float(data[9]),
                }
            except (ValueError, IndexError):
                continue

        return result

    def _parse_cisco_utilization(self) -> Dict[str, Dict[str, Any]]:
        """解析 Cisco IOS show interfaces | include rate|load|packets 输出

        每个接口输出块:
            reliability 255/255, txload 1/255, rxload 1/255
            5 minute input rate 7000 bits/sec, 7 packets/sec
            5 minute output rate 12000 bits/sec, 6 packets/sec

        Cisco输出不含接口名，这里只能按块顺序存储（与interface-status顺序对齐）。
        由于不确定性高，此解析为基本实现。
        """
        result = {}
        blocks = []
        current_block = None

        for line in self.interface_utilization.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # reliability行标志新接口块开始
            if stripped.startswith("reliability"):
                if current_block:
                    blocks.append(current_block)
                current_block = {"input_rate_bps": 0, "input_rate_pps": 0,
                                 "output_rate_bps": 0, "output_rate_pps": 0}
                # 解析 rxload/txload
                m = re.search(r'rxload\s+(\d+)/255', stripped)
                if m:
                    current_block["rxload"] = int(m.group(1))
                m = re.search(r'txload\s+(\d+)/255', stripped)
                if m:
                    current_block["txload"] = int(m.group(1))
                continue

            if current_block is None:
                continue

            # 5 minute input rate
            m = re.search(r'5 minute input rate\s+(\d+)\s+bits/sec,\s+(\d+)\s+packets/sec', stripped)
            if m:
                current_block["input_rate_bps"] = int(m.group(1))
                current_block["input_rate_pps"] = int(m.group(2))
                continue

            # 5 minute output rate
            m = re.search(r'5 minute output rate\s+(\d+)\s+bits/sec,\s+(\d+)\s+packets/sec', stripped)
            if m:
                current_block["output_rate_bps"] = int(m.group(1))
                current_block["output_rate_pps"] = int(m.group(2))
                continue

        if current_block:
            blocks.append(current_block)

        # 按索引存储，后续通过_enrich_port_details与status列表对齐
        for i, block in enumerate(blocks):
            result[f"_cisco_block_{i}"] = {
                "rx_mbps": round(block["input_rate_bps"] / 1_000_000, 4),
                "rx_pps": block["input_rate_pps"],
                "tx_mbps": round(block["output_rate_bps"] / 1_000_000, 4),
                "tx_pps": block["output_rate_pps"],
                "rxload": block.get("rxload", 0),
                "txload": block.get("txload", 0),
            }

        return result

    # =========================================================================
    # 数据合并
    # =========================================================================

    def _enrich_port_details(self, details: List[Dict[str, Any]],
                             utilization_data: Dict[str, Dict[str, Any]]):
        """将利用率数据合并到端口详情中"""
        for i, detail in enumerate(details):
            port_name = detail.get("name", "")

            util = utilization_data.get(port_name)

            # Cisco设备按索引对齐
            if util is None and self.device_type in ("cisco_ios", "cisco_ios_router"):
                block_key = f"_cisco_block_{i}"
                util = utilization_data.get(block_key)

            if util:
                for key in ("rx_mbps", "tx_mbps", "total_mbps",
                            "rx_util_pct", "tx_util_pct", "total_util_pct",
                            "rx_kpps", "tx_kpps", "total_kpps",
                            "rx_pps", "tx_pps", "rxload", "txload",
                            "interval_sec"):
                    if key in util:
                        detail[key] = util[key]

    def _build_utilization_summary(self, details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从已合并的端口详情中构建利用率汇总"""
        if not details:
            return {}

        total_rx_mbps = 0.0
        total_tx_mbps = 0.0
        max_util_port = None
        max_util = 0

        for detail in details:
            rx = detail.get("rx_mbps", 0) or 0
            tx = detail.get("tx_mbps", 0) or 0
            total_rx_mbps += rx
            total_tx_mbps += tx
            pct = detail.get("total_util_pct", 0) or (rx + tx)
            if pct > max_util:
                max_util = pct
                max_util_port = detail.get("name")

        return {
            "total_rx_mbps": round(total_rx_mbps, 2),
            "total_tx_mbps": round(total_tx_mbps, 2),
            "max_util_port": max_util_port,
            "max_util_pct": max_util,
            "port_count_with_traffic": sum(1 for d in details if (d.get("rx_mbps") or 0) > 0 or (d.get("tx_mbps") or 0) > 0)
        }
