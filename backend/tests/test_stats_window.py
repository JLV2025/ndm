"""区间流量 Top10 测试 —— 周锚定口径

核心断言：同一周内再采几次，排行榜**必须完全不变**。
"""
from datetime import date, datetime, time, timedelta

import pytest

import storage.database as db
from api.stats import (
    ALLOWED_WINDOWS,
    DEFAULT_WINDOW,
    _iso_week_str,
    _top_traffic,
)

TODAY = date.today()
THIS_MONDAY = TODAY - timedelta(days=TODAY.isoweekday() - 1)


def monday_weeks_ago(n: int) -> date:
    return THIS_MONDAY - timedelta(weeks=n)


def at(d: date, hour: int = 9) -> datetime:
    return datetime.combine(d, time(hour=hour))


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.execute("INSERT INTO devices (name, ip, type) VALUES ('D1SWI01', '10.0.0.1', 'cisco_ios')")
    c.commit()
    yield c
    c.commit()
    db.close_connection()
    db._db_path = original


def add_collection(conn, when: datetime, ports: dict, week: str = "", device_id: int = 1) -> int:
    """插入一次采集及其端口快照。ports: {端口名: (in_octets, out_octets, is_uplink)}"""
    week = week or _iso_week_str(when.date())
    cur = conn.execute(
        "INSERT INTO collections (device_id, week, phase, collected_at) VALUES (?, ?, '1', ?)",
        (device_id, week, when.isoformat()),
    )
    cid = cur.lastrowid
    for name, reading in ports.items():
        in_octets, out_octets, is_uplink = reading
        conn.execute(
            "INSERT INTO port_snapshots "
            "(collection_id, device_id, port_name, status, status_up, is_uplink, in_octets, out_octets) "
            "VALUES (?, ?, ?, 'connected', 1, ?, ?, ?)",
            (cid, device_id, name, is_uplink, in_octets, out_octets),
        )
    conn.commit()
    return cid


# 一周的字节数换算成 Mbps 的期望值
WEEK_SEC = 7 * 86400


def mbps(nbytes: int, span_sec: int = WEEK_SEC) -> float:
    return round(nbytes * 8 / span_sec / 1e6, 2)


# ============================================================
# 周口径
# ============================================================

def test_一周流量等于本周最早减上周最早(conn):
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (1000, 2000, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (3000, 5000, 0)})

    rows = _top_traffic(conn, 1)
    assert len(rows) == 1
    assert rows[0]["rx_mbps"] == mbps(2000)
    assert rows[0]["tx_mbps"] == mbps(3000)
    assert rows[0]["span_sec"] == WEEK_SEC


def test_周中再采一次结果完全不变(conn):
    """周口径锁死 —— 本周基准是「本周最早」那次读数，不是「本次采集」"""
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (1000, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (3000, 0, 0)})
    before = _top_traffic(conn, 1)

    # 本周二、周三又采了两次，读数继续增长
    add_collection(conn, at(monday_weeks_ago(0) + timedelta(days=1)), {"Gi1/0/1": (5000, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0) + timedelta(days=2)), {"Gi1/0/1": (9000, 0, 0)})

    assert _top_traffic(conn, 1) == before


def test_上周多采一次也不影响基线(conn):
    """基线取上周【最早】，不是最后一次 —— 否则会少算一截"""
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (1000, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(1) + timedelta(days=4)), {"Gi1/0/1": (1800, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (3000, 0, 0)})

    rows = _top_traffic(conn, 1)
    assert rows[0]["rx_mbps"] == mbps(2000)      # 3000 - 1000，而不是 3000 - 1800


def test_窗口4取四周前的最早读数(conn):
    for n in range(5):
        add_collection(conn, at(monday_weeks_ago(4 - n)), {"Gi1/0/1": (n * 1000, 0, 0)})

    rows = _top_traffic(conn, 4)
    assert rows[0]["span_sec"] == 4 * WEEK_SEC
    assert rows[0]["rx_mbps"] == mbps(4000, 4 * WEEK_SEC)


