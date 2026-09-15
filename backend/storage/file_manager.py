"""存储管理模块

- 按周组织数据：``{data_root}/{device}/YYYY-WW/running-config.raw``
- 分层保留（取代原先从未生效的 ``max_versions`` 单一阈值）：

  | 对象 | 规则 |
  |---|---|
  | 配置文本文件 | 最近 ``WEEKLY_KEEP`` 周按周保留；更早的**按月收缩** —— 该月**最后一个**版本移入 ``archive/{YYYY}-M{MM}/running-config.raw``，该月其余版本删除 |
  | DB ``collections.running_config`` | 每设备留最近 ``CONFIG_KEEP`` 次全文，更早的置 NULL |
  | DB ``device_logs`` | 每设备留最近 ``LOGS_KEEP`` 次采集的日志 |

归档的动机是**可查看性**，不是省空间（实测约 140 MB/年）。能保留就保留，只把粒度放粗。

**归档是不可逆删除** —— 该月非末周的配置会被永久删除。调用 ``apply_archive`` 前
先用 ``plan_archive`` 拿清单（命令行脚本提供 ``--dry-run``）。

"配置取月末"与"流量取周初"方向相反但都对：配置是**状态快照**（月末那份最能代表
该月状态），流量是**累计值**（需要最早读数作基线）。
"""

import os
import re
import shutil
from datetime import date, datetime

# 周目录按周保留的周数。16 = 流量排行最大窗口 13 周 + 余量：
# 窗口要用 13 周前的计数器读数做基线，留少了排行榜会静默缺数据。
WEEKLY_KEEP = 16

# DB 配置全文保留次数。**不能小于 2** —— 变更检测读的是「倒数第二次」采集的配置
# （collector_service 里 ORDER BY id DESC LIMIT 1 OFFSET 1），只留 1 次就没有基线了。
CONFIG_KEEP = 2

# DB 日志保留次数
LOGS_KEEP = 2

ARCHIVE_DIR = "archive"
CONFIG_FILENAME = "running-config.raw"

# 周目录识别**必须用严格正则**，否则月归档目录 2026-M09 会被当成周目录参与清理。
WEEK_DIR_RE = re.compile(r"^\d{4}-\d{2}$")
ARCHIVE_DIR_RE = re.compile(r"^\d{4}-M\d{2}$")


# ============================================================
# 路径
# ============================================================

def get_week_dir(base_path: str) -> str:
    """获取当前周的目录名 YYYY-WW"""
    now = datetime.now()
    iso_cal = now.isocalendar()
    return f"{iso_cal[0]}-{iso_cal[1]:02d}"


def get_device_path(base_path: str, device_name: str, week: str) -> str:
    """获取设备数据路径"""
    return os.path.join(base_path, week, device_name)


def create_device_dir(base_path: str, device_name: str, week: str) -> str:
    """创建设备数据目录"""
    device_dir = get_device_path(base_path, device_name, week)
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


def week_to_month(week_dir: str) -> str:
    """周目录名 → 月归档目录名：``2026-38`` → ``2026-M09``

    取该 ISO 周**周一**所在的月份 —— 跨月的周归属到周一那天，保证确定性
    （同一个周目录在任何时候算出的月份都一样）。
    """
    year, week = week_dir.split("-")
    monday = date.fromisocalendar(int(year), int(week), 1)
    return f"{monday.year}-M{monday.month:02d}"


# ============================================================
# 配置文本文件：按周保留 + 按月归档
# ============================================================

def plan_archive(data_root: str, weekly_keep: int = WEEKLY_KEEP) -> list:
    """扫描所有设备，列出归档计划（**只读，不修改任何文件**）

    规则：周目录按名称升序排，超出最近 ``weekly_keep`` 周的为过期；
    过期目录按所属月份分组，每组**只留最后一个**（该月最有代表性的一份）归档，
    其余删除。

    返回 ``[{"device", "week", "action", "path", "target", "archive"}]``，
    action 为 ``"archive"``（移入月目录）或 ``"delete"``（永久删除）。
    """
    plan: list = []
    if not os.path.isdir(data_root):
        return plan

    for device in sorted(os.listdir(data_root)):
        device_dir = os.path.join(data_root, device)
        # archive/ 自身要跳过 —— 它不是设备目录
        if not os.path.isdir(device_dir) or device == ARCHIVE_DIR:
            continue

        weeks = sorted(
            d for d in os.listdir(device_dir)
            if WEEK_DIR_RE.match(d) and os.path.isdir(os.path.join(device_dir, d))
        )
        if len(weeks) <= weekly_keep:
            continue

        by_month: dict = {}
        for w in weeks[: len(weeks) - weekly_keep]:
            by_month.setdefault(week_to_month(w), []).append(w)

        for month, month_weeks in sorted(by_month.items()):
            month_weeks.sort()
            target = os.path.join(device_dir, ARCHIVE_DIR, month)
            for w in month_weeks[:-1]:
                plan.append({
                    "device": device, "week": w, "action": "delete",
                    "path": os.path.join(device_dir, w),
                    "target": "", "archive": "",
                })
            last = month_weeks[-1]
            plan.append({
                "device": device, "week": last, "action": "archive",
                "path": os.path.join(device_dir, last),
                "target": target, "archive": month,
            })

    return plan


