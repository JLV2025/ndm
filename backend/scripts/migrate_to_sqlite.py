#!/usr/bin/env python3
"""历史数据迁移脚本
从 data/ 目录遍历已有 JSON/RAW 文件，解析并写入 SQLite 数据库

用法：python -m backend.scripts.migrate_to_sqlite
"""

import os
import sys
import json
import re
import yaml
from datetime import datetime
from pathlib import Path

# 确保 backend 在 sys.path
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

from storage.database import init_db, get_connection, close_connection
from utils.settings_loader import get_devices_config_path, load_settings, load_devices
from services.collector_service import parse_syslog_lines, extract_uptime_seconds


def migrate():
    """主迁移入口"""
    settings = load_settings()
    data_root = settings.get("data_root", "./data")
    if not os.path.isabs(data_root):
        data_root = os.path.join(os.path.dirname(_BACKEND_DIR), data_root)

    print(f"[迁移] 数据目录: {data_root}")

    # 初始化数据库
    db_path = init_db(data_root)
    db = get_connection()
    print(f"[迁移] 数据库: {db_path}")

    # 加载设备清单 (返回 {"devices": [{name, ip, type, ...}, ...]})
    try:
        raw = load_devices()
        devices_list = raw.get("devices", []) if isinstance(raw, dict) else raw
    except Exception as e:
        print(f"[迁移] 无法加载设备清单: {e}")
        devices_list = []

    # 设备名 → 配置映射
    device_map = {d.get("name", ""): d for d in devices_list if isinstance(d, dict)}

    stats = {"devices": 0, "collections": 0, "ports": 0, "neighbors": 0, "logs": 0, "alerts": 0, "skipped": 0}

    # 遍历 data/ 下的设备目录
    if not os.path.exists(data_root):
        print(f"[迁移] data/ 目录不存在")
        return stats

    for entry in sorted(os.listdir(data_root)):
        device_dir = os.path.join(data_root, entry)
        if not os.path.isdir(device_dir):
            continue

        # 跳过 ndm.db 等非设备目录
        if entry.endswith(".db") or entry.startswith("."):
            continue

        device_config = device_map.get(entry)
        if not device_config:
            print(f"[迁移] 跳过未知设备: {entry}")
            stats["skipped"] += 1
            continue

        # 获取 YYYY-WW 周目录
        week_dirs = []
        for w in os.listdir(device_dir):
            w_path = os.path.join(device_dir, w)
            if os.path.isdir(w_path) and re.match(r'^\d{4}-\d{2}$', w):
                week_dirs.append(w)

        if not week_dirs:
            continue

        week_dirs.sort()
        stats["devices"] += 1

        # 确保设备记录存在
        _ensure_device(db, device_config)
        device_id = db.execute(
            "SELECT id FROM devices WHERE name=?", (device_config.get("name", ""),)
        ).fetchone()["id"]

        # 按周处理
        for week in week_dirs:
            try:
                col_stats = _migrate_week(db, device_id, device_dir, week, device_config)
                if col_stats:
                    stats["collections"] += 1
                    stats["ports"] += col_stats.get("ports", 0)
                    stats["neighbors"] += col_stats.get("neighbors", 0)
                    stats["logs"] += col_stats.get("logs", 0)
            except Exception as e:
                print(f"[迁移] {entry}/{week} 处理失败: {e}")
                db.rollback()

        print(f"[迁移] {entry}: {len(week_dirs)} 周数据已处理")

    db.commit()
    print(f"\n[迁移] 完成: {stats}")
    close_connection()
    return stats


def _ensure_device(db, device_config: dict):
    """确保设备在 devices 表中存在"""
    db.execute("""
        INSERT OR IGNORE INTO devices (name, ip, type, platform, location)
        VALUES (?, ?, ?, ?, ?)
    """, (
        device_config.get("name", ""),
        device_config.get("ip", ""),
        device_config.get("type", "cisco_ios"),
        device_config.get("platform", "") or "",
        device_config.get("location", "") or "",
    ))
    # 同步更新已有记录
    db.execute("""
        UPDATE devices SET ip=?, type=?, platform=?, location=?
        WHERE name=?
    """, (
        device_config.get("ip", ""), device_config.get("type", "cisco_ios"),
        device_config.get("platform", "") or "",
        device_config.get("location", "") or "",
        device_config.get("name", ""),
    ))


