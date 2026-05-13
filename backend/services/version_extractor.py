"""版本信息提取器"""

import re
from typing import Dict


class VersionExtractor:
    """版本信息提取器"""

    def __init__(self, version_output: str, device_type: str):
        self.version_output = version_output
        self.device_type = device_type

    def extract_version(self) -> str:
        """提取软件版本号"""
        lines = self.version_output.splitlines()

        if self.device_type == "cisco_ios":
            for line in lines:
                match = re.search(r'Version\s+(\d+\.\d+(?:\(\d+\))?)', line, re.IGNORECASE)
                if match:
                    return match.group(1)
        elif self.device_type == "aruba_osswitch":
            for line in lines:
                match = re.search(r'ArubaOSv9,\s*(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)
                match = re.search(r'Firmware Version\s+(\d+\.\d+\.\d+\.\d+)', line, re.IGNORECASE)
                if match:
                    return match.group(1)

        return "未知"

    def extract_serial_number(self) -> str:
        """提取设备序列号"""
        lines = self.version_output.splitlines()

        if self.device_type == "cisco_ios":
            for line in lines:
                match = re.search(r'Serial Number[:\s]+([A-Za-z0-9]+)', line)
                if match:
                    return match.group(1)
        elif self.device_type == "aruba_osswitch":
            for line in lines:
                match = re.search(r'Serial Number[:\s]+([A-Z0-9]+)', line)
                if match:
                    return match.group(1)

        return "未知"
