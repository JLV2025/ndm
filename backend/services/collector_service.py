"""配置收集服务"""

import os
import json
import re
import sys
import traceback
import threading
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def _get_device_connection():
    """延迟导入 DeviceConnection 以支持 mocking"""
    from collectors.base import DeviceConnection
    return DeviceConnection
from analyzers.config_validator import ConfigValidator
from analyzers.performance import PerformanceAnalyzer
from analyzers.change_detector import ChangeDetector
from utils.settings_loader import load_settings, load_devices, get_devices_config_path
from utils.password import password_manager
from storage.file_manager import get_week_dir
from storage.database import get_connection as get_db
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
            # 不去重 — 每个堆叠成员各记一条，与序列号保持 1:1 对应
            m = re.search(r'Model\s+number\s*:\s*(\S+)', line, re.IGNORECASE)
            if m:
                models.append(m.group(1).strip())
        return ", ".join(models) if models else "未知"

    return "未知"


def extract_uptime_seconds(version_output: str = "", boot_history: str = "", device_type: str = "") -> int | None:
    """从 show version (Cisco) 或 show boot-history (Aruba) 提取设备运行时间（秒）

    Cisco: System uptime is 2 years, 12 weeks, 3 days, 5 hours, 22 minutes
    Aruba: Current Boot, up for 545 days 19 hrs 43 mins 22 secs
    """
    if device_type == "aruba_aoscx" and boot_history:
        return _parse_aruba_uptime(boot_history)
    if device_type.startswith("cisco") and version_output:
        return _parse_cisco_uptime(version_output)
    return None


def _parse_cisco_uptime(version_output: str) -> int | None:
    """解析 Cisco show version 中的 System uptime"""
    output = _strip_ansi(version_output)
    m = re.search(
        r'System uptime is\s+'
        r'(?:(\d+)\s+years?,\s*)?'
        r'(?:(\d+)\s+weeks?,\s*)?'
        r'(?:(\d+)\s+days?,\s*)?'
        r'(?:(\d+)\s+hours?,\s*)?'
        r'(?:(\d+)\s+minutes?)',
        output, re.IGNORECASE
    )
    if not m:
        return None
    years = int(m.group(1) or 0)
    weeks = int(m.group(2) or 0)
    days = int(m.group(3) or 0)
    hours = int(m.group(4) or 0)
    minutes = int(m.group(5) or 0)
    total = days + weeks * 7 + years * 365
    return total * 86400 + hours * 3600 + minutes * 60


