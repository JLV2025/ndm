"""数据文件 API 路由"""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
import os
import re
from storage.database import get_connection as _get_db

router = APIRouter()

# 从 settings 读取 data_root，避免相对路径问题
def _get_data_root() -> str:
    from utils.settings_loader import load_settings
    settings = load_settings()
    return settings.get("data_root", os.path.join(os.path.dirname(__file__), "..", "data"))


def validate_filename(filename: str) -> str:
    """
    验证文件名，防止路径遍历攻击
    只允许字母、数字、下划线、连字符和点号

    Args:
        filename: 要验证的文件名

    Returns:
        验证后的文件名

    Raises:
        HTTPException: 当文件名包含非法字符时
    """
    if not filename or not isinstance(filename, str):
        raise HTTPException(status_code=400, detail="文件名无效")

    # 防止路径遍历
    if '..' in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    if '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="文件名包含非法路径分隔符")

    # 只允许字母、数字、下划线、连字符和点号
    if not re.match(r'^[a-zA-Z0-9_\-\.\d]+$', filename):
        raise HTTPException(status_code=400, detail="文件名包含非法字符")

    # 防止文件名过长
    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="文件名过长")

    # 防止文件名以点号开头（隐藏文件）
    if filename.startswith('.'):
        raise HTTPException(status_code=400, detail="文件名不能以点号开头")

    return filename


def sanitize_device_name(device_name: str) -> str:
    """
    清理设备名称，防止路径遍历攻击

    Args:
        device_name: 要清理的设备名称

    Returns:
        清理后的设备名称

    Raises:
        HTTPException: 当设备名称包含非法字符时
    """
    if not device_name or not isinstance(device_name, str):
        raise HTTPException(status_code=400, detail="设备名称无效")

    # 防止路径遍历
    if '..' in device_name:
        raise HTTPException(status_code=400, detail="设备名称包含非法路径")

    if '/' in device_name or '\\' in device_name:
        raise HTTPException(status_code=400, detail="设备名称包含非法路径分隔符")

    # 只允许字母、数字、下划线、连字符
    if not re.match(r'^[a-zA-Z0-9_\-\d]+$', device_name):
        raise HTTPException(status_code=400, detail="设备名称包含非法字符")

    return device_name


@router.get("/{device_name}/weeks")
async def get_device_weeks(device_name: str):
    """获取设备所有可用的周目录列表（从 SQLite 查询）"""
    safe_device_name = sanitize_device_name(device_name)
    db = _get_db()
    if not db:
        return {"weeks": []}

    rows = db.execute(
        "SELECT DISTINCT c.week FROM collections c "
        "JOIN devices d ON c.device_id = d.id "
        "WHERE d.name = ? ORDER BY c.week DESC",
        (safe_device_name,)
    ).fetchall()
    return {"weeks": [r["week"] for r in rows]}


@router.get("/{device_name}/ports/latest")
async def get_device_ports(device_name: str):
    """获取设备最新端口状态和流量数据（从 SQLite 查询）"""
    safe_device_name = sanitize_device_name(device_name)
    db = _get_db()
    if not db:
        raise HTTPException(status_code=404, detail="数据不存在")

    # 查询最新 port_snapshots
    rows = db.execute("""
        SELECT ps.* FROM port_snapshots ps
        JOIN collections c ON ps.collection_id = c.id
        JOIN devices d ON ps.device_id = d.id
        WHERE d.name = ?
        ORDER BY c.id DESC, ps.port_name ASC
    """, (safe_device_name,)).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="无端口数据")

    # 按最新 collection_id 截断
    latest_cid = rows[0]["collection_id"]
    ports = []
    status_up = 0
    status_down = 0
    status_disabled = 0
    for r in rows:
        if r["collection_id"] != latest_cid:
            break
        status = r["status"] or ""
        if status == "up":
            status_up += 1
        elif status == "down":
            status_down += 1
        elif status in ("disabled", "admin down", "err-disabled"):
            status_disabled += 1
        ports.append({
            "name": r["port_name"],
            "status": status,
            "speed": r["speed"],
            "mode": r["mode"],
            "port_type": r["port_type"],
            "description": r["description"] or "",
            "native_vlan": r["native_vlan"],
            "is_uplink": bool(r["is_uplink"]),
            "rx_mbps": r["rx_mbps"],
            "tx_mbps": r["tx_mbps"],
            "rx_util_pct": r["rx_util_pct"],
            "tx_util_pct": r["tx_util_pct"],
        })

    return {
        "device_name": safe_device_name,
        "ports": ports,
        "total_ports": len(ports),
        "up_ports": status_up,
        "down_ports": status_down,
        "disabled_ports": status_disabled,
        "error_ports": 0,
    }


