"""拓扑图 API 路由
返回设备端口连接关系"""
from fastapi import APIRouter, HTTPException
import os
import re
import json
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

    # 2. 查找最新 running-config.raw
    config_path, found_week = _find_device_data_file(device_name, data_root, "running-config.raw")

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


# ============================================================
# 共享辅助: 定位设备数据文件
# ============================================================

def _find_device_data_file(device_name: str, data_root: str, filename: str) -> tuple[str | None, str | None]:
    """在 data_root 下扫描 YYYY-WW 目录, 找到设备的最新指定文件

    Returns:
        (file_path, week) 或 (None, None)
    """
    week_dirs = []
    for entry in os.listdir(data_root):
        full_path = os.path.join(data_root, entry)
        if os.path.isdir(full_path) and re.match(r'^\d{4}-\d{2}$', entry):
            week_dirs.append(entry)
    week_dirs.sort(reverse=True)

    for week in week_dirs:
        candidate = os.path.join(data_root, week, device_name, filename)
        if os.path.exists(candidate):
            return candidate, week

    # 回退: 旧版路径 data/{device_name}/{YYYY-WW}/filename
    alt_device_dir = os.path.join(data_root, device_name)
    if os.path.isdir(alt_device_dir):
        alt_weeks = sorted(
            [d for d in os.listdir(alt_device_dir)
             if os.path.isdir(os.path.join(alt_device_dir, d)) and re.match(r'^\d{4}-\d{2}$', d)],
            reverse=True
        )
        for week in alt_weeks:
            candidate = os.path.join(alt_device_dir, week, filename)
            if os.path.exists(candidate):
                return candidate, week

    return None, None


def _scan_device_files(data_root: str, filename: str) -> dict[str, str]:
    """一次扫描 data_root，返回 {device_name: file_path} 映射"""
    result: dict[str, str] = {}
    week_dirs = []
    for entry in os.listdir(data_root):
        full = os.path.join(data_root, entry)
        if os.path.isdir(full) and re.match(r'^\d{4}-\d{2}$', entry):
            week_dirs.append(entry)
    week_dirs.sort(reverse=True)

    seen: set[str] = set()
    for week in week_dirs:
        week_path = os.path.join(data_root, week)
        for device_name in os.listdir(week_path):
            if device_name in seen:
                continue
            candidate = os.path.join(week_path, device_name, filename)
            if os.path.isfile(candidate):
                seen.add(device_name)
                result[device_name] = candidate

    # 回退: 旧版路径 data/{device_name}/{YYYY-WW}/filename
    for entry in os.listdir(data_root):
        alt_dir = os.path.join(data_root, entry)
        if not os.path.isdir(alt_dir) or entry in week_dirs:
            continue
        if entry in seen:
            continue
        alt_weeks = sorted(
            [d for d in os.listdir(alt_dir)
             if os.path.isdir(os.path.join(alt_dir, d)) and re.match(r'^\d{4}-\d{2}$', d)],
            reverse=True
        )
        for week in alt_weeks:
            if entry in seen:
                break
            candidate = os.path.join(alt_dir, week, filename)
            if os.path.isfile(candidate):
                seen.add(entry)
                result[entry] = candidate
                break

    return result


# ============================================================
# Location 拓扑端点
# ============================================================