def _parse_aruba_uptime(boot_history: str) -> int | None:
    """解析 Aruba show boot-history 中的 Current Boot 运行时间"""
    output = _strip_ansi(boot_history)
    m = re.search(
        r'Current Boot, up for (\d+) days (\d+) hrs (\d+) mins (\d+) secs',
        output
    )
    if not m:
        return None
    days = int(m.group(1))
    hours = int(m.group(2))
    minutes = int(m.group(3))
    seconds = int(m.group(4))
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def parse_syslog_lines(log_output: str, device_type: str) -> list:
    """将原始日志输出解析为结构化列表

    Cisco Syslog 格式: *Mar  1 00:00:00.000: %FACILITY-SEVERITY-MNEMONIC: message
    Cisco 无时间戳格式: %FACILITY-SEVERITY-MNEMONIC: message
    Aruba 格式: YYYY-MM-DDTHH:MM:SS.XXXXXX+XX:XX {facility} {severity} {mnemonic} message

    返回: [{"timestamp": "...", "severity": "...", "facility": "...", "message": "..."}]
    """
    if not log_output or log_output.startswith('% 收集失败'):
        return []

    entries = []
    output = _strip_ansi(log_output)

    # Aruba 结构化格式
    if device_type == "aruba_aoscx":
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            m = re.match(
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})\s+'
                r'(\S+)\s+(\S+)\s+(\S+)\s+(.*)',
                stripped
            )
            if m:
                entries.append({
                    "timestamp": m.group(1),
                    "facility": m.group(2),
                    "severity": m.group(3),
                    "message": f"{m.group(4)}: {m.group(5)}",
                })
                continue
            entries.append({"timestamp": "", "severity": "", "facility": "", "message": stripped})
        return entries

    # Cisco 格式: %FACILITY-SEVERITY-MNEMONIC: message (severity 为 0-7 单数字)
    cisco_ts_re = re.compile(
        r'^(?:\*)?(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\s+\w+)?):\s*'
        r'%(\w+)-(\d)-(\w+):\s*(.*)'
    )
    cisco_no_ts_re = re.compile(
        r'^%(\w+)-(\d)-(\w+):\s*(.*)'
    )

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Syslog logging:") or stripped.startswith("Buffer logging:"):
            continue
        if stripped.startswith("Trap logging:") or stripped.startswith("Log Buffer"):
            continue

        m = cisco_ts_re.match(stripped)
        if m:
            entries.append({
                "timestamp": m.group(1),
                "facility": m.group(2),
                "severity": m.group(3),
                "message": m.group(5) or "",
            })
            continue

        m2 = cisco_no_ts_re.match(stripped)
        if m2:
            entries.append({
                "timestamp": "",
                "facility": m2.group(1),
                "severity": m2.group(2),
                "message": m2.group(4) or "",
            })
            continue

    return entries


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
        boot_history = ""
        if _is_aruba_device(effective_type):
            print(f"[收集进度] 获取 system info (序列号)...")
            system_info = _safe_collect(conn.collect_system_info, "show system")
            print(f"[收集进度] 获取 vsf info (堆叠成员)...")
            vsf_info = _safe_collect(conn.collect_vsf_info, "show vsf")
            print(f"[收集进度] 获取 boot-history (运行时间)...")
            boot_history = _safe_collect(conn.collect_boot_history, "show boot-history")
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

        # 提取设备运行时间（秒）
        system_uptime_seconds = extract_uptime_seconds(version_info, boot_history, effective_type)

        # 从 SQLite 查找上一次采集的 running-config（基线对比）
        old_running_config = None
        try:
            db = get_db()
            row = db.execute(
                "SELECT running_config FROM collections WHERE device_id = "
                "(SELECT id FROM devices WHERE name=?) AND phase='1' "
                "ORDER BY id DESC LIMIT 1 OFFSET 1",
                (device_name,)
            ).fetchone()
            if row and row["running_config"]:
                old_running_config = row["running_config"]
        except Exception:
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
            device_name, device_ip, effective_type,
            week, data_root, settings,
            running_config, startup_config, logs,
            interface_status, version_info, interface_utilization, system_info, vsf_info, switch_info, route_info,
            validation_results, performance_results, change_results,
            software_version, serial_number, device_model,
            cdp_neighbors_raw, lldp_neighbors_raw,
            boot_history=boot_history,
            system_uptime_seconds=system_uptime_seconds,
            platform=device_platform,
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


