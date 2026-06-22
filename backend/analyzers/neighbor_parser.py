"""CDP / LLDP 邻居解析器
从 show cdp nei / show lldp nei 输出中提取网络设备邻居信息"""

from dataclasses import dataclass, field
import re
from typing import List, Optional

# 网络设备名正则: 3位site + 2位room + 3位类型码(SWI/RTW/FWL/WLC/SDW/QIS) + 2位编号
# site/room 不限字母数字；以类型码为识别锚点，位宽固定 10 字符
DEVICE_NAME_RE = re.compile(r'\b(\w{3}\w{2}(?:SWI|RTW|FWL|WLC|SDW|QIS)\d{2})\b')

# 接口名模式 (Cisco/Aruba 常见缩写)
IFACE_SHORT_RE = re.compile(
    r'\b('
    r'TwentyFiveGigE|HundredGigE|FortyGigE|TenGigabitEthernet|GigabitEthernet|FastEthernet'
    r'|Twe|Hu|Fo|Te|Gi|Fa'
    r')\s*\d+/\d+(?:/\d+)?',
    re.IGNORECASE
)

# 设备类型缩写映射 (设备名第6-8位, 0-indexed: 5:8)
TYPE_MAP = {
    "SWI": "switch",
    "RTW": "router",
    "FWL": "firewall",
    "WLC": "wireless",
    "SDW": "sdwan",
    "ESX": "esxi",
    "SRV": "server",
    "QIS": "switch",  # 部分站点自定义交换机类型码
}

# 需跳过的接口名开头
SKIP_PORT_PREFIXES = ("mgmt", "vlan", "lo", "port-channel")


@dataclass
class NeighborEntry:
    """CDP/LLDP 邻居条目"""
    local_port: str
    neighbor_name: str
    neighbor_type: str        # switch / router / firewall / wireless / sdwan
    neighbor_platform: str    # 设备型号, 如 "WS-C2960X"
    neighbor_desc: str        # 端口描述 (LLDP PORT-DESC)


# ============================================================
# 辅助函数
# ============================================================

def _extract_type(device_name: str) -> str:
    """从设备名提取设备类型 (第6-8位)"""
    if len(device_name) >= 8:
        code = device_name[5:8].upper()
        return TYPE_MAP.get(code, "unknown")
    return "unknown"


def _is_valid_network_device(name: str) -> bool:
    """判断是否为有效网络设备名"""
    return bool(DEVICE_NAME_RE.fullmatch(name))


def _is_endpoint(name: str) -> bool:
    """判断是否为端点设备 (需过滤)"""
    if not name:
        return True
    upper = name.upper()
    return (
        upper.startswith("SEP")
        or "PHONE" in upper
        or "LAPTOP" in upper
        or "PRINTER" in upper
        or "TL-" in upper   # TP-Link 消费级
        or "-AP" in upper or upper.startswith("AP")  # AP 接入点
        or upper.endswith(".C1D1") or upper.endswith(".842C")  # AP hostname 模式
        or upper.endswith(".9294") or upper.endswith(".93A8")
        or upper.endswith(".89B0")
    )


def _is_command_prompt(line: str) -> bool:
    """检测命令行提示符: DEVICENAME# 或 DEVICENAME>"""
    stripped = line.strip()
    return bool(re.match(r'^\S+[#>]', stripped))


def _should_skip_port(port: str) -> bool:
    """检查是否跳过该端口 (mgmt/vlan/loopback 等)"""
    port_lower = port.strip().lower()
    return port_lower.startswith(SKIP_PORT_PREFIXES)


def _strip_domain(raw_name: str) -> str:
    """去除域名后缀, 提取短设备名"""
    name = raw_name.strip()
    # 去除 .corp.qorvo.com / .corp.com 等后缀
    name = re.sub(r'\.corp\.\w+(?:\.com)?$', '', name)
    name = re.sub(r'\.\w+\.(?:com|net|org)$', '', name)
    # 如果仍然 > 10 位, 用正则提取
    if len(name) > 10:
        m = DEVICE_NAME_RE.search(name)
        if m:
            return m.group(1)
    return name


def _extract_platform(text: str) -> str:
    """从文本中提取设备平台/型号"""
    m = re.search(
        r'(WS-C\d+[^\s]*|AIR-[^\s]+|C\d{4}[^\s]*|c?[iI]sco\s+[A-Z]\d+[^\s]*)',
        text
    )
    return m.group(1) if m else ""


# ============================================================
# Cisco CDP
# ============================================================

