"""
异常检测引擎
Phase 1 收集完成后自动运行，对比本周 vs 上周数据，发现异常生成告警
"""

import json
from datetime import datetime
from typing import List, Dict, Optional

from utils.config_diff import diff_configs


def _distinct_nonempty(value: str) -> set:
    """逗号拼接的成员级字段（与序列号同序）→ 去重后的非空取值集合

    只有一个成员值（非堆叠 / 解析失败退回整机版本）时集合大小为 1，不构成不一致。
    """
    return {v.strip() for v in (value or "").split(",") if v.strip()}


class AnomalyDetector:
    """Phase 1 后自动异常检测"""

    def __init__(self, db_connection):
        """传入 sqlite3.Connection（WAL 模式，线程安全）"""
        self.db = db_connection

    def detect_all(self, device_id: int, collection_id: int, week: str) -> List[Dict]:
        """运行全部检测规则，返回告警列表（不写入数据库）"""
        # 缓存一次 prev_collection，后续 check 方法复用
        self._prev_cache = self._get_prev_collection(device_id, week)

        alerts: List[Dict] = []
        alerts.extend(self._check_reboot(device_id, collection_id, week))
        alerts.extend(self._check_port_down(device_id, collection_id, week))
        alerts.extend(self._check_port_errors(device_id, collection_id, week))
        alerts.extend(self._check_config_change(device_id, collection_id))
        alerts.extend(self._check_config_drift(device_id, collection_id))
        alerts.extend(self._check_topology_change(device_id, collection_id, week))
        alerts.extend(self._check_version_mismatch(device_id, collection_id))
        alerts.extend(self._check_high_utilization(device_id, collection_id, week))

        self._prev_cache = None
        return alerts

    def detect_and_save(self, device_id: int, collection_id: int, week: str) -> int:
        """运行全部检测并写入 alerts 表，返回告警数"""
        # 先处理"状态型"告警的恢复：running/startup 一致了就把未保存告警自动消除。
        # 放在检测前，避免"先把旧的留着、又插一条新的"。
        self.resolve_recovered_drift(device_id, collection_id)
        alerts = self.detect_all(device_id, collection_id, week)

        now = datetime.now().isoformat()
        for a in alerts:
            detail_json = json.dumps(a.get("detail", {}), ensure_ascii=False)
            self.db.execute(
                """INSERT INTO alerts (device_id, collection_id, alert_type, severity, title, detail, suggestion, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id,
                    collection_id,
                    a["alert_type"],
                    a.get("severity", "WARNING"),
                    a["title"],
                    detail_json,
                    a.get("suggestion", ""),
                    now,
                ),
            )

        self.db.commit()
        return len(alerts)

    # ================================================================
    # 检测规则
    # ================================================================

    def _get_prev_collection(self, device_id: int, current_week: str) -> Optional[Dict]:
        """获取该设备上一次采集（不是本周）的 collection_id 和 week"""
        row = self.db.execute(
            """SELECT id, week, system_uptime_seconds
               FROM collections
               WHERE device_id = ? AND week != ? AND phase = '1'
               ORDER BY week DESC LIMIT 1""",
            (device_id, current_week),
        ).fetchone()
        return dict(row) if row else None

    def _check_reboot(self, device_id: int, collection_id: int, week: str) -> List[Dict]:
        """检测设备重启：本周 uptime < 上周 uptime"""
        prev = self._prev_cache
        if not prev or not prev.get("system_uptime_seconds"):
            return []

        cur_row = self.db.execute(
            "SELECT system_uptime_seconds FROM collections WHERE id=?",
            (collection_id,),
        ).fetchone()
        if not cur_row or not cur_row["system_uptime_seconds"]:
            return []

        cur_uptime = cur_row["system_uptime_seconds"]
        prev_uptime = prev["system_uptime_seconds"]

        if cur_uptime < prev_uptime:
            device_row = self.db.execute(
                "SELECT name FROM devices WHERE id=?", (device_id,)
            ).fetchone()
            return [{
                "alert_type": "device_reboot",
                "severity": "HIGH",
                "title": f"设备 {device_row['name']} 发生重启",
                "detail": {
                    "prev_uptime_seconds": prev_uptime,
                    "cur_uptime_seconds": cur_uptime,
                    "downtime_seconds": prev_uptime,  # 约等于旧 uptime
                    "prev_week": prev["week"],
                },
            }]
        return []

    def _check_port_down(self, device_id: int, collection_id: int, week: str) -> List[Dict]:
        """检测端口突然 DOWN：上周 UP 本周 DOWN，仅关注出现在邻居列表中的端口"""
        prev = self._prev_cache
        if not prev:
            return []

        prev_id = prev["id"]

        # 上周 UP ∩ 本周 DOWN，且端口出现在邻居列表中（过滤终端端口）
        rows = self.db.execute(
            """SELECT cur.port_name, cur.description
               FROM port_snapshots cur
               JOIN port_snapshots prev
                 ON prev.device_id = cur.device_id AND prev.port_name = cur.port_name
               WHERE cur.collection_id = ?
                 AND prev.collection_id = ?
                 AND cur.status_up = 0
                 AND prev.status_up = 1
                 AND cur.port_name IN (
                   SELECT DISTINCT local_port FROM neighbors
                   WHERE device_id = cur.device_id
                 )""",
            (collection_id, prev_id),
        ).fetchall()

        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "port_sudden_down",
                "severity": "HIGH",
                "title": f"端口 {r['port_name']} 异常 DOWN",
                "detail": {
                    "port_name": r["port_name"],
                    "description": r["description"] or "",
                    "prev_week": prev["week"],
                },
            })
        return alerts

    def _check_port_errors(self, device_id: int, collection_id: int, week: str) -> List[Dict]:
        """检测新增端口错误：本周有 err-disabled/discards 等"""
        prev = self._prev_cache
        if not prev:
            return []

        prev_id = prev["id"]

        # 本周有错误但上周没有（按 port_name + error_type）
        rows = self.db.execute(
            """SELECT cur.port_name, cur.error_type
               FROM port_errors cur
               WHERE cur.collection_id = ?
                 AND NOT EXISTS (
                   SELECT 1 FROM port_errors prev
                   WHERE prev.collection_id = ?
                     AND prev.device_id = cur.device_id
                     AND prev.port_name = cur.port_name
                     AND prev.error_type = cur.error_type
                 )""",
            (collection_id, prev_id),
        ).fetchall()

        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "port_errors",
                "severity": "WARNING",
                "title": f"端口 {r['port_name']} 出现新错误: {r['error_type']}",
                "detail": {
                    "port_name": r["port_name"],
                    "error_type": r["error_type"],
                },
            })
        return alerts

    def _check_config_change(self, device_id: int, collection_id: int) -> List[Dict]:
        """检测配置变更"""
        row = self.db.execute(
            "SELECT has_changes, added_lines, removed_lines FROM config_changes WHERE collection_id=?",
            (collection_id,),
        ).fetchone()

        if row and row["has_changes"]:
            device_row = self.db.execute(
                "SELECT name FROM devices WHERE id=?", (device_id,)
            ).fetchone()
            return [{
                "alert_type": "config_changed",
                "severity": "INFO",
                "title": f"设备 {device_row['name']} 配置发生变更",
                "detail": {
                    "added_lines": row["added_lines"],
                    "removed_lines": row["removed_lines"],
                },
            }]
        return []

    def _check_config_drift(self, device_id: int, collection_id: int) -> List[Dict]:
        """running-config 与 startup-config 不一致 → 存在**未保存的配置变更**。

        设备一旦重启，这些变更会全部丢失。现网已实测到一例：SHAD1SWI01 的
        C9500 SVL 链路配置在 running 里、不在 startup 里（设备自报时间戳印证：
        配置 6/30 变更、NVRAM 6/25 保存）。

        **这是"状态型"告警，不是"事件型"**（对比 config_changed：每次变更一条是合理的）：
          · 只要没人保存，它就一直存在 —— 每次都插一条的话，一周能堆上千条
          · 所以：已有未处理的同类告警就不重复新增；恢复一致时自动消除（见 resolve_recovered）
        """
        row = self.db.execute(
            "SELECT running_config, startup_config FROM collections WHERE id=?",
            (collection_id,),
        ).fetchone()
        if not row:
            return []
        running, startup = row["running_config"] or "", row["startup_config"] or ""
        if not running or not startup:
            return []          # 没采到就不判 —— 绝不能因为"没采到"报一条假问题

        d = diff_configs(running, startup)
        if not d["differ"]:
            return []
        if self._has_open_drift(device_id):
            return []          # 已在提示中，不重复

        device_row = self.db.execute(
            "SELECT name FROM devices WHERE id=?", (device_id,)
        ).fetchone()
        sample = [x["text"].strip() for x in d["only_running"][:5]]
        return [{
            "alert_type": "config_drift",
            "severity": "WARNING",
            "title": f"设备 {device_row['name']} 有未保存的配置变更",
            "detail": {
                "unsaved_lines": d.get("total_running_only", 0),
                "startup_extra_lines": d.get("total_startup_only", 0),
                "sample": sample,
                "truncated": d.get("truncated", False),
            },
            "suggestion": "在设备上执行 write memory（Aruba CX: write memory / copy running-config startup-config）"
                          "保存配置；未保存的变更在设备重启后会全部丢失。",
        }]

    def _has_open_drift(self, device_id: int) -> bool:
        """该设备是否已有未处理的"未保存配置"告警"""
        return self.db.execute(
            "SELECT 1 FROM alerts WHERE device_id=? AND alert_type='config_drift' "
            "AND resolved_at IS NULL LIMIT 1",
            (device_id,),
        ).fetchone() is not None

    def resolve_recovered_drift(self, device_id: int, collection_id: int) -> int:
        """running 与 startup 恢复一致时，把未处理的"未保存配置"告警自动消除。

        没有这一步，用户保存完配置后告警会一直挂着 —— 一个不会自己消失的告警，
        很快就会被人无视，那这条检查就白做了。
        返回被消除的告警数。
        """
        row = self.db.execute(
            "SELECT running_config, startup_config FROM collections WHERE id=?",
            (collection_id,),
        ).fetchone()
        if not row:
            return 0
        running, startup = row["running_config"] or "", row["startup_config"] or ""
        if not running or not startup:
            return 0                       # 没采到就保持现状，不误消除
        if diff_configs(running, startup)["differ"]:
            return 0
        return self.db.execute(
            "UPDATE alerts SET resolved_at=? WHERE device_id=? AND alert_type='config_drift' "
            "AND resolved_at IS NULL",
            (datetime.now().isoformat(), device_id),
        ).rowcount

    def _check_topology_change(self, device_id: int, collection_id: int, week: str) -> List[Dict]:
        """检测拓扑变更：邻居列表与上周不同"""
        prev = self._prev_cache
        if not prev:
            return []

        prev_id = prev["id"]

        # 本周有但上周没有的邻居（新增）
        new_rows = self.db.execute(
            """SELECT cur.local_port, cur.neighbor_name, cur.neighbor_type
               FROM neighbors cur
               WHERE cur.collection_id = ?
                 AND NOT EXISTS (
                   SELECT 1 FROM neighbors prev
                   WHERE prev.collection_id = ?
                     AND prev.device_id = cur.device_id
                     AND prev.local_port = cur.local_port
                     AND prev.neighbor_name = cur.neighbor_name
                 )""",
            (collection_id, prev_id),
        ).fetchall()

        # 上周有但本周没有的邻居（消失）
        gone_rows = self.db.execute(
            """SELECT prev.local_port, prev.neighbor_name, prev.neighbor_type
               FROM neighbors prev
               WHERE prev.collection_id = ?
                 AND NOT EXISTS (
                   SELECT 1 FROM neighbors cur
                   WHERE cur.collection_id = ?
                     AND cur.device_id = prev.device_id
                     AND cur.local_port = prev.local_port
                     AND cur.neighbor_name = prev.neighbor_name
                 )""",
            (prev_id, collection_id),
        ).fetchall()

        if not new_rows and not gone_rows:
            return []

        detail = {
            "new_neighbors": [{"port": r["local_port"], "name": r["neighbor_name"], "type": r["neighbor_type"]} for r in new_rows],
            "gone_neighbors": [{"port": r["local_port"], "name": r["neighbor_name"], "type": r["neighbor_type"]} for r in gone_rows],
        }

        return [{
            "alert_type": "topology_changed",
            "severity": "WARNING",
            "title": f"拓扑连接发生变更（+{len(new_rows)}/-{len(gone_rows)}）",
            "detail": detail,
        }]

    def _check_version_mismatch(self, device_id: int, collection_id: int) -> List[Dict]:
        """检测**同一台设备内部**堆叠成员版本不一致（软件版本或 ROM 版本）

        只比同一堆叠内部：跨设备同型号版本不同是正常的分站点差异（不同升级批次），
        不报警 —— 与「软件版本报告」的口径一致。

        现实意义：堆叠整机共享一个软件镜像，成员版本不同只会出现在 classic IOS 堆叠
        的升级窗口（一个成员已进新镜像、另一个还没重启）；Aruba VSF 的成员级版本
        只能比 ROM Version。
        """
        row = self.db.execute(
            """SELECT d.name, d.model, d.member_versions, d.member_rom_versions
               FROM devices d WHERE d.id = ?""",
            (device_id,),
        ).fetchone()
        if not row:
            return []

        versions = _distinct_nonempty(row["member_versions"])
        roms = _distinct_nonempty(row["member_rom_versions"])
        if len(versions) < 2 and len(roms) < 2:
            return []

        detail = {"device": row["name"], "model": row["model"]}
        parts = []
        if len(versions) > 1:
            detail["member_versions"] = sorted(versions)
            parts.append("软件版本 " + " / ".join(sorted(versions)))
        if len(roms) > 1:
            detail["member_rom_versions"] = sorted(roms)
            parts.append("ROM 版本 " + " / ".join(sorted(roms)))

        return [{
            "alert_type": "version_mismatch",
            "severity": "WARNING",
            "title": f"{row['name']} 堆叠成员版本不一致",
            "detail": {**detail, "summary": "；".join(parts)},
        }]

    def _check_high_utilization(self, device_id: int, collection_id: int, week: str) -> List[Dict]:
        """检测端口带宽利用率飙升：本周 > 80% 且上周 < 50%"""
        prev = self._prev_cache
        if not prev:
            return []

        prev_id = prev["id"]

        rows = self.db.execute(
            """SELECT cur.port_name, cur.rx_util_pct, cur.tx_util_pct,
                      prev.rx_util_pct AS prev_rx, prev.tx_util_pct AS prev_tx
               FROM port_snapshots cur
               JOIN port_snapshots prev
                 ON prev.device_id = cur.device_id AND prev.port_name = cur.port_name
               WHERE cur.collection_id = ?
                 AND prev.collection_id = ?
                 AND (cur.rx_util_pct > 80 OR cur.tx_util_pct > 80)
                 AND (prev.rx_util_pct < 50 AND prev.tx_util_pct < 50)""",
            (collection_id, prev_id),
        ).fetchall()

        alerts = []
        for r in rows:
            max_util = max(r["rx_util_pct"], r["tx_util_pct"])
            alerts.append({
                "alert_type": "high_utilization",
                "severity": "WARNING",
                "title": f"端口 {r['port_name']} 带宽利用率飙升到 {max_util:.0f}%",
                "detail": {
                    "port_name": r["port_name"],
                    "rx_util_pct": r["rx_util_pct"],
                    "tx_util_pct": r["tx_util_pct"],
                    "prev_rx_util_pct": r["prev_rx"],
                    "prev_tx_util_pct": r["prev_tx"],
                },
            })
        return alerts