def _save_to_sqlite(
    device_name: str, device_ip: str, device_type: str, device_platform: str,
    week: str, collected_at: str,
    running_config: str, logs_raw: str,
    performance_results: str, validation_results: str, change_results: str,
    software_version: str, serial_number: str, device_model: str,
    system_uptime_seconds: int | None,
    port_details: list, port_errors: list,
    neighbors_data: list, boot_history: str,
) -> dict:
    """将采集数据写入 SQLite 数据库

    返回写入统计信息。
    此函数与文件写入并行执行，互不影响。
    """
    try:
        db = get_db()
    except RuntimeError:
        print("[SQLite] 数据库未初始化，跳过 SQLite 写入")
        return {"status": "skipped"}

    try:
        # 显式事务包裹：确保 8 步写入原子化，避免孤儿记录
        db.execute("BEGIN IMMEDIATE")

        # 1. 确保 device 记录存在
        db.execute("""
            INSERT INTO devices (name, ip, type, platform, serial_number, model, version, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                ip=excluded.ip, type=excluded.type, platform=excluded.platform,
                serial_number=CASE WHEN excluded.serial_number != '' AND excluded.serial_number != '未知'
                                   THEN excluded.serial_number ELSE devices.serial_number END,
                model=CASE WHEN excluded.model != '' AND excluded.model != '未知'
                           THEN excluded.model ELSE devices.model END,
                version=CASE WHEN excluded.version != '' AND excluded.version != '未知'
                              THEN excluded.version ELSE devices.version END,
                last_synced=excluded.last_synced
        """, (
            device_name, device_ip, device_type, device_platform,
            serial_number if serial_number != "未知" else "",
            device_model if device_model != "未知" else "",
            software_version if software_version != "未知" else "",
            collected_at,
        ))
        device_row = db.execute("SELECT id FROM devices WHERE name=?", (device_name,)).fetchone()
        device_id = device_row["id"]

        # 2. 写入采集会话
        running_lines = len(running_config.splitlines()) if running_config and not running_config.startswith('%') else 0
        db.execute("""
            INSERT INTO collections (device_id, week, phase, collected_at,
                software_version, serial_number, model, system_uptime_seconds,
                running_config, running_config_lines, boot_history_raw)
            VALUES (?, ?, '1', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, week, collected_at,
            software_version, serial_number, device_model,
            system_uptime_seconds,
            running_config, running_lines,
            boot_history,
        ))
        collection_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 3. 写入端口快照
        if port_details:
            def _safe_str(val) -> str:
                """安全转字符串：None→''，保留数值 0"""
                return str(val) if val is not None else ""

            rows = []
            for p in port_details:
                rows.append((
                    collection_id, device_id, p.get("name", ""),
                    p.get("status", ""), 1 if p.get("status_up") else 0,
                    _safe_str(p.get("speed")), _safe_str(p.get("mode")),
                    _safe_str(p.get("type")), _safe_str(p.get("description")),
                    _safe_str(p.get("native_vlan")),
                    1 if p.get("is_uplink") else 0,
                    float(p.get("rx_mbps") or 0), float(p.get("tx_mbps") or 0),
                    float(p.get("rx_util_pct") or 0), float(p.get("tx_util_pct") or 0),
                    int(p.get("rx_pps") or 0), int(p.get("tx_pps") or 0),
                    int(p.get("rxload") or 0), int(p.get("txload") or 0),
                ))
            db.executemany("""
                INSERT INTO port_snapshots
                    (collection_id, device_id, port_name, status, status_up,
                     speed, mode, port_type, description, native_vlan, is_uplink,
                     rx_mbps, tx_mbps, rx_util_pct, tx_util_pct, rx_pps, tx_pps, rxload, txload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

        # 4. 写入端口错误
        if port_errors:
            err_rows = []
            for err_type, ports in port_errors.items():
                for pn in ports:
                    err_rows.append((collection_id, device_id, pn, err_type, 1))
            db.executemany(
                "INSERT INTO port_errors (collection_id, device_id, port_name, error_type, count) VALUES (?, ?, ?, ?, ?)",
                err_rows,
            )

        # 5. 写入邻居关系
        if neighbors_data:
            neigh_rows = []
            for n in neighbors_data:
                neigh_rows.append((
                    collection_id, device_id,
                    n.get("local_port", ""), n.get("neighbor_name", ""),
                    n.get("neighbor_type", ""), n.get("neighbor_platform", ""),
                    n.get("neighbor_desc", ""), n.get("source", "cdp"),
                ))
            db.executemany(
                "INSERT INTO neighbors (collection_id, device_id, local_port, neighbor_name, neighbor_type, neighbor_platform, neighbor_desc, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                neigh_rows,
            )

        # 6. 写入配置变更
        if change_results and change_results != "{}":
            try:
                change = json.loads(change_results)
                has_changes = 1 if change.get("has_changes") else 0
                summary_json = json.dumps(change.get("changes", []), ensure_ascii=False)
                db.execute(
                    "INSERT INTO config_changes (collection_id, device_id, detected_at, has_changes, added_lines, removed_lines, change_summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (collection_id, device_id, collected_at, has_changes,
                     change.get("summary", {}).get("added", 0),
                     change.get("summary", {}).get("removed", 0),
                     summary_json),
                )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                print(f"[SQLite] 配置变更解析失败: {e}")

        # 7. 写入验证结果
        if validation_results and validation_results != "{}":
            try:
                val = json.loads(validation_results)
                vs = val.get("summary", {})
                db.execute(
                    "INSERT INTO validation_results (collection_id, device_id, errors_count, warnings_count, info_count, details) VALUES (?, ?, ?, ?, ?, ?)",
                    (collection_id, device_id, vs.get("errors", 0), vs.get("warnings", 0), vs.get("info", 0),
                     json.dumps(val, ensure_ascii=False)),
                )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                print(f"[SQLite] 验证结果解析失败: {e}")

        # 8. 写入设备日志
        if logs_raw and not logs_raw.startswith('% 收集失败'):
            log_entries = parse_syslog_lines(logs_raw, device_type)
            if log_entries:
                log_rows = [
                    (collection_id, device_id, e["timestamp"], e["severity"], e["facility"], e["message"])
                    for e in log_entries
                ]
                db.executemany(
                    "INSERT INTO device_logs (collection_id, device_id, log_timestamp, severity, facility, message) VALUES (?, ?, ?, ?, ?, ?)",
                    log_rows,
                )

        db.commit()
        stats = {
            "status": "ok",
            "collection_id": collection_id,
            "port_snapshots": len(port_details),
            "port_errors": sum(len(v) for v in (port_errors or {}).values()),
            "neighbors": len(neighbors_data),
            "logs": len(logs_raw.splitlines()) if logs_raw else 0,
        }
        print(f"[SQLite] 数据已写入: {stats}")
        return stats

    except Exception as e:
        print(f"[SQLite] 写入失败: {e}")
        traceback.print_exc()
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


def _save_data(
    device_name: str, device_ip: str, device_type: str,
    week: str, data_dir: str, settings: Dict,
    running_config: str, startup_config: str,
    logs_raw: str, interface_status: str, version_info: str,
    interface_utilization: str, system_info: str, vsf_info: str, switch_info: str, route_info: str,
    validation_results: str, performance_results: str, change_results: str,
    software_version: str, serial_number: str, device_model: str = "",
    cdp_neighbors_raw: str = "", lldp_neighbors_raw: str = "",
    boot_history: str = "", system_uptime_seconds: int | None = None,
    platform: str = "",
) -> None:
    """保存数据到本地"""

    device_base_dir = os.path.join(data_dir, device_name)
    week_dir = os.path.join(device_base_dir, week)
    os.makedirs(week_dir, exist_ok=True)
    print(f"[保存] 设备={device_name}, 周={week}, 目录={week_dir}")

    # 保存原始配置
    with open(os.path.join(week_dir, "running-config.raw"), "w", encoding="utf-8") as f:
        f.write(running_config)

    # 仅保留 running-config.raw 文件写入（双轨策略）
    # 其他所有数据仅写入 SQLite

    # 生成 neighbors.json (CDP/LLDP + ConfigParser 端口描述补充)
    _neighbors_in_memory = []  # 供后续 SQLite 写入使用，避免磁盘回读
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
        _neighbors_in_memory = neighbors_data["neighbors"]  # 保存引用供 SQLite 写入
        print(f"[保存] 邻居解析完成: {len(merged)} 条邻居记录（仅写 SQLite）")
    except Exception as e:
        print(f"[警告] 邻居解析失败: {e}")

    # 分析结果仅写入 SQLite（不再写 JSON 文件 + summary.txt）
    # 设备信息更新不再写 devices.yaml（由 SQLite UPSERT 完成）
    # 旧版本清理不再需要（仅 running-config.raw 一个文件）

    # 双轨写入: 写入 SQLite 数据库
    try:
        # 从 performance_results JSON 中提取端口详情和错误数据
        port_details = []
        port_errors_dict = {}
        if performance_results and performance_results != "{}":
            try:
                perf_json = json.loads(performance_results)
                iface_summary = perf_json.get("interface_summary", {})
                port_details = iface_summary.get("details", [])
                errors = perf_json.get("errors", {})
                port_errors_dict = errors.get("ports", {})
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                pass

        # 使用内存中已处理的邻居数据（避免磁盘回读）
        neighbors_list = _neighbors_in_memory

        sqlite_result = _save_to_sqlite(
            device_name=device_name,
            device_ip=device_ip,
            device_type=device_type,
            device_platform=platform,
            week=week,
            collected_at=datetime.now().isoformat(),
            running_config=running_config,
            logs_raw=logs_raw,
            performance_results=performance_results,
            validation_results=validation_results,
            change_results=change_results,
            software_version=software_version,
            serial_number=serial_number,
            device_model=device_model,
            system_uptime_seconds=system_uptime_seconds,
            port_details=port_details,
            port_errors=port_errors_dict,
            neighbors_data=neighbors_list,
            boot_history=boot_history,
        )
        # 写入完成后自动运行异常检测
        if isinstance(sqlite_result, dict) and sqlite_result.get("collection_id"):
            try:
                dev_id = _get_device_id(device_name)
                if dev_id is None:
                    print(f"[异常检测] 跳过 {device_name}: 未找到设备 ID")
                else:
                    from analyzers.anomaly_detector import AnomalyDetector
                    detector = AnomalyDetector(get_db())
                    alert_count = detector.detect_and_save(
                        device_id=dev_id,
                        collection_id=sqlite_result["collection_id"],
                        week=week,
                    )
                    if alert_count:
                        print(f"[异常检测] {device_name}: {alert_count} 条告警")
            except Exception as e:
                print(f"[异常检测] 失败: {e}")

    except Exception as e:
        print(f"[SQLite] 双轨写入失败（不影响文件存储）: {e}")


def _get_device_id(device_name: str) -> int | None:
    """从 SQLite 中查询设备 ID"""
    try:
        db = get_db()
        row = db.execute("SELECT id FROM devices WHERE name=?", (device_name,)).fetchone()
        return row["id"] if row else None
    except Exception:
        return None


# ================================================================
# Phase 2 深度收集触发规则
# ================================================================

PHASE2_TRIGGERS = {
    "device_reboot": {
        "label": "设备重启",
        "collect": ["show logging"],
        "button_text": "收集全量日志诊断重启原因",
    },
    "port_sudden_down": {
        "label": "端口异常 DOWN",
        "collect": ["show interface {port_name}"],
        "button_text": "深度检查端口状态",
    },
    "port_errors": {
        "label": "端口错误",
        "collect": ["show interface {port_name}", "show logging | include {port_name}"],
        "button_text": "收集端口错误详情",
    },
    "topology_changed": {
        "label": "拓扑变更",
        "collect": ["show cdp nei detail", "show lldp nei detail"],
        "button_text": "收集详细邻居信息",
    },
    "high_utilization": {
        "label": "带宽利用率飙升",
        "collect": ["show interface {port_name}"],
        "button_text": "检查端口流量详情",
    },
    "config_changed": {
        "label": "配置变更",
        "collect": [],
        "button_text": None,
    },
    "version_mismatch": {
        "label": "版本不一致",
        "collect": [],
        "button_text": None,
    },
}


def collect_all_devices_parallel(
    devices: List[Device],
    username: str,
    password: str,
    settings: Dict,
    max_workers: int = 4,
) -> List[Dict]:
    """并行收集所有设备（Phase 1）

    Args:
        devices: 设备列表
        username: SSH 用户名
        password: SSH 密码
        settings: 全局设置
        max_workers: 最大并发线程数

    Returns:
        每个设备的收集结果列表
    """
    results: List[Dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_device = {
            executor.submit(collect_device, device, username, password, settings): device
            for device in devices
        }
        for future in as_completed(future_to_device):
            device = future_to_device[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[并行] 设备 {device.name} 收集异常: {e}")
                traceback.print_exc()
                results.append({
                    "name": device.name,
                    "ip": device.ip,
                    "status": "failed",
                    "error": str(e),
                })

    return results


def run_phase2_collection(
    device_name: str,
    triggers: List[str],
    username: str,
    password: str,
    settings: Dict,
    port_name: str = "",
) -> Dict:
    """执行单设备 Phase 2 深度收集

    Args:
        device_name: 设备名称
        triggers: 触发条件列表 (如 ["device_reboot", "port_sudden_down"])
        username: SSH 用户名
        password: SSH 密码
        settings: 全局设置
        port_name: 相关端口名（用于端口类触发条件）

    Returns:
        收集结果
    """
    devices = load_devices()
    device_config = None
    for d in devices:
        if d.name == device_name:
            device_config = d
            break

    if device_config is None:
        return {"status": "failed", "error": f"设备 {device_name} 不存在"}

    _set_progress(device_name, "phase2_connecting")

    conn = _get_device_connection()({
        "name": device_config.name,
        "ip": device_config.ip,
        "type": device_config.type,
        "platform": getattr(device_config, 'platform', '') or '',
        "port": 22,
        "timeout": 120,
    })

    if not conn.connect(username, password):
        error_msg = getattr(conn, '_last_error', '') or 'SSH 连接失败'
        _set_progress(device_name, "failed", error_msg)
        return {"status": "failed", "error": error_msg}

    collected: Dict[str, str] = {}
    try:
        # 根据触发条件收集对应命令
        dt = conn.actual_device_type or conn.configured_device_type
        for trigger in triggers:
            rule = PHASE2_TRIGGERS.get(trigger, {})
            for cmd_template in rule.get("collect", []):
                cmd = cmd_template.format(port_name=port_name)
                print(f"[Phase2] {device_name}: {cmd}")
                output = conn.send_command(cmd, read_timeout=30)
                collected[cmd] = output

        _set_progress(device_name, "phase2_saving")

        # 写入 SQLite（Phase 2 标记）
        week = get_week_dir(settings.get("data_root", "./data"))
        try:
            db = get_db()
            device_row = db.execute("SELECT id FROM devices WHERE name=?", (device_name,)).fetchone()
            if device_row:
                device_id = device_row["id"]
                collected_at = datetime.now().isoformat()
                db.execute(
                    "INSERT INTO collections (device_id, week, phase, collected_at) VALUES (?, ?, '2', ?)",
                    (device_id, week, collected_at),
                )
                collection_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

                # 保存全量日志（若收集了）
                full_logs = collected.get("show logging", "")
                if full_logs:
                    log_entries = parse_syslog_lines(full_logs, dt)
                    if log_entries:
                        log_rows = [
                            (collection_id, device_id, e["timestamp"], e["severity"], e["facility"], e["message"])
                            for e in log_entries
                        ]
                        db.executemany(
                            "INSERT INTO device_logs (collection_id, device_id, log_timestamp, severity, facility, message) VALUES (?, ?, ?, ?, ?, ?)",
                            log_rows,
                        )
                        print(f"[Phase2] {device_name}: {len(log_rows)} 条日志已写入数据库")

                db.commit()
        except Exception as e:
            print(f"[Phase2] SQLite 写入失败: {e}")

        _set_progress(device_name, "complete")
        import time
        time.sleep(0.5)
        _clear_progress(device_name)

        return {
            "status": "success",
            "device_name": device_name,
            "triggers": triggers,
            "collected_commands": list(collected.keys()),
        }

    except Exception as e:
        print(f"[Phase2] 异常: {e}")
        traceback.print_exc()
        _set_progress(device_name, "failed", str(e))
        return {"status": "failed", "error": str(e)}
    finally:
        conn.disconnect()
