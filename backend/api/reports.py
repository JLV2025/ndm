"""自定义报告 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()

# 数据库已在 main.py 启动时初始化，可直接顶层导入
from storage.database import get_connection as _get_db


def _distinct_models(model: str) -> list[str]:
    """型号字段去重（堆叠设备的 model 是逗号拼接的成员型号，同型号成员会重复）

    "JL658A, JL658A"                    → ["JL658A"]
    "WS-C2960X-48FPD-L, ...-48LPD-L, ...-48LPD-L" → ["WS-C2960X-48FPD-L", "WS-C2960X-48LPD-L"]
    """
    seen: list[str] = []
    for part in (model or "").split(","):
        p = part.strip()
        if p and p not in seen:
            seen.append(p)
    return seen or ["未知"]


@router.get("/api/reports/software-versions")
async def report_software_versions(
    device_type: Optional[str] = None,
    location: Optional[str] = None,
):
    """软件版本报告（扁平列表，前端一张表 + 列头排序）

    查询参数：device_type（设备类型）、location（位置，不传则查全部）。
    默认值用普通 None 而非 Query(...) —— Query 对象在直接调用（测试）时会原样传进 SQL。

    型号字段含堆叠成员（逗号拼接）→ 去重后作为分组/比较键：
    单机 "JL658A" 与堆叠 "JL658A, JL658A" 归为同一型号，版本一致性比较才成立。
    """
    db = _get_db()

    conditions = ["d.version != ''", "d.version != '未知'"]
    params = []
    if device_type:
        # cisco_ios_router 在 SQLite 中存储为 cisco_ios（Netmiko 驱动映射）
        if device_type == "cisco_ios_router":
            conditions.append("d.type IN ('cisco_ios', 'cisco_ios_router')")
        else:
            conditions.append("d.type = ?")
            params.append(device_type)
    if location:
        conditions.append("d.location = ?")
        params.append(location)

    where = " AND ".join(conditions)
    rows = db.execute(
        f"""SELECT d.name, d.type, d.location, d.model, d.version, d.last_synced
            FROM devices d WHERE {where}
            ORDER BY d.model, d.name""",
        params,
    ).fetchall()

    devices = []
    versions_by_model: dict[str, set] = {}
    for r in rows:
        models = _distinct_models(r["model"])
        model_key = ", ".join(models)
        devices.append({
            "name": r["name"],
            "type": r["type"],
            "location": r["location"] or "",
            "model": model_key,
            "version": r["version"],
            "last_synced": r["last_synced"],
        })
        versions_by_model.setdefault(model_key, set()).add(r["version"])

    # 同一型号出现多个版本 → 版本不一致（只报有比较对象的：≥2 台且版本不同）
    mismatches = [
        {"model": model, "versions": sorted(versions)}
        for model, versions in versions_by_model.items()
        if len(versions) > 1
    ]

    return {"devices": devices, "mismatches": mismatches}


@router.get("/api/reports/device-uptime")
async def report_device_uptime(location: Optional[str] = None):
    """所有设备的最新在线时间报告（含暂无数据的设备）

    查询参数：location（位置，不传则查全部）。
    """
    db = _get_db()

    params = []
    location_filter = ""
    if location:
        location_filter = "WHERE d.location = ?"
        params.append(location)

    rows = db.execute(
        f"""SELECT d.name, d.type, d.location, c.system_uptime_seconds,
                   c.collected_at, c.software_version
           FROM devices d
           LEFT JOIN collections c ON c.device_id = d.id
               AND c.id = (SELECT MAX(c2.id) FROM collections c2
                           WHERE c2.device_id = d.id AND c2.phase = '1')
           {location_filter}
           ORDER BY d.name""",
        params,
    ).fetchall()

    devices = []
    for r in rows:
        secs = r["system_uptime_seconds"]
        devices.append({
            "name": r["name"],
            "type": r["type"],
            "location": r["location"] or "",
            "system_uptime_seconds": secs,
            "uptime_days": round(secs / 86400, 1) if secs else None,
            "collected_at": r["collected_at"],
            "software_version": r["software_version"] or "",
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
async def report_bandwidth_summary(location: Optional[str] = None):
    """带宽利用率汇总（每台设备最新一次采集，只列有流量的端口）

    查询参数：location（位置，不传则查全部）。

    默认按吞吐（RX+TX Mbps）降序 —— 前端表头可再切按利用率排。
    利用率在 SQL 侧过滤而非 Python 侧：这两列可能为 NULL，
    原先的 max(rx, tx) 遇到 NULL 会直接抛 TypeError。
    """
    db = _get_db()

    params = []
    location_filter = ""
    if location:
        location_filter = "AND d.location = ?"
        params.append(location)

    rows = db.execute(
        f"""SELECT d.name AS device_name, d.location, p.port_name,
                   p.rx_util_pct, p.tx_util_pct, p.rx_mbps, p.tx_mbps,
                   p.status, p.description, c.collected_at
            FROM port_snapshots p
            JOIN collections c ON c.id = p.collection_id
            JOIN devices d ON d.id = p.device_id
            WHERE c.id IN (
                SELECT MAX(c2.id) FROM collections c2
                WHERE c2.phase = '1' GROUP BY c2.device_id
            )
            {location_filter}
              AND (p.rx_util_pct > 0 OR p.tx_util_pct > 0)
            ORDER BY (COALESCE(p.rx_mbps, 0) + COALESCE(p.tx_mbps, 0)) DESC
            LIMIT 1000""",
        params,
    ).fetchall()

    ports = []
    for r in rows:
        ports.append({
            "device_name": r["device_name"],
            "location": r["location"] or "",
            "port_name": r["port_name"],
            "rx_util_pct": r["rx_util_pct"],
            "tx_util_pct": r["tx_util_pct"],
            "rx_mbps": r["rx_mbps"],
            "tx_mbps": r["tx_mbps"],
            "status": r["status"],
            "description": r["description"],
            "collected_at": r["collected_at"],
        })

    return {"ports": ports, "count": len(ports)}
