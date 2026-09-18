"""自定义报告 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()

# 数据库已在 main.py 启动时初始化，可直接顶层导入
from storage.database import get_connection as _get_db


def _split_list(value: str) -> list[str]:
    """逗号拼接字段 → 列表（成员级字段都与序列号同序）"""
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _expand_device_members(row) -> tuple[list[dict], dict | None]:
    """把一台逻辑设备展开成**物理成员行**（堆叠拆成 设备名-1 / -2 / -3）

    成员三元组（序列号 / 型号 / 成员编号）在采集时就按同序逗号拼接入库：
    - 成员编号：Aruba VSF 用真实 Member ID，Cisco 堆叠没有 → 顺序号（≤9 不补零，
      与仪表盘设备清单同一套规则）
    - 成员版本：classic IOS 堆叠逐成员给出；IOS-XE 堆叠与 Aruba VSF 整堆叠共享
      一个镜像 → 用整机版本填充
    - 运行时间：成员级优先（Cisco 的 Switch Uptime / Aruba 的 Uptime）；
      **单机设备没有成员段** → 回退到设备级 system_uptime_seconds（就是这台机器自己的
      运行时间，准确）。多成员设备拿不到成员级数据时保持空 —— 设备级值只代表主/活动
      成员，填给其它成员是错的。

    版本一致性只看**同一台设备内部**的成员（跨设备型号相同但版本不同属正常：
    不同站点、不同升级批次）。返回 (成员行, 不一致信息或 None)。
    """
    serials = _split_list(row["serial_number"]) or [""]
    member_ids = _split_list(row["member_ids"])
    models = _split_list(row["model"])
    versions = _split_list(row["member_versions"])
    roms = _split_list(row["member_rom_versions"])
    uptimes = _split_list(row["member_uptimes"])
    # 设备级运行时间（SQL 里 LEFT JOIN 最新一次采集带出；直接构造的行没有该键）
    device_uptime = row["device_uptime_seconds"] if "device_uptime_seconds" in row.keys() else None
    total = len(serials)
    aligned_ids = member_ids if len(member_ids) == total else []
    pad = len(str(total))

    members: list[dict] = []
    for i in range(total):
        version = versions[i] if len(versions) == total else (row["version"] or "")
        rom = roms[i] if len(roms) == total else ""
        uptime = int(uptimes[i]) if len(uptimes) == total and uptimes[i].isdigit() else None
        if uptime is None and total == 1 and device_uptime:
            uptime = int(device_uptime)
        suffix = aligned_ids[i] if aligned_ids else str(i + 1).zfill(pad)
        members.append({
            "name": row["name"] if total == 1 else f'{row["name"]}-{suffix}',
            "device": row["name"],
            "type": row["type"],
            "location": row["location"] or "",
            "model": models[i] if i < len(models) else (models[-1] if models else ""),
            "serial": serials[i],
            "version": version,
            "rom_version": rom,
            "uptime_days": round(uptime / 86400, 1) if uptime else None,
            "last_synced": row["last_synced"],
            "member_count": total,
        })

    version_set = {m["version"] for m in members if m["version"]}
    rom_set = {m["rom_version"] for m in members if m["rom_version"]}
    mismatch = None
    if len(version_set) > 1 or len(rom_set) > 1:
        mismatch = {
            "device": row["name"],
            "versions": sorted(version_set),
            "rom_versions": sorted(rom_set),
            "members": [
                {"name": m["name"], "version": m["version"], "rom_version": m["rom_version"]}
                for m in members
            ],
        }
    return members, mismatch


@router.get("/api/reports/software-versions")
async def report_software_versions(
    device_type: Optional[str] = None,
    location: Optional[str] = None,
):
    """软件版本报告 —— 按**物理成员**展开（堆叠拆成 SZXD1SWI01-1 / -2 / -3）

    每行是一个物理交换机：自己的序列号、自己的型号、自己的版本与运行时间。
    查询参数：device_type（设备类型）、location（位置，不传则查全部）。
    默认值用普通 None 而非 Query(...) —— Query 对象在直接调用（测试）时会原样传进 SQL。
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
        f"""SELECT d.name, d.type, d.location, d.model, d.version, d.last_synced,
                   d.serial_number, d.member_ids,
                   d.member_versions, d.member_rom_versions, d.member_uptimes,
                   c.system_uptime_seconds AS device_uptime_seconds
            FROM devices d
            LEFT JOIN collections c ON c.device_id = d.id
                AND c.id = (SELECT MAX(c2.id) FROM collections c2
                            WHERE c2.device_id = d.id AND c2.phase = '1')
            WHERE {where}
            ORDER BY d.model, d.name""",
        params,
    ).fetchall()

    devices: list[dict] = []
    mismatches: list[dict] = []
    for r in rows:
        members, mismatch = _expand_device_members(r)
        devices.extend(members)
        if mismatch:
            mismatches.append(mismatch)

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
