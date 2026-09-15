"""Dashboard 统计 API — 全量从 SQLite 读取"""
from datetime import date, timedelta

from fastapi import APIRouter

from analyzers.counter_parser import compute_week_deltas
from storage.database import get_connection as _get_db
from storage.device_dal import get_all_devices

router = APIRouter()

# 时间窗白名单（单位：周）：近 1 周 / 近 1 个月 / 近 3 个月
ALLOWED_WINDOWS = (1, 4, 13)
DEFAULT_WINDOW = 1
TOP_N = 10


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


def _iso_week_str(d: date) -> str:
    """ISO 周字符串，与 collections.week 格式一致（YYYY-WW，周两位补零）"""
    year, week, _ = d.isocalendar()
    return f"{year}-{week:02d}"


def _week_baselines(db, week_from: str, week_to: str) -> list:
    """取窗口内【每个 ISO 周最早一次采集】的计数器读数

    每周只留最早一条，是「一周内结果锁死」的唯一保证：本周基准 = 本周最早那次读数，
    周中再采多少次都不改变它。

    排序用 collected_at 而不是 week 字符串 —— 实测 week 全部两位补零、字符串排序
    安全，但用真实时间戳更稳，不依赖补零约定。
    """
    return db.execute("""
        WITH weekly AS (
            SELECT ps.device_id, ps.port_name, ps.in_octets, ps.out_octets, c.collected_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY ps.device_id, ps.port_name, c.week
                       ORDER BY c.collected_at, c.id
                   ) AS rn
            FROM port_snapshots ps
            JOIN collections c ON c.id = ps.collection_id
            WHERE c.phase = '1'
              AND c.week BETWEEN ? AND ?
              AND ps.in_octets IS NOT NULL
        )
        SELECT device_id, port_name, in_octets, out_octets, collected_at
        FROM weekly WHERE rn = 1
    """, (week_from, week_to)).fetchall()


def _port_metadata(db) -> dict:
    """每个端口最新一次快照的元数据：设备名 / 状态 / 是否上行口"""
    rows = db.execute("""
        SELECT d.name AS device_name, ps.device_id, ps.port_name,
               ps.status, ps.status_up, ps.is_uplink
        FROM port_snapshots ps
        JOIN devices d ON d.id = ps.device_id
        WHERE ps.collection_id IN (
            SELECT MAX(id) FROM collections WHERE phase = '1' GROUP BY device_id
        )
    """).fetchall()
    return {(r["device_id"], r["port_name"]): r for r in rows}


def _top_traffic(db, window: int) -> list:
    """按窗口计算区间流量并取 Top N

    排序 is_uplink DESC, (rx+tx) DESC —— 上行口优先，不足 TOP_N 条时用普通端口补齐：
    目的就是「知道哪些端口流量大」，不该因为上行口只有几个就只显示几条。

    过渡期（窗口内没有两条可比基准）返回空列表，**不回退到旧的瞬时速率口径** ——
    那批数据正是已知错位的。前端显示空态提示。
    """
    today = date.today()
    week_to = _iso_week_str(today)
    week_from = _iso_week_str(today - timedelta(weeks=window))

    deltas = compute_week_deltas(_week_baselines(db, week_from, week_to))
    if not deltas:
        return []

    meta = _port_metadata(db)
    rows = []
    for key, delta in deltas.items():
        rx = delta["rx_mbps"] or 0.0
        tx = delta["tx_mbps"] or 0.0
        if rx <= 0 and tx <= 0:
            continue  # 单方向计数器重置、另一方向本来就为 0
        info = meta.get(key)
        rows.append({
            "device": info["device_name"] if info else "",
            "port": key[1],
            "status": info["status"] if info else "",
            "is_uplink": bool(info["is_uplink"]) if info else False,
            "rx_mbps": rx,
            "tx_mbps": tx,
            "total_mbps": rx + tx,
            "span_sec": delta["span_sec"],
        })

    rows.sort(key=lambda r: (r["is_uplink"], r["total_mbps"]), reverse=True)
    for row in rows[:TOP_N]:
        row["rx_mbps"] = round(row["rx_mbps"], 2)
        row["tx_mbps"] = round(row["tx_mbps"], 2)
        row["total_mbps"] = round(row["total_mbps"], 2)
    return rows[:TOP_N]


@router.get("/overview")
async def get_overview(window: int = DEFAULT_WINDOW):
    """Dashboard 汇总数据：设备数、端口统计、区间流量 Top 10、最近采集时间（全量 SQLite）

    流量取「周锚定的累计计数器差值」，不是设备上报的瞬时速率 —— 采集间隔实测从
    13 分钟到 21 天不等，用 5 分钟瞬时值代表一周没有意义，且旧实现存在端口错位。
    """
    if window not in ALLOWED_WINDOWS:
        window = DEFAULT_WINDOW

    db = _get_db()
    yaml_data = get_all_devices()
    devices_list = yaml_data

    device_count = _count_physical_devices(devices_list)
    device_types = {}
    locations = set()

    # 设备类型统计
    type_set = set(d.get("type", "unknown") for d in devices_list)
    for dt in type_set:
        c = _count_physical_for_type(devices_list, dt)
        if c > 0:
            device_types[dt] = c

    # 从 SQLite 获取位置
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

    # 区间流量 Top 10（周锚定计数器差值，与「最新一次采集」无关）
    top_traffic = _top_traffic(db, window)

    # 错误端口数
    err_row = db.execute("""
        SELECT COUNT(DISTINCT pe.port_name) AS cnt
        FROM port_errors pe
        JOIN collections c ON c.id = pe.collection_id
        WHERE c.id IN (SELECT MAX(id) FROM collections WHERE phase = '1' GROUP BY device_id)
    """).fetchone()
    error_ports = err_row["cnt"] if err_row else 0

    return {
        "device_count": device_count,
        "device_types": device_types,
        "port_stats": port_stats,
        "error_ports": error_ports,
        "top_traffic": top_traffic,
        "window": window,
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
