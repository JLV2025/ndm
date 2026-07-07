"""告警 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json

router = APIRouter()

# 数据库已在 main.py 启动时初始化，可直接顶层导入
from storage.database import get_connection as _get_db


@router.get("/api/alerts")
async def get_alerts(
    device_name: Optional[str] = Query(None, description="按设备名过滤"),
    alert_type: Optional[str] = Query(None, description="告警类型过滤"),
    severity: Optional[str] = Query(None, description="严重级别: INFO/WARNING/HIGH/CRITICAL"),
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 ISO 格式 YYYY-MM-DD"),
    unread_only: bool = Query(False, description="仅未读"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取告警列表，支持分页和过滤"""
    db = _get_db()

    conditions = []
    params = []

    if device_name:
        conditions.append("d.name = ?")
        params.append(device_name)

    if alert_type:
        conditions.append("a.alert_type = ?")
        params.append(alert_type)

    if severity:
        conditions.append("a.severity = ?")
        params.append(severity.upper())

    if unread_only:
        conditions.append("a.is_read = 0 AND a.resolved_at IS NULL")

    if date_from:
        conditions.append("a.created_at >= ?")
        params.append(date_from + "T00:00:00")

    if date_to:
        conditions.append("a.created_at <= ?")
        params.append(date_to + "T23:59:59")

    where = " AND ".join(conditions) if conditions else "1=1"

    # 总数
    count_row = db.execute(
        f"""SELECT COUNT(*) AS cnt FROM alerts a
            JOIN devices d ON d.id = a.device_id
            WHERE {where}""",
        params,
    ).fetchone()
    total = count_row["cnt"] if count_row else 0

    # 数据
    rows = db.execute(
        f"""SELECT a.id, a.device_id, d.name AS device_name, a.alert_type,
                   a.severity, a.title, a.detail, a.suggestion,
                   a.is_read, a.resolved_at, a.created_at
            FROM alerts a
            JOIN devices d ON d.id = a.device_id
            WHERE {where}
            ORDER BY
                CASE a.severity
                    WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1
                    WHEN 'WARNING' THEN 2 ELSE 3
                END,
                a.created_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    alerts = []
    for r in rows:
        detail = {}
        if r["detail"]:
            try:
                detail = json.loads(r["detail"])
            except (json.JSONDecodeError, TypeError):
                detail = {"raw": r["detail"]}
        alerts.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "alert_type": r["alert_type"],
            "severity": r["severity"],
            "title": r["title"],
            "detail": detail,
            "suggestion": r["suggestion"] or "",
            "is_read": bool(r["is_read"]),
            "resolved_at": r["resolved_at"],
            "created_at": r["created_at"],
        })

    return {"alerts": alerts, "total": total, "limit": limit, "offset": offset}


@router.get("/api/alerts/summary")
async def get_alerts_summary():
    """获取告警摘要（Dashboard 红点用）"""
    db = _get_db()

    rows = db.execute(
        """SELECT severity, COUNT(*) AS cnt
           FROM alerts
           WHERE is_read = 0 AND resolved_at IS NULL
           GROUP BY severity"""
    ).fetchall()

    summary = {"CRITICAL": 0, "HIGH": 0, "WARNING": 0, "INFO": 0, "total": 0}
    for r in rows:
        sev = r["severity"] or "INFO"
        summary[sev] = r["cnt"]
        summary["total"] += r["cnt"]

    # 最近 5 条未处理告警
    recent = db.execute(
        """SELECT a.id, a.title, a.severity, d.name AS device_name, a.created_at
           FROM alerts a JOIN devices d ON d.id = a.device_id
           WHERE a.is_read = 0 AND a.resolved_at IS NULL
           ORDER BY a.created_at DESC LIMIT 5"""
    ).fetchall()

    summary["recent"] = [dict(r) for r in recent]
    return summary


@router.put("/api/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: int):
    """标记告警为已读"""
    db = _get_db()
    db.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
    db.commit()
    return {"status": "ok"}


@router.put("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    """标记告警为已处理"""
    from datetime import datetime
    db = _get_db()
    db.execute(
        "UPDATE alerts SET resolved_at = ?, is_read = 1 WHERE id = ?",
        (datetime.now().isoformat(), alert_id),
    )
    db.commit()
    return {"status": "ok"}


@router.get("/api/alerts/{alert_id}/suggestion")
async def get_alert_suggestion(alert_id: int):
    """获取告警的处理建议"""
    db = _get_db()

    alert = db.execute(
        "SELECT alert_type, suggestion FROM alerts WHERE id = ?", (alert_id,)
    ).fetchone()

    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    # 优先使用告警自身的建议
    if alert["suggestion"]:
        return {"suggestion": alert["suggestion"]}

    # 回退到规则库
    hints = db.execute(
        "SELECT suggestion FROM remediation_hints WHERE alert_type = ?",
        (alert["alert_type"],),
    ).fetchall()

    if hints:
        return {"suggestion": hints[0]["suggestion"]}

    return {"suggestion": "暂无处理建议，请手动排查"}