@router.get("/topology/location/{location}")
async def get_location_topology(location: str):
    """
    获取指定 location 下所有网络设备的互联拓扑

    遍历 location 内所有设备, 读取 neighbors.json, 合并为统一节点/边列表。
    """
    # 验证 location
    if not location or not isinstance(location, str):
        raise HTTPException(status_code=400, detail="location 参数无效")
    if '..' in location or '/' in location or '\\' in location:
        raise HTTPException(status_code=400, detail="location 包含非法字符")
    if not re.match(r'^[a-zA-Z0-9_\-]+$', location):
        raise HTTPException(status_code=400, detail="location 包含非法字符")

    data_root = _get_data_root()
    if not os.path.exists(data_root):
        raise HTTPException(status_code=404, detail="数据目录不存在")

    # 加载所有设备, 按 location 过滤
    from utils.settings_loader import load_devices
    all_devices = load_devices().get("devices", [])
    location_devices = [d for d in all_devices if d.get("location", "").upper() == location.upper()]

    if not location_devices:
        raise HTTPException(status_code=404, detail=f"未找到 location={location} 的设备")

    # 构建全局设备 notes 查找表 (供外部邻居设备 tier 判断)
    device_notes_map: dict[str, str] = {d["name"]: d.get("notes", "") for d in all_devices}

    device_count = len(location_devices)
    skipped_devices: list[str] = []
    nodes: list[dict] = []
    all_edges: list[dict] = []
    node_set: set[str] = set()

    # 预扫描: 一次扫描 data_root 构建 {device: path} 映射
    device_file_map = _scan_device_files(data_root, "neighbors.json")

    for dev in location_devices:
        device_name = dev["name"]
        neighbors_path = device_file_map.get(device_name)
        if not neighbors_path:
            skipped_devices.append(device_name)
            continue

        try:
            with open(neighbors_path, "r", encoding="utf-8") as f:
                neighbor_data = json.load(f)
        except Exception:
            skipped_devices.append(device_name)
            continue

        # 确保本设备节点已加入
        if device_name not in node_set:
            node_set.add(device_name)
            device_type = dev.get("type", "")
            notes = dev.get("notes", "")
            nodes.append({
                "id": device_name,
                "label": device_name,
                "type": _map_device_type(device_type),
                "platform": dev.get("platform", ""),
                "tier": _compute_tier(device_name, notes),
                "is_location_device": True,
                "location": location,
            })

        # 添加邻居节点 + 边
        for nb in neighbor_data.get("neighbors", []):
            neighbor_name = nb.get("neighbor_name", "")
            if not neighbor_name:
                continue

            # 邻居节点
            if neighbor_name not in node_set:
                node_set.add(neighbor_name)
                is_loc = _is_in_location(neighbor_name, location_devices)
                nodes.append({
                    "id": neighbor_name,
                    "label": neighbor_name,
                    "type": nb.get("neighbor_type", "unknown"),
                    "platform": nb.get("neighbor_platform", ""),
                    "tier": _compute_tier(neighbor_name, device_notes_map.get(neighbor_name, "")),
                    "is_location_device": is_loc,
                    "location": location if is_loc else "",
                })

            # 边
            edge_id = f"{device_name}-{nb['local_port']}-{neighbor_name}"
            all_edges.append({
                "id": edge_id,
                "source": device_name,
                "target": neighbor_name,
                "source_interface": nb["local_port"],
                "target_interface": "",
                "is_cross_location": not _is_in_location(neighbor_name, location_devices),
            })

    # 去重边: 同向同端口去重 + 双向链路合并
    deduped_edges: list[dict] = []
    seen_keys: set[tuple] = set()
    for edge in all_edges:
        # key 包含 source_interface，保留多端口并行链路
        key = (edge["source"], edge["target"], edge["source_interface"])
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_edges.append(edge)

    # 双向链路合并: 匹配 A→B 和 B→A，填充 target_interface
    reverse_map: dict[tuple, int] = {}
    for i, edge in enumerate(deduped_edges):
        rkey = (edge["target"], edge["source"])
        reverse_map.setdefault(rkey, []).append(i)

    for i, edge in enumerate(deduped_edges):
        fkey = (edge["source"], edge["target"])
        if fkey in reverse_map:
            for ri in reverse_map[fkey]:
                if ri != i and not edge["target_interface"]:
                    edge["target_interface"] = deduped_edges[ri]["source_interface"]
                    break

    return {
        "location": location,
        "device_count": device_count,
        "node_count": len(nodes),
        "skipped_count": len(skipped_devices),
        "skipped_devices": skipped_devices,
        "nodes": nodes,
        "edges": deduped_edges,
    }


def _map_device_type(device_type: str) -> str:
    """映射设备类型字符串"""
    dt = device_type.lower() if device_type else ""
    if "router" in dt:
        return "router"
    return "switch"


def _compute_tier(device_name: str, notes: str) -> str:
    """计算拓扑层级

    - wan: RTW / SDW 类型
    - core: SWI 且 notes 含 [Core]
    - access: 其余
    """
    type_code = device_name[5:8].upper() if len(device_name) >= 8 else ""
    if type_code in ("RTW", "SDW"):
        return "wan"
    if type_code == "SWI" and notes.lower().startswith("core"):
        return "core"
    if type_code == "SWI":
        return "access"
    return "unknown"


def _is_in_location(device_name: str, location_devices: list[dict]) -> bool:
    """检查设备名是否属于该 location"""
    return any(d.get("name") == device_name for d in location_devices)

