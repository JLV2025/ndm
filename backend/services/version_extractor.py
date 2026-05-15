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
        elif self.device_type in ("aruba_osswitch", "aruba_aoscx"):
            for line in lines:
                # Version      : FL.10.10.1070  (ArubaOS-CX)
                match = re.search(r'Version\s*:\s*([A-Z]+\.\d+\.\d+\.\d+)', line, re.IGNORECASE)
                if match:
                    return match.group(1)
                # ArubaOS-CX FL.10.10.1070 (同一行)
                match = re.search(r'ArubaOS-CX\s+(?:[A-Z]+\.)?(\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)
                # ArubaOSv9, 10.10.1070.0001
                match = re.search(r'ArubaOSv\d+,\s*(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)
                # Firmware Version 10.10.1070
                match = re.search(r'Firmware Version\s+(\d+\.\d+\.\d+\.?\d*)', line, re.IGNORECASE)
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
        elif self.device_type in ("aruba_osswitch", "aruba_aoscx"):
            for line in lines:
                match = re.search(r'Serial Number[:\s]+([A-Za-z0-9]+)', line)
                if match:
                    return match.group(1)

        return "未知"
