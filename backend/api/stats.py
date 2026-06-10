"""Dashboard 统计 API"""
import os
import json
import glob
from fastapi import APIRouter
from utils.settings_loader import load_devices, load_settings

router = APIRouter()


def _count_physical_devices(devices_list: list[dict]) -> int:
    """按物理设备计数（堆叠设备按逗号分隔的序列号数计算）"""
    count = 0
    for dev in devices_list:
        sn = (dev.get("serial_number") or "").strip()
        if not sn or sn == "未知" or "," not in sn:
            count += 1
        else:
            count += len([s for s in sn.split(",") if s.strip()])
    return count


def _count_physical_for_type(devices_list: list[dict], device_type: str) -> int:
    """按类型统计物理设备数"""
    count = 0
    for dev in devices_list:
        if dev.get("type", "") != device_type:
            continue
        sn = (dev.get("serial_number") or "").strip()
        if not sn or sn == "未知" or "," not in sn:
            count += 1
        else:
            count += len([s for s in sn.split(",") if s.strip()])
    return count


@router.get("/overview")
async def get_overview():
    """Dashboard 汇总数据：设备数、端口统计、Top 10 上行流量、最近采集时间"""
    settings = load_settings()
    data_root = settings.get("data_root", "./data")
    yaml_data = load_devices()
    devices_list = yaml_data.get("devices", [])

    device_count = _count_physical_devices(devices_list)
    device_types = {}
    port_stats = {"total": 0, "up": 0, "down": 0, "disabled": 0}
    error_ports = 0
    top_traffic = []
    last_collection = None
    locations = set()

    # 先统计各类型物理设备数
    from collections import Counter
    type_set = set(d.get("type", "unknown") for d in devices_list)
    for dt in type_set:
        c = _count_physical_for_type(devices_list, dt)
        if c > 0:
            device_types[dt] = c

    for dev in devices_list:
        device_name = dev.get("name", "")
        location = dev.get("location", "")
        device_type = dev.get("type", "unknown")
        if location:
            locations.add(location)

        # 查找最新周的性能数据
        device_dir = os.path.join(data_root, device_name)
        if not os.path.exists(device_dir):
            continue

        weeks = sorted(
            [d for d in os.listdir(device_dir)
             if os.path.isdir(os.path.join(device_dir, d)) and "-" in d],
            reverse=True
        )
        if not weeks:
            continue

        latest_week = weeks[0]
        perf_path = os.path.join(device_dir, latest_week, "performance.json")
        if not os.path.exists(perf_path):
            continue

        try:
            with open(perf_path, "r", encoding="utf-8") as f:
                perf = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        # 汇总端口统计
        iface_summary = perf.get("interface_summary", {})
        port_stats["total"] += iface_summary.get("total", 0)
        port_stats["up"] += iface_summary.get("up", 0)
        port_stats["down"] += iface_summary.get("down", 0)

        # 错误端口
        errors = perf.get("errors", {})
        err_counts = errors.get("counts", {})
        error_ports += err_counts.get("total", 0) if isinstance(err_counts, dict) else 0

        # 上行链路流量（用于 Top 10）
        details = iface_summary.get("details", [])
        for port in details:
            if port.get("is_uplink") and (port.get("rx_mbps") or port.get("tx_mbps")):
                rx = port.get("rx_mbps", 0) or 0
                tx = port.get("tx_mbps", 0) or 0
                top_traffic.append({
                    "device": device_name,
                    "port": port.get("name", ""),
                    "total_mbps": round(rx + tx, 2),
                    "rx_mbps": round(rx, 2),
                    "tx_mbps": round(tx, 2),
                })

        # 最近采集时间
        ts = perf.get("timestamp", "")
        if ts and (last_collection is None or ts > last_collection):
            last_collection = ts

    # Top 10 按总流量降序
    top_traffic.sort(key=lambda x: x["total_mbps"], reverse=True)
    top_traffic = top_traffic[:10]

    # 如果没有上行端口流量数据，回退到所有端口 Top 10
    if not top_traffic:
        all_ports = []
        for dev in devices_list:
            device_name = dev.get("name", "")
            device_dir = os.path.join(data_root, device_name)
            if not os.path.exists(device_dir):
                continue
            weeks = sorted(
                [d for d in os.listdir(device_dir)
                 if os.path.isdir(os.path.join(device_dir, d)) and "-" in d],
                reverse=True
            )
            if not weeks:
                continue
            perf_path = os.path.join(device_dir, weeks[0], "performance.json")
            if not os.path.exists(perf_path):
                continue
            try:
                with open(perf_path, "r", encoding="utf-8") as f:
                    perf = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
            details = perf.get("interface_summary", {}).get("details", [])
            for port in details:
                rx = port.get("rx_mbps", 0) or 0
                tx = port.get("tx_mbps", 0) or 0
                if rx > 0 or tx > 0:
                    all_ports.append({
                        "device": device_name,
                        "port": port.get("name", ""),
                        "total_mbps": round(rx + tx, 2),
                        "rx_mbps": round(rx, 2),
                        "tx_mbps": round(tx, 2),
                    })
        all_ports.sort(key=lambda x: x["total_mbps"], reverse=True)
        top_traffic = all_ports[:10]

    return {
        "device_count": device_count,
        "device_types": device_types,
        "port_stats": port_stats,
        "error_ports": error_ports,
        "top_traffic": top_traffic,
        "last_collection": last_collection,
        "locations": sorted(locations)
    }


@router.get("/config-history")
async def get_config_history():
    """每设备每周的配置行数时间序列，用于配置变更趋势图"""
    settings = load_settings()
    data_root = settings.get("data_root", "./data")
    yaml_data = load_devices()
    devices_list = yaml_data.get("devices", [])

    weeks_set = set()
    device_data: dict = {}

    for dev in devices_list:
        device_name = dev.get("name", "")
        device_dir = os.path.join(data_root, device_name)
        if not os.path.exists(device_dir):
            continue

        week_dirs = sorted([
            d for d in os.listdir(device_dir)
            if os.path.isdir(os.path.join(device_dir, d)) and "-" in d
        ])

        for week in week_dirs:
            val_path = os.path.join(device_dir, week, "validation.json")
            if not os.path.exists(val_path):
                continue

            try:
                with open(val_path, "r", encoding="utf-8") as f:
                    val = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

            config_lines = val.get("config_lines", 0)
            ts = val.get("timestamp", "")

            weeks_set.add(week)
            if device_name not in device_data:
                device_data[device_name] = {}
            device_data[device_name][week] = {
                "config_lines": config_lines,
                "timestamp": ts,
            }

    sorted_weeks = sorted(weeks_set)

    # 构建每设备的时序数据
    series = []
    for device_name, week_map in device_data.items():
        data_points = []
        for week in sorted_weeks:
            entry = week_map.get(week)
            if entry:
                data_points.append({
                    "week": week,
                    "config_lines": entry["config_lines"],
                    "timestamp": entry["timestamp"],
                })
        if data_points:
            series.append({
                "device": device_name,
                "data": data_points,
            })

    return {
        "weeks": sorted_weeks,
        "series": series,
    }
