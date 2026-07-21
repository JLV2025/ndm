"""
设备数据访问层 — SQLite 唯一数据源

统一管理设备的 CRUD，替换 YAML 直读直写。
"""

import json
import sqlite3
from typing import Optional

from storage.database import get_connection

# ================================================================
# 查询
# ================================================================


def get_all_devices() -> list[dict]:
    """获取所有设备，返回字典列表（前端 API 兼容格式）"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT name, ip, type, platform, location, notes,
                  serial_number, model, version, last_synced,
                  uplink_ports, username
           FROM devices
           ORDER BY name"""
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_device_by_name(name: str) -> dict | None:
    """根据设备名获取单个设备"""
    conn = get_connection()
    row = conn.execute(
        """SELECT name, ip, type, platform, location, notes,
                  serial_number, model, version, last_synced,
                  uplink_ports, username
           FROM devices WHERE name = ?""",
        (name,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def device_exists(name: str) -> bool:
    """检查设备名是否已存在"""
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM devices WHERE name = ?", (name,)).fetchone()
    return row is not None


# ================================================================
# 写入
# ================================================================


def create_device(data: dict) -> int:
    """新增设备，返回新记录 ID"""
    conn = get_connection()
    row = conn.execute(
        """INSERT INTO devices (name, ip, type, platform, location, notes,
                                serial_number, model, version,
                                uplink_ports, username)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data["name"], *_extract_fields(data)),
    ).lastrowid
    conn.commit()
    return row


def update_device(name: str, data: dict) -> bool:
    """更新设备。仅更新传入的字段，未传入的保留原值。返回是否找到设备

    Raises:
        ValueError: 改名时目标名已被占用（UNIQUE 约束冲突）
    """
    import sqlite3

    conn = get_connection()
    existing = get_device_by_name(name)
    if not existing:
        return False

    # 合并：传入值覆盖已有值
    merged = {**existing, **data}
    new_name = merged.get("name", name)
    merged["name"] = new_name
    try:
        cursor = conn.execute(
            """UPDATE devices SET
                 name=?, ip=?, type=?, platform=?, location=?, notes=?,
                 serial_number=?, model=?, version=?,
                 uplink_ports=?, username=?
               WHERE name=?""",
            (new_name, *_extract_fields(merged), name),
        )
        conn.commit()
        # 检查 rowcount：并发场景下设备可能已被删除/改名
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        # 唯一约束冲突 → 目标名已被占用
        raise ValueError(f"设备名 '{new_name}' 已存在")
    except sqlite3.Error:
        conn.rollback()
        return False


def delete_device(name: str) -> bool:
    """删除设备及其关联数据（级联删除 collections/ports/neighbors 等）"""
    conn = get_connection()
    device = get_device_by_name(name)
    if not device:
        return False
    device_id = conn.execute(
        "SELECT id FROM devices WHERE name = ?", (name,)
    ).fetchone()["id"]

    # 删除设备关联的所有数据
    conn.execute("DELETE FROM device_logs WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM alerts WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM port_errors WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM port_snapshots WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM neighbors WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM config_changes WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM validation_results WHERE device_id = ?", (device_id,))
    conn.execute(
        "DELETE FROM collections WHERE device_id = ?", (device_id,)
    )
    conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()
    return True


# ================================================================
# YAML 迁移（一次性）
# ================================================================


def migrate_from_yaml(yaml_path: str) -> int:
    """从 devices.yaml 迁移设备数据到 SQLite（幂等：已有设备跳过）"""
    import yaml
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return 0

    device_list = data.get("devices", []) if data else []
    conn = get_connection()
    migrated = 0

    for d in device_list:
        name = d.get("name", "")
        if not name:
            continue
        if device_exists(name):
            # 已有设备：仅补充 YAML 中有但 SQLite 中为空的字段
            existing = get_device_by_name(name)
            updates = {}
            for field in ("notes", "uplink_ports", "username", "platform", "location"):
                if not existing.get(field) and d.get(field):
                    updates[field] = d[field]
            if updates:
                update_device(name, updates)
                migrated += 1
        else:
            create_device(d)
            migrated += 1

    conn.commit()
    return migrated


# ================================================================
# 内部辅助
# ================================================================


def _row_to_dict(row: sqlite3.Row) -> dict:
    """将 SQLite Row 转为字典，uplink_ports 从 JSON 字符串还原为数组"""
    d = dict(row)
    # 解析 uplink_ports JSON
    raw = d.get("uplink_ports", "")
    if raw and isinstance(raw, str):
        try:
            d["uplink_ports"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            d["uplink_ports"] = None
    else:
        d["uplink_ports"] = None
    return d


def _extract_fields(data: dict) -> tuple:
    """从数据字典中提取 11 个字段（用于 INSERT/UPDATE）"""
    uplink = data.get("uplink_ports")
    if isinstance(uplink, list):
        uplink = json.dumps(uplink)
    elif not uplink:
        uplink = ""

    return (
        data.get("ip", ""),
        data.get("type", "cisco_ios"),
        data.get("platform", "") or "",
        data.get("location", "") or "",
        data.get("notes", "") or "",
        data.get("serial_number", "") or "",
        data.get("model", "") or "",
        data.get("version", "") or "",
        uplink,
        data.get("username", "") or "",
    )