def apply_archive(plan: list) -> dict:
    """执行归档计划 —— **不可逆删除**，调用前务必先看过 plan_archive 的清单"""
    stats = {"archived": 0, "deleted": 0, "errors": []}

    for item in plan:
        try:
            if item["action"] == "archive":
                os.makedirs(item["target"], exist_ok=True)
                src = os.path.join(item["path"], CONFIG_FILENAME)
                dst = os.path.join(item["target"], CONFIG_FILENAME)
                # 同月再次归档时用更新的版本覆盖：越晚成为过期的周，越是该月最后一个版本
                if os.path.exists(dst):
                    os.remove(dst)
                if os.path.exists(src):
                    shutil.move(src, dst)
                shutil.rmtree(item["path"])
                stats["archived"] += 1
            else:
                shutil.rmtree(item["path"])
                stats["deleted"] += 1
        except OSError as e:
            stats["errors"].append(f"{item['path']}: {e}")

    return stats


# ============================================================
# DB：配置全文与日志按次数保留
# ============================================================

def prune_db(conn, config_keep: int = CONFIG_KEEP, logs_keep: int = LOGS_KEEP) -> dict:
    """DB 分层保留

    - ``collections.running_config``：每设备只留最近 ``config_keep`` 次采集的**全文**
      （即 682 份 = 22.93 MB，占 43 MB 库的 53%）。``running_config_lines`` 保留 ——
      配置变更趋势图要用它。
    - ``device_logs``：每设备只留最近 ``logs_keep`` 次采集的日志。

    按**记录数**而非时间 —— 不受采集间隔不均影响（实测 13 分钟到 21 天不等）。
    """
    stats = {"config_cleared": 0, "logs_deleted": 0}

    for (device_id,) in conn.execute("SELECT id FROM devices").fetchall():
        keep_ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM collections WHERE device_id = ? AND phase = '1' "
                "ORDER BY collected_at DESC, id DESC LIMIT ?",
                (device_id, config_keep),
            ).fetchall()
        ]
        if not keep_ids:
            continue
        marks = ",".join("?" * len(keep_ids))

        stats["config_cleared"] += conn.execute(
            f"UPDATE collections SET running_config = NULL "
            f"WHERE device_id = ? AND phase = '1' AND running_config IS NOT NULL "
            f"AND id NOT IN ({marks})",
            (device_id, *keep_ids),
        ).rowcount

        stats["logs_deleted"] += conn.execute(
            f"DELETE FROM device_logs WHERE device_id = ? AND collection_id NOT IN ({marks})",
            (device_id, *keep_ids),
        ).rowcount

    return stats


# ============================================================
# 统一入口
# ============================================================

def run_retention(data_root: str, conn=None, dry_run: bool = False,
                  weekly_keep: int = WEEKLY_KEEP) -> dict:
    """执行分层保留。采集结束后调用，也可由命令行脚本手动触发

    ``dry_run=True`` 时**只列清单不动手** —— 归档是不可逆删除，先用它确认。
    """
    plan = plan_archive(data_root, weekly_keep=weekly_keep)

    result = {
        "planned": len(plan),
        "archived": 0,
        "deleted": 0,
        "config_cleared": 0,
        "logs_deleted": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    if dry_run:
        result["plan"] = [
            f"{i['action']:7s} {i['device']}/{i['week']}"
            + (f" -> archive/{i['archive']}" if i["archive"] else "")
            for i in plan
        ]
        if conn is not None:
            # DB 侧也如实报数：先跑一遍再回滚，避免为了「预览」写一套重复的统计查询
            pruned = prune_db(conn)
            conn.rollback()
            result["config_cleared"] = pruned["config_cleared"]
            result["logs_deleted"] = pruned["logs_deleted"]
        return result

    if plan:
        applied = apply_archive(plan)
        result["archived"] = applied["archived"]
        result["deleted"] = applied["deleted"]
        result["errors"] = applied["errors"]

    if conn is not None:
        pruned = prune_db(conn)
        result["config_cleared"] = pruned["config_cleared"]
        result["logs_deleted"] = pruned["logs_deleted"]
        conn.commit()

    return result
