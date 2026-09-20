"""设备生命周期数据访问 —— EoL 型号缓存 + 逐序列号保修登记。

三条语义（都在测试里钉住）：
  1. **手工值不被自动刷新覆盖**：`source='manual'` 的行，API 刷新时跳过（除非 force）——
     人工核实过的数据不该被一次外部查询悄悄改掉。
  2. **序列号匹配要容忍现实输入**：大小写、首尾空格、堆叠成员串（"A, B" 拆开）、
     同一序列号命中多台设备（报 ambiguous，不猜）。
  3. **日期一律 YYYY-MM-DD**：坏日期报 ValueError，不静默丢弃（否则页面显示为空，
     没人知道是"没填"还是"填错了"）。

函数都显式接收 `conn`（与 analyzers/compliance 同一风格，便于用临时库测试）。
"""
from __future__ import annotations

import datetime
import re
import sqlite3

_IMPORT_LINE_RE = re.compile(
    r"^\s*(\S+?)[,\t\s]+(\d{4}-\d{2}-\d{2})\s*(?:[,\t\s]+(.*))?$")


def split_serials(value: str | None) -> list[str]:
    """逗号/分号串 → 序列号列表（去空、去重、保序）。堆叠设备存的是 "A, B"。"""
    if not value:
        return []
    out: list[str] = []
    for part in re.split(r"[,;\s]+", value):
        s = part.strip()
        if s and s not in out:
            out.append(s)
    return out


def norm_date(value: str | None, field: str = "日期") -> str:
    """规范为 YYYY-MM-DD；空值返回空串；坏格式抛 ValueError（不静默丢）。"""
    v = (value or "").strip()
    if not v:
        return ""
    try:
        return datetime.date.fromisoformat(v).isoformat()
    except ValueError:
        raise ValueError(f"{field} 需为 YYYY-MM-DD 格式，收到 {value!r}")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- 读

def list_device_serials(conn, device_name: str) -> list[str]:
    """该设备的序列号清单（最近一次采集为主，devices 表兜底）。堆叠设备逐成员。"""
    row = conn.execute(
        "SELECT c.serial_number FROM collections c JOIN devices d ON d.id = c.device_id "
        "WHERE d.name = ? ORDER BY c.id DESC LIMIT 1", (device_name,)).fetchone()
    serials = split_serials(row[0] if row else None)
    if not serials:
        row = conn.execute("SELECT serial_number FROM devices WHERE name = ?",
                           (device_name,)).fetchone()
        serials = split_serials(row[0] if row else None)
    return serials


def get_model_eol(conn, model: str) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM eol_models WHERE model = ?", (model,)).fetchone()
    return dict(row) if row else None


def get_device_lifecycle(conn, device_name: str) -> dict:
    """设备生命周期全景：已知序列号 + 各自保修记录 + 型号 EoL。"""
    conn.row_factory = sqlite3.Row
    dev = conn.execute("SELECT model FROM devices WHERE name = ?", (device_name,)).fetchone()
    models = split_serials(dev[0] if dev else None)
    serials = list_device_serials(conn, device_name)
    rows = {r["serial"]: dict(r) for r in conn.execute(
        "SELECT * FROM device_lifecycle WHERE device_name = ?", (device_name,))}
    return {
        "device_name": device_name,
        "models": models,
        "model_eol": [{"model": m, **(get_model_eol(conn, m) or {})} for m in models],
        "serials": [{"serial": s, **rows.get(s, {})} for s in serials],
        # 库里登记了、但设备当前采集不到该序列号的行（改名/换件后仍要能看到）
        "extra_rows": [r for s, r in rows.items() if s not in serials],
    }


def serial_index(conn) -> dict[str, list[str]]:
    """全库序列号（大写）→ 设备名列表。取每台设备最近一次采集的序列号串。"""
    idx: dict[str, list[str]] = {}
    for name, serial_str in conn.execute(
            "SELECT d.name, c.serial_number FROM devices d JOIN collections c ON c.device_id = d.id "
            "WHERE c.id = (SELECT MAX(id) FROM collections WHERE device_id = d.id)"):
        for s in split_serials(serial_str):
            idx.setdefault(s.upper(), []).append(name)
    # devices 表兜底（还没采集过的设备）
    for name, serial_str in conn.execute("SELECT name, serial_number FROM devices"):
        for s in split_serials(serial_str):
            if name not in idx.setdefault(s.upper(), []):
                idx[s.upper()].append(name)
    return idx


def overview(conn) -> list[dict]:
    """每台设备一行：型号 / 序列号数 / 已登记数 / 最早到期日 —— 供"待查"清单与页面筛选。"""
    out = []
    for name, model in conn.execute("SELECT name, model FROM devices ORDER BY name"):
        serials = list_device_serials(conn, name)
        rows = conn.execute(
            "SELECT warranty_end, verified_at, source FROM device_lifecycle WHERE device_name = ?",
            (name,)).fetchall()
        ends = sorted(r[0] for r in rows if r[0])
        models = split_serials(model)
        eol_rows = [r for m in models for r in [get_model_eol(conn, m)] if r]
        out.append({
            "device_name": name,
            "models": models,
            "serials": serials,
            # 只数**填了日期**的行 —— 有行无日期等于没登记，别让"待查"被假的已登记数骗过
            "registered": len([r for r in rows if r[0]]),
            "warranty_end": ends[0] if ends else "",   # 最早到期（最需要关注的）
            "verified_at": max((r[1] or "" for r in rows), default=""),
            "eol_announced": any(r.get("end_of_sale") or r.get("end_of_support") for r in eol_rows),
        })
    return out


