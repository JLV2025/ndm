"""CDP / LLDP 邻居解析器
从 show cdp nei / show lldp nei 输出中提取网络设备邻居信息"""

from dataclasses import dataclass, field
import re
from typing import List, Optional

# 网络设备名正则: 3位site + 2位room + 3位类型码(SWI/RTW/FWL/WLC/SDW/QIS) + 2位编号
# site/room 不限字母数字；以类型码为识别锚点，位宽固定 10 字符
DEVICE_NAME_RE = re.compile(r'\b(\w{3}\w{2}(?:SWI|RTW|FWL|WLC|SDW|QIS)\d{2})\b')

# GTS 服务器名正则: GTS + 3位site code + 3位类型码(ESX/SRV) + 可选编号
# 例: GTSPEKESX01, GTSPEKSRV
GTS_SERVER_NAME_RE = re.compile(r'\b(GTS\w{3}(?:ESX|SRV)\d*)\b')

# Aruba AP 名: 3位site + 点 + location + AP + 编号 + 点 + 4位MAC
# 例: SZX.F11AP2.7C5F → {site: SZX, location: F11, num: 2, mac: 7C5F}
# 宽松模式只认格式不解析字段；site 含数字（KR3）也匹配
AP_NAME_PATTERN = r'\w{3}\.[\w-]+AP\d+\.[0-9A-Fa-f]{4}'
AP_NAME_RE = re.compile(rf'\b({AP_NAME_PATTERN})\b')

# 组合设备名搜索正则（任意有效设备名）
DEVICE_NAME_SEARCH_RE = re.compile(
    r'\b('
    r'GTS\w{3}(?:ESX|SRV)\d*'          # GTS 服务器
    r'|'
    r'\w{3}\w{2}(?:SWI|RTW|FWL|WLC|SDW|QIS)\d{2}'  # 标准网络设备
    r'|'
    r'\w{3}\.[\w-]+AP\d+\.[0-9A-Fa-f]{4}'  # Aruba AP (SZX.F11AP2.7C5F)，与 AP_NAME_PATTERN 同步
    r')\b'
)

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

# 需跳过的接口名开头（lag = Aruba LAG, port-channel = Cisco EtherChannel）
SKIP_PORT_PREFIXES = ("mgmt", "vlan", "lo", "port-channel", "lag")


@dataclass
class NeighborEntry:
    """CDP/LLDP 邻居条目"""
    local_port: str
    neighbor_name: str
    neighbor_type: str        # switch / router / firewall / wireless / sdwan
    neighbor_platform: str    # 设备型号, 如 "WS-C2960X"
    neighbor_desc: str        # 端口描述 (LLDP PORT-DESC)
    neighbor_port: str = ""   # 远端端口 (LLDP PORT-ID / CDP Port ID)


# ============================================================
# 辅助函数
# ============================================================

def _extract_type(device_name: str) -> str:
    """从设备名提取设备类型：
    标准格式 PVGD1SWI02 → 第6-8位 (SWI)
    GTS 服务器 GTSPEKESX01 → 第7-9位 (ESX)
    """
    if device_name.startswith('GTS') and len(device_name) >= 9:
        code = device_name[6:9].upper()
        return TYPE_MAP.get(code, "unknown")
    if len(device_name) >= 8:
        code = device_name[5:8].upper()
        return TYPE_MAP.get(code, "unknown")
    return "unknown"


def _is_valid_network_device(name: str) -> bool:
    """判断是否为有效网络设备名（含 Aruba AP 名）"""
    return bool(DEVICE_NAME_RE.fullmatch(name)) or bool(GTS_SERVER_NAME_RE.fullmatch(name)) or bool(AP_NAME_RE.fullmatch(name))


