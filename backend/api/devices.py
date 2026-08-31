"""设备管理 API 路由 — SQLite 唯一数据源"""

from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel, field_validator
from typing import List, Optional
import re
import csv
import io
from storage.device_dal import (
    get_all_devices,
    get_device_by_name,
    create_device as dal_create,
    update_device as dal_update,
    delete_device as dal_delete,
    device_exists,
)

router = APIRouter()


class DeviceCreate(BaseModel):
    name: str
    ip: str
    type: str = "cisco_ios"
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    uplink_ports: Optional[List[str]] = None
    member_ids: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError('设备名称不能为空')
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('设备名称包含非法字符')
        if not re.match(r'^[a-zA-Z0-9_\-\d]+$', v):
            raise ValueError('设备名称只能包含字母、数字、下划线和连字符')
        if len(v) > 100:
            raise ValueError('设备名称过长')
        return v

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError('IP 地址不能为空')
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, v):
            raise ValueError('无效的 IP 地址格式')
        parts = v.split('.')
        for part in parts:
            if int(part) > 255:
                raise ValueError('无效的 IP 地址')
        return v

    @field_validator('type', 'platform')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v and v not in ['cisco_ios', 'cisco_ios_xe', 'cisco_ios_router', 'aruba_aoscx']:
            raise ValueError('不支持的设备类型，仅支持 cisco_ios / cisco_ios_xe / cisco_ios_router / aruba_aoscx')
        return v


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    type: Optional[str] = None
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    uplink_ports: Optional[List[str]] = None
    member_ids: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError('设备名称必须为字符串')
            if '..' in v or '/' in v or '\\' in v:
                raise ValueError('设备名称包含非法字符')
            if not re.match(r'^[a-zA-Z0-9_\-\d]+$', v):
                raise ValueError('设备名称只能包含字母、数字、下划线和连字符')
        return v

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError('IP 地址必须为字符串')
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if not re.match(ip_pattern, v):
                raise ValueError('无效的 IP 地址格式')
            parts = v.split('.')
            for part in parts:
                if int(part) > 255:
                    raise ValueError('无效的 IP 地址')
        return v

    @field_validator('type', 'platform')
    @classmethod
    def validate_type_update(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ['cisco_ios', 'cisco_ios_xe', 'cisco_ios_router', 'aruba_aoscx']:
            raise ValueError('不支持的设备类型，仅支持 cisco_ios / cisco_ios_xe / cisco_ios_router / aruba_aoscx')
        return v


class DeviceResponse(BaseModel):
    name: str
    ip: str
    type: str
    platform: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    serial_number: Optional[str] = None
    member_ids: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    last_synced: Optional[str] = None
    username: Optional[str] = None
    uplink_ports: Optional[list] = None


class OfflineDeviceResponse(BaseModel):
    """离线物理设备档案（device_members 表）"""
    serial_number: str
    model: Optional[str] = None
    version: Optional[str] = None
    last_device: Optional[str] = None
    last_member: Optional[str] = None
    last_seen: Optional[str] = None
    first_seen: Optional[str] = None


# ================================================================
# CSV 导入
# ================================================================

CSV_TEMPLATE = (
    "name,ip,type,platform,location,notes,uplink_ports\r\n"
    'SWI01,192.168.1.1,aruba_aoscx,aruba_aoscx,DC1,Core Switch,"1/1/49,1/1/50"\r\n'
    'SWI02,192.168.1.2,cisco_ios,cisco_ios_xe,DC1,Access Switch,"Te1/0/1,Te1/0/2"\r\n'
)


@router.get("/batch-import/template")
async def download_import_template():
    from fastapi.responses import Response
    return Response(
        content=CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=NDM_Device_Import_Template.csv"},
    )


@router.post("/batch-import")
async def batch_import_devices(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 解析失败：{str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV 文件为空")

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, row in enumerate(rows):
        row_num = idx + 2
        row_data = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

        name = row_data.get("name", "")
        ip = row_data.get("ip", "")
        dev_type = row_data.get("type", "")
        platform = row_data.get("platform", "")
        location = row_data.get("location", "")
        notes = row_data.get("notes", "")
        uplink_raw = row_data.get("uplink_ports", "")

        errors = []
        if not name:
            errors.append("设备名称为空")
        elif not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
            errors.append("设备名称包含非法字符")
        if not ip:
            errors.append("IP 地址为空")
        elif not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            errors.append("IP 地址格式无效")
        else:
            parts = ip.split('.')
            if any(int(p) > 255 for p in parts):
                errors.append("IP 地址值无效")
        if not dev_type:
            errors.append("设备类型为空")
        elif dev_type not in ['cisco_ios', 'cisco_ios_xe', 'cisco_ios_router', 'aruba_aoscx']:
            errors.append(f"不支持的设备类型：{dev_type}")

        if errors:
            results.append({"row": row_num, "name": name or "(空)", "status": "failed", "errors": errors})
            failed_count += 1
            continue

        if device_exists(name):
            results.append({"row": row_num, "name": name, "status": "skipped", "errors": ["设备名称已存在"]})
            skipped_count += 1
            continue

        uplink_ports = None
        if uplink_raw:
            uplink_ports = [p.strip() for p in uplink_raw.replace("，", ",").split(",") if p.strip()]

        device_dict = {
            "name": name, "ip": ip, "type": dev_type,
            "platform": platform or None, "location": location or None,
            "notes": notes or None, "uplink_ports": uplink_ports,
        }
        device_dict = {k: v for k, v in device_dict.items() if v is not None}

        try:
            dal_create(device_dict)
            results.append({"row": row_num, "name": name, "status": "success", "errors": []})
            success_count += 1
        except Exception as e:
            results.append({"row": row_num, "name": name, "status": "failed", "errors": [str(e)]})
            failed_count += 1

    return {
        "success": True,
        "total": len(rows),
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "results": results,
    }


# ================================================================
# CRUD
# ================================================================


@router.get("/")
async def list_devices():
    """获取设备列表"""
    return [DeviceResponse(**d).model_dump() for d in get_all_devices()]


@router.get("/offline")
async def list_offline_devices(days: int = 30):
    """获取离线物理设备（device_members 中超过 days 天未见的档案）

    时间阈值判定：last_seen 距今超过 days 天即视为离线。
    注意: 必须注册在 /{name} 之前, 否则会被捕获为设备名。
    """
    from datetime import datetime, timedelta
    from storage.database import get_connection

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        """SELECT serial_number, model, version, last_device, last_member,
                  last_seen, first_seen
           FROM device_members
           WHERE last_seen < ? AND last_seen != ''
           ORDER BY last_seen DESC""",
        (cutoff,),
    ).fetchall()
    return [OfflineDeviceResponse(**dict(r)).model_dump() for r in rows]


@router.delete("/offline/{serial}")
async def delete_offline_device(serial: str):
    """彻底删除物理设备档案（不影响 collections 历史统计）"""
    from storage.database import get_connection

    conn = get_connection()
    cur = conn.execute("DELETE FROM device_members WHERE serial_number = ?", (serial,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="档案不存在")
    return {"success": True, "message": "设备档案已删除"}


@router.get("/{name}")
async def get_device(name: str):
    """获取单个设备详情"""
    dev = get_device_by_name(name)
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    return DeviceResponse(**dev).model_dump()


@router.post("/")
async def add_device(device: DeviceCreate):
    """添加设备"""
    if device_exists(device.name):
        raise HTTPException(status_code=400, detail="设备名称已存在")
    device_dict = device.model_dump()
    dal_create(device_dict)
    return {"success": True, "message": "设备添加成功", "device": device_dict}


@router.delete("/{name}")
async def delete_device(name: str):
    """删除设备"""
    if not dal_delete(name):
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"success": True, "message": "设备删除成功"}


@router.patch("/{name}")
async def update_device(name: str, device: DeviceUpdate):
    """更新设备"""
    updates = {k: v for k, v in device.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    # 改名冲突检查：目标名已存在且不属于当前设备 → 409
    new_name = updates.get("name")
    if new_name is not None and new_name != name and device_exists(new_name):
        raise HTTPException(status_code=409, detail=f"设备名 '{new_name}' 已存在")
    try:
        ok = dal_update(name, updates)
    except ValueError as e:
        # DAL 层 UNIQUE 约束冲突（并发场景下 device_exists 未覆盖到的竞态）
        raise HTTPException(status_code=409, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="设备不存在")
    lookup_name = new_name or name
    updated = get_device_by_name(lookup_name)
    if not updated:
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"success": True, "message": "设备更新成功", "device": updated}
