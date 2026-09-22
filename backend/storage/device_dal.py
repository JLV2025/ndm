"""
设备数据访问层 — SQLite 唯一数据源

统一管理设备的 CRUD，替换 YAML 直读直写。
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from storage.database import get_connection

# ================================================================
# 查询
# ================================================================


# 查询列（含身份三列 kind/stack_name/member_no —— API 与前端按 kind 分流）
_DEVICE_COLUMNS = """name, ip, type, platform, location, notes,
                     serial_number, member_ids, model, version, last_synced,
                     member_versions, member_rom_versions, member_uptimes,
                     uplink_ports, username, kind, stack_name, member_no"""


def list_managed() -> list[dict]:
    """全部**管理体**（stack + standalone）—— 采集/审计/配置/日志类页面的唯一入口。

    纪律（spec 第八节）：**禁止新代码裸查 devices**；需要设备清单时用本函数
    或 list_physical()。成员行不得混入管理体视角。
    """
    conn = get_connection()
    rows = conn.execute(
        f"SELECT {_DEVICE_COLUMNS} FROM devices "
        "WHERE kind IN ('stack', 'standalone') ORDER BY name"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_physical() -> list[dict]:
    """全部**物理设备**（member + standalone）—— 清单/版本/保修/画图类页面的唯一入口"""
    conn = get_connection()
    rows = conn.execute(
        f"SELECT {_DEVICE_COLUMNS} FROM devices "
        "WHERE kind IN ('member', 'standalone') ORDER BY name"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_devices() -> list[dict]:
    """兼容别名 = list_managed（既有调用点的语义就是"管理体清单"）"""
    return list_managed()


def get_device_by_name(name: str) -> dict | None:
    """根据设备名获取单个设备（任何 kind —— 成员行详情页也要能按名取到）"""
    conn = get_connection()
    row = conn.execute(
        f"SELECT {_DEVICE_COLUMNS} FROM devices WHERE name = ?",
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
                                serial_number, member_ids, model, version,
                                member_versions, member_rom_versions, member_uptimes,
                                uplink_ports, username)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                 serial_number=?, member_ids=?, model=?, version=?,
                 member_versions=?, member_rom_versions=?, member_uptimes=?,
                 uplink_ports=?, username=?
               WHERE name=?""",
            (new_name, *_extract_fields(merged), name),
        )
        if new_name != name:
            # 改名级联（spec 第五节：改名只允许改堆叠行；成员行名字是物化派生）
            conn.execute(
                "UPDATE devices SET name = ? || '-' || member_no, stack_name = ? "
                "WHERE kind = 'member' AND stack_name = ?",
                (new_name, new_name, name))
            # 档案表 last_device 同步 —— 否则下次采集把改名误报成"调拨"
            conn.execute("UPDATE device_members SET last_device = ? WHERE last_device = ?",
                         (new_name, name))
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
    """删除设备及其关联数据（级联删除 collections/ports/neighbors 等）。

    成员行**不可单独删除**（ValueError）—— 它是堆叠的一部分；
    删除堆叠行时级联删除其成员行与变更事件。
    """
    conn = get_connection()
    device = get_device_by_name(name)
    if not device:
        return False
    if device.get("kind") == "member":
        raise ValueError(
            f"{name} 是堆叠成员，请对堆叠 {device.get('stack_name') or '（未知）'} 操作")
    device_id = conn.execute(
        "SELECT id FROM devices WHERE name = ?", (name,)
    ).fetchone()["id"]

    # 删除设备关联的所有数据
    conn.execute("DELETE FROM device_logs WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM alerts WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM port_errors WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM port_snapshots WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM neighbors WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM stp_snapshots WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM config_changes WHERE device_id = ?", (device_id,))
    conn.execute("DELETE FROM validation_results WHERE device_id = ?", (device_id,))
    conn.execute(
        "DELETE FROM collections WHERE device_id = ?", (device_id,)
    )
    conn.execute("DELETE FROM device_change_events WHERE device_id = ?", (device_id,))
    # 成员行级联（成员行自身无 collections 等数据，只删行）
    conn.execute("DELETE FROM devices WHERE kind = 'member' AND stack_name = ?", (name,))
    conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()
    return True


# ================================================================
# 物理设备档案（device_members 表）
# ================================================================


def list_offline_members(days: int = 30) -> list[dict]:
    """获取离线物理设备档案

    时间阈值判定：last_seen 距今超过 days 天即视为离线
    （如拆机搬运中、长期闲置；重新上线后不再出现在此列表）。
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        """SELECT serial_number, model, version, last_device, last_member,
                  last_seen, first_seen
           FROM device_members
           WHERE last_seen < ? AND last_seen != ''
           ORDER BY last_seen DESC""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_member(serial: str) -> bool:
    """彻底删除物理设备档案，返回是否找到并删除"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM device_members WHERE serial_number = ?", (serial,))
    conn.commit()
    return cur.rowcount > 0


def member_reject_message(name: str) -> str:
    """按名入口的统一拒绝文案（spec 第八节：成员行不可采集/执行/查日志/单台审计）。

    返回空串 = 不是成员行。API 层用法：
        if msg := member_reject_message(device_name):
            raise HTTPException(status_code=400, detail=msg)
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT stack_name FROM devices WHERE name = ? AND kind = 'member'",
        (name,)).fetchone()
    if not row:
        return ""
    return f"{name} 是堆叠成员，请对堆叠 {row['stack_name'] or '（未知）'} 操作"


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
    """从数据字典中提取 12 个字段（用于 INSERT/UPDATE）"""
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
        data.get("member_ids", "") or "",
        data.get("model", "") or "",
        data.get("version", "") or "",
        data.get("member_versions", "") or "",
        data.get("member_rom_versions", "") or "",
        data.get("member_uptimes", "") or "",
        uplink,
        data.get("username", "") or "",
    )