def parse_cdp_cisco(text: str) -> List[NeighborEntry]:
    """解析 Cisco IOS show cdp nei

    两遍扫描: 合并跨行 → 逐行解析
    Cisco CDP 跨行: Device ID 独占一行, 接口信息在下一行
    """
    entries: List[NeighborEntry] = []
    lines = text.splitlines()

    # --- 第一遍: 合并跨行 + 提取有效行 ---
    merged_lines: List[str] = []
    in_data = False
    pending = ""  # 跨行缓存的设备名

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 命令提示符 → 结束 (除非还没进入数据区)
        if _is_command_prompt(stripped):
            if in_data:
                break
            continue

        # 表头
        if re.match(r'Device\s+ID\s+Local\s+Intrfce', stripped, re.IGNORECASE):
            in_data = True
            continue
        if "Total cdp entries" in stripped:
            break
        if not in_data:
            continue

        # 跳过能力码等非数据行
        if 'Capability Codes' in stripped or stripped.startswith('Capability'):
            continue

        # 以空格开头 = 续行 (接口数据)
        is_continuation = not line or line[0] in (' ', '\t')
        # 当前行是否含接口字段
        has_iface = bool(IFACE_SHORT_RE.search(stripped))

        if is_continuation and pending:
            merged_lines.append(f"{pending} {stripped}")
            pending = ""
        elif has_iface and pending:
            merged_lines.append(f"{pending} {stripped}")
            pending = ""
        elif has_iface:
            merged_lines.append(stripped)
        else:
            # 可能是纯设备名行 (跨行头部) 或无效行
            if DEVICE_NAME_RE.search(stripped):
                pending = stripped
            # 否则认为无效, 清空缓存
            else:
                pending = ""

    # --- 第二遍: 解析合并行 ---
    # 行格式: DEVICE_NAME[.domain] IFACE HOLDTIME CAP PLATFORM REMOTE_PORT
    for line in merged_lines:
        stripped = line.strip()

        dm = DEVICE_NAME_RE.search(stripped)
        if not dm:
            continue

        device_name = dm.group(1)
        if _is_endpoint(device_name):
            continue

        # 本地接口: 设备名之后第一个 IFACE 匹配
        after = stripped[dm.end():]
        # 去除域名残余 (小写字母 + 点)
        after = re.sub(r'^[a-z.]*', '', after).strip()
        im = IFACE_SHORT_RE.search(after)
        if not im:
            continue

        local_port = im.group(0).replace(' ', '')
        if _should_skip_port(local_port):
            continue

        # 平台 (接口之后)
        after_iface = after[im.end():]
        platform = _extract_platform(after_iface)

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=device_name,
            neighbor_type=_extract_type(device_name),
            neighbor_platform=platform,
            neighbor_desc="",
        ))

    return entries


# ============================================================
# Cisco LLDP
# ============================================================

def parse_lldp_cisco(text: str) -> List[NeighborEntry]:
    """解析 Cisco IOS show lldp nei

    列合并: SHAD2SWI02.corp.qorvTwe2/0/24 (域名被截断, 紧跟接口)
    格式: Device ID  Local Intf  Hold-time  Capability  Port ID
    """
    entries: List[NeighborEntry] = []
    lines = text.splitlines()
    in_data = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _is_command_prompt(stripped):
            if in_data:
                break
            continue

        if re.match(r'Device\s+ID\s+Local\s+Intf', stripped, re.IGNORECASE):
            in_data = True
            continue
        if "Total entries displayed" in stripped:
            break
        if not in_data:
            continue

        dm = DEVICE_NAME_RE.search(stripped)
        if not dm:
            continue

        device_name = dm.group(1)
        if _is_endpoint(device_name):
            continue

        # 本地接口: 设备名之后 → 去除域名残余 → 第一个 IFACE
        after = stripped[dm.end():]
        after = re.sub(r'^[a-z.]*', '', after).strip()
        im = IFACE_SHORT_RE.search(after)
        if not im:
            continue

        local_port = im.group(0).replace(' ', '')
        if _should_skip_port(local_port):
            continue

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=device_name,
            neighbor_type=_extract_type(device_name),
            neighbor_platform="",
            neighbor_desc="",
        ))

    return entries


# ============================================================
# Aruba CDP
# ============================================================

