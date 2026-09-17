"""分层保留与归档测试

归档是**不可逆删除**，所以这里既测「该归档的归档了」，也测「不该动的没动」。
"""
from pathlib import Path

import pytest

import storage.database as db
from storage.file_manager import (
    ARCHIVE_DIR,
    CONFIG_FILENAME,
    apply_archive,
    plan_archive,
    prune_db,
    run_retention,
    week_to_month,
)


def make_weeks(root: Path, device: str, weeks, with_file: bool = True) -> None:
    for w in weeks:
        d = root / device / w
        d.mkdir(parents=True, exist_ok=True)
        if with_file:
            (d / CONFIG_FILENAME).write_text(f"config of {w}", encoding="utf-8")


def week_dirs(root: Path, device: str) -> list:
    d = root / device
    return sorted(p.name for p in d.iterdir() if p.is_dir() and p.name != ARCHIVE_DIR)


# ============================================================
# 周 → 月 映射
# ============================================================

def test_周目录映射到周一所在月份():
    # 2026 年第 38 周的周一是 09-14
    assert week_to_month("2026-38") == "2026-M09"


def test_跨年周归属到周一那天():
    """2025 年第 1 周的周一落在 2024-12-30，应归到 2024 年 12 月"""
    assert week_to_month("2025-01") == "2024-M12"


# ============================================================
# 计划生成
# ============================================================

def test_未超过保留周数则不动(tmp_path):
    weeks = [f"2026-{i:02d}" for i in range(20, 20 + 16)]
    make_weeks(tmp_path, "D1SWI01", weeks)

    assert plan_archive(str(tmp_path)) == []


def test_超出部分按月收缩_每月只留最后一个(tmp_path):
    weeks = ["2026-10", "2026-11", "2026-12", "2026-13",
             "2026-20", "2026-21", "2026-22", "2026-23"]
    make_weeks(tmp_path, "D1SWI01", weeks)

    plan = plan_archive(str(tmp_path), weekly_keep=4)
    stale = weeks[:4]                      # 保留最近 4 周，过期的是最早的 4 个

    archived = {i["week"] for i in plan if i["action"] == "archive"}
    deleted = {i["week"] for i in plan if i["action"] == "delete"}
    assert archived | deleted == set(stale)
    assert not (archived & deleted)

    # 每个受影响的月份只留最后一个版本归档
    for month, month_weeks in _group_by_month(stale).items():
        assert archived & set(month_weeks) == {max(month_weeks)}


def _group_by_month(weeks) -> dict:
    out: dict = {}
    for w in weeks:
        out.setdefault(week_to_month(w), []).append(w)
    return out


def test_月归档目录不会被当成周目录(tmp_path):
    """严格正则的意义：2026-M09 若被当成周目录参与清理，归档内容会被删掉"""
    make_weeks(tmp_path, "D1SWI01", [f"2026-{i:02d}" for i in range(20, 20 + 20)])
    # 造一个已存在的月归档目录
    archive = tmp_path / "D1SWI01" / ARCHIVE_DIR / "2026-M09"
    archive.mkdir(parents=True)
    (archive / CONFIG_FILENAME).write_text("archived", encoding="utf-8")

    plan = plan_archive(str(tmp_path))

    assert not [i for i in plan if "M" in i["week"]]
    assert not [i for i in plan if i["path"].endswith(ARCHIVE_DIR)]


def test_archive目录本身不被当作设备(tmp_path):
    make_weeks(tmp_path, "D1SWI01", ["2026-20"])
    (tmp_path / ARCHIVE_DIR).mkdir()

    assert plan_archive(str(tmp_path)) == []


# ============================================================
# 执行
# ============================================================

def test_归档把文件移入月目录并删掉其余(tmp_path):
    make_weeks(tmp_path, "D1SWI01", ["2026-30", "2026-31", "2026-32", "2026-33"])

    plan = plan_archive(str(tmp_path), weekly_keep=2)
    stats = apply_archive(plan)

    assert stats["errors"] == []
    assert week_dirs(tmp_path, "D1SWI01") == ["2026-32", "2026-33"]     # 保留最近 2 周
    archived_files = list((tmp_path / "D1SWI01" / ARCHIVE_DIR).rglob(CONFIG_FILENAME))
    assert len(archived_files) >= 1
    assert archived_files[0].read_text(encoding="utf-8").startswith("config of ")


