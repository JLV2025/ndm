"""配置收集服务"""

import os
import json
import re
import sys
from typing import Dict, List
from datetime import datetime

def _get_device_connection():
    """延迟导入 DeviceConnection 以支持 mocking"""
    from collectors.base import DeviceConnection
    return DeviceConnection
from analyzers.config_validator import ConfigValidator
from analyzers.performance import PerformanceAnalyzer
from analyzers.change_detector import ChangeDetector
from utils.settings_loader import load_settings, load_devices
from utils.password import password_manager
from storage.file_manager import (
    get_week_dir, create_device_dir, keep_latest_versions_per_device
)
from models.devices import Device


def _is_aruba_device(device_type: str) -> bool:
    """判断是否为 Aruba 设备（兼容多种类型名）"""
    return device_type in ("aruba_osswitch", "aruba_aoscx")


def extract_software_version(version_output: str, device_type: str) -> str:
    """从 show version 输出中提取软件版本号"""
    lines = version_output.splitlines()

    if device_type == "cisco_ios":
        for line in lines:
            match = re.search(r'Version\s+(\d+\.\d+(?:\(\d+\))?)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    elif _is_aruba_device(device_type):
        for line in lines:
            match = re.search(r'ArubaOSv9,\s*(\d+\.\d+\.\d+\.\d+)', line)
            if match:
                return match.group(1)
            match = re.search(r'Firmware Version\s+(\d+\.\d+\.\d+\.\d+)', line, re.IGNORECASE)
            if match:
                return match.group(1)

    return "未知"


def extract_serial_number(version_output: str, device_type: str) -> str:
    """从 show version 输出中提取设备序列号"""
    lines = version_output.splitlines()

    if device_type == "cisco_ios":
        for line in lines:
            match = re.search(r'Serial Number[:\s]+([A-Za-z0-9]+)', line)
            if match:
                return match.group(1)
    elif _is_aruba_device(device_type):
        for line in lines:
            match = re.search(r'Serial Number[:\s]+([A-Z0-9]+)', line)
            if match:
                return match.group(1)

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

    conn = _get_device_connection()({
        "name": device_name,
        "ip": device_ip,
        "type": device_type,
        "platform": device_platform,
        "port": 22,
        "timeout": 30
    })

    if not conn.connect(username, password):
        error_msg = getattr(conn, '_last_error', '') or 'SSH 连接失败'
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "failed",
            "error": error_msg
        }

    # 使用实际探测到的设备类型（可能与配置不同）
    effective_type = conn.actual_device_type or device_type
    type_mismatch = conn.type_mismatch

    try:
        # 收集原始数据
        running_config, startup_config = conn.collect_config()
        logs = conn.collect_logs()
        interface_status = conn.collect_interface_status()
        version_info = conn.collect_show_version()
        interface_utilization = conn.collect_show_interface_utilization()

        # 提取版本号和序列号（使用实际设备类型）
        software_version = extract_software_version(version_info, effective_type)
        serial_number = extract_serial_number(version_info, effective_type)

        # 查找基准配置路径
        baseline_path = os.path.join(data_root, device_name, "latest", "running-config.raw")
        old_running_config = None
        try:
            with open(baseline_path, "r", encoding="utf-8") as f:
                old_running_config = f.read()
        except FileNotFoundError:
            pass

        # 运行分析
        if settings.get("analysis", {}).get("enable_config_validation", True):
            validator = ConfigValidator(running_config)
            validation_results = json.dumps(validator.validate(), indent=2, ensure_ascii=False)
        else:
            validation_results = "{}"

        if settings.get("analysis", {}).get("enable_performance_analysis", True):
            perf_analyzer = PerformanceAnalyzer(interface_status, running_config)
            performance_results = json.dumps(perf_analyzer.analyze(), indent=2, ensure_ascii=False)
        else:
            performance_results = "{}"

        if settings.get("analysis", {}).get("enable_change_detection", True) and old_running_config:
            detector = ChangeDetector(running_config, old_running_config)
            change_results = json.dumps(detector.detect(), indent=2, ensure_ascii=False)
        else:
            change_results = "{}"

        # 保存数据
        week = get_week_dir(data_root)
        _save_data(
            device_name, device_ip, device_type,
            week, data_root, settings,
            running_config, startup_config, logs,
            interface_status, version_info, interface_utilization,
            validation_results, performance_results, change_results,
            software_version, serial_number
        )

        return {
            "name": device_name,
            "ip": device_ip,
            "status": "success",
            "device_type": effective_type,
            "type_mismatch": type_mismatch,
            "configured_type": device_type if type_mismatch else None,
            "running_lines": len(running_config.splitlines()),
            "software_version": software_version,
            "serial_number": serial_number
        }

    except Exception as e:
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
    interface_utilization: str,
    validation_results: str, performance_results: str, change_results: str,
    software_version: str, serial_number: str
) -> None:
    """保存数据到本地"""

    display_name = serial_number if serial_number else device_name
    device_base_dir = os.path.join(data_dir, device_name)
    week_dir = os.path.join(device_base_dir, week)
    create_device_dir(week, data_dir, device_name)

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
        week_dir
    )

    # 清理旧版本
    max_versions = settings.get("max_versions", 10)
    keep_latest_versions_per_device(data_dir, device_name, max_versions)

    # 更新设备清单中的序列号和最后同步时间
    if serial_number and serial_number != "未知":
        _update_device_serial(device_name, serial_number)
    _update_device_field(device_name, "last_synced", datetime.now().strftime("%m/%d/%Y %H:%M"))