def parse_cdp_aruba(text: str) -> List[NeighborEntry]:
    """解析 Aruba CX show cdp nei

    格式:
        Port        Device ID                Platform                 Capability
        1/1/6       BJQD1RTW01.corp.com      cisco C8300-1N1S-4T2X    IRS
        2/1/16      PVGD1SWI04.corp.qorvo.comcisco WS-C3560G-48TS     IS

    列合并: Device ID 与 Platform 之间可能无空格 (域名过长)
    """
    entries: List[NeighborEntry] = []
    lines = text.splitlines()
    in_data = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _is_command_prompt(stripped):
            if in_data:
                break
            continue

        if re.match(r'Port\s+Device\s+ID\s+Platform', stripped, re.IGNORECASE):
            in_data = True
            continue
        if re.match(r'^-{5,}$', stripped):  # 分隔线
            continue
        if not in_data:
            continue

        # 第一个字段 = 本地端口
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            continue
        local_port = parts[0]
        rest = parts[1]

        if _should_skip_port(local_port):
            continue

        # 从剩余部分提取网络设备名
        dm = DEVICE_NAME_RE.search(rest)
        if not dm:
            continue

        device_name = dm.group(1)
        if _is_endpoint(device_name):
            continue

        # 平台: 设备名之后 → 去除域名残余 → 提取型号
        after_name = rest[dm.end():]
        after_name = re.sub(r'^[a-z.]*', '', after_name).strip()
        platform = _extract_platform(after_name)

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=device_name,
            neighbor_type=_extract_type(device_name),
            neighbor_platform=platform,
            neighbor_desc="",
        ))

    return entries


# ============================================================
# Aruba LLDP
# ============================================================

def parse_lldp_aruba(text: str) -> List[NeighborEntry]:
    """解析 Aruba CX show lldp nei

    格式:
        LOCAL-PORT  CHASSIS-ID         PORT-ID         PORT-DESC         TTL  SYS-NAME
        1/1/6       8c:44:a5:2c:2c:10  Gi0/0/1         Qorvo-LAN         120  BJQD1RTW01.corp.com

    设备名在最后一列 SYS-NAME
    """
    entries: List[NeighborEntry] = []
    lines = text.splitlines()
    in_data = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _is_command_prompt(stripped):
            if in_data:
                break
            continue

        if re.match(r'LOCAL-PORT\s+CHASSIS-ID', stripped, re.IGNORECASE):
            in_data = True
            continue
        if re.match(r'^-{5,}$', stripped):
            continue
        if not in_data:
            continue

        # 第一列 = 本地端口
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            continue
        local_port = parts[0]
        rest = parts[1]

        if _should_skip_port(local_port):
            continue

        # SYS-NAME = 最后一个非空格字段
        words = rest.split()
        if len(words) < 4:  # 至少: CHASSIS-ID PORT-ID TTL SYS-NAME
            continue
        sys_name_raw = words[-1]

        # 截断行跳过
        if sys_name_raw.endswith('...'):
            continue

        device_name = _strip_domain(sys_name_raw)
        if not _is_valid_network_device(device_name):
            continue
        if _is_endpoint(device_name):
            continue

        # PORT-DESC: CHASSIS-ID 和 PORT-ID 之后, TTL 之前
        desc = ""
        if len(words) >= 5:
            # words[0]=CHASSIS-ID, words[1]=PORT-ID, ..., words[-2]=TTL, words[-1]=SYS-NAME
            desc_parts = words[2:-2]  # 中间的描述字段
            desc = ' '.join(desc_parts)

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=device_name,
            neighbor_type=_extract_type(device_name),
            neighbor_platform="",
            neighbor_desc=desc,
        ))

    return entries


# ============================================================
# 统一入口
# ============================================================

def parse_cdp(text: str, device_type: str = "") -> List[NeighborEntry]:
    """解析 CDP 输出, 自动识别 Cisco/Aruba 格式"""
    if not text or not text.strip():
        return []

    head = text[:500]
    if re.search(r'Port\s+Device\s+ID\s+Platform', head):
        return parse_cdp_aruba(text)
    if re.search(r'Device\s+ID\s+Local\s+Intrfce', head):
        return parse_cdp_cisco(text)

    if "aruba" in device_type.lower():
        return parse_cdp_aruba(text)
    return parse_cdp_cisco(text)


def parse_lldp(text: str, device_type: str = "") -> List[NeighborEntry]:
    """解析 LLDP 输出, 自动识别 Cisco/Aruba 格式"""
    if not text or not text.strip():
        return []

    head = text[:500]
    if re.search(r'LOCAL-PORT\s+CHASSIS-ID', head):
        return parse_lldp_aruba(text)
    if re.search(r'Device\s+ID\s+Local\s+Intf', head):
        return parse_lldp_cisco(text)

    if "aruba" in device_type.lower():
        return parse_lldp_aruba(text)
    return parse_lldp_cisco(text)


def merge_neighbors(
    cdp_entries: List[NeighborEntry],
    lldp_entries: List[NeighborEntry]
) -> List[NeighborEntry]:
    """合并 CDP + LLDP, 同端口同邻居去重 (CDP 优先)"""
    seen: set = set()
    merged: List[NeighborEntry] = []

    for e in cdp_entries:
        key = (e.local_port, e.neighbor_name)
        seen.add(key)
        merged.append(e)

    for e in lldp_entries:
        key = (e.local_port, e.neighbor_name)
        if key not in seen:
            seen.add(key)
            merged.append(e)

    return merged
