"""
配置验证模块
- 检查配置完整性
- 检查关键配置项
- 检测语法错误
"""

import json
from analyzers._helpers import extract_device_name, get_iso_timestamp
import re
from typing import Dict, List, Any


class ConfigValidator:
    """配置验证器"""

    def __init__(self, config_text: str):
        self.config_text = config_text
        self.config_lines = config_text.splitlines()
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.info: List[Dict] = []

    def validate(self) -> Dict[str, Any]:
        """执行所有验证"""
        self.check_completeness()
        self.check_critical_items()
        self.check_syntax()
        return self._build_report()

    def check_completeness(self):
        """检查配置完整性"""
        # 检查是否有明显的截断
        if self.config_text.endswith("..."):
            self.errors.append({
                "type": "incomplete_config",
                "message": "配置文本可能不完整（以...结尾）",
                "severity": "error"
            })
        elif not self.config_text.strip():
            self.errors.append({
                "type": "empty_config",
                "message": "配置为空",
                "severity": "error"
            })

        # 检查 Cisco 配置是否包含必需部分
        if "Cisco IOS" in self.config_text or "cisco ios" in self.config_text:
            if not re.search(r"^Building configuration$", self.config_text, re.MULTILINE):
                self.warnings.append({
                    "type": "missing_header",
                    "message": "缺少配置头部信息",
                    "severity": "warning"
                })

    def check_critical_items(self):
        """检查关键配置项"""
        # 检查 VLAN 配置
        if re.search(r"^\s*interface\s+Vlan\d+", self.config_text, re.MULTILINE):
            self.info.append({
                "type": "vlan_config",
                "message": "检测到 VLAN 配置",
                "severity": "info"
            })

        # 检查接口配置
        interface_count = len(re.findall(r"^\s*interface\s+\w+", self.config_text, re.MULTILINE))
        if interface_count > 0:
            self.info.append({
                "type": "interface_count",
                "message": f"检测到 {interface_count} 个接口配置",
                "severity": "info"
            })

        # 检查路由配置
        if re.search(r"^\s*ip\s+route\b", self.config_text, re.MULTILINE) or \
           re.search(r"^\s*router\s+\w+", self.config_text, re.MULTILINE):
            self.info.append({
                "type": "routing_config",
                "message": "检测到路由配置",
                "severity": "info"
            })

        # 检查认证配置
        if re.search(r"^\s*login\s+local", self.config_text, re.MULTILINE) or \
           re.search(r"^\s*aaa\s+new-model", self.config_text, re.MULTILINE):
            self.info.append({
                "type": "auth_config",
                "message": "检测到认证配置",
                "severity": "info"
            })

    def check_syntax(self):
        """检测语法错误"""
        # 检查是否有未闭合的配置块
        block_depth = 0
        for line in self.config_lines:
            line = line.strip()
            if line.startswith("interface "):
                block_depth += 1
            elif line.startswith("no interface "):
                block_depth -= 1

        if block_depth > 0:
            self.warnings.append({
                "type": "unclosed_block",
                "message": f"检测到 {block_depth} 个未闭合的配置块",
                "severity": "warning"
            })

    def _build_report(self) -> Dict[str, Any]:
        """构建验证报告"""
        return {
            "device": extract_device_name(self.config_text),
            "timestamp": get_iso_timestamp(),
            "config_lines": len(self.config_lines),
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": len(self.info)
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info
        }

