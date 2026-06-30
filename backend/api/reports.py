"""自定义报告 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()

# 数据库已在 main.py 启动时初始化，可直接顶层导入
from storage.database import get_connection as _get_db


@router.get("/api/reports/software-versions")
async def report_software_versions(
    device_type: Optional[str] = Query(None, description="设备类型: cisco_ios / aruba_aoscx"),
):
    """所有设备的软件版本报告"""
    db = _get_db()

    conditions = ["d.version != ''", "d.version != '未知'"]
    params = []
    if device_type:
        conditions.append("d.type = ?")
        params.append(device_type)

    where = " AND ".join(conditions)
    rows = db.execute(
        f"""SELECT d.name, d.type, d.model, d.version, d.last_synced
            FROM devices d WHERE {where}
            ORDER BY d.type, d.model, d.version""",
        params,
    ).fetchall()

    # 按型号分组，找出不一致
    by_model = {}
    for r in rows:
        model = r["model"] or "未知"
        if model not in by_model:
            by_model[model] = []
        by_model[model].append({
            "name": r["name"],
            "type": r["type"],
            "version": r["version"],
            "last_synced": r["last_synced"],
        })

    return {
        "devices": [dict(r) for r in rows],
        "by_model": {
            model: {
                "devices": devs,
                "has_mismatch": len(set(d["version"] for d in devs)) > 1,
                "versions": list(set(d["version"] for d in devs)),
            }
            for model, devs in by_model.items()
        },
    }


@router.get("/api/reports/device-uptime")
async def report_device_uptime():
    """所有设备的最新在线时间报告"""
    db = _get_db()

    rows = db.execute(
        """SELECT d.name, d.type, c.system_uptime_seconds, c.collected_at, c.software_version
           FROM collections c
           JOIN devices d ON d.id = c.device_id
           WHERE c.id IN (
               SELECT MAX(c2.id) FROM collections c2
               WHERE c2.phase = '1' AND c2.system_uptime_seconds IS NOT NULL
               GROUP BY c2.device_id
           )
           ORDER BY d.name"""
    ).fetchall()

    devices = []
    for r in rows:
        uptime_days = r["system_uptime_seconds"] / 86400 if r["system_uptime_seconds"] else 0
        devices.append({
            "name": r["name"],
            "type": r["type"],
            "system_uptime_seconds": r["system_uptime_seconds"],
            "uptime_days": round(uptime_days, 1),
            "collected_at": r["collected_at"],
            "software_version": r["software_version"],
        })

    return {"devices": devices}


@router.get("/api/reports/port-trend")
async def report_port_trend(
    device_name: str = Query(..., description="设备名称"),
    port_name: str = Query(..., description="端口名称"),
    weeks: int = Query(8, ge=1, le=52, description="周数"),
):
    """指定端口的趋势数据（流量/利用率/状态）"""
    db = _get_db()

    device_row = db.execute("SELECT id FROM devices WHERE name=?", (device_name,)).fetchone()
    if not device_row:
        raise HTTPException(status_code=404, detail="设备不存在")

    device_id = device_row["id"]

    rows = db.execute(
        """SELECT c.week, p.rx_mbps, p.tx_mbps, p.rx_util_pct, p.tx_util_pct,
                  p.status, p.status_up, p.speed, p.description
           FROM port_snapshots p
           JOIN collections c ON c.id = p.collection_id
           WHERE p.device_id = ? AND p.port_name = ? AND c.phase = '1'
           ORDER BY c.week DESC
           LIMIT ?""",
        (device_id, port_name, weeks),
    ).fetchall()

    if not rows:
        return {"port_name": port_name, "device_name": device_name, "data_points": [], "message": "无数据"}

    # 反转为时间升序
    rows_reversed = list(reversed(rows))
    current = rows[0]

    return {
        "device_name": device_name,
        "port_name": port_name,
        "current_status": current["status"],
        "current_speed": current["speed"],
        "description": current["description"],
        "data_points": [
            {
                "week": r["week"],
                "rx_mbps": r["rx_mbps"],
                "tx_mbps": r["tx_mbps"],
                "rx_util_pct": r["rx_util_pct"],
                "tx_util_pct": r["tx_util_pct"],
                "status": r["status"],
                "status_up": bool(r["status_up"]),
            }
            for r in rows_reversed
        ],
    }


@router.get("/api/reports/bandwidth-summary")
async def report_bandwidth_summary(
    device_name: Optional[str] = Query(None, description="设备名称，不传则查全部"),
):
    """带宽利用率汇总"""
    db = _get_db()

    params = []
    device_filter = ""
    if device_name:
        device_filter = "AND d.name = ?"
        params.append(device_name)

    rows = db.execute(
        f"""SELECT d.name AS device_name, p.port_name, p.rx_util_pct, p.tx_util_pct,
                   p.rx_mbps, p.tx_mbps, p.status, p.description
            FROM port_snapshots p
            JOIN collections c ON c.id = p.collection_id
            JOIN devices d ON d.id = p.device_id
            WHERE c.id IN (
                SELECT MAX(c2.id) FROM collections c2
                WHERE c2.phase = '1' GROUP BY c2.device_id
            )
            {device_filter}
            ORDER BY (p.rx_util_pct + p.tx_util_pct) DESC
            LIMIT 200""",
        params,
    ).fetchall()

    high_util_ports = []
    for r in rows:
        max_util = max(r["rx_util_pct"], r["tx_util_pct"])
        if max_util > 0:
            high_util_ports.append({
                "device_name": r["device_name"],
                "port_name": r["port_name"],
                "rx_util_pct": r["rx_util_pct"],
                "tx_util_pct": r["tx_util_pct"],
                "rx_mbps": r["rx_mbps"],
                "tx_mbps": r["tx_mbps"],
                "status": r["status"],
                "description": r["description"],
            })

    return {"ports": high_util_ports, "count": len(high_util_ports)}
