"""
运行配置解析模块
- 从 running-config 文本中提取 interface + description 配对
- 从 description 中识别连接的设备名称、类型、站点等信息
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class InterfaceEntry:
    """接口条目，包含接口名称、描述及解析出的设备信息"""
    name: str                              # 接口名称，如 "1/1/1" 或 "TwentyFiveGigE1/0/15"
    description: str                        # 完整的 description 文本
    device_name: Optional[str] = None       # 提取出的设备名称
    device_type: Optional[str] = None       # 设备类型：switch, router, firewall, wireless, sdwan, esxi, server, printer, mgmt
    site_code: Optional[str] = None         # 站点代码：BJQ, SHA, DZN 等
    dc: Optional[str] = None                # 数据中心标识：D1, 0 等
    device_number: Optional[str] = None     # 设备编号：01, 02 等
    is_endpoint: bool = False               # 是否为终端设备（Phone, Printer, Laptop, AP, Internet 等）


class ConfigParser:
    """
    运行配置解析器

    从交换机 running-config 文本中提取 interface->description 配对，
    并识别 description 中引用的设备名称及类型。
    支持 Aruba CX 和 Cisco IOS 两种格式。
    """

    # 设备类型缩写 → 可读类型名映射（仅已知网络设备类型，不在表中的都归为 server）
    TYPE_MAP = {
        'SWI': 'switch',
        'RTW': 'router',
        'FWL': 'firewall',
        'WLC': 'wireless',
        'SDW': 'sdwan',
    }

    # 终端设备关键词匹配
    ENDPOINT_KEYWORDS = ['Phone', 'Printer', 'Laptop', 'AP', 'Internet']

    # 设备名正则: 3位site + 2位room + 3位类型码 + 2位编号，以类型码为识别锚点
    DEVICE_FROM_DESC_RE = re.compile(
        r'\b(\w{3})(\w{2})(SWI|RTW|FWL|WLC|SDW|QIS)(\d{2})\b'
    )

    # 网络设备类型缩写（不是端点）
    NETWORK_TYPES = {'SWI', 'RTW', 'FWL', 'WLC', 'SDW'}

    def __init__(self, device_type: str = ""):
        """
        Args:
            device_type: 设备类型，如 "aruba_aoscx" 或 "cisco_ios"
        """
        self.device_type = device_type

    def parse(self, config_text: str) -> List[InterfaceEntry]:
        """
        解析 running-config 文本，提取所有 interface + description 配对

        过滤规则：
          - 跳过 VLAN / mgmt / loopback / port-channel 虚接口
          - 跳过带 shutdown 的端口（admin down 的端口邻居数据不可靠）

        Args:
            config_text: running-config 的完整文本

        Returns:
            解析出的接口条目列表
        """
        entries: List[InterfaceEntry] = []
        current_interface: Optional[str] = None
        pending_entry: Optional[InterfaceEntry] = None
        interface_shutdown: bool = False  # 当前 interface 块内是否出现 shutdown
        skip_prefixes = ('vlan', 'mgmt', 'loopback', 'port-channel')

        def _flush_pending():
            """提交待定条目：仅在接口未被 shutdown 时写入结果"""
            nonlocal pending_entry, interface_shutdown
            if pending_entry and not interface_shutdown:
                entries.append(pending_entry)
            pending_entry = None
            interface_shutdown = False

        for line in config_text.splitlines():
            stripped = line.strip()

            # 检测 interface 行 → 先提交上一个接口的待定条目
            if_match = re.match(r'^interface\s+(.+?)\s*$', stripped, re.IGNORECASE)
            if if_match:
                _flush_pending()
                iface_name = if_match.group(1)
                lower_name = iface_name.lower()
                if any(lower_name.startswith(prefix) for prefix in skip_prefixes):
                    current_interface = None
                else:
                    current_interface = iface_name
                continue

            # shutdown / no shutdown：在 interface 块内任意位置都生效
            if re.match(r'^\s*shutdown\s*$', line):
                interface_shutdown = True
                continue
            if re.match(r'^\s*no\s+shutdown\s*$', line):
                interface_shutdown = False
                continue

            # 检测 description 行（同一接口只取第一个 description）
            desc_match = re.match(r'^\s*description\s+(.+?)\s*$', stripped)
            if desc_match and current_interface:
                desc_text = desc_match.group(1).strip()
                device_info = self._extract_device_from_desc(desc_text)
                entry = InterfaceEntry(
                    name=current_interface,
                    description=desc_text,
                )
                if device_info:
                    entry.device_name = device_info.get('device_name')
                    entry.device_type = device_info.get('device_type')
                    entry.site_code = device_info.get('site_code')
                    entry.dc = device_info.get('dc')
                    entry.device_number = device_info.get('device_number')
                    entry.is_endpoint = device_info.get('is_endpoint', False)
                pending_entry = entry
                current_interface = None  # 防止同一接口重复匹配
                continue

        # 文件末尾：提交最后一个待定条目
        _flush_pending()

        return entries

    def _extract_device_from_desc(self, desc: str) -> Optional[Dict]:
        """
        按优先级顺序应用 3 条规则，从 description 文本中识别设备信息

        Rule 1 (最高优先级): 关键词匹配 — Phone, Printer, Laptop, AP, Internet
        Rule 2: 数据中心设备 — [SITE]D[DATACENTER_DIGIT][TYPE][NN]
        Rule 3: 非数据中心设备 — [SITE][DIGIT][TYPE][NN]（且第3个字符后不是 'D'）

        Args:
            desc: description 文本

        Returns:
            解析出的设备信息字典，无法识别时返回 None
        """
        # === Rule 1: 关键词匹配（最高优先级）===
        # printer 不区分大小写
        if re.search(r'printer', desc, re.IGNORECASE):
            return {
                'device_name': desc,
                'device_type': 'Printer',
                'is_endpoint': True,
            }

        # AP 作为独立单词或前缀（不在其他单词内部）
        if re.search(r'\bAP\b', desc) or re.search(r'\bAP-', desc):
            return {
                'device_name': desc,
                'device_type': 'AP',
                'is_endpoint': True,
            }

        # Phone- 前缀
        if re.search(r'Phone-', desc):
            return {
                'device_name': desc,
                'device_type': 'Phone',
                'is_endpoint': True,
            }

        # Laptop- 前缀
        if re.search(r'Laptop-', desc):
            return {
                'device_name': desc,
                'device_type': 'Laptop',
                'is_endpoint': True,
            }

        # Internet 关键词
        if re.search(r'\bInternet\b', desc, re.IGNORECASE):
            return {
                'device_name': desc,
                'device_type': 'Internet',
                'is_endpoint': True,
            }

        # === Rule 2: 网络设备识别 — [SITE 3位][ROOM 2位][TYPE 3位][NUM 2位] ===
        # 以 SWI/RTW/FWL/WLC/SDW 类型码为识别锚点，site/room 不限字母数字
        dc_match = self.DEVICE_FROM_DESC_RE.search(desc)
        if dc_match:
            site = dc_match.group(1)
            room = dc_match.group(2)
            dev_type_abbr = dc_match.group(3)
            dev_num = dc_match.group(4)
            full_match = dc_match.group(0)

            dev_type = self.TYPE_MAP.get(dev_type_abbr, 'server')

            return {
                'device_name': full_match,
                'device_type': dev_type,
                'site_code': site,
                'dc': room,
                'device_number': dev_num,
                'is_endpoint': False,
            }

        # 无法识别
        return None