def test_归档后重复执行是空操作(tmp_path):
    make_weeks(tmp_path, "D1SWI01", ["2026-30", "2026-31", "2026-32", "2026-33"])
    apply_archive(plan_archive(str(tmp_path), weekly_keep=2))

    assert plan_archive(str(tmp_path), weekly_keep=2) == []


def test_多设备各自独立保留(tmp_path):
    make_weeks(tmp_path, "D1SWI01", ["2026-30", "2026-31", "2026-32", "2026-33"])
    make_weeks(tmp_path, "D2SWI01", ["2026-32", "2026-33"])

    plan = plan_archive(str(tmp_path), weekly_keep=2)

    assert {i["device"] for i in plan} == {"D1SWI01"}      # D2 只有 2 周，不动


def test_数据根目录不存在时不报错(tmp_path):
    assert plan_archive(str(tmp_path / "nope")) == []


# ============================================================
# DB 侧
# ============================================================

@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.execute("INSERT INTO devices (name, ip, type) VALUES ('D1SWI01', '10.0.0.1', 'cisco_ios')")
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def add_collection(c, when: str, config: str = "hostname X", logs: int = 0) -> int:
    cur = c.execute(
        "INSERT INTO collections (device_id, week, phase, collected_at, running_config) "
        "VALUES (1, '2026-38', '1', ?, ?)",
        (when, config),
    )
    cid = cur.lastrowid
    for i in range(logs):
        c.execute(
            "INSERT INTO device_logs (collection_id, device_id, log_timestamp, message) "
            "VALUES (?, 1, '2026-09-15', ?)",
            (cid, f"log {i}"),
        )
    c.commit()
    return cid


def add_stp_rows(c, collection_id: int, n: int = 3) -> None:
    """给某次采集插 n 行 STP 快照（设备 1）"""
    for i in range(n):
        c.execute(
            "INSERT INTO stp_snapshots (collection_id, device_id, vlan, port_name, role, state, mode) "
            "VALUES (?, 1, 10, ?, 'root', 'forwarding', 'rapid-pvst')",
            (collection_id, f"lag{i}"),
        )
    c.commit()


def test_DB配置只留最近两次(tmp_path, conn):
    ids = [add_collection(conn, f"2026-09-{d:02d}T09:00:00") for d in range(1, 6)]

    prune_db(conn)
    conn.commit()

    kept = [r[0] for r in conn.execute(
        "SELECT id FROM collections WHERE running_config IS NOT NULL ORDER BY id")]
    assert kept == ids[-2:]


def test_配置行数不受影响(tmp_path, conn):
    """配置变更趋势图要用 running_config_lines，不能被一起清掉"""
    add_collection(conn, "2026-09-01T09:00:00")
    conn.execute("UPDATE collections SET running_config_lines = 507")
    for d in range(2, 5):
        add_collection(conn, f"2026-09-{d:02d}T09:00:00")

    prune_db(conn)
    conn.commit()

    assert conn.execute("SELECT COUNT(*) FROM collections WHERE running_config_lines = 507").fetchone()[0] == 1


def test_日志只留最近两次采集(tmp_path, conn):
    ids = [add_collection(conn, f"2026-09-{d:02d}T09:00:00", logs=3) for d in range(1, 5)]

    prune_db(conn)
    conn.commit()

    remaining = {r[0] for r in conn.execute("SELECT DISTINCT collection_id FROM device_logs")}
    assert remaining == set(ids[-2:])
    assert conn.execute("SELECT COUNT(*) FROM device_logs").fetchone()[0] == 6


def test_留两次才能保住变更检测的基线(tmp_path, conn):
    """变更检测读「倒数第二次」的配置，只留 1 次会让基线消失"""
    add_collection(conn, "2026-09-01T09:00:00", config="old")
    add_collection(conn, "2026-09-08T09:00:00", config="middle")
    add_collection(conn, "2026-09-15T09:00:00", config="new")

    prune_db(conn)
    conn.commit()

    # collector_service 的写法：ORDER BY id DESC LIMIT 1 OFFSET 1
    baseline = conn.execute(
        "SELECT running_config FROM collections WHERE device_id = 1 AND phase = '1' "
        "ORDER BY id DESC LIMIT 1 OFFSET 1"
    ).fetchone()
    assert baseline[0] == "middle"