def _is_ap(name: str) -> bool:
    """判断是否为 Aruba AP 名（宽松模式，只认格式不解析字段）
    例: SZX.F11AP2.7C5F → {site: SZX, location: F11, num: 2, mac: 7C5F}"""
    return bool(AP_NAME_RE.fullmatch(name or ""))


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
        m = DEVICE_NAME_SEARCH_RE.search(name)
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
            if DEVICE_NAME_SEARCH_RE.search(stripped):
                pending = stripped
            # 否则认为无效, 清空缓存
            else:
                pending = ""

    # --- 第二遍: 解析合并行 ---
    # 行格式: DEVICE_NAME[.domain] IFACE HOLDTIME CAP PLATFORM REMOTE_PORT
    for line in merged_lines:
        stripped = line.strip()

        dm = DEVICE_NAME_SEARCH_RE.search(stripped)
        if not dm:
            continue

        device_name = dm.group(1)
        if _is_ap(device_name):
            device_type = "AP"
        elif _is_endpoint(device_name):
            continue
        else:
            device_type = _extract_type(device_name)

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
            neighbor_type=device_type,
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

        dm = DEVICE_NAME_SEARCH_RE.search(stripped)
        if not dm:
            continue

        device_name = dm.group(1)
        if _is_ap(device_name):
            device_type = "AP"
        elif _is_endpoint(device_name):
            continue
        else:
            device_type = _extract_type(device_name)

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
            neighbor_type=device_type,
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
        dm = DEVICE_NAME_SEARCH_RE.search(rest)
        if not dm:
            continue

        device_name = dm.group(1)
        if _is_ap(device_name):
            device_type = "AP"
        elif _is_endpoint(device_name):
            continue
        else:
            device_type = _extract_type(device_name)

        # 平台: 设备名之后 → 去除域名残余 → 提取型号
        after_name = rest[dm.end():]
        after_name = re.sub(r'^[a-z.]*', '', after_name).strip()
        platform = _extract_platform(after_name)

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=device_name,
            neighbor_type=device_type,
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
        if _is_ap(device_name):
            device_type = "AP"
        elif _is_endpoint(device_name):
            continue
        else:
            device_type = _extract_type(device_name)

        # PORT-DESC: CHASSIS-ID 和 PORT-ID 之后, TTL 之前
        desc = ""
        if len(words) >= 5:
            # words[0]=CHASSIS-ID, words[1]=PORT-ID, ..., words[-2]=TTL, words[-1]=SYS-NAME
            desc_parts = words[2:-2]  # 中间的描述字段
            desc = ' '.join(desc_parts)

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=device_name,
            neighbor_type=device_type,
            neighbor_platform="",
            neighbor_desc=desc,
            neighbor_port=words[1],  # PORT-ID = 远端端口
        ))

    return entries


# ============================================================
# Aruba LLDP Detail (show lldp neighbor-info detail)
# ============================================================

def parse_lldp_aruba_detail(text: str) -> List[NeighborEntry]:
    """解析 Aruba CX show lldp neighbor-info detail

    分块 KV 格式:
        Port                           : 1/1/6
        Neighbor System-Name           : BJQD1RTW01.corp.com
        Neighbor System-Description    : Cisco IOS Software ...
        Neighbor Port-ID               : Gi0/0/1
        Neighbor Port-Desc             : Qorvo-LAN

    按 --- 分隔线切块, 逐行匹配 Key : Value
    """
    entries: List[NeighborEntry] = []
    if not text or not text.strip():
        return entries

    # 切块: Port 键行 = 新邻居块的开始。
    # 不依赖特定分隔线格式——分隔线与设备实际输出不符时，
    # 整段文本会被当单块、逐行 KV 覆盖只剩最后一个邻居。
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in text.splitlines():
        if re.match(r'^\s*Port\s*:', line):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)

    for block_lines in blocks:
        block = "\n".join(block_lines).strip()
        if not block:
            continue

        # 逐行提取 KV 对
        local_port = ""
        neighbor_name = ""
        neighbor_port = ""
        neighbor_desc = ""
        neighbor_platform = ""
        system_desc = ""

        for line in block.splitlines():
            # 匹配 Key : Value 或 Key: Value
            m = re.match(r'^(.+?)\s*:\s*(.*)', line)
            if not m:
                continue
            key = m.group(1).strip()
            value = m.group(2).strip()

            if key == "Port":
                local_port = value
            elif key == "Neighbor System-Name":
                neighbor_name = value
            elif key == "Neighbor Port-ID":
                neighbor_port = value
            elif key == "Neighbor Port-Desc":
                neighbor_desc = value
            elif key == "Neighbor System-Description":
                system_desc = value

        # 校验必要字段
        if not local_port or not neighbor_name:
            continue
        if _should_skip_port(local_port):
            continue

        # 域名剥离 + 设备名验证
        neighbor_name = _strip_domain(neighbor_name)
        if not neighbor_name:
            continue
        if not _is_valid_network_device(neighbor_name):
            continue
        if _is_ap(neighbor_name):
            device_type = "AP"
        elif _is_endpoint(neighbor_name):
            continue
        else:
            device_type = _extract_type(neighbor_name)

        # 从 System-Description 提取平台型号
        if system_desc:
            neighbor_platform = _extract_platform(system_desc)

        entries.append(NeighborEntry(
            local_port=local_port,
            neighbor_name=neighbor_name,
            neighbor_type=device_type,
            neighbor_platform=neighbor_platform,
            neighbor_desc=neighbor_desc,
            neighbor_port=neighbor_port,
        ))

    return entries