@router.get("/{device_name}/{week}/collection")
async def get_collection_meta(device_name: str, week: str):
    """获取某设备某周的采集元信息和可用数据类型列表（从 SQLite 查询）"""
    safe_device_name = sanitize_device_name(device_name)
    db = _get_db()
    if not db:
        raise HTTPException(status_code=404, detail="数据不存在")

    row = db.execute(
        """SELECT c.id, c.collected_at, c.software_version, c.serial_number,
                  c.model, c.system_uptime_seconds, c.running_config_lines,
                  c.boot_history_raw,
                  (SELECT COUNT(*) FROM device_logs dl WHERE dl.collection_id = c.id) AS log_count,
                  (SELECT COUNT(*) FROM port_snapshots ps WHERE ps.collection_id = c.id) AS port_count,
                  (SELECT COUNT(*) FROM neighbors n WHERE n.collection_id = c.id) AS neighbor_count,
                  (SELECT COUNT(*) FROM config_changes cc WHERE cc.collection_id = c.id AND cc.has_changes = 1) AS change_count
           FROM collections c
           JOIN devices d ON c.device_id = d.id
           WHERE d.name = ? AND c.week = ?
           ORDER BY c.id DESC LIMIT 1""",
        (safe_device_name, week),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="该周无采集记录")

    available_types = ["running-config"]
    if row["boot_history_raw"]:
        available_types.append("boot-history")
    if row["log_count"] > 0:
        available_types.append("logs")
    if row["port_count"] > 0:
        available_types.append("port-status")
    if row["neighbor_count"] > 0:
        available_types.append("neighbors")
    if row["change_count"] > 0:
        available_types.append("config-changes")

    return {
        "device_name": safe_device_name,
        "week": week,
        "collected_at": row["collected_at"],
        "available_types": available_types,
        "metadata": {
            "software_version": row["software_version"] or "",
            "serial_number": row["serial_number"] or "",
            "model": row["model"] or "",
            "system_uptime_seconds": row["system_uptime_seconds"],
            "running_config_lines": row["running_config_lines"] or 0,
        },
    }


