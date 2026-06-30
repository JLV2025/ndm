"""Dashboard 统计 API — 全量从 SQLite 读取"""
from fastapi import APIRouter
from storage.database import get_connection as _get_db
from utils.settings_loader import load_devices

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
    """Dashboard 汇总数据：设备数、端口统计、Top 10 上行流量、最近采集时间（全量 SQLite）"""
    db = _get_db()
    yaml_data = load_devices()
    devices_list = yaml_data.get("devices", [])

    device_count = _count_physical_devices(devices_list)
    device_types = {}
    locations = set()

    # 设备类型统计
    type_set = set(d.get("type", "unknown") for d in devices_list)
    for dt in type_set:
        c = _count_physical_for_type(devices_list, dt)
        if c > 0:
            device_types[dt] = c

    # 从 YAML 获取位置（SQLite devices 表暂不存储 location）
    for dev in devices_list:
        loc = dev.get("location", "")
        if loc:
            locations.add(loc)

    # 查询所有设备最新一次采集的端口汇总
    latest_cols = db.execute("""
        SELECT c.id AS cid, c.device_id, d.name AS device_name, c.collected_at
        FROM collections c
        JOIN devices d ON d.id = c.device_id
        WHERE c.phase = '1'
          AND c.id IN (SELECT MAX(id) FROM collections WHERE phase = '1' GROUP BY device_id)
    """).fetchall()

    port_stats = {"total": 0, "up": 0, "down": 0, "disabled": 0}
    top_traffic = []
    last_collection = None

    for col in latest_cols:
        ts = col["collected_at"]
        if ts and (last_collection is None or ts > last_collection):
            last_collection = ts

        # 端口统计（单次聚合查询）
        port_row = db.execute(
            "SELECT COUNT(*) AS total, SUM(status_up) AS up "
            "FROM port_snapshots WHERE collection_id = ?",
            (col["cid"],)
        ).fetchone()
        if port_row:
            port_stats["total"] += port_row["total"] or 0
            port_stats["up"] += port_row["up"] or 0
            port_stats["down"] += (port_row["total"] or 0) - (port_row["up"] or 0)

        # 上行链路流量 Top 10
        uplinks = db.execute(
            "SELECT port_name, rx_mbps, tx_mbps FROM port_snapshots "
            "WHERE collection_id = ? AND is_uplink = 1 AND (rx_mbps > 0 OR tx_mbps > 0) "
            "ORDER BY (rx_mbps + tx_mbps) DESC LIMIT 10",
            (col["cid"],)
        ).fetchall()
        for p in uplinks:
            top_traffic.append({
                "device": col["device_name"],
                "port": p["port_name"],
                "total_mbps": round((p["rx_mbps"] or 0) + (p["tx_mbps"] or 0), 2),
                "rx_mbps": round(p["rx_mbps"] or 0, 2),
                "tx_mbps": round(p["tx_mbps"] or 0, 2),
            })

    # 错误端口数
    err_row = db.execute("""
        SELECT COUNT(DISTINCT pe.port_name) AS cnt
        FROM port_errors pe
        JOIN collections c ON c.id = pe.collection_id
        WHERE c.id IN (SELECT MAX(id) FROM collections WHERE phase = '1' GROUP BY device_id)
    """).fetchone()
    error_ports = err_row["cnt"] if err_row else 0

    # Top 10 排序
    top_traffic.sort(key=lambda x: x["total_mbps"], reverse=True)
    top_traffic = top_traffic[:10]

    # 上行端口为空时回退到所有有流量端口
    if not top_traffic:
        all_ports = db.execute("""
            SELECT d.name AS device_name, ps.port_name, ps.rx_mbps, ps.tx_mbps
            FROM port_snapshots ps
            JOIN collections c ON c.id = ps.collection_id
            JOIN devices d ON d.id = ps.device_id
            WHERE c.id IN (SELECT MAX(id) FROM collections WHERE phase = '1' GROUP BY device_id)
              AND (ps.rx_mbps > 0 OR ps.tx_mbps > 0)
            ORDER BY (ps.rx_mbps + ps.tx_mbps) DESC
            LIMIT 10
        """).fetchall()
        for p in all_ports:
            top_traffic.append({
                "device": p["device_name"],
                "port": p["port_name"],
                "total_mbps": round((p["rx_mbps"] or 0) + (p["tx_mbps"] or 0), 2),
                "rx_mbps": round(p["rx_mbps"] or 0, 2),
                "tx_mbps": round(p["tx_mbps"] or 0, 2),
            })

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
    """每设备每周的配置行数时间序列（全量 SQLite）"""
    db = _get_db()

    rows = db.execute("""
        SELECT d.name AS device_name, c.week, c.running_config_lines, c.collected_at
        FROM collections c
        JOIN devices d ON d.id = c.device_id
        WHERE c.phase = '1'
        ORDER BY d.name, c.week
    """).fetchall()

    weeks_set = set()
    device_data: dict = {}

    for r in rows:
        w = r["week"]
        weeks_set.add(w)
        dn = r["device_name"]
        if dn not in device_data:
            device_data[dn] = {}
        device_data[dn][w] = {
            "config_lines": r["running_config_lines"] or 0,
            "timestamp": r["collected_at"] or "",
        }

    sorted_weeks = sorted(weeks_set)
    series = []
    for device_name, week_map in device_data.items():
        data_points = [
            {"week": w, "config_lines": week_map[w]["config_lines"],
             "timestamp": week_map[w]["timestamp"]}
            for w in sorted_weeks if w in week_map
        ]
        if data_points:
            series.append({"device": device_name, "data": data_points})

    return {"weeks": sorted_weeks, "series": series}