def _read_file(device_dir: str, week: str, filename: str) -> str:
    """读取文件，不存在返回空字符串"""
    path = os.path.join(device_dir, week, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _read_json(device_dir: str, week: str, filename: str) -> dict:
    """读取 JSON 文件"""
    content = _read_file(device_dir, week, filename)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return {}


def _migrate_week(db, device_id: int, device_dir: str, week: str, device_config: dict) -> dict | None:
    """迁移一周的数据"""
    week_path = os.path.join(device_dir, week)

    # 读取文件
    version_raw = _read_file(device_dir, week, "version.raw")
    running_config = _read_file(device_dir, week, "running-config.raw")
    logs_raw = _read_file(device_dir, week, "logs.raw")
    system_raw = _read_file(device_dir, week, "system.raw")
    boot_history = _read_file(device_dir, week, "boot-history.raw")  # Aruba only

    performance = _read_json(device_dir, week, "performance.json")
    validation = _read_json(device_dir, week, "validation.json")
    change = _read_json(device_dir, week, "change.json")
    neighbors = _read_json(device_dir, week, "neighbors.json")

    # 读取 summary.txt 提取版本号和序列号
    summary_text = _read_file(device_dir, week, "summary.txt")
    software_version = ""
    serial_number = ""
    device_model = ""
    if summary_text:
        for line in summary_text.splitlines():
            if "软件版本" in line:
                software_version = line.split("：")[-1].strip() if "：" in line else ""
            if "序列号" in line:
                serial_number = line.split("：")[-1].strip() if "：" in line else ""
            if "设备型号" in line:
                device_model = line.split("：")[-1].strip() if "：" in line else ""

    device_type = device_config.get("type", "cisco_ios")

    # 从 version.raw 提取版本号（若 summary 没有）
    if not software_version or software_version == "未知":
        from services.collector_service import extract_software_version
        software_version = extract_software_version(version_raw, device_type)

    # 从 version.raw / boot-history 提取运行时间
    system_uptime_seconds = extract_uptime_seconds(version_raw, boot_history, device_type)

    # 确定采集时间
    collected_at = ""
    summary_time = ""
    if summary_text:
        for line in summary_text.splitlines():
            if "生成时间" in line:
                summary_time = line.split("：")[-1].strip() if "：" in line else ""

    # 从文件名推断时间（文件修改时间）
    perf_file = os.path.join(week_path, "performance.json")
    if os.path.exists(perf_file):
        mtime = os.path.getmtime(perf_file)
        collected_at = datetime.fromtimestamp(mtime).isoformat()
    elif summary_time:
        collected_at = summary_time
    else:
        collected_at = datetime.now().isoformat()

    # 跳过空采集（没有 running-config）
    if not running_config or running_config.startswith('% 收集失败'):
        return None

    running_lines = len(running_config.splitlines()) if running_config else 0

    # 写入 collections
    db.execute("""
        INSERT INTO collections (device_id, week, phase, collected_at,
            software_version, serial_number, model, system_uptime_seconds,
            running_config, running_config_lines)
        VALUES (?, ?, '1', ?, ?, ?, ?, ?, ?, ?)
    """, (
        device_id, week, collected_at,
        software_version, serial_number, device_model,
        system_uptime_seconds, running_config, running_lines,
    ))
    collection_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    stats = {}

    # 迁移端口快照
    if performance:
        iface_summary = performance.get("interface_summary", {})
        port_details = iface_summary.get("details", [])
        if port_details:
            rows = []
            for p in port_details:
                rows.append((
                    collection_id, device_id, p.get("name", ""),
                    str(p.get("status", "")), 1 if p.get("status_up") else 0,
                    str(p.get("speed", "") or ""), str(p.get("mode", "") or ""),
                    str(p.get("type", "") or ""), str(p.get("description", "") or ""),
                    str(p.get("native_vlan", "") or ""),
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
            stats["ports"] = len(rows)

        # 迁移端口错误
        errors = performance.get("errors", {})
        error_ports = errors.get("ports", {})
        if error_ports:
            err_rows = []
            for err_type, ports in error_ports.items():
                for pn in ports:
                    err_rows.append((collection_id, device_id, pn, err_type, 1))
            db.executemany(
                "INSERT INTO port_errors (collection_id, device_id, port_name, error_type, count) VALUES (?, ?, ?, ?, ?)",
                err_rows,
            )

    # 迁移邻居关系
    neighbor_list = neighbors.get("neighbors", [])
    if neighbor_list:
        neigh_rows = []
        for n in neighbor_list:
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
        stats["neighbors"] = len(neigh_rows)

    # 迁移配置变更
    if change and change != {}:
        has_changes = 1 if change.get("has_changes") else 0
        change_summary = json.dumps(change.get("changes", []), ensure_ascii=False)
        cs = change.get("summary", {})
        db.execute(
            "INSERT INTO config_changes (collection_id, device_id, detected_at, has_changes, added_lines, removed_lines, change_summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (collection_id, device_id, collected_at, has_changes,
             cs.get("added", 0), cs.get("removed", 0), change_summary),
        )

    # 迁移验证结果
    if validation and validation != {}:
        vs = validation.get("summary", {})
        db.execute(
            "INSERT INTO validation_results (collection_id, device_id, errors_count, warnings_count, info_count, details) VALUES (?, ?, ?, ?, ?, ?)",
            (collection_id, device_id, vs.get("errors", 0), vs.get("warnings", 0), vs.get("info", 0),
             json.dumps(validation, ensure_ascii=False)),
        )

    # 迁移日志
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
            stats["logs"] = len(log_rows)

    db.commit()
    return stats


if __name__ == "__main__":
    migrate()
