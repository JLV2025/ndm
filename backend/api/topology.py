"""拓扑图 API 路由
返回设备端口连接关系"""
from fastapi import APIRouter, HTTPException
import os
import re
import logging
from typing import Dict, List
from analyzers.config_parser import ConfigParser
from analyzers.role_verifier import RoleVerifier
from storage.database import get_connection as _get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# 端口名规范化: Cisco 长名 → 短名，确保 CDP/LLDP 与 ConfigParser 端口名可比
_CISCO_PORT_TO_SHORT = {
    'GigabitEthernet': 'Gi', 'TenGigabitEthernet': 'Te',
    'TwentyFiveGigE': 'Twe', 'HundredGigE': 'Hu',
    'FortyGigE': 'Fo', 'FastEthernet': 'Fa',
    'Port-channel': 'Po', 'Loopback': 'Lo',
}


def _norm_port(port: str) -> str:
    """将 Cisco 长接口名规范化为短名: GigabitEthernet1/1/2 → Gi1/1/2"""
    for long_pfx, short_pfx in _CISCO_PORT_TO_SHORT.items():
        if port.startswith(long_pfx):
            return short_pfx + port[len(long_pfx):]
    return port


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


# ============================================================
# SQLite 查询辅助函数
# ============================================================

def _get_latest_running_config(device_name: str) -> tuple[str | None, str | None]:
    """从 SQLite 获取设备最新 running-config

    Returns:
        (config_text, week) 或 (None, None)
    """
    db = _get_db()
    if not db:
        return None, None
    row = db.execute(
        "SELECT c.running_config, c.week FROM collections c "
        "JOIN devices d ON c.device_id = d.id "
        "WHERE d.name = ? AND c.running_config IS NOT NULL AND c.running_config != '' "
        "ORDER BY c.id DESC LIMIT 1",
        (device_name,)
    ).fetchone()
    if row:
        return row["running_config"], row["week"]
    return None, None


def _get_latest_neighbors(device_name: str) -> list[dict]:
    """从 SQLite 获取设备最新邻居数据

    Returns:
        [{local_port, neighbor_name, neighbor_type, ...}, ...]
    """
    db = _get_db()
    if not db:
        return []
    rows = db.execute("""
        SELECT n.local_port, n.neighbor_name, n.neighbor_type,
               n.neighbor_platform, n.neighbor_desc, n.source
        FROM neighbors n
        JOIN devices d ON n.device_id = d.id
        WHERE d.name = ?
          AND n.collection_id = (
              SELECT c.id FROM collections c
              WHERE c.device_id = n.device_id
              ORDER BY c.id DESC LIMIT 1
          )
    """, (device_name,)).fetchall()
    return [dict(r) for r in rows]


def _scan_device_neighbors() -> dict[str, list[dict]]:
    """一次查询聚合所有设备最新邻居

    Returns:
        {device_name: [neighbor_dict, ...]}
    """
    db = _get_db()
    if not db:
        return {}
    rows = db.execute("""
        SELECT d.name AS device_name, n.local_port, n.neighbor_name,
               n.neighbor_type, n.neighbor_platform, n.neighbor_desc, n.source
        FROM neighbors n
        JOIN devices d ON n.device_id = d.id
        WHERE n.collection_id = (
            SELECT c.id FROM collections c
            WHERE c.device_id = n.device_id
            ORDER BY c.id DESC LIMIT 1
        )
    """).fetchall()
    result: dict[str, list[dict]] = {}
    for r in rows:
        name = r["device_name"]
        if name not in result:
            result[name] = []
        result[name].append({
            "local_port": r["local_port"],
            "neighbor_name": r["neighbor_name"],
            "neighbor_type": r["neighbor_type"],
            "neighbor_platform": r["neighbor_platform"],
            "neighbor_desc": r["neighbor_desc"],
            "source": r["source"],
        })
    return result