# ============================================================
# LACP / EtherChannel 聚合组解析
# ============================================================

def parse_lacp_aruba(text: str) -> dict:
    """解析 Aruba CX show lacp aggregates

    格式:
        Aggregate name   : lag49
        Interfaces       : 1/1/49 2/1/49
        ...

    返回: {"lag49": ["1/1/49", "2/1/49"], "lag1": ["1/1/5", "2/1/5"]}
    """
    result: dict = {}
    if not text or not text.strip():
        return result

    current_lag = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        m = re.match(r'^(.+?)\s*:\s*(.*)', stripped)
        if not m:
            continue
        key = m.group(1).strip()
        value = m.group(2).strip()

        if key == "Aggregate name":
            current_lag = value
        elif key == "Interfaces" and current_lag:
            ports = value.split()
            result[current_lag] = ports

    return result


def parse_etherchannel_cisco(text: str) -> dict:
    """解析 Cisco IOS show etherchannel summary

    格式:
        Group  Port-channel  Protocol    Ports
        1      Po1(SU)         LACP      Te1/0/2(P)   Te2/0/2(P)

    返回: {"Po1": ["Te1/0/2", "Te2/0/2"]}
    """
    # 端口名规范化: Cisco 长名 → 短名
    _CISCO_TO_SHORT = {
        'GigabitEthernet': 'Gi', 'TenGigabitEthernet': 'Te',
        'TwentyFiveGigE': 'Twe', 'HundredGigE': 'Hu',
        'FortyGigE': 'Fo', 'FastEthernet': 'Fa',
    }

    def _shorten(port_name: str) -> str:
        for long_pfx, short_pfx in _CISCO_TO_SHORT.items():
            if port_name.startswith(long_pfx):
                return short_pfx + port_name[len(long_pfx):]
        return port_name

    result: dict = {}
    if not text or not text.strip():
        return result

    in_data = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # 表头检测
        if re.match(r'Group\s+Port-channel\s+Protocol\s+Ports', stripped, re.IGNORECASE):
            in_data = True
            continue
        if re.match(r'^-{5,}$', stripped):
            continue
        if not in_data:
            continue

        # 数据行: "1      Po1(SU)         LACP      Te1/0/2(P)   Te2/0/2(P)"
        parts = stripped.split()
        if len(parts) < 3:
            continue

        # 第二列 = Port-channel 名, 提取纯名 (去掉括号状态)
        po_match = re.match(r'^(Po\d+)', parts[1])
        if not po_match:
            continue
        po_name = po_match.group(1)

        # 剩余部分提取物理端口 (去掉 (P) 等后缀)
        member_ports = []
        for p in parts[2:]:
            p_clean = re.sub(r'\(.*\)$', '', p)
            if re.match(r'^[A-Z][a-z]+\d', p_clean):  # 看起来像端口名
                member_ports.append(_shorten(p_clean))

        if member_ports:
            result[po_name] = member_ports

    return result


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
    # Aruba detail 格式: LLDP Neighbor Information
    if re.search(r'LLDP\s+Neighbor\s+Information', head):
        return parse_lldp_aruba_detail(text)
    # Aruba 表格格式: LOCAL-PORT CHASSIS-ID ...
    if re.search(r'LOCAL-PORT\s+CHASSIS-ID', head):
        return parse_lldp_aruba(text)
    # Cisco 格式: Device ID Local Intf ...
    if re.search(r'Device\s+ID\s+Local\s+Intf', head):
        return parse_lldp_cisco(text)

    # 回退: 按设备类型猜测
    if "aruba" in device_type.lower():
        # 先尝试 detail 格式, 再尝试表格格式
        if "LLDP Neighbor Information" in text[:2000]:
            return parse_lldp_aruba_detail(text)
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