@router.get("/{device_name}/{week}/raw/{data_type}")
async def get_raw_data(device_name: str, week: str, data_type: str):
    """从 SQLite 获取指定类型的原始数据"""
    if data_type not in ("running-config", "boot-history", "logs", "port-status", "neighbors", "config-changes"):
        raise HTTPException(status_code=400, detail=f"不支持的数据类型：{data_type}")

    safe_device_name = sanitize_device_name(device_name)
    db = _get_db()
    if not db:
        raise HTTPException(status_code=404, detail="数据不存在")

    # 获取 collection_id
    coll = db.execute(
        """SELECT c.id FROM collections c
           JOIN devices d ON c.device_id = d.id
           WHERE d.name = ? AND c.week = ?
           ORDER BY c.id DESC LIMIT 1""",
        (safe_device_name, week),
    ).fetchone()

    if not coll:
        raise HTTPException(status_code=404, detail="该周无采集记录")

    cid = coll["id"]

    if data_type == "running-config":
        row = db.execute(
            "SELECT running_config FROM collections WHERE id = ?", (cid,)
        ).fetchone()
        content = row["running_config"] if row else ""

    elif data_type == "boot-history":
        row = db.execute(
            "SELECT boot_history_raw FROM collections WHERE id = ?", (cid,)
        ).fetchone()
        content = row["boot_history_raw"] if row else ""
        if not content:
            raise HTTPException(status_code=404, detail="该设备该周无 boot-history 数据")

    elif data_type == "logs":
        rows = db.execute(
            """SELECT log_timestamp, severity, facility, message
               FROM device_logs
               WHERE collection_id = ?
               ORDER BY log_timestamp""",
            (cid,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="该设备该周无日志数据")
        content = "\n".join(
            f"{r['log_timestamp'] or '----'}  {r['severity'] or '-'}  {r['facility'] or '-'}  {r['message']}"
            for r in rows
        )

    elif data_type == "port-status":
        rows = db.execute(
            """SELECT port_name, status, speed, mode, port_type, description,
                      rx_mbps, tx_mbps, rx_util_pct, tx_util_pct
               FROM port_snapshots
               WHERE collection_id = ?
               ORDER BY port_name""",
            (cid,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="该设备该周无端口数据")
        header = f"{'Port':<16s} {'Status':<10s} {'Speed':<8s} {'Mode':<8s} {'Type':<8s} {'Rx Mbps':>8s} {'Tx Mbps':>8s} {'Rx%':>5s} {'Tx%':>5s}  Description"
        lines = [header, "-" * len(header)]
        for r in rows:
            desc = (r["description"] or "")[:40]
            lines.append(
                f"{r['port_name']:<16s} {r['status']:<10s} {r['speed']:<8s} {r['mode']:<8s} "
                f"{r['port_type'] or '':<8s} {r['rx_mbps'] or 0:>8.1f} {r['tx_mbps'] or 0:>8.1f} "
                f"{r['rx_util_pct'] or 0:>5.0f} {r['tx_util_pct'] or 0:>5.0f}  {desc}"
            )
        content = "\n".join(lines)

    elif data_type == "neighbors":
        rows = db.execute(
            """SELECT local_port, neighbor_name, neighbor_type, neighbor_platform,
                      neighbor_desc, source
               FROM neighbors
               WHERE collection_id = ?
               ORDER BY local_port""",
            (cid,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="该设备该周无邻居数据")
        header = f"{'Local Port':<16s} {'Neighbor':<24s} {'Type':<12s} {'Platform':<10s} {'Source':<6s}  Description"
        lines = [header, "-" * len(header)]
        for r in rows:
            desc = (r["neighbor_desc"] or "")[:40]
            lines.append(
                f"{r['local_port']:<16s} {r['neighbor_name']:<24s} {r['neighbor_type'] or '':<12s} "
                f"{r['neighbor_platform'] or '':<10s} {r['source'] or '':<6s}  {desc}"
            )
        content = "\n".join(lines)

    elif data_type == "config-changes":
        row = db.execute(
            """SELECT has_changes, added_lines, removed_lines, change_summary
               FROM config_changes
               WHERE collection_id = ?""",
            (cid,),
        ).fetchone()
        if not row or not row["has_changes"]:
            raise HTTPException(status_code=404, detail="该设备该周无配置变更")
        lines = [
            f"配置变更 — 新增 {row['added_lines']} 行，删除 {row['removed_lines']} 行",
            "=" * 60,
        ]
        if row["change_summary"]:
            import json
            try:
                changes = json.loads(row["change_summary"])
                for i, group in enumerate(changes):
                    group_type = group.get("type", "?")
                    group_lines = group.get("lines", [])
                    lines.append(f"\n[{i+1}] {group_type} ({len(group_lines)} 行):")
                    lines.append("-" * 40)
                    for line in group_lines:
                        prefix = "+ " if group_type == "added" else "- "
                        lines.append(f"{prefix}{line}")
            except (json.JSONDecodeError, TypeError):
                lines.append(row["change_summary"])
        content = "\n".join(lines)

    return {"type": data_type, "content": content}


@router.get("/{device_name}/{week}/files")
async def get_files_list(device_name: str, week: str):
    """获取文件列表 - 添加输入验证"""
    # 验证输入参数
    safe_device_name = sanitize_device_name(device_name)
    safe_filename = validate_filename(week)

    data_root = _get_data_root()
    file_path = os.path.join(data_root, safe_device_name, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="目录不存在")

    files = [f for f in os.listdir(file_path) if os.path.isfile(os.path.join(file_path, f))]
    return {"files": files}


@router.get("/{device_name}/{week}/{filename}")
async def get_data_file(device_name: str, week: str, filename: str):
    """获取数据文件 - 添加输入验证防止路径遍历"""
    # 验证输入参数
    safe_device_name = sanitize_device_name(device_name)
    safe_week = validate_filename(week)
    safe_filename = validate_filename(filename)

    data_root = _get_data_root()
    file_path = os.path.join(data_root, safe_device_name, safe_week, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    with open(file_path, "r", encoding="utf-8") as f:
        return {"filename": safe_filename, "content": f.read()}
