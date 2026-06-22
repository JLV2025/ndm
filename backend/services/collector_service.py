"""配置收集服务"""

import os
import json
import re
import sys
import traceback
import yaml
import threading
from typing import Dict, List
from datetime import datetime

def _get_device_connection():
    """延迟导入 DeviceConnection 以支持 mocking"""
    from collectors.base import DeviceConnection
    return DeviceConnection
from analyzers.config_validator import ConfigValidator
from analyzers.performance import PerformanceAnalyzer
from analyzers.change_detector import ChangeDetector
from utils.settings_loader import load_settings, load_devices, get_devices_config_path
from utils.password import password_manager
from storage.file_manager import (
    get_week_dir, keep_latest_versions_per_device
)
from models.devices import Device


# 全局收集进度追踪
_progress_lock = threading.Lock()
_collection_progress: Dict[str, Dict] = {}


def get_collection_progress(device_name: str) -> Dict | None:
    """获取设备收集进度（线程安全）"""
    with _progress_lock:
        return _collection_progress.get(device_name)


def _set_progress(device_name: str, step: str, error: str = ""):
    """设置设备收集进度（线程安全）"""
    with _progress_lock:
        _collection_progress[device_name] = {
            "step": step,
            "started_at": datetime.now().isoformat(),
            "error": error,
        }


def _clear_progress(device_name: str):
    """清除设备收集进度"""
    with _progress_lock:
        _collection_progress.pop(device_name, None)


def _is_aruba_device(device_type: str) -> bool:
    """判断是否为 Aruba 设备（兼容多种类型名）"""
    return device_type == "aruba_aoscx"


def _is_router_device(device_type: str) -> bool:
    """判断是否为 Cisco IOS 路由器"""
    return device_type == "cisco_ios_router"


def _strip_ansi(text: str) -> str:
    """去除 ANSI 转义码和终端控制字符"""
    # ANSI escape sequences: ESC[...m, ESC[...K, etc.
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # 其他控制字符 (保留 \r\n)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text


def _extract_shutdown_ports(config_text: str, norm_fn) -> set:
    """从 running-config 中提取所有 admin down (shutdown) 端口的规范化名称"""
    shutdown: set = set()
    current_iface: str | None = None
    is_shutdown: bool = False
    for line in config_text.splitlines():
        if_match = re.match(r'^interface\s+(\S+)', line)
        if if_match:
            if current_iface and is_shutdown:
                shutdown.add(norm_fn(current_iface))
            current_iface = if_match.group(1)
            is_shutdown = False
        elif re.match(r'^\s*shutdown\s*$', line):
            is_shutdown = True
        elif re.match(r'^\s*no\s+shutdown\s*$', line):
            is_shutdown = False
    if current_iface and is_shutdown:
        shutdown.add(norm_fn(current_iface))
    return shutdown


