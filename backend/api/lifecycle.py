"""设备生命周期 API —— EoL 与保修期的登记、批量导入、刷新与概况。

设计要点：
  · **手工登记永远是可用路径**（Aruba 无 API、Cisco 保修无权限、EoX 凭据未到位，都靠它）
  · 批量导入按序列号自动匹配设备；**未匹配的序列号原样返回**让用户自己核对（不猜、不静默丢）
  · 刷新（Cisco EoX）未配凭据时返回 400 + 可读原因，界面直接展示；不影响手工登记
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

from services import eox_client  # noqa: E402
from services.lifecycle_status import eol_status, warranty_status  # noqa: E402
from storage import lifecycle_dal as dal  # noqa: E402
from storage.database import get_connection as _get_db  # noqa: E402

MAX_IMPORT_LINES = 500


class WarrantyRow(BaseModel):
    serial: str = ""
    warranty_end: str = ""      # YYYY-MM-DD；空串 = 清空日期
    note: str = ""


class DeviceLifecycleUpdate(BaseModel):
    rows: list[WarrantyRow] = []
    verified_by: str = ""


class ImportRequest(BaseModel):
    text: str = ""
    verified_by: str = ""


class ModelEolUpdate(BaseModel):
    description: str = ""
    end_of_sale: str = ""
    end_of_support: str = ""
    announcement: str = ""
    bulletin: str = ""
    bulletin_url: str = ""
    note: str = ""
    updated_by: str = ""


def _require_device(db, name: str) -> None:
    if not db.execute("SELECT 1 FROM devices WHERE name = ?", (name,)).fetchone():
        raise HTTPException(status_code=404, detail=f"设备不存在：{name}")


def _attach_statuses(info: dict) -> dict:
    """给生命周期全景的每行装配三色状态（判定唯一来源：services/lifecycle_status）。"""
    for item in list(info.get("serials", [])) + list(info.get("extra_rows", [])):
        item["warranty_status"] = warranty_status(item.get("warranty_end") or "",
                                                  item.get("note") or "")
    for m in info.get("model_eol", []):
        m["status"] = eol_status(m.get("end_of_sale") or "", m.get("end_of_support") or "")
    return info


def _lifecycle_payload(db, name: str) -> dict:
    return _attach_statuses(dal.get_device_lifecycle(db, name))


@router.get("/api/lifecycle/device/{name}")
async def get_device_lifecycle(name: str):
    """该设备的生命周期全景 + 刷新可用性（前端据此显示"未配凭据"提示）。"""
    db = _get_db()
    _require_device(db, name)
    info = _lifecycle_payload(db, name)
    info["refresh"] = eox_client.status()
    return info


@router.put("/api/lifecycle/device/{name}")
async def save_device_lifecycle(name: str, body: DeviceLifecycleUpdate):
    """逐序列号保存保修期（手工，source=manual）。"""
    db = _get_db()
    _require_device(db, name)
    saved = []
    try:
        for row in body.rows:
            dal.upsert_warranty(db, name, row.serial, row.warranty_end,
                                note=row.note, verified_by=body.verified_by,
                                model="", source="manual")
            saved.append(row.serial)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"ok": True, "saved": saved, "lifecycle": _lifecycle_payload(db, name)}


@router.post("/api/lifecycle/import")
async def import_warranty(body: ImportRequest):
    """批量粘贴导入：每行 ``序列号,到期日[,备注]``（逗号/制表/空格分隔）。

    返回 matched / unmatched / ambiguous / invalid 四类，未匹配的原样回显 —— 让用户
    自己核对而不是我们猜（序列号抄错一个字符就是另一台设备）。
    """
    lines = [ln for ln in (body.text or "").splitlines() if ln.strip()]
    if len(lines) > MAX_IMPORT_LINES:
        raise HTTPException(status_code=400,
                            detail=f"一次最多导入 {MAX_IMPORT_LINES} 行（当前 {len(lines)} 行）")
    rows, invalid = dal.parse_import_text(body.text or "")
    if not rows and not invalid:
        raise HTTPException(status_code=400, detail="没有可解析的行（格式：序列号,到期日[,备注]）")
    db = _get_db()
    res = dal.bulk_import_warranty(db, rows, verified_by=body.verified_by)
    db.commit()
    res["invalid"] = invalid
    return res


@router.put("/api/lifecycle/model/{model}")
async def save_model_eol(model: str, body: ModelEolUpdate):
    """手工登记型号 EoL（Aruba 与凭据到位前的 Cisco 都用它）。

    手工编辑**覆盖**已有记录（force=True）—— 这正是"手工修正"的用途。
    """
    db = _get_db()
    try:
        dal.upsert_model_eol(db, model, description=body.description,
                             end_of_sale=body.end_of_sale, end_of_support=body.end_of_support,
                             announcement=body.announcement, bulletin=body.bulletin,
                             bulletin_url=body.bulletin_url, note=body.note,
                             source="manual", updated_by=body.updated_by, force=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"ok": True, "model": dal.get_model_eol(db, model)}

@router.post("/api/lifecycle/refresh")
async def refresh_eox(force: bool = False):
    """按型号刷新 Cisco EoX（型号取自 devices.model，逗号串拆分去重）。"""
    db = _get_db()
    models = sorted({m for (v,) in db.execute("SELECT model FROM devices")
                     for m in dal.split_serials(v)})
    if not models:
        raise HTTPException(status_code=400, detail="还没有可查询的型号（设备表里 model 为空）")
    try:
        res = eox_client.refresh_models(db, models, force=force)
    except RuntimeError as e:            # 未配凭据 / 请求失败 → 可读原因
        raise HTTPException(status_code=400, detail=str(e))
    res["models"] = models
    return res


@router.get("/api/lifecycle/overview")
async def lifecycle_overview():
    """全部设备的生命周期概况（供"待查"清单与页面筛选）。"""
    db = _get_db()
    return {"devices": dal.overview(db), "refresh": eox_client.status()}


@router.get("/api/lifecycle/physical")
async def lifecycle_physical():
    """全部**物理设备**（成员 + 单机）一行一台：EoS/EoL + 维保 + 三色状态。

    生命周期页的唯一数据源（spec 第十三节）；约 50 行量级 —— 筛选/排序在前端做。
    每行 `device` = 编辑目标（所属堆叠/单机本身）：保修记账以管理体为单位。
    """
    db = _get_db()
    rows = dal.list_physical_rows(db)
    for row in rows:
        row["warranty_status"] = warranty_status(row["warranty_end"], row["note"])
        row["eol"]["status"] = eol_status(row["eol"]["end_of_sale"], row["eol"]["end_of_support"])
    return {"devices": rows}
