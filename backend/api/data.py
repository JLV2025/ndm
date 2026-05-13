"""数据文件 API 路由"""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
import os
import re

router = APIRouter()


def validate_filename(filename: str) -> str:
    """
    验证文件名，防止路径遍历攻击
    只允许字母、数字、下划线、连字符和点号

    Args:
        filename: 要验证的文件名

    Returns:
        验证后的文件名

    Raises:
        HTTPException: 当文件名包含非法字符时
    """
    if not filename or not isinstance(filename, str):
        raise HTTPException(status_code=400, detail="文件名无效")

    # 防止路径遍历
    if '..' in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    if '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="文件名包含非法路径分隔符")

    # 只允许字母、数字、下划线、连字符和点号
    if not re.match(r'^[a-zA-Z0-9_\-\.\d]+$', filename):
        raise HTTPException(status_code=400, detail="文件名包含非法字符")

    # 防止文件名过长
    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="文件名过长")

    # 防止文件名以点号开头（隐藏文件）
    if filename.startswith('.'):
        raise HTTPException(status_code=400, detail="文件名不能以点号开头")

    return filename


def sanitize_device_name(device_name: str) -> str:
    """
    清理设备名称，防止路径遍历攻击

    Args:
        device_name: 要清理的设备名称

    Returns:
        清理后的设备名称

    Raises:
        HTTPException: 当设备名称包含非法字符时
    """
    if not device_name or not isinstance(device_name, str):
        raise HTTPException(status_code=400, detail="设备名称无效")

    # 防止路径遍历
    if '..' in device_name:
        raise HTTPException(status_code=400, detail="设备名称包含非法路径")

    if '/' in device_name or '\\' in device_name:
        raise HTTPException(status_code=400, detail="设备名称包含非法路径分隔符")

    # 只允许字母、数字、下划线、连字符
    if not re.match(r'^[a-zA-Z0-9_\-\d]+$', device_name):
        raise HTTPException(status_code=400, detail="设备名称包含非法字符")

    return device_name


@router.get("/{device_name}/weeks")
async def get_device_weeks(device_name: str):
    """获取设备所有可用的周目录列表"""
    safe_device_name = sanitize_device_name(device_name)
    data_root = os.path.join(os.path.dirname(__file__), "..", "data")
    device_path = os.path.join(data_root, safe_device_name)

    if not os.path.exists(device_path):
        return {"weeks": []}

    weeks = sorted(
        [d for d in os.listdir(device_path)
         if os.path.isdir(os.path.join(device_path, d)) and re.match(r'^\d{4}-\d{2}$', d)],
        reverse=True
    )
    return {"weeks": weeks}


@router.get("/{device_name}/{week}/files")
async def get_files_list(device_name: str, week: str):
    """获取文件列表 - 添加输入验证"""
    # 验证输入参数
    safe_device_name = sanitize_device_name(device_name)
    safe_filename = validate_filename(week)

    data_root = os.path.join(os.path.dirname(__file__), "..", "data")
    file_path = os.path.join(data_root, safe_device_name, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="目录不存在")

    files = [f for f in os.listdir(file_path) if os.path.isfile(os.path.join(file_path, f))]
    return {"files": files}


@router.get("/{device_name}/{week}/{filename}")
async def get_data_file(device_name: str, week: str, filename: str):
    """获取数据文件 - 添加输入验证防止路径遍历"""
    # 验证输入参数
    safe_device_name = sanitize_device_name(device_name)
    safe_week = validate_filename(week)
    safe_filename = validate_filename(filename)

    data_root = os.path.join(os.path.dirname(__file__), "..", "data")
    file_path = os.path.join(data_root, safe_device_name, safe_week, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    with open(file_path, "r", encoding="utf-8") as f:
        return {"filename": safe_filename, "content": f.read()}