def extract_software_version(version_output: str, device_type: str) -> str:
    """从 show version 输出中提取软件版本号"""
    version_output = _strip_ansi(version_output)
    lines = version_output.splitlines()

    if device_type in ("cisco_ios", "cisco_ios_router"):
        for line in lines:
            match = re.search(r'Version\s+(\d+\.\d+(?:\.\d+)?(?:\(\d+\))?)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    elif _is_aruba_device(device_type):
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            # Version      : FL.10.10.1070  (ArubaOS-CX)
            match = re.search(r'Version\s*:\s*([A-Z]+\.\d+\.\d+\.\d+)', line_clean, re.IGNORECASE)
            if match:
                print(f"[版本匹配] 模式1 (Version:): {match.group(1)}")
                return match.group(1)
            # ArubaOS-CX FL.10.10.1070 或 ML.10.13.1040
            match = re.search(r'ArubaOS-CX\s+(?:[A-Z]+\.)?(\d+\.\d+\.\d+)', line_clean)
            if match:
                print(f"[版本匹配] 模式2 (ArubaOS-CX): {match.group(1)}")
                return match.group(1)
            # ArubaOSv9, 10.10.1070.0001
            match = re.search(r'ArubaOSv\d+,\s*(\d+\.\d+\.\d+\.\d+)', line_clean)
            if match:
                print(f"[版本匹配] 模式3 (ArubaOSv): {match.group(1)}")
                return match.group(1)
            # Firmware Version 10.10.1070
            match = re.search(r'Firmware Version\s+(\d+\.\d+\.\d+\.?\d*)', line_clean, re.IGNORECASE)
            if match:
                print(f"[版本匹配] 模式4 (Firmware Version): {match.group(1)}")
                return match.group(1)

    print(f"[版本提取失败] 设备类型={device_type}, 内容前500字符: {repr(version_output[:500])}")
    return "未知"


def extract_serial_number(version_output: str, device_type: str, system_output: str = "", vsf_output: str = "", platform: str = "") -> str:
    """从 show version、show system、show vsf 输出中提取设备序列号（VSF/Stack 返回逗号拼接）"""
    version_output = _strip_ansi(version_output)
    lines = version_output.splitlines()
    serials = []

    if device_type in ("cisco_ios", "cisco_ios_router"):
        if platform == "cisco_ios_xe":
            # Cisco IOS XE：序列号来自 Motherboard Serial Number（每个堆叠成员一个）
            for line in lines:
                match = re.search(r'Motherboard\s+[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
        # 回退：System Serial Number（非 XE 或 XE 无 Motherboard SN 时）
        if not serials:
            for line in lines:
                match = re.search(r'System\s+[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
        # 回退：Processor board ID（独立交换机/路由器）
        if not serials:
            for line in lines:
                match = re.search(r'Processor\s+board\s+ID[:\s]+([A-Za-z0-9]+)', line, re.IGNORECASE)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
    elif _is_aruba_device(device_type):
        # 1. 从 show vsf detail 提取成员序列号（VSF 堆叠）
        if vsf_output:
            vsf_output = _strip_ansi(vsf_output)
            for line in vsf_output.splitlines():
                match = re.search(r'[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
                    print(f"[序列号匹配] show vsf detail: {match.group(1)}")
        # 2. 从 show version 提取
        if not serials:
            for line in lines:
                match = re.search(r'[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
        # 3. 从 show system 提取
        if not serials and system_output:
            system_output = _strip_ansi(system_output)
            for line in system_output.splitlines():
                match = re.search(r'(?:Chassis\s*)?[Ss]erial\s*[Nn](?:br|umber)?[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
                    print(f"[序列号匹配] show system: {match.group(1)}")

    result = ", ".join(serials) if serials else "未知"
    if result == "未知":
        print(f"[序列号提取失败] 设备类型={device_type}, 版本输出前300字符: {repr(version_output[:300])}")
        if system_output:
            print(f"[序列号提取失败] 系统输出前300字符: {repr(system_output[:300])}")
    return result


def extract_model(system_output: str, version_output: str, device_type: str) -> str:
    """从 show system / show version 输出中提取设备型号

    - Aruba: system.raw → Product Name 行，取前 2 个 token (SKU + 系列名)
      例: "JL659A 6300M 48SR5 CL6 PoE 4SFP56 Swch" → "JL659A 6300M"
    - Cisco: version.raw → Model number 行 (堆叠设备多 member 逗号拼接)
      例: "WS-C2960X-48FPD-L" 或 "WS-C2960X-48FPD-L, WS-C2960X-48FPD-L"
    """
    version_output = _strip_ansi(version_output)

    if _is_aruba_device(device_type):
        # 从 system.raw 提取 Product Name
        if system_output:
            system_output = _strip_ansi(system_output)
            for line in system_output.splitlines():
                m = re.search(r'Product\s+Name\s*:\s*(.+)', line, re.IGNORECASE)
                if m:
                    tokens = m.group(1).strip().split()
                    if len(tokens) >= 2:
                        return f"{tokens[0]} {tokens[1]}"
                    return tokens[0] if tokens else "未知"
        # 回退: 从 version.raw 搜索 JL 型号模式
        for line in version_output.splitlines():
            m = re.search(r'(JL\d{3}[AB]\s+\d{4}M)', line)
            if m:
                return m.group(1)
        return "未知"

    elif device_type in ("cisco_ios", "cisco_ios_router"):
        models = []
        for line in version_output.splitlines():
            # "Model number                    : WS-C2960X-48FPD-L"
            m = re.search(r'Model\s+number\s*:\s*(\S+)', line, re.IGNORECASE)
            if m:
                model = m.group(1).strip()
                if model not in models:
                    models.append(model)
        return ", ".join(models) if models else "未知"

    return "未知"


def collect_device(
    device: Device,
    username: str,
    password: str,
    settings: Dict,
) -> Dict:
    """Collect device configuration data"""

    device_name = device.name
    device_ip = device.ip
    device_type = device.type
    device_platform = getattr(device, 'platform', '') or ''
    data_root = settings.get("data_root", "./data")

    _set_progress(device_name, "connecting")

    conn = _get_device_connection()({
        "name": device_name,
        "ip": device_ip,
        "type": device_type,
        "platform": device_platform,
        "port": 22,
        "timeout": 120
    })

    if not conn.connect(username, password):
        error_msg = getattr(conn, '_last_error', '') or 'SSH 连接失败'
        print(f"[收集失败] 连接失败: {error_msg}")
        _set_progress(device_name, "failed", error_msg)
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "failed",
            "error": error_msg
        }

    print(f"[收集进度] SSH 连接成功，开始收集数据...")
    _set_progress(device_name, "collecting_config")

    # 使用实际探测到的设备类型（可能与配置不同）
    effective_type = conn.actual_device_type or device_type
    type_mismatch = conn.type_mismatch

    def _safe_collect(collect_func, label: str) -> str:
        """安全执行单条命令收集，失败时返回错误信息但不抛异常"""
        try:
            return collect_func()
        except Exception as e:
            print(f"[收集异常] {label}: {e}")
            return f"% 收集失败: {str(e)}"

    try:
        # 收集原始数据
        print(f"[收集进度] 获取 running-config...")
        try:
            running_config, startup_config = conn.collect_config()
        except Exception as e:
            print(f"[收集异常] config: {e}")
            running_config = f"% 收集失败: {str(e)}"
            startup_config = running_config
        print(f"[收集进度] running-config: {len(running_config)} 行, startup-config: {len(startup_config)} 行")
        _set_progress(device_name, "collecting_logs")

        # Cisco IOS 日志无法限制条目数，全量收集太慢，跳过
        # Cisco IOS XE 支持管道过滤（show logging | tail 100），可以收集
        if device_platform == "cisco_ios_xe":
            print(f"[收集进度] Cisco IOS XE 收集日志...")
            logs = _safe_collect(conn.collect_logs, "logs")
            print(f"[收集进度] logs: {len(logs)} 行")
        elif effective_type == "cisco_ios" and not _is_router_device(device_type):
            print(f"[收集进度] Cisco IOS 跳过日志收集（全量 show logging 太慢）")
            logs = ""
        else:
            print(f"[收集进度] 获取 logs...")
            logs = _safe_collect(conn.collect_logs, "logs")
            print(f"[收集进度] logs: {len(logs)} 行")

        print(f"[收集进度] 获取 interface status...")
        interface_status = _safe_collect(conn.collect_interface_status, "interface status")
        _set_progress(device_name, "collecting_logs")

        print(f"[收集进度] 获取 version...")
        version_info = _safe_collect(conn.collect_show_version, "version")
        _set_progress(device_name, "collecting_interface")
        print(f"[收集进度] 获取 interface utilization...")
        interface_utilization = _safe_collect(conn.collect_show_interface_utilization, "interface utilization")

        # Aruba CX show version 不含序列号，需要 show system + show vsf
        system_info = ""
        vsf_info = ""
        switch_info = ""
        if _is_aruba_device(effective_type):
            print(f"[收集进度] 获取 system info (序列号)...")
            system_info = _safe_collect(conn.collect_system_info, "show system")
            print(f"[收集进度] 获取 vsf info (堆叠成员)...")
            vsf_info = _safe_collect(conn.collect_vsf_info, "show vsf")
        elif effective_type == "cisco_ios" and not _is_router_device(device_type):
            print(f"[收集进度] 获取 switch detail (堆叠信息)...")
            switch_info = _safe_collect(conn.collect_switch_detail, "show switch detail")

        # 路由器专属：收集路由表
        route_info = ""
        if _is_router_device(device_type):
            print(f"[收集进度] 获取 routing table...")
            route_info = _safe_collect(conn.collect_routing_table, "show ip route")

        # 收集 CDP / LLDP 邻居信息 (所有设备类型)
        print(f"[收集进度] 获取 CDP neighbors...")
        cdp_neighbors_raw = _safe_collect(conn.collect_cdp_neighbors, "show cdp nei")
        print(f"[收集进度] 获取 LLDP neighbors...")
        lldp_neighbors_raw = _safe_collect(conn.collect_lldp_neighbors, "show lldp nei")

        # 提取版本号和序列号（使用实际设备类型，传入 system + vsf 信息）
        software_version = extract_software_version(version_info, effective_type)
        serial_number = extract_serial_number(version_info, effective_type, system_info, vsf_info, platform=device_platform)

        # 提取设备型号（Aruba 从 system.raw, Cisco 从 version.raw）
        device_model = extract_model(system_info, version_info, effective_type)

        # 查找基准配置路径
        baseline_path = os.path.join(data_root, device_name, "latest", "running-config.raw")
        old_running_config = None
        try:
            with open(baseline_path, "r", encoding="utf-8") as f:
                old_running_config = f.read()
        except FileNotFoundError:
            pass

        # 运行分析
        _set_progress(device_name, "analyzing")
        if settings.get("analysis", {}).get("enable_config_validation", True):
            validator = ConfigValidator(running_config)
            validation_results = json.dumps(validator.validate(), indent=2, ensure_ascii=False)
        else:
            validation_results = "{}"

        if settings.get("analysis", {}).get("enable_performance_analysis", True):
            perf_analyzer = PerformanceAnalyzer(
                interface_status, running_config, device_type,
                interface_utilization, uplink_ports=device.uplink_ports
            )
            performance_results = json.dumps(perf_analyzer.analyze(), indent=2, ensure_ascii=False)
        else:
            performance_results = "{}"

        if settings.get("analysis", {}).get("enable_change_detection", True) and old_running_config:
            detector = ChangeDetector(running_config, old_running_config)
            change_results = json.dumps(detector.detect(), indent=2, ensure_ascii=False)
        else:
            change_results = "{}"

        # 保存数据
        _set_progress(device_name, "saving")
        week = get_week_dir(data_root)
        _save_data(
            device_name, device_ip, device_type,
            week, data_root, settings,
            running_config, startup_config, logs,
            interface_status, version_info, interface_utilization, system_info, vsf_info, switch_info, route_info,
            validation_results, performance_results, change_results,
            software_version, serial_number, device_model,
            cdp_neighbors_raw, lldp_neighbors_raw
        )

        _set_progress(device_name, "complete")
        # 延迟清除，给前端轮询窗口读取 "complete" 状态
        import time
        time.sleep(0.5)
        _clear_progress(device_name)
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "success",
            "device_type": effective_type,
            "type_mismatch": type_mismatch,
            "configured_type": device_type if type_mismatch else None,
            "running_lines": len(running_config.splitlines()),
            "software_version": software_version,
            "serial_number": serial_number,
            "model": device_model
        }

    except Exception as e:
        print(f"[收集异常] {e}")
        traceback.print_exc()
        _set_progress(device_name, "failed", str(e))
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "failed",
            "error": str(e)
        }
    finally:
        conn.disconnect()


def _save_data(
    device_name: str, device_ip: str, device_type: str,
    week: str, data_dir: str, settings: Dict,
    running_config: str, startup_config: str,
    logs_raw: str, interface_status: str, version_info: str,
    interface_utilization: str, system_info: str, vsf_info: str, switch_info: str, route_info: str,
    validation_results: str, performance_results: str, change_results: str,
    software_version: str, serial_number: str, device_model: str = "",
    cdp_neighbors_raw: str = "", lldp_neighbors_raw: str = ""
) -> None:
    """保存数据到本地"""

    device_base_dir = os.path.join(data_dir, device_name)
    week_dir = os.path.join(device_base_dir, week)
    os.makedirs(week_dir, exist_ok=True)
    print(f"[保存] 设备={device_name}, 周={week}, 目录={week_dir}")

    # 保存原始配置
    with open(os.path.join(week_dir, "running-config.raw"), "w", encoding="utf-8") as f:
        f.write(running_config)

    with open(os.path.join(week_dir, "startup-config.raw"), "w", encoding="utf-8") as f:
        f.write(startup_config)

    with open(os.path.join(week_dir, "logs.raw"), "w", encoding="utf-8") as f:
        f.write(logs_raw)

    with open(os.path.join(week_dir, "interface-status.raw"), "w", encoding="utf-8") as f:
        f.write(interface_status)

    with open(os.path.join(week_dir, "version.raw"), "w", encoding="utf-8") as f:
        f.write(version_info)

    with open(os.path.join(week_dir, "interface-utilization.raw"), "w", encoding="utf-8") as f:
        f.write(interface_utilization)

    if system_info:
        with open(os.path.join(week_dir, "system.raw"), "w", encoding="utf-8") as f:
            f.write(system_info)

    if vsf_info:
        with open(os.path.join(week_dir, "vsf.raw"), "w", encoding="utf-8") as f:
            f.write(vsf_info)

    if switch_info:
        with open(os.path.join(week_dir, "switch-detail.raw"), "w", encoding="utf-8") as f:
            f.write(switch_info)

    if route_info:
        with open(os.path.join(week_dir, "routing-table.raw"), "w", encoding="utf-8") as f:
            f.write(route_info)

    # 保存 CDP / LLDP 原始输出 + 解析合并后的 neighbors.json
    if cdp_neighbors_raw:
        with open(os.path.join(week_dir, "cdp-neighbors.raw"), "w", encoding="utf-8") as f:
            f.write(cdp_neighbors_raw)

    if lldp_neighbors_raw:
        with open(os.path.join(week_dir, "lldp-neighbors.raw"), "w", encoding="utf-8") as f:
            f.write(lldp_neighbors_raw)

    # 生成 neighbors.json (CDP/LLDP + ConfigParser 端口描述补充)
    try:
        from analyzers.neighbor_parser import parse_cdp, parse_lldp, merge_neighbors, NeighborEntry
        cdp_entries = parse_cdp(cdp_neighbors_raw, device_type) if cdp_neighbors_raw else []
        lldp_entries = parse_lldp(lldp_neighbors_raw, device_type) if lldp_neighbors_raw else []
        merged = merge_neighbors(cdp_entries, lldp_entries)

        # 端口名规范化: Cisco 长名 → 短名，确保 CDP/LLDP 与 ConfigParser 的去重 key 可比
        _CISCO_PORT_SHORT = {
            'GigabitEthernet': 'Gi', 'TenGigabitEthernet': 'Te',
            'TwentyFiveGigE': 'Twe', 'HundredGigE': 'Hu',
            'FortyGigE': 'Fo', 'FastEthernet': 'Fa',
            'Port-channel': 'Po', 'Loopback': 'Lo',
        }

        def _normalize_port_name(port: str) -> str:
            """将 Cisco 长接口名规范化短名: GigabitEthernet1/1/2 → Gi1/1/2"""
            for long_pfx, short_pfx in _CISCO_PORT_SHORT.items():
                if port.startswith(long_pfx):
                    return short_pfx + port[len(long_pfx):]
            return port

        # 规范化 CDP/LLDP 已有条目的端口名（CDP 输出通常已是短名，LLDP 格式多样）
        for e in merged:
            e.local_port = _normalize_port_name(e.local_port)

        # 从 running-config 提取 admin down (shutdown) 端口，过滤不可靠的邻居数据
        shutdown_ports: set = set()
        if running_config and not running_config.startswith('%'):
            shutdown_ports = _extract_shutdown_ports(running_config, _normalize_port_name)
            if shutdown_ports:
                merged = [e for e in merged if _normalize_port_name(e.local_port) not in shutdown_ports]
                print(f"[邻居] 过滤 admin down 端口: {shutdown_ports}")

        # 补充: 从 running-config 端口描述中收集 CDP/LLDP 无法发现的设备
        if running_config and not running_config.startswith('%'):
            try:
                from analyzers.config_parser import ConfigParser
                cp = ConfigParser(device_type=device_type)
                config_entries = cp.parse(running_config)
                seen_ports = set(
                    (_normalize_port_name(e.local_port), e.neighbor_name)
                    for e in merged
                )
                extra_count = 0
                for entry in config_entries:
                    if not entry.device_name:
                        continue
                    if entry.is_endpoint or not entry.device_type:
                        continue
                    # CDP/LLDP 优先；端口描述中同端口+同邻居名则跳过去重
                    key = (_normalize_port_name(entry.name), entry.device_name)
                    if key not in seen_ports:
                        seen_ports.add(key)
                        merged.append(NeighborEntry(
                            local_port=_normalize_port_name(entry.name),
                            neighbor_name=entry.device_name,
                            neighbor_type=entry.device_type,
                            neighbor_platform='',
                            neighbor_desc=entry.description[:80] if entry.description else '',
                        ))
                        extra_count += 1
                if extra_count:
                    print(f"[邻居] ConfigParser 补充: {extra_count} 条")
            except Exception as e:
                print(f"[邻居] ConfigParser 补充失败: {e}")

        neighbors_data = {
            "device": device_name,
            "week": week,
            "collected_at": __import__('datetime').datetime.now().isoformat(),
            "neighbors": [
                {
                    "local_port": e.local_port,
                    "neighbor_name": e.neighbor_name,
                    "neighbor_type": e.neighbor_type,
                    "neighbor_platform": e.neighbor_platform,
                    "neighbor_desc": e.neighbor_desc,
                }
                for e in merged
            ]
        }
        with open(os.path.join(week_dir, "neighbors.json"), "w", encoding="utf-8") as f:
            json.dump(neighbors_data, f, ensure_ascii=False, indent=2)
        print(f"[保存] neighbors.json: {len(merged)} 条邻居记录")
    except Exception as e:
        print(f"[警告] 邻居解析失败: {e}")

    # 保存分析结果
    with open(os.path.join(week_dir, "validation.json"), "w", encoding="utf-8") as f:
        f.write(validation_results)

    with open(os.path.join(week_dir, "performance.json"), "w", encoding="utf-8") as f:
        f.write(performance_results)

    with open(os.path.join(week_dir, "change.json"), "w", encoding="utf-8") as f:
        f.write(change_results)

    # 生成摘要
    _generate_summary(
        device_name, device_ip, device_type,
        running_config, startup_config, logs_raw,
        version_info, software_version, serial_number,
        validation_results, performance_results, change_results,
        week_dir, device_model
    )

    # 清理旧版本
    max_versions = settings.get("max_versions", 10)
    keep_latest_versions_per_device(data_dir, device_name, max_versions)

    # 更新设备清单中的序列号、型号、版本和最后同步时间
    if serial_number and serial_number != "未知":
        _update_device_serial(device_name, serial_number)
    if device_model and device_model != "未知":
        _update_device_field(device_name, "model", device_model)
    if software_version and software_version != "未知":
        _update_device_field(device_name, "version", software_version)
    _update_device_field(device_name, "last_synced", datetime.now().strftime("%m/%d/%Y %H:%M"))


def _generate_summary(
    device_name: str, device_ip: str, device_type: str,
    running_config: str, startup_config: str, logs_raw: str,
    version_info: str, software_version: str, serial_number: str,
    validation_results: str, performance_results: str, change_results: str,
    week_dir: str, device_model: str = ""
) -> None:
    """生成 summary.txt"""

    lines = []
    lines.append("=" * 70)
    lines.append(f"设备配置摘要报告")
    lines.append(f"设备名称：{device_name}")
    lines.append(f"IP 地址：{device_ip}")
    lines.append(f"类型：{device_type}")
    if serial_number:
        lines.append(f"序列号 (SN): {serial_number}")
    if device_model:
        lines.append(f"设备型号：{device_model}")
    lines.append(f"软件版本：{software_version}")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")

    # 配置统计
    lines.append("-" * 70)
    lines.append("配置统计")
    lines.append("-" * 70)
    lines.append(f"Running-Config 行数：{len(running_config.splitlines())}")
    lines.append(f"Startup-Config 行数：{len(startup_config.splitlines())}")
    lines.append("")

    # 接口统计
    lines.append("-" * 70)
    lines.append("接口状态摘要")
    lines.append("-" * 70)
    interface_lines = [l for l in startup_config.splitlines()
                      if ('interface' in l.lower() and ('Gi' in l or 'Ve' in l or 'Fa' in l or 'Se' in l or 'Te' in l or 'Lo' in l))]
    lines.append(f"接口配置条目：{len(interface_lines)}")
    lines.append("")

    # 验证结果
    lines.append("-" * 70)
    lines.append("配置验证结果")
    lines.append("-" * 70)
    if validation_results:
        try:
            validation = json.loads(validation_results)
            summary = validation.get('summary', {})
            lines.append(f"错误数：{summary.get('errors', 0)}")
            lines.append(f"警告数：{summary.get('warnings', 0)}")
            lines.append(f"信息数：{summary.get('info', 0)}")
            if summary.get('errors', 0) > 0:
                lines.append("⚠️ 发现配置错误，请检查！")
            elif summary.get('warnings', 0) > 0:
                lines.append("⚠️ 发现配置警告")
            else:
                lines.append("✓ 配置验证通过")
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            lines.append("验证数据解析失败")
    lines.append("")

    # 性能摘要
    lines.append("-" * 70)
    lines.append("性能分析摘要")
    lines.append("-" * 70)
    if performance_results:
        try:
            perf = json.loads(performance_results)
            iface_summary = perf.get('interface_summary', {})
            lines.append(f"接口总数：{iface_summary.get('total', 0)}")
            lines.append(f"接口 UP: {iface_summary.get('up', 0)}")
            lines.append(f"接口 DOWN: {iface_summary.get('down', 0)}")
            errors = perf.get('errors', {})
            if errors:
                lines.append("错误统计:")
                for err, count in list(errors.items())[:5]:
                    lines.append(f"  {err}: {count}")
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            lines.append("性能数据解析失败")
    lines.append("")

    # 变更摘要
    lines.append("-" * 70)
    lines.append("变更检测摘要")
    lines.append("-" * 70)
    if change_results:
        try:
            change = json.loads(change_results)
            summary = change.get('summary', {})
            if summary:
                lines.append(f"新增行数：{summary.get('added', 0)}")
                lines.append(f"删除行数：{summary.get('removed', 0)}")
                lines.append(f"有变更：{change.get('has_changes', False)}")
            else:
                lines.append("没有基准配置，无法检测变更")
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            lines.append("变更数据解析失败")
    lines.append("")

    lines.append("=" * 70)
    lines.append("报告结束")
    lines.append("=" * 70)

    summary_path = os.path.join(week_dir, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _update_device_field(device_name: str, field: str, value: any) -> None:
    """更新 devices.yaml 中某个设备的字段"""
    config_path = get_devices_config_path()
    if not os.path.exists(config_path):
        return
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for device in data.get("devices", []):
        if device.get("name") == device_name:
            device[field] = value
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, Dumper=yaml.SafeDumper)


def _update_device_serial(device_name: str, serial_number: str) -> None:
    """更新设备清单中的序列号"""
    _update_device_field(device_name, "serial_number", serial_number)
 