"""拓扑图 API 路由
返回设备端口连接关系"""
from fastapi import APIRouter, HTTPException
import os
import re
import logging
from typing import Dict, List
from analyzers.config_parser import ConfigParser

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_data_root() -> str:
    """从 settings 读取 data_root，返回绝对路径"""
    from utils.settings_loader import load_settings
    settings = load_settings()
    data_root = settings.get("data_root", "./data")
    # 解析相对路径：相对于项目根目录（backend/ 的上级目录）
    if not os.path.isabs(data_root):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_root = os.path.join(backend_dir, "..", data_root)
    return os.path.normpath(data_root)


@router.get("/topology/{device_name}")
async def get_device_topology(device_name: str):
    """
    获取设备拓扑数据

    从最新 running-config.raw 中解析端口连接关系。
    数据路径为 data/{YYYY-WW}/{device_name}/running-config.raw
    """
    # 1. 验证设备名称（防止路径遍历攻击）
    if not device_name or not isinstance(device_name, str):
        raise HTTPException(status_code=400, detail="设备名称无效")
    if '..' in device_name or '/' in device_name or '\\' in device_name:
        raise HTTPException(status_code=400, detail="设备名称包含非法字符")
    if not re.match(r'^[a-zA-Z0-9_\-]+$', device_name):
        raise HTTPException(status_code=400, detail="设备名称包含非法字符")

    data_root = _get_data_root()
    if not os.path.exists(data_root):
        raise HTTPException(status_code=404, detail="数据目录不存在")

    # 2. 扫描 data_root，按 YYYY-WW 格式找到最新周目录
    week_dirs = []
    for entry in os.listdir(data_root):
        full_path = os.path.join(data_root, entry)
        if os.path.isdir(full_path) and re.match(r'^\d{4}-\d{2}$', entry):
            week_dirs.append(entry)
    week_dirs.sort(reverse=True)

    # 3. 查找包含目标设备的最近一周
    config_path = None
    found_week = None
    for week in week_dirs:
        candidate = os.path.join(data_root, week, device_name, "running-config.raw")
        if os.path.exists(candidate):
            config_path = candidate
            found_week = week
            break

    # 回退：尝试旧版路径 data/{device_name}/{YYYY-WW}/running-config.raw
    if not config_path:
        alt_device_dir = os.path.join(data_root, device_name)
        if os.path.isdir(alt_device_dir):
            alt_weeks = sorted(
                [d for d in os.listdir(alt_device_dir)
                 if os.path.isdir(os.path.join(alt_device_dir, d)) and re.match(r'^\d{4}-\d{2}$', d)],
                reverse=True
            )
            for week in alt_weeks:
                candidate = os.path.join(alt_device_dir, week, "running-config.raw")
                if os.path.exists(candidate):
                    config_path = candidate
                    found_week = week
                    break

    if not config_path:
        raise HTTPException(status_code=404, detail=f"未找到设备 {device_name} 的 running-config 数据")

    # 4. 读取 running-config.raw
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_text = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}")

    # 5. 推断设备类型（根据文件名或目录名中的提示）
    detected_type = _detect_device_type(config_text)

    # 6. 检测堆叠成员
    members = _detect_stack_members(config_text, detected_type)
    if len(members) < 2:
        members = ["1"]

    # 7. 用 ConfigParser 解析
    parser = ConfigParser(device_type=detected_type)
    results = parser.parse(config_text)

    # 8. 按堆叠成员分配端口
    def _member_for_iface(iface: str) -> str:
        """根据接口名推断所属堆叠成员"""
        if detected_type == "cisco_ios":
            # Cisco StackWise: TwentyFiveGigE1/0/x → member 1, TwentyFiveGigE2/0/x → member 2
            m = re.match(r'[A-Za-z]+(\d+)', iface)
            if m:
                slot = m.group(1)
                if slot in members:
                    return slot
            return "1"
        else:
            # Aruba VSF: 1/1/x → member 1, 2/1/x → member 2
            parts = iface.split('/')
            if len(parts) >= 1 and parts[0].isdigit():
                if parts[0] in members:
                    return parts[0]
            return "1"

    # 9. 构建返回结果（按成员分组）
    member_neighbors: Dict[str, list] = {m: [] for m in members}

    for entry in results:
        member = _member_for_iface(entry.name)
        item = {
            "interface": entry.name,
            "description": entry.description,
            "device_name": entry.device_name,
            "device_type": entry.device_type,
            "site_code": entry.site_code,
            "dc": entry.dc,
            "device_number": entry.device_number,
            "is_endpoint": entry.is_endpoint,
            "member": member,
        }
        if member in member_neighbors:
            member_neighbors[member].append(item)

    # 过滤无标识端口
    neighbors = [i for m_list in member_neighbors.values() for i in m_list if i["device_name"]]
    endpoints = [i for i in neighbors if i["is_endpoint"]]
    network_devices = [i for i in neighbors if not i["is_endpoint"]]

    return {
        "device_name": device_name,
        "week": found_week,
        "stack_members": members,
        "member_neighbors": member_neighbors,
        "neighbors": neighbors,
        "endpoints": endpoints,
        "network_devices": network_devices,
    }


def _detect_device_type(config_text: str) -> str:
    """
    从 running-config 文本中推断设备类型

    Args:
        config_text: running-config 文本

    Returns:
        设备类型字符串，如 "aruba_aoscx" 或 "cisco_ios"
    """
    head = config_text[:3000]
    # Aruba CX: running-config 包含 "!Version ArubaOS-CX" 或 "ArubaOS-CX"
    if 'ArubaOS-CX' in head or 'ArubaOS-CX' in head:
        return "aruba_aoscx"
    # Cisco IOS: running-config 以 "version 16.9" 等形式开头，"boot system" 也是 Cisco 特有
    if 'Cisco IOS' in head or 'Cisco Internetwork Operating System' in head:
        return "cisco_ios"
    if re.search(r'^version\s+\d+\.\d+', head, re.MULTILINE):
        return "cisco_ios"
    if 'boot system' in head or 'boot-start-marker' in head:
        return "cisco_ios"
    # 根据接口命名风格推断
    if re.search(r'\b(TwentyFiveGigE|GigabitEthernet|TenGigabitEthernet|FastEthernet)\d', head):
        return "cisco_ios"
    return ""


def _detect_stack_members(config_text: str, device_type: str) -> List[str]:
    """
    检测堆叠成员数

    - Aruba CX VSF: 通过 port slot 号检测 (1/1/x → member 1, 2/1/x → member 2)
    - Cisco StackWise: 通过接口前缀检测 (TwentyFiveGigE1/... → switch 1, TwentyFiveGigE2/... → switch 2)

    返回成员 ID 列表，如 ['1', '2'] 或 ['1']
    """
    slots = set()

    if device_type == "cisco_ios":
        # Cisco StackWise: 匹配 interface [Type]slot/subslot/port (排除 slot 0 管理口)
        for m in re.finditer(r'\b(?:TwentyFiveGigE|HundredGigE|GigabitEthernet|TenGigabitEthernet|FastEthernet)(\d+)/', config_text):
            slot = m.group(1)
            if slot != '0':
                slots.add(slot)
    else:
        # Aruba VSF: 匹配 interface slot/subslot/port (排除 slot 0)
        for m in re.finditer(r'^interface\s+(\d+)/\d+/\d+', config_text, re.MULTILINE):
            slot = m.group(1)
            if slot != '0':
                slots.add(slot)

    return sorted(slots) if len(slots) > 1 else []