def _generate_summary(
    device_name: str, device_ip: str, device_type: str,
    running_config: str, startup_config: str, logs_raw: str,
    version_info: str, software_version: str, serial_number: str,
    validation_results: str, performance_results: str, change_results: str,
    week_dir: str
) -> None:
    """生成 summary.txt"""
    from datetime import datetime

    lines = []
    lines.append("=" * 70)
    lines.append(f"设备配置摘要报告")
    lines.append(f"设备名称：{device_name}")
    lines.append(f"IP 地址：{device_ip}")
    lines.append(f"类型：{device_type}")
    if serial_number:
        lines.append(f"序列号 (SN): {serial_number}")
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
                      if ('interface' in l.lower() and ('Gi' in l or 'Ve' in l or 'Fa' in l))]
    lines.append(f"接口配置条目：{len(interface_lines)}")
    lines.append("")

    # 验证结果
    lines.append("-" * 70)
    lines.append("配置验证结果")
    lines.append("-" * 70)
    if validation_results:
        try:
            import json
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
        except:
            lines.append("验证数据解析失败")
    lines.append("")

    # 性能摘要
    lines.append("-" * 70)
    lines.append("性能分析摘要")
    lines.append("-" * 70)
    if performance_results:
        try:
            import json
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
        except:
            lines.append("性能数据解析失败")
    lines.append("")

    # 变更摘要
    lines.append("-" * 70)
    lines.append("变更检测摘要")
    lines.append("-" * 70)
    if change_results:
        try:
            import json
            change = json.loads(change_results)
            summary = change.get('summary', {})
            if summary:
                lines.append(f"新增行数：{summary.get('added', 0)}")
                lines.append(f"删除行数：{summary.get('removed', 0)}")
                lines.append(f"有变更：{change.get('has_changes', False)}")
            else:
                lines.append("没有基准配置，无法检测变更")
        except:
            lines.append("变更数据解析失败")
    lines.append("")

    lines.append("=" * 70)
    lines.append("报告结束")
    lines.append("=" * 70)

    summary_path = os.path.join(week_dir, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _get_devices_yaml_path() -> str:
    """获取 devices.yaml 的绝对路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "devices.yaml")


def _update_device_field(device_name: str, field: str, value: any) -> None:
    """更新 devices.yaml 中某个设备的字段"""
    import yaml
    config_path = _get_devices_yaml_path()
    if not os.path.exists(config_path):
        return
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for device in data.get("devices", []):
        if device.get("name") == device_name:
            device[field] = value
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _update_device_serial(device_name: str, serial_number: str) -> None:
    """更新设备清单中的序列号"""
    _update_device_field(device_name, "serial_number", serial_number)
 