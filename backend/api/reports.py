"""自定义报告 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()

# 数据库已在 main.py 启动时初始化，可直接顶层导入
from storage.database import get_connection as _get_db
from storage.device_dal import list_managed
from utils.device_identity import display_name, member_suffixes


def _split_list(value: str) -> list[str]:
    """逗号拼接字段 → 列表（成员级缓存串都与序列号同序 1:1）"""
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@router.get("/api/reports/software-versions")
async def report_software_versions(
    device_type: Optional[str] = None,
    location: Optional[str] = None,
):
    """软件版本报告 —— 按**物理成员行**逐行（2026-09-22 身份模型：物理成员在库中成行）。

    数据源是成员行自身（serial/model/version 为权威，展示层不再展开逗号串）；
    只列**当前在位**的成员（序列号在堆叠行的序列号缓存里）——已离线/已拆除的
    成员行不进报告，与旧展开语义一致。

    过渡期分工（第二步并入成员行后停用）：
    - ROM 版本 / 运行时间仍在堆叠行的 member_* 缓存串里（与序列号同序 1:1）；
    - 单机运行时间回退设备级（最新一次采集）。

    版本一致性只看**同一堆叠内部**（跨设备同型号版本不同属正常：分站点/升级批次）。
    查询参数：device_type（设备类型）、location（位置，不传则查全部）。
    默认值用普通 None 而非 Query(...) —— Query 对象在直接调用（测试）时会原样传进 SQL。
    """
    db = _get_db()
    managed = {d["name"]: d for d in list_managed()}

    conditions = ["d.kind != 'stack'", "d.version != ''", "d.version != '未知'"]
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
        f"""SELECT d.name, d.kind, d.stack_name, d.member_no, d.type, d.serial_number,
                   d.model, d.version, d.location, d.last_synced
            FROM devices d
            WHERE {where}
            ORDER BY d.model, d.name""",
        params,
    ).fetchall()

    # 设备级运行时间（单机回退用）：管理体各自最新一次采集
    uptime_by_managed = {
        r["name"]: r["system_uptime_seconds"]
        for r in db.execute(
            """SELECT d.name, c.system_uptime_seconds
               FROM devices d LEFT JOIN collections c ON c.device_id = d.id
                 AND c.id = (SELECT MAX(c2.id) FROM collections c2
                             WHERE c2.device_id = d.id AND c2.phase = '1')
               WHERE d.kind IN ('stack', 'standalone')""")
    }

    devices: list[dict] = []
    stack_groups: dict[str, list[dict]] = {}
    for r in rows:
        if r["kind"] == "member":
            stack = managed.get(r["stack_name"] or "")
            serials = _split_list(stack["serial_number"]) if stack else []
            if r["serial_number"] not in serials:
                continue                      # 已离线成员不进报告
            suffixes = member_suffixes(len(serials), (stack.get("member_ids") or ""))
            idx = suffixes.index(str(r["member_no"])) if str(r["member_no"]) in suffixes else -1
            roms = _split_list(stack.get("member_rom_versions") or "")
            upts = _split_list(stack.get("member_uptimes") or "")
            rom = roms[idx] if 0 <= idx < len(roms) else ""
            uptime = int(upts[idx]) if 0 <= idx < len(upts) and upts[idx].isdigit() else None
            name = display_name(r["stack_name"], str(r["member_no"]), len(serials))
            device_name = r["stack_name"]
            member_count = len(serials)
        else:
            rom = ""
            uptime = uptime_by_managed.get(r["name"])
            uptime = int(uptime) if uptime else None
            name = r["name"]
            device_name = r["name"]
            member_count = 1

        row = {
            "name": name,
            "device": device_name,
            "type": r["type"],
            "location": r["location"] or "",
            "model": r["model"] or "",
            "serial": r["serial_number"],
            "version": r["version"] or "",
            "rom_version": rom,
            "uptime_days": round(uptime / 86400, 1) if uptime else None,
            "last_synced": r["last_synced"],
            "member_count": member_count,
        }
        devices.append(row)
        if r["kind"] == "member":
            stack_groups.setdefault(device_name, []).append(row)

    mismatches: list[dict] = []
    for stack_name, members in stack_groups.items():
        version_set = {m["version"] for m in members if m["version"]}
        rom_set = {m["rom_version"] for m in members if m["rom_version"]}
        if len(version_set) > 1 or len(rom_set) > 1:
            mismatches.append({
                "device": stack_name,
                "versions": sorted(version_set),
                "rom_versions": sorted(rom_set),
                "members": [{"name": m["name"], "version": m["version"],
                             "rom_version": m["rom_version"]} for m in members],
            })

    return {"devices": devices, "mismatches": mismatches}


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