# ---------------------------------------------------------------- 写

def upsert_warranty(conn, device_name: str, serial: str, warranty_end: str, *,
                    note: str = "", verified_by: str = "", source: str = "manual",
                    model: str = "", force: bool = False) -> bool:
    """登记/更新一条保修记录。返回是否写入。

    **手工值不被自动刷新覆盖**：source='api' 且已有 source='manual' 的行 → 跳过（除非 force）。
    """
    serial = (serial or "").strip()
    end = norm_date(warranty_end, "保修到期日")
    if source == "api" and not force:
        row = conn.execute(
            "SELECT source FROM device_lifecycle WHERE device_name = ? AND serial = ?",
            (device_name, serial)).fetchone()
        if row and row[0] == "manual":
            return False
    now = _now()
    conn.execute(
        "INSERT INTO device_lifecycle (device_name, serial, model, warranty_end, note, source, "
        "verified_at, verified_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(device_name, serial) DO UPDATE SET "
        "model=excluded.model, warranty_end=excluded.warranty_end, note=excluded.note, "
        "source=excluded.source, verified_at=excluded.verified_at, "
        "verified_by=excluded.verified_by, updated_at=excluded.updated_at",
        (device_name, serial, model, end, note or "", source, now, verified_by or "", now))
    return True


def upsert_model_eol(conn, model: str, *, description: str = "", end_of_sale: str = "",
                     end_of_support: str = "", announcement: str = "", bulletin: str = "",
                     bulletin_url: str = "", source: str = "manual", updated_by: str = "",
                     note: str = "", force: bool = False, fetched_at: str = "") -> bool:
    """登记/更新型号 EoL。与保修同理：api 不覆盖 manual（除非 force）。"""
    model = (model or "").strip()
    if not model:
        raise ValueError("型号不能为空")
    if source == "api" and not force:
        row = conn.execute("SELECT source FROM eol_models WHERE model = ?", (model,)).fetchone()
        if row and row[0] == "manual":
            return False
    conn.execute(
        "INSERT INTO eol_models (model, description, end_of_sale, end_of_support, announcement, "
        "bulletin, bulletin_url, source, fetched_at, updated_by, note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(model) DO UPDATE SET "
        "description=excluded.description, end_of_sale=excluded.end_of_sale, "
        "end_of_support=excluded.end_of_support, announcement=excluded.announcement, "
        "bulletin=excluded.bulletin, bulletin_url=excluded.bulletin_url, "
        "source=excluded.source, fetched_at=excluded.fetched_at, "
        "updated_by=excluded.updated_by, note=excluded.note",
        (model, description or "", norm_date(end_of_sale, "EoS 日期"),
         norm_date(end_of_support, "停止支持日期"), norm_date(announcement, "公告日期"),
         bulletin or "", bulletin_url or "", source, fetched_at or _now(),
         updated_by or "", note or ""))
    return True


def parse_import_text(text: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """批量粘贴文本 → [(serial, 到期日, 备注)] + 无法解析的行。

    容忍：逗号/制表/空格分隔、前导标题行、空行、# 注释。
    例：``FOC1234X5AB,2028-05-01,Smart Net 到期``
    """
    rows, bad = [], []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _IMPORT_LINE_RE.match(line)
        if not m:
            bad.append(line)
            continue
        serial, date, note = m.group(1).strip(), m.group(2), (m.group(3) or "").strip()
        try:
            rows.append((serial, norm_date(date, "保修到期日"), note))
        except ValueError:
            bad.append(line)
    return rows, bad


def bulk_import_warranty(conn, rows: list[tuple[str, str, str]], *, verified_by: str = "") -> dict:
    """按序列号匹配设备并写入。返回 {matched, unmatched, ambiguous}。

    - 匹配：大小写不敏感；同一序列号命中多台 → 全部写入并计入 ambiguous（提示人工确认）
    - 匹配不到 → unmatched（不改任何数据）
    """
    idx = serial_index(conn)
    matched, unmatched, ambiguous = [], [], []
    for serial, end, note in rows:
        devices = idx.get(serial.upper(), [])
        if not devices:
            unmatched.append(serial)
            continue
        if len(devices) > 1:
            ambiguous.append({"serial": serial, "devices": devices})
        for name in devices:
            upsert_warranty(conn, name, serial, end, note=note, verified_by=verified_by,
                            source="manual")
            matched.append({"device_name": name, "serial": serial, "warranty_end": end})
    return {"matched": matched, "unmatched": unmatched, "ambiguous": ambiguous}