@router.get("/topology/{device_name}")
async def get_device_topology(device_name: str):
    """
    获取设备拓扑数据

    从 SQLite 读取最新 running-config 和 CDP/LLDP 邻居数据，
    解析端口连接关系。
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

    # 2. 从 SQLite 获取最新 running-config
    config_text, found_week = _get_latest_running_config(device_name)

    if not config_text:
        raise HTTPException(status_code=404, detail=f"未找到设备 {device_name} 的 running-config 数据")

    # 4. 推断设备类型
    detected_type = _detect_device_type(config_text)

    # 5. 检测堆叠成员
    members = _detect_stack_members(config_text, detected_type)
    if len(members) < 2:
        members = ["1"]

    # 6. 预加载 YAML 设备信息
    device_info_map: Dict[str, dict] = {}
    try:
        from utils.settings_loader import load_devices
        for dev in load_devices().get("devices", []):
            device_info_map[dev.get("name", "")] = dev
    except Exception as e:
        logger.warning(f"加载 YAML 设备信息失败: {e}")

    # 7. 按堆叠成员分配端口
    def _member_for_iface(iface: str) -> str:
        if detected_type == "cisco_ios":
            m = re.match(r'[A-Za-z]+(\d+)', iface)
            if m and m.group(1) in members:
                return m.group(1)
            return "1"
        else:
            parts = iface.split('/')
            if len(parts) >= 1 and parts[0].isdigit() and parts[0] in members:
                return parts[0]
            return "1"

    member_neighbors: Dict[str, list] = {m: [] for m in members}

    # ---- 数据源1: CDP/LLDP neighbors（网络设备邻居，从 SQLite 读取） ----
    cdp_lldp_neighbors: Dict[str, List[dict]] = {}  # member → [items]
    try:
        for nb in _get_latest_neighbors(device_name):
            iface = _norm_port(nb.get("local_port", ""))
            nb_name = nb.get("neighbor_name", "")
            if not nb_name or not iface:
                continue
            # 过滤 LAG / Port-Channel 虚接口
            if re.match(r'^(lag|port-channel)\s*\d', iface, re.IGNORECASE):
                continue
            member = _member_for_iface(iface)
            item = {
                "interface": iface,
                "description": nb.get("neighbor_desc", ""),
                "device_name": nb_name,
                "device_type": nb.get("neighbor_type", ""),
                "site_code": None,
                "dc": None,
                "device_number": None,
                "is_endpoint": False,
                "member": member,
                "neighbor_ip": device_info_map.get(nb_name, {}).get("ip", ""),
                "neighbor_model": nb.get("neighbor_platform", ""),
                "neighbor_notes": device_info_map.get(nb_name, {}).get("notes", "") or "",
                "_source": "cdp_lldp",
            }
            cdp_lldp_neighbors.setdefault(member, []).append(item)
    except Exception as e:
        logger.warning(f"读取 CDP/LLDP 数据失败: {e}")

    # ---- 反查邻居设备的远程端口（从 SQLite 批量查询） ----
    neighbor_port_list: Dict[str, list] = {}  # 邻居名 → [(本地接口, member)]
    for member in members:
        for item in cdp_lldp_neighbors.get(member, []):
            nb_name = item["device_name"]
            if nb_name:
                if nb_name not in neighbor_port_list:
                    neighbor_port_list[nb_name] = []
                neighbor_port_list[nb_name].append((item["interface"], member))

    # 批量获取所有邻居的邻居数据
    all_neighbors_map = _scan_device_neighbors()

    neighbor_port_map: Dict[tuple, str] = {}  # (邻居名, 本地接口) → 邻居侧端口
    for nb_name, local_ports in neighbor_port_list.items():
        try:
            nb_neighbors = all_neighbors_map.get(nb_name, [])
            # 收集邻居侧所有指向当前设备（device_name）的端口
            remote_ports: List[str] = []
            for nb_nb in nb_neighbors:
                if nb_nb.get("neighbor_name") == device_name:
                    rp = nb_nb.get("local_port", "")
                    if rp and not re.match(r'^(lag|port-channel)\s*\d', rp, re.IGNORECASE):
                        remote_ports.append(rp)
            # 排序后按序配对，CDP/LLDP 端口通常有序，排序确保确定性
            local_ports.sort(key=lambda x: x[0])
            remote_ports.sort()
            for i, (local_iface, _member) in enumerate(local_ports):
                if i < len(remote_ports):
                    neighbor_port_map[(nb_name, local_iface)] = remote_ports[i]
                elif remote_ports:
                    neighbor_port_map[(nb_name, local_iface)] = remote_ports[-1]
        except Exception as e:
            logger.warning(f"反查邻居 {nb_name} 远程端口失败: {e}")
    # 把远程端口写入条目
    for member in members:
        for item in cdp_lldp_neighbors.get(member, []):
            key = (item["device_name"], item["interface"])
            if key in neighbor_port_map:
                item["neighbor_interface"] = neighbor_port_map[key]

    # ---- 数据源2: ConfigParser（端点设备，CDP/LLDP 过滤掉的 Phone/Printer/AP 等） ----
    parser = ConfigParser(device_type=detected_type)
    config_entries = parser.parse(config_text)
    endpoints_by_member: Dict[str, List[dict]] = {}  # member → [items]
    for entry in config_entries:
        member = _member_for_iface(entry.name)
        iface_norm = _norm_port(entry.name)
        item = {
            "interface": iface_norm,
            "description": entry.description,
            "device_name": entry.device_name,
            "device_type": entry.device_type,
            "site_code": entry.site_code,
            "dc": entry.dc,
            "device_number": entry.device_number,
            "is_endpoint": entry.is_endpoint,
            "member": member,
            "neighbor_ip": device_info_map.get(entry.device_name, {}).get("ip", ""),
            "neighbor_model": device_info_map.get(entry.device_name, {}).get("model", ""),
            "neighbor_notes": device_info_map.get(entry.device_name, {}).get("notes", "") or "",
            "_source": "config_parser",
        }
        endpoints_by_member.setdefault(member, []).append(item)

    # ---- 合并: CDP/LLDP 优先（网络设备），ConfigParser 补端点 ----
    for member in members:
        cdp_items = cdp_lldp_neighbors.get(member, [])
        ep_items = endpoints_by_member.get(member, [])
        # CDP/LLDP 条目（网络设备）直接加入
        seen_ports = set()
        for item in cdp_items:
            if item["device_name"]:
                seen_ports.add((member, item["interface"]))
                member_neighbors[member].append(item)
        # ConfigParser 端点条目：仅当非 LAG 且未被 CDP/LLDP 覆盖时加入
        for item in ep_items:
            key = (member, item["interface"])
            if not item["device_name"]:
                continue
            if not item["is_endpoint"]:
                continue  # 非端点的 ConfigParser 条目不纳入（CDP/LLDP 更准）
            if key in seen_ports:
                continue
            if re.match(r'^(lag|port-channel)\s*\d', item["interface"], re.IGNORECASE):
                continue  # LAG 口在后端过滤
            seen_ports.add(key)
            member_neighbors[member].append(item)

    # 过滤无标识端口
    neighbors = [i for m_list in member_neighbors.values() for i in m_list if i["device_name"]]
    endpoints = [i for i in neighbors if i["is_endpoint"]]
    network_devices = [i for i in neighbors if not i["is_endpoint"]]

    # 10. 从 YAML 读取设备备注、型号、IP
    device_notes = ""
    device_model = ""
    device_ip = ""
    try:
        from utils.settings_loader import load_devices
        devices_config = load_devices()
        for dev in devices_config.get("devices", []):
            if dev.get("name") == device_name:
                device_notes = dev.get("notes", "") or ""
                device_model = dev.get("model", "") or ""
                device_ip = dev.get("ip", "") or ""
                break
    except Exception as e:
        logger.warning(f"加载 YAML 设备信息失败: {e}")

    # 11. 为邻居交换机检测堆叠成员数（从 SQLite 读取配置）
    neighbor_members_map: Dict[str, list] = {}
    for nb in network_devices:
        nb_name = nb["device_name"]
        if not nb_name or nb_name in neighbor_members_map:
            continue
        # 仅对交换机检测堆叠
        nb_type = nb.get("device_type", "")
        if nb_type not in ("switch", "cisco_ios", "aruba_osswitch"):
            continue
        try:
            nb_config, _ = _get_latest_running_config(nb_name)
            if nb_config:
                nb_members = _detect_stack_members(nb_config, nb_type)
                if len(nb_members) > 1:
                    neighbor_members_map[nb_name] = nb_members
        except Exception as e:
            logger.warning(f"检测邻居 {nb_name} 堆叠成员失败: {e}")

    # 为每个 neighbor 条目附加邻居堆叠信息
    for item in neighbors:
        nb_name = item.get("device_name", "")
        if nb_name in neighbor_members_map:
            item["neighbor_members"] = neighbor_members_map[nb_name]

    # 12. 拆分逗号分隔的设备型号，按成员分配
    member_models: Dict[str, str] = {}
    if device_model:
        model_parts = [m.strip() for m in device_model.split(",") if m.strip()]
        for i, member in enumerate(members):
            if i < len(model_parts):
                member_models[member] = model_parts[i]
            elif model_parts:
                member_models[member] = model_parts[-1]  # 型号不够则用最后一个
    else:
        for member in members:
            member_models[member] = ""

    return {
        "device_name": device_name,
        "week": found_week,
        "stack_members": members,
        "member_neighbors": member_neighbors,
        "neighbors": neighbors,
        "endpoints": endpoints,
        "network_devices": network_devices,
        "device_notes": device_notes,
        "device_model": device_model,
        "device_ip": device_ip,
        "member_models": member_models,
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
    if 'ArubaOS-CX' in head:
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
# 共享辅助: 定位设备数据文件 (已废弃，保留待清理)
# ============================================================

def _find_device_data_file(device_name: str, data_root: str, filename: str) -> tuple[str | None, str | None]:
    """在 data_root 下扫描 YYYY-WW 目录, 找到设备的最新指定文件

    Returns:
        (file_path, week) 或 (None, None)
    """
    # 防御纵深：无论调用者是否已验证，此处再做路径遍历检查
    if not device_name or not isinstance(device_name, str):
        return None, None
    if '..' in device_name or '/' in device_name or '\\' in device_name:
        return None, None
    if not re.match(r'^[a-zA-Z0-9_\-]+$', device_name):
        return None, None
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

    从 SQLite 读取邻居数据，合并为统一节点/边列表。
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

    # 加载所有设备, 按 location 过滤 → 然后拆分为物理设备
    from utils.settings_loader import load_devices
    all_devices = load_devices().get("devices", [])
    raw_location_devices = [d for d in all_devices if d.get("location", "").upper() == location.upper()]
    if not raw_location_devices:
        raise HTTPException(status_code=404, detail=f"未找到 location={location} 的设备")

    physical_devices = _expand_physical_devices(raw_location_devices)

    # 构建全局设备查找表 (key=逻辑设备名, 供邻居查询 ip/platform)
    device_info_map: dict[str, dict] = {
        d.get("name", d.get("logical_name", "")): {
            "ip": d.get("ip", ""), "platform": d.get("platform", ""),
            "notes": d.get("notes", ""), "model": d.get("model", "")
        }
        for d in all_devices
    }

    # 构建逻辑设备 → 物理成员名称的反查表
    logical_to_physical: dict[str, list[str]] = {}
    for pd in physical_devices:
        log_name = pd["logical_name"]
        logical_to_physical.setdefault(log_name, []).append(pd["expanded_name"])

    device_count = len(physical_devices)
    skipped_devices: list[str] = []
    nodes: list[dict] = []
    all_edges: list[dict] = []
    node_set: set[str] = set()

    # 批量获取所有设备最新邻居
    device_neighbor_map = _scan_device_neighbors()

    # ─── 第一遍：先创建所有本 location 设备节点（确保 YAML 类型优先生效）───
    for dev in physical_devices:
        expanded_name = dev["expanded_name"]
        logical_name = dev["logical_name"]
        if expanded_name in node_set:
            continue
        node_set.add(expanded_name)
        device_type = dev.get("type", "")
        device_platform = dev.get("platform", "")
        device_ip = dev.get("ip", "")
        device_model = dev.get("model", "")
        notes = dev.get("notes", "")
        nodes.append({
            "id": expanded_name,
            "label": expanded_name,
            "type": _map_device_type(device_type),
            "platform": device_platform or device_info_map.get(logical_name, {}).get("platform", ""),
            "model": device_model or device_info_map.get(logical_name, {}).get("model", ""),
            "ip": device_ip or device_info_map.get(logical_name, {}).get("ip", ""),
            "tier": _compute_tier(logical_name, notes),
            "is_location_device": True,
            "location": location,
            "stack_group": dev.get("stack_group", ""),
            "physical_index": dev.get("physical_index", 1),
            "physical_count": dev.get("physical_count", 1),
        })

    # ─── 第二遍：遍历有邻居数据的设备，创建邻居节点和边 ───
    for dev in physical_devices:
        logical_name = dev["logical_name"]
        expanded_name = dev["expanded_name"]
        neighbor_list = device_neighbor_map.get(logical_name, [])
        if not neighbor_list:
            if logical_name not in skipped_devices:
                skipped_devices.append(logical_name)
            continue

        try:
            # 包装为 {"neighbors": [...]} 兼容下游迭代逻辑
            neighbor_data = {"neighbors": neighbor_list}
        except Exception:
            if logical_name not in skipped_devices:
                skipped_devices.append(logical_name)
            continue

        # 邻居 + 边: 按端口 member slot 映射到物理成员
        for nb in neighbor_data.get("neighbors", []):
            neighbor_name = nb.get("neighbor_name", "")
            if not neighbor_name:
                continue

            # source 端口 → 对应物理成员名称
            local_port = _norm_port(nb.get("local_port", ""))
            member_idx = _member_slot_for_port(local_port, dev.get("type", ""))
            member_name = logical_to_physical.get(logical_name, [])
            source_name = member_name[member_idx - 1] if member_name and member_idx <= len(member_name) else expanded_name

            # 邻居节点 (target): 如果邻居是堆叠设备, 也拆分
            nb_info = device_info_map.get(neighbor_name, {})
            is_loc = _is_in_location(neighbor_name, raw_location_devices)

            # 同级邻居的物理映射
            nb_physicals = logical_to_physical.get(neighbor_name, [])

            # 对端口-level 的 target 做映射; 没有端口信息时直接用第一个物理成员
            target_name = neighbor_name  # 默认逻辑名
            if nb_physicals:
                target_name = nb_physicals[0]  # 邻居也用第一个物理成员

            # 外部邻居节点：仅当不在本 location 设备列表中时才创建
            if not is_loc and target_name not in node_set:
                node_set.add(target_name)
                nodes.append({
                    "id": target_name,
                    "label": target_name,
                    "type": nb.get("neighbor_type", "unknown"),
                    "platform": nb.get("neighbor_platform", "") or nb_info.get("platform", ""),
                    "model": nb_info.get("model", ""),
                    "ip": nb_info.get("ip", ""),
                    "tier": _compute_tier(neighbor_name, nb_info.get("notes", "")),
                    "is_location_device": False,
                    "location": "",
                    "stack_group": neighbor_name if nb_physicals and len(nb_physicals) > 1 else "",
                    "physical_index": 1,
                    "physical_count": len(nb_physicals) if nb_physicals else 1,
                })

            edge_id = f"{source_name}-{local_port}-{target_name}"
            all_edges.append({
                "id": edge_id,
                "source": source_name,
                "target": target_name,
                "source_interface": local_port,
                "target_interface": "",
                "is_cross_location": not is_loc,
            })

    # 去重边: 同向同端口去重
    deduped_edges: list[dict] = []
    seen_keys: set[tuple] = set()
    for edge in all_edges:
        key = (edge["source"], edge["target"], edge["source_interface"])
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_edges.append(edge)

    # 双向链路合并: 同一设备对+同接口名 → 合并为一条边，取第一方向
    from collections import defaultdict
    pair_group: dict = defaultdict(list)
    for edge in deduped_edges:
        pair = tuple(sorted([edge["source"], edge["target"]]))
        pair_group[(pair[0], pair[1], edge["source_interface"])].append(edge)

    final_edges: list[dict] = []
    for group in pair_group.values():
        best = group[0].copy()
        # 从组内其他边补充 target_interface
        for e in group[1:]:
            if not best.get("target_interface"):
                best["target_interface"] = e["source_interface"]
        final_edges.append(best)

    # 两轮填充 target_interface: 第一轮从组内补, 第二轮从反向边补
    reverse_map: dict[tuple, list[int]] = defaultdict(list)
    for i, edge in enumerate(final_edges):
        rkey = (edge["target"], edge["source"])
        reverse_map[rkey].append(i)

    for i, edge in enumerate(final_edges):
        fkey = (edge["source"], edge["target"])
        if fkey in reverse_map:
            for ri in reverse_map[fkey]:
                if ri != i and not edge["target_interface"]:
                    edge["target_interface"] = final_edges[ri]["source_interface"]
                    break

    return {
        "location": location,
        "device_count": device_count,
        "node_count": len(nodes),
        "skipped_count": len(skipped_devices),
        "skipped_devices": skipped_devices,
        "nodes": nodes,
        "edges": final_edges,
    }


def _map_device_type(device_type: str) -> str:
    """映射设备类型字符串"""
    dt = device_type.lower() if device_type else ""
    if "router" in dt:
        return "router"
    return "switch"


def _compute_tier(device_name: str, notes: str) -> str:
    """计算拓扑层级

    命名规则: [3位站点][D+1位机房][3位设备类型][2位编号]
    - wan: RTW / SDW / FWL 类型
    - core: SWI 且 notes 含 Core
    - access: SWI / QIS 及其他非 WAN 类型
    """
    base_name = _logical_name(device_name)
    type_code = base_name[5:8].upper() if len(base_name) >= 8 else ""
    if type_code in ("RTW", "SDW", "FWL"):
        return "wan"
    if type_code == "SWI" and (notes or "").lower().startswith("core"):
        return "core"
    # SWI、QIS 及其他非 WAN 类型 → access
    return "access"


def _is_in_location(device_name: str, location_devices: list[dict]) -> bool:
    """检查设备名是否属于该 location"""
    return any(d.get("name") == device_name for d in location_devices)


def _logical_name(device_name: str) -> str:
    """剥离物理设备序号后缀，返回逻辑设备名

    "BJQD1SWI01-01" → "BJQD1SWI01"
    "BJQD1SWI01"    → "BJQD1SWI01"
    """
    m = re.match(r'^(.+?)-\d{2}$', device_name)
    return m.group(1) if m else device_name


def _member_slot_for_port(local_port: str, device_type: str) -> int:
    """从端口名推断所属堆叠成员序号 (1-based)

    Aruba VSF: 1/1/49 → member 1, 2/1/49 → member 2
    Cisco Stack: TwentyFiveGigE1/0/x → member 1
    """
    if not local_port:
        return 1
    m = re.match(r'^(\d+)/', local_port)
    if m:
        slot = int(m.group(1))
        if slot >= 1:
            return slot
    m = re.match(r'^[A-Za-z]+(\d+)/', local_port)
    if m:
        slot = int(m.group(1))
        if slot >= 1:
            return slot
    return 1


def _expand_physical_devices(location_devices: list[dict]) -> list[dict]:
    """将堆叠设备拆分为物理设备

    返回展开后的设备列表，每个物理设备新增:
      - expanded_name: "BJQD1SWI01-01"
      - logical_name: "BJQD1SWI01"
      - physical_index: 1-based
      - physical_count: 总成员数
      - stack_group: 堆叠组标识 (逻辑设备名，非堆叠为空字符串)
    """
    expanded = []
    for dev in location_devices:
        sn = (dev.get("serial_number") or "").strip()
        if not sn or sn == "未知" or "," not in sn:
            d = dict(dev)
            d["expanded_name"] = dev["name"]
            d["logical_name"] = dev["name"]
            d["physical_index"] = 1
            d["physical_count"] = 1
            d["stack_group"] = ""
            expanded.append(d)
            continue

        sn_list = [s.strip() for s in sn.split(",") if s.strip()]
        model_str = (dev.get("model") or "").strip()
        model_list = [m.strip() for m in model_str.split(",")] if model_str else [""] * len(sn_list)
        ver_str = (dev.get("version") or "").strip()
        ver_list = [v.strip() for v in ver_str.split(",")] if ver_str else [""] * len(sn_list)

        for i, s in enumerate(sn_list):
            d = dict(dev)
            d["expanded_name"] = f"{dev['name']}-{i + 1:02d}"
            d["logical_name"] = dev["name"]
            d["physical_index"] = i + 1
            d["physical_count"] = len(sn_list)
            d["stack_group"] = dev["name"]
            d["serial_number"] = s
            d["model"] = model_list[i] if i < len(model_list) else ""
            d["version"] = ver_list[i] if i < len(ver_list) else ""
            expanded.append(d)

    return expanded


# ============================================================
# 角色核查 API
# ============================================================

@router.get("/topology/{device_name}/role-verify")
async def verify_device_role(device_name: str):
    """
    核查单台交换机的角色标注

    交叉验证 YAML notes 与 LLDP 邻居拓扑数据，
    检测标注缺失、连接不一致、命名冲突等问题。

    Returns:
        { device, passed, warnings: [{ rule, message, severity }] }
    """
    if not device_name or not isinstance(device_name, str):
        raise HTTPException(status_code=400, detail="设备名称无效")
    if '..' in device_name or '/' in device_name or '\\' in device_name:
        raise HTTPException(status_code=400, detail="设备名称包含非法字符")

    data_root = _get_data_root()
    config_root = os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "config"
    ))

    verifier = RoleVerifier(data_root=data_root, config_root=config_root)
    warnings = verifier.verify_device(device_name)

    return {
        "device": device_name,
        "passed": len(warnings) == 0,
        "warnings": [
            {"rule": w.rule, "message": w.message, "severity": w.severity}
            for w in warnings
        ],
    }


@router.get("/topology/location/{location}/role-audit")
async def audit_location_roles(location: str):
    """
    整站角色审计

    Returns:
        { location, devices, warnings, summary }
    """
    if not location or not isinstance(location, str):
        raise HTTPException(status_code=400, detail="站点代码无效")

    data_root = _get_data_root()
    config_root = os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "config"
    ))

    verifier = RoleVerifier(data_root=data_root, config_root=config_root)
    result = verifier.audit_location(location.upper())

    return result

