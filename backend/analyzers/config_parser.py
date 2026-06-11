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

    # Rule 2 正则：数据中心设备 [SITE]D[DATACENTER_DIGIT][TYPE][NN]
    DC_DEVICE_RE = re.compile(r'\b([A-Z]{3})D(\d)([A-Z]{3,8})(\d{2})\b')

    # Rule 3 正则：非数据中心设备 [SITE][DIGIT][TYPE][NN]
    NON_DC_DEVICE_RE = re.compile(r'\b([A-Z]{3})(\d)([A-Z]{3,8})(\d{2})\b')

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

        Args:
            config_text: running-config 的完整文本

        Returns:
            解析出的接口条目列表
        """
        entries: List[InterfaceEntry] = []
        current_interface: Optional[str] = None
        skip_prefixes = ('vlan', 'mgmt', 'loopback', 'port-channel')

        for line in config_text.splitlines():
            stripped = line.strip()

            # 检测 interface 行
            if_match = re.match(r'^interface\s+(.+?)\s*$', stripped, re.IGNORECASE)
            if if_match:
                iface_name = if_match.group(1)
                # 跳过 VLAN、管理口、Loopback、Port-Channel 等虚拟接口
                lower_name = iface_name.lower()
                if any(lower_name.startswith(prefix) for prefix in skip_prefixes):
                    current_interface = None
                else:
                    current_interface = iface_name
                continue

            # 检测 description 行
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
                entries.append(entry)
                current_interface = None  # 重置，避免同一接口重复匹配

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

        # === Rule 2: 数据中心设备 [SITE]D[DIGIT][TYPE][NN] ===
        dc_match = self.DC_DEVICE_RE.search(desc)
        if dc_match:
            site = dc_match.group(1)
            dc_digit = dc_match.group(2)
            dev_type_abbr = dc_match.group(3)
            dev_num = dc_match.group(4)
            full_match = dc_match.group(0)

            # 已知网络设备类型 → TYPE_MAP 查找；其余 → server
            is_known = dev_type_abbr in self.NETWORK_TYPES
            dev_type = self.TYPE_MAP.get(dev_type_abbr, 'server')

            return {
                'device_name': full_match,
                'device_type': dev_type,
                'site_code': site,
                'dc': f'D{dc_digit}',
                'device_number': dev_num,
                'is_endpoint': False,
            }

        # === Rule 3: 非数据中心设备 [SITE][DIGIT][TYPE][NN] ===
        for match in self.NON_DC_DEVICE_RE.finditer(desc):
            full_match = match.group(0)
            site = match.group(1)
            digit = match.group(2)
            dev_type_abbr = match.group(3)
            dev_num = match.group(4)

            # 检查不是 Rule 2 的匹配：完整匹配字符串中，digit 的前一个字符是否为 'D'
            # Rule 2 格式: [SITE]D[DIGIT][TYPE][NN], Rule 3 格式: [SITE][DIGIT][TYPE][NN]
            # 在完整匹配中，SITE 占 3 个字符，digit 在第 4 位（索引 3）
            # 如果 digit 前是 'D'，则说明这实际上是 Rule 2 格式，跳过
            pos = match.start()
            if pos >= 1 and desc[pos - 1:pos] == 'D':
                continue

            # 已知网络设备类型 → TYPE_MAP 查找；其余 → server
            is_known = dev_type_abbr in self.NETWORK_TYPES
            dev_type = self.TYPE_MAP.get(dev_type_abbr, 'server')

            return {
                'device_name': full_match,
                'device_type': dev_type,
                'site_code': site,
                'dc': digit,
                'device_number': dev_num,
                'is_endpoint': False,
            }

        # 无法识别
        return None