def test_窗口13取十三周前的最早读数(conn):
    for n in range(14):
        add_collection(conn, at(monday_weeks_ago(13 - n)), {"Gi1/0/1": (n * 1000, 0, 0)})

    rows = _top_traffic(conn, 13)
    assert rows[0]["span_sec"] == 13 * WEEK_SEC
    assert rows[0]["rx_mbps"] == mbps(13000, 13 * WEEK_SEC)


def test_只有一周数据则无结果(conn):
    """过渡期：显示空白，不回退到旧的瞬时口径"""
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (3000, 0, 0)})
    assert _top_traffic(conn, 1) == []


def test_计数器重置则该端口无值(conn):
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (5000, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (100, 0, 0)})   # 变小 = 重置

    assert _top_traffic(conn, 1) == []


def test_新端口不按0算(conn):
    """按 0 算会造出虚高假峰值直接冲榜首"""
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (0, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (500, 0, 0), "Gi1/0/9": (10**13, 0, 0)})

    ports = [r["port"] for r in _top_traffic(conn, 1)]
    assert "Gi1/0/9" not in ports


# ============================================================
# 排序与筛选
# ============================================================

def test_上行口优先_普通端口补齐(conn):
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (0, 0, 1), "Gi1/0/2": (0, 0, 0)})
    # 普通端口流量远大于上行口，但上行口仍排前面
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (1000, 0, 1), "Gi1/0/2": (9 * 10**6, 0, 0)})

    rows = _top_traffic(conn, 1)
    assert [r["port"] for r in rows] == ["Gi1/0/1", "Gi1/0/2"]
    assert rows[0]["is_uplink"] is True


def test_排序按总流量降序(conn):
    ports = {f"Gi1/0/{i}": (0, 0, 0) for i in range(1, 4)}
    add_collection(conn, at(monday_weeks_ago(1)), ports)
    add_collection(conn, at(monday_weeks_ago(0)), {
        "Gi1/0/1": (1000, 0, 0), "Gi1/0/2": (5000, 0, 0), "Gi1/0/3": (3000, 0, 0)})

    assert [r["port"] for r in _top_traffic(conn, 1)] == ["Gi1/0/2", "Gi1/0/3", "Gi1/0/1"]


def test_最多返回10条(conn):
    ports = {f"Gi1/0/{i}": (0, 0, 0) for i in range(1, 21)}
    add_collection(conn, at(monday_weeks_ago(1)), ports)
    add_collection(conn, at(monday_weeks_ago(0)), {f"Gi1/0/{i}": (i * 1000, 0, 0) for i in range(1, 21)})

    assert len(_top_traffic(conn, 1)) == 10


def test_零流量端口不进榜(conn):
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (0, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (0, 0, 0)})

    assert _top_traffic(conn, 1) == []


def test_带出设备名与状态(conn):
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (0, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (1000, 0, 0)})

    row = _top_traffic(conn, 1)[0]
    assert row["device"] == "D1SWI01"
    assert row["status"] == "connected"


def test_多设备互不干扰(conn):
    conn.execute("INSERT INTO devices (name, ip, type) VALUES ('D2SWI01', '10.0.0.2', 'cisco_ios')")
    conn.commit()
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (0, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (7000, 0, 0)})
    add_collection(conn, at(monday_weeks_ago(1)), {"Gi1/0/1": (0, 0, 0)}, device_id=2)
    add_collection(conn, at(monday_weeks_ago(0)), {"Gi1/0/1": (1000, 0, 0)}, device_id=2)

    rows = _top_traffic(conn, 1)
    assert [(r["device"], r["rx_mbps"]) for r in rows] == [
        ("D1SWI01", mbps(7000)), ("D2SWI01", mbps(1000))]


# ============================================================
# 窗口参数
# ============================================================

def test_窗口白名单():
    assert ALLOWED_WINDOWS == (1, 4, 13)
    assert DEFAULT_WINDOW == 1


def test_无数据返回空列表(conn):
    assert _top_traffic(conn, 1) == []