def test_STP快照只留最近两次采集(tmp_path, conn):
    """STP 图只读最新一轮；留第 2 轮作为「根桥/阻塞变化」的对比基线（用户指定）"""
    ids = [add_collection(conn, f"2026-09-{d:02d}T09:00:00") for d in range(1, 6)]
    for cid in ids:
        add_stp_rows(conn, cid, n=3)

    prune_db(conn)
    conn.commit()

    remaining = {r[0] for r in conn.execute("SELECT DISTINCT collection_id FROM stp_snapshots")}
    assert remaining == set(ids[-2:])
    assert conn.execute("SELECT COUNT(*) FROM stp_snapshots").fetchone()[0] == 6


def test_三种数据的保留次数各自生效(tmp_path, conn):
    """logs_keep / stp_keep 各自取 keep 列表 —— 曾错误借用 config 的列表（参数形同虚设）"""
    ids = [add_collection(conn, f"2026-09-{d:02d}T09:00:00", logs=2) for d in range(1, 6)]
    for cid in ids:
        add_stp_rows(conn, cid, n=2)

    prune_db(conn, config_keep=4, logs_keep=3, stp_keep=1)
    conn.commit()

    assert conn.execute(
        "SELECT COUNT(*) FROM collections WHERE running_config IS NOT NULL").fetchone()[0] == 4
    assert len({r[0] for r in conn.execute("SELECT DISTINCT collection_id FROM device_logs")}) == 3
    assert {r[0] for r in conn.execute(
        "SELECT DISTINCT collection_id FROM stp_snapshots")} == {ids[-1]}


# ============================================================
# 统一入口
# ============================================================

def test_dry_run不修改任何东西(tmp_path, conn):
    make_weeks(tmp_path, "D1SWI01", ["2026-30", "2026-31", "2026-32", "2026-33"])
    for d in range(1, 5):
        cid = add_collection(conn, f"2026-09-{d:02d}T09:00:00")
        add_stp_rows(conn, cid, n=3)

    result = run_retention(str(tmp_path), conn=conn, dry_run=True, weekly_keep=2)

    assert result["planned"] == len(result["plan"]) > 0
    assert result["config_cleared"] > 0          # 如实报数
    assert result["stp_deleted"] > 0
    # 但一个字节都没动
    assert week_dirs(tmp_path, "D1SWI01") == ["2026-30", "2026-31", "2026-32", "2026-33"]
    assert conn.execute(
        "SELECT COUNT(*) FROM collections WHERE running_config IS NOT NULL").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM stp_snapshots").fetchone()[0] == 12


def test_执行会真的归档与收缩(tmp_path, conn):
    make_weeks(tmp_path, "D1SWI01", ["2026-30", "2026-31", "2026-32", "2026-33"])
    for d in range(1, 5):
        cid = add_collection(conn, f"2026-09-{d:02d}T09:00:00")
        add_stp_rows(conn, cid, n=3)

    result = run_retention(str(tmp_path), conn=conn, dry_run=False, weekly_keep=2)

    assert result["archived"] + result["deleted"] == 2
    assert week_dirs(tmp_path, "D1SWI01") == ["2026-32", "2026-33"]
    assert conn.execute(
        "SELECT COUNT(*) FROM collections WHERE running_config IS NOT NULL").fetchone()[0] == 2
    assert result["stp_deleted"] > 0
    assert len({r[0] for r in conn.execute(
        "SELECT DISTINCT collection_id FROM stp_snapshots")}) == 2      # 只留最近 2 次


def test_没有过期目录时什么都不做(tmp_path, conn):
    make_weeks(tmp_path, "D1SWI01", ["2026-37", "2026-38"])
    add_collection(conn, "2026-09-15T09:00:00")

    result = run_retention(str(tmp_path), conn=conn, dry_run=False)

    assert result["archived"] == 0 and result["deleted"] == 0
    assert week_dirs(tmp_path, "D1SWI01") == ["2026-37", "2026-38"]
