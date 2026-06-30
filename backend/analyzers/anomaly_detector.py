"""
异常检测引擎
Phase 1 收集完成后自动运行，对比本周 vs 上周数据，发现异常生成告警
"""

import json
from datetime import datetime
from typing import List, Dict, Optional


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
        alerts.extend(self._check_topology_change(device_id, collection_id, week))
        alerts.extend(self._check_version_mismatch(device_id, collection_id))
        alerts.extend(self._check_high_utilization(device_id, collection_id, week))

        self._prev_cache = None
        return alerts

    def detect_and_save(self, device_id: int, collection_id: int, week: str) -> int:
        """运行全部检测并写入 alerts 表，返回告警数"""
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
        """检测同型号设备版本不一致"""
        # 获取当前设备型号和版本
        cur = self.db.execute(
            "SELECT d.model, c.software_version FROM collections c JOIN devices d ON d.id=c.device_id WHERE c.id=?",
            (collection_id,),
        ).fetchone()
        if not cur or not cur["model"] or cur["model"] == "未知":
            return []
        if not cur["software_version"] or cur["software_version"] == "未知":
            return []

        # 查找同型号、不同版本的设备
        rows = self.db.execute(
            """SELECT d.name, d.version
               FROM devices d
               WHERE d.model = ?
                 AND d.version != ''
                 AND d.version != '未知'
                 AND d.version != ?""",
            (cur["model"], cur["software_version"]),
        ).fetchall()

        if rows:
            versions = {r["version"] for r in rows}
            versions.add(cur["software_version"])
            return [{
                "alert_type": "version_mismatch",
                "severity": "WARNING",
                "title": f"型号 {cur['model']} 存在版本不一致",
                "detail": {
                    "model": cur["model"],
                    "current_version": cur["software_version"],
                    "other_versions": list(versions),
                },
            }]
        return []

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
