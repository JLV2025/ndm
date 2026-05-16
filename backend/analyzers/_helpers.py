"""分析器公共辅助函数"""

import re
from datetime import datetime


def extract_device_name(config_text: str) -> str:
    """从配置文本中提取设备名称（Cisco 'Router <name>' 或 Aruba 'Switch <name>'）"""
    for pattern in [r"^Router\s+(.+)", r"^Switch\s+(.+)"]:
        match = re.search(pattern, config_text, re.MULTILINE)
        if match:
            return match.group(1)
    return "unknown"


def get_iso_timestamp() -> str:
    """返回当前时间的 ISO 8601 字符串"""
    return datetime.now().isoformat()
