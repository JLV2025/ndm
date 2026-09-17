"""生成树（STP）输出解析器

解析两平台完整版 `show spanning-tree`（同一条命令，输出形态不同）：

Aruba AOS-CX（RPVST）：
    Spanning tree status           : Enabled Protocol: RPVST
    VLAN1
      Root ID    Priority   : 8192
                 MAC-Address: 9c:37:08:06:b5:40
                 This bridge is the root
      Bridge ID  Priority  : 8192
                 MAC-Address: 9c:37:08:06:b5:40
    Port         Role           State      Cost  Priority   Type  ...
    1/1/4        Designated     Forwarding 4     128        P2P

Cisco IOS / IOS-XE（PVST / Rapid-PVST）：
    VLAN0001
      Spanning tree enabled protocol rstp
      Root ID    Priority    8193
                 Address     9c37.0806.b540
                 Cost        3
                 Port        640 (Port-channel24)
      Bridge ID  Priority    32769  (priority 32768 sys-id-ext 1)
                 Address     f87b.2009.3f00
    Interface           Role Sts Cost      Prio.Nbr Type
    Po24                Root FWD 3         128.640  P2p

跨平台归一化（跨设备比对必须）：
- MAC 统一为无分隔符小写：Aruba 冒号 `9c:37:08:06:b5:40` / Cisco 点号 `9c37.0806.b540` → `9c370806b540`
- 角色统一：Root/Desg/Altn/Back → root/designated/alternate/backup
- 状态统一：FWD/BLK/LRN/LIS、Forwarding/Blocking/Down/Loop-Inc/... → 小写单词
- 模式归族：RPVST ≡ Rapid-PVST（per-VLAN RSTP，厂商叫法不同）→ `rapid-pvst`；
  `ieee` → `pvst`；`mst`/`mstp` → `mstp`（站点级一致性检查用）
- 优先级不做数值换算：Cisco 显示含 sys-id-ext（VLAN1 显示 8193），跨设备认根一律比 MAC
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# 角色归一化（覆盖两平台全部取值）
_ROLE_MAP = {
    "root": "root",
    "desg": "designated",
    "designated": "designated",
    "altn": "alternate",
    "alternate": "alternate",
    "back": "backup",
    "backup": "backup",
    "disabled": "disabled",
}

# 状态归一化（覆盖两平台全部取值）
_STATE_MAP = {
    "fwd": "forwarding",
    "forwarding": "forwarding",
    "blk": "blocking",
    "blocking": "blocking",
    "lrn": "learning",
    "learning": "learning",
    "lis": "listening",
    "listening": "listening",
    "down": "down",
    "loop-inc": "loop-inc",
    "root-inc": "root-inc",
}

# 模式归一化：厂商叫法 → 互操作族
_MODE_MAP = {
    "rpvst": "rapid-pvst",       # Aruba 的 per-VLAN RSTP
    "rapid-pvst": "rapid-pvst",  # Cisco 的 per-VLAN RSTP（与 RPVST 互通）
    "rstp": "rapid-pvst",        # Cisco 每 VLAN 块内的协议名
    "pvst": "pvst",              # 传统 per-VLAN 802.1D
    "ieee": "pvst",              # Cisco 纯 PVST 块内的协议名
    "mstp": "mstp",
    "mst": "mstp",
}

_RE_ARUBA_HEADER = re.compile(r"Spanning tree status\s*:\s*Enabled\s+Protocol\s*:\s*(\S+)")
_RE_VLAN_BLOCK = re.compile(r"^VLAN(\d+)\s*$")
_RE_ROOT_FLAG = re.compile(r"This bridge is the root")

# Aruba 块内
_RE_ARUBA_ROOT_PRI = re.compile(r"Root ID\s+Priority\s*:\s*(\d+)")
_RE_ARUBA_BRIDGE_PRI = re.compile(r"Bridge ID\s+Priority\s*:\s*(\d+)")
_RE_ARUBA_MAC = re.compile(r"MAC-Address\s*:\s*([0-9a-fA-F:.\-]+)")

# Cisco 块内
_RE_CISCO_PROTO = re.compile(r"Spanning tree enabled protocol\s+(\S+)")
_RE_CISCO_ROOT_PRI = re.compile(r"Root ID\s+Priority\s+(\d+)")
_RE_CISCO_BRIDGE_PRI = re.compile(r"Bridge ID\s+Priority\s+(\d+)")
_RE_CISCO_ADDR = re.compile(r"Address\s+([0-9a-fA-F.]+)")


@dataclass
class StpPort:
    """单个 STP 端口（端口名保持设备原样：lag14 / Po24 / Gi1/0/42 / 1/1/3）"""
    name: str
    role: str                    # root / designated / alternate / backup / disabled
    state: str                   # forwarding / blocking / learning / listening / down / loop-inc / root-inc
    cost: int | None = None
    port_priority: int | None = None


@dataclass
class StpVlan:
    """单个 VLAN（RPVST/PVST 实例）的生成树信息"""
    vlan: int
    root_priority: int | None = None
    root_mac: str = ""           # 归一化：无分隔符小写
    bridge_priority: int | None = None
    bridge_mac: str = ""
    is_root: bool = False
    root_port: str | None = None  # 本设备朝根方向的端口；根桥为 None
    ports: list[StpPort] = field(default_factory=list)


@dataclass
class StpResult:
    """整台设备的 STP 解析结果"""
    device: str = ""
    mode: str = ""               # 归一化族：rapid-pvst / pvst / mstp
    mode_raw: str = ""           # 原始模式串（RPVST / rstp / ieee / ...）
    vlans: dict[int, StpVlan] = field(default_factory=dict)


def normalize_mac(mac: str) -> str:
    """MAC 归一化：去掉冒号/点号等分隔符并转小写（跨厂商比对用）"""
    return re.sub(r"[^0-9a-f]", "", mac.lower())


def normalize_mode(raw: str) -> str:
    """模式归族；未知模式原样返回（小写）"""
    key = raw.strip().lower()
    return _MODE_MAP.get(key, key)


def _parse_port_row(line: str) -> StpPort | None:
    """端口表行解析（两平台通用）

    Aruba: name role state cost priority type [计数器...]
    Cisco: name role sts   cost prio.nbr type
    前 5 列语义一致；Type 列可含空格（如 `P2P  Edge`），计数器列忽略。
    """
    parts = line.split()
    if len(parts) < 5:
        return None
    role = _ROLE_MAP.get(parts[1].lower())
    state = _STATE_MAP.get(parts[2].lower())
    if not role or not state or not parts[3].isdigit():
        return None
    prio_match = re.match(r"(\d+)", parts[4])
    return StpPort(
        name=parts[0],
        role=role,
        state=state,
        cost=int(parts[3]),
        port_priority=int(prio_match.group(1)) if prio_match else None,
    )


def _finalize(result: StpResult) -> StpResult:
    """收尾：补 root_port 与 is_root 兜底（根桥 = 根 MAC 与本桥 MAC 相同）"""
    for vlan in result.vlans.values():
        for port in vlan.ports:
            if port.role == "root":
                vlan.root_port = port.name
                break
        if not vlan.is_root and vlan.root_mac and vlan.bridge_mac \
                and vlan.root_mac == vlan.bridge_mac:
            vlan.is_root = True
    return result


def _parse_aruba(text: str, device: str) -> StpResult:
    result = StpResult(device=device)
    header = _RE_ARUBA_HEADER.search(text)
    if header:
        result.mode_raw = header.group(1)
        result.mode = normalize_mode(result.mode_raw)

    current: StpVlan | None = None
    section = ""  # "root" / "bridge" —— MAC 行按所在小节归属
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        block = _RE_VLAN_BLOCK.match(line)
        if block:
            vlan_id = int(block.group(1))
            current = StpVlan(vlan=vlan_id)
            result.vlans[vlan_id] = current
            section = ""
            continue
        if current is None:
            continue
        if _RE_ROOT_FLAG.search(line):
            current.is_root = True
            continue
        match = _RE_ARUBA_ROOT_PRI.search(line)
        if match:
            current.root_priority = int(match.group(1))
            section = "root"
            continue
        match = _RE_ARUBA_BRIDGE_PRI.search(line)
        if match:
            current.bridge_priority = int(match.group(1))
            section = "bridge"
            continue
        match = _RE_ARUBA_MAC.search(line)
        if match:
            mac = normalize_mac(match.group(1))
            if section == "root":
                current.root_mac = mac
            elif section == "bridge":
                current.bridge_mac = mac
            continue
        port = _parse_port_row(line)
        if port:
            current.ports.append(port)
    return _finalize(result)


def _parse_cisco(text: str, device: str) -> StpResult:
    result = StpResult(device=device)
    current: StpVlan | None = None
    section = ""  # "root" / "bridge"
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        block = _RE_VLAN_BLOCK.match(line)
        if block:
            vlan_id = int(block.group(1))
            current = StpVlan(vlan=vlan_id)
            result.vlans[vlan_id] = current
            section = ""
            continue
        if current is None:
            continue
        match = _RE_CISCO_PROTO.search(line)
        if match:
            # 每 VLAN 块协议一致；以第一块为准（rstp → rapid-pvst / ieee → pvst）
            raw = match.group(1)
            if not result.mode:
                result.mode_raw = raw
                result.mode = normalize_mode(raw)
            continue
        if _RE_ROOT_FLAG.search(line):
            current.is_root = True
            continue
        match = _RE_CISCO_ROOT_PRI.search(line)
        if match:
            current.root_priority = int(match.group(1))
            section = "root"
            continue
        match = _RE_CISCO_BRIDGE_PRI.search(line)
        if match:
            current.bridge_priority = int(match.group(1))
            section = "bridge"
            continue
        match = _RE_CISCO_ADDR.search(line)
        if match:
            mac = normalize_mac(match.group(1))
            if section == "root":
                current.root_mac = mac
            elif section == "bridge":
                current.bridge_mac = mac
            continue
        port = _parse_port_row(line)
        if port:
            current.ports.append(port)
    return _finalize(result)


def parse_spanning_tree(text: str, device: str = "") -> StpResult:
    """统一入口：按输出头部自动识别平台并解析

    空文本、错误回显（`% 收集失败: ...` / `% Invalid input`）等返回空结果
    （mode=""、vlans={}），由调用方决定如何呈现「无数据」。
    """
    if not text:
        return StpResult(device=device)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if _RE_ARUBA_HEADER.search(normalized):
        return _parse_aruba(normalized, device)
    if _RE_CISCO_PROTO.search(normalized) or _RE_CISCO_ROOT_PRI.search(normalized):
        return _parse_cisco(normalized, device)
    return StpResult(device=device)
