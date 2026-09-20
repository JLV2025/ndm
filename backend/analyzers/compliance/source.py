"""审计数据源 —— 从 NDM 库取"这次审计要审什么"。

取最新一次采集的 running-config，连同端口角色所需的辅助数据
（邻居、生成树角色、LAG 成员、设备档案的上行口清单）一起交给引擎。

三条必须守住的边界（计划 §六 风险 2/3 + §三 C）：
  1. **采集失败文本必须跳过**（`% 收集失败: …`）。不跳的话整台设备会被判成
     "配置全缺"，一口气报出几十条假问题——这是最容易毁掉审计可信度的坑。
  2. **区分"配置全文已被保留策略清理"与"从未采集"**。两者给用户的提示完全不同：
     前者是"历史上采过、全文已被清理"，后者是"这台设备从没采过"。
  3. **只读**。审计不写库；全量审计的结果落库是 API 层的事。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field

from .port_roles import PortContext

# 采集失败文本的前缀（collector_service 写入的原文）
FAILED_PREFIX = "% 收集失败"
# 低于这个长度基本不可能是真实配置（现网最小配置约 11 KB）
MIN_CONFIG_LEN = 1000


@dataclass
class Snapshot:
    """一台设备"此刻可审"的快照。"""
    device_id: int
    name: str
    location: str = ""
    platform: str = ""          # devices.platform（Netmiko 驱动名，不是 cx/cisco）
    model: str = ""
    collection_id: int | None = None
    week: str = ""
    collected_at: str = ""
    config: str = ""
    usable: bool = False        # 配置文本是否可用于审计
    reason: str = ""            # 不可用原因（给用户看的中文说明）

    @property
    def config_hash(self) -> str:
        """配置文本指纹 —— 随审计结果一起返回，前端据此判断"面板里渲染的配置"
        与"引擎判的配置"是不是同一份。"""
        if not self.config:
            return ""
        return hashlib.sha256(self.config.encode("utf-8")).hexdigest()[:16]


@dataclass
class AuditInput:
    """交给引擎的全部输入。"""
    snapshot: Snapshot
    port_context: PortContext = field(default_factory=PortContext)


def _clean_config(text: str) -> tuple[str, str]:
    """返回 (配置文本, 不可用原因)。可用时原因为空串。"""
    if text is None:
        return "", "配置全文已被保留策略清理（库中仅保留最近 2 次采集的全文）"
    if text.lstrip().startswith(FAILED_PREFIX):
        first = text.strip().splitlines()[0][:120] if text.strip() else ""
        return "", f"最近一次采集失败：{first}"
    if len(text) < MIN_CONFIG_LEN:
        return "", f"配置文本过短（{len(text)} 字节），疑似采集不完整"
    return text, ""


def load_snapshot(conn: sqlite3.Connection, name: str) -> Snapshot | None:
    """按设备名取最新一次采集的快照。设备不存在返回 None。"""
    conn.row_factory = sqlite3.Row
    dev = conn.execute(
        "SELECT id, name, location, platform, model FROM devices WHERE name = ?",
        (name,)).fetchone()
    if dev is None:
        return None

    snap = Snapshot(device_id=dev["id"], name=dev["name"], location=dev["location"] or "",
                    platform=dev["platform"] or "", model=dev["model"] or "")

    row = conn.execute(
        "SELECT id, week, collected_at, running_config FROM collections "
        "WHERE device_id = ? ORDER BY id DESC LIMIT 1", (dev["id"],)).fetchone()
    if row is None:
        snap.reason = "该设备从未采集过配置"
        return snap

    snap.collection_id = row["id"]
    snap.week = row["week"] or ""
    snap.collected_at = row["collected_at"] or ""
    config, reason = _clean_config(row["running_config"])
    snap.config, snap.usable, snap.reason = config, bool(config), reason
    return snap


def load_port_context(conn: sqlite3.Connection, snapshot: Snapshot) -> PortContext:
    """装载端口角色所需的辅助数据。缺哪一路都不影响出结果，只是置信度上不去。"""
    ctx = PortContext()
    if snapshot.collection_id is None:
        return ctx
    conn.row_factory = sqlite3.Row
    cid = snapshot.collection_id

    for row in conn.execute(
            "SELECT port_name, role FROM stp_snapshots WHERE collection_id = ?", (cid,)):
        ctx.stp_roles[row["port_name"]] = row["role"]

    for row in conn.execute(
            "SELECT local_port, neighbor_type FROM neighbors WHERE collection_id = ?", (cid,)):
        # 同一端口可能既有 CDP 又有 LLDP 记录，取第一条即可
        ctx.neighbor_types.setdefault(row["local_port"], row["neighbor_type"])

    lag = conn.execute("SELECT lag_membership FROM collections WHERE id = ?", (cid,)).fetchone()
    if lag and lag["lag_membership"]:
        try:
            ctx.lag_members = PortContext.from_lag_membership(
                json.loads(lag["lag_membership"])).lag_members
        except (ValueError, TypeError):
            pass

    dev = conn.execute("SELECT uplink_ports FROM devices WHERE id = ?",
                       (snapshot.device_id,)).fetchone()
    if dev and dev["uplink_ports"]:
        try:
            ctx.uplink_ports = set(json.loads(dev["uplink_ports"]))
        except (ValueError, TypeError):
            pass
    return ctx


def load_audit_input(conn: sqlite3.Connection, name: str) -> AuditInput | None:
    """按设备名装配一次审计的全部输入。设备不存在返回 None。"""
    snap = load_snapshot(conn, name)
    if snap is None:
        return None
    return AuditInput(snapshot=snap, port_context=load_port_context(conn, snap))


def list_audit_inputs(conn: sqlite3.Connection) -> list[AuditInput]:
    """全网快照（用于全量审计）。包含不可用的设备——它们的 reason 要展示给用户。"""
    conn.row_factory = sqlite3.Row
    names = [r["name"] for r in conn.execute("SELECT name FROM devices ORDER BY name")]
    out = []
    for n in names:
        item = load_audit_input(conn, n)
        if item is not None:
            out.append(item)
    return out
