"""
变更检测模块
对比不同时间点的配置，高亮显示变化
"""

import json
import difflib
import re
from typing import Dict, List, Any
from analyzers._helpers import extract_device_name, get_iso_timestamp


class ChangeDetector:
    """变更检测器"""

    def __init__(self, new_config: str, old_config: str = None):
        self.new_config = new_config
        self.old_config = old_config
        self.changes: List[Dict] = []

    def detect(self) -> Dict[str, Any]:
        """检测配置变更"""
        if not self.old_config:
            return self._no_baseline_report()

        self.changes = self._compare_configs()
        return self._build_report()

    def _compare_configs(self) -> List[Dict]:
        """对比配置"""
        new_lines = self.new_config.splitlines()
        old_lines = self.old_config.splitlines()

        # 使用 difflib 进行行级对比
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile='old', tofile='new',
            lineterm=''
        )

        current_context = []
        change_type = None

        for line in diff:
            if line.startswith('---'):
                if current_context:
                    self.changes.append({
                        "type": "context",
                        "lines": current_context
                    })
                    current_context = []
                change_type = 'removed'
                continue
            elif line.startswith('+++'):
                if current_context:
                    self.changes.append({
                        "type": "context",
                        "lines": current_context
                    })
                    current_context = []
                change_type = 'added'
                continue
            elif line.startswith('@'):
                if current_context:
                    self.changes.append({
                        "type": change_type,
                        "lines": current_context
                    })
                    current_context = []
                # 提取行号 — 添加到最新一个 change block（若存在）
                match = re.search(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
                if match and self.changes:
                    self.changes[-1].update({
                        "start_line_old": int(match.group(1)),
                        "start_line_new": int(match.group(3))
                    })
                change_type = 'added' if '+' in line else 'removed'
                continue

            # 跳过仅含行号的 @@ 后续行
            if line.startswith(' ') or line.startswith('-') or line.startswith('+'):
                line_content = line[1:]
                current_context.append(line_content)

        # 添加最后的上下文
        if current_context:
            self.changes.append({
                "type": change_type,
                "lines": current_context
            })

        return self.changes

    def _no_baseline_report(self) -> Dict[str, Any]:
        """没有基准线的报告"""
        return {
            "device": "unknown",
            "timestamp": get_iso_timestamp(),
            "baseline": None,
            "changes": [],
            "summary": {
                "added": 0,
                "removed": 0,
                "modified": 0
            },
            "message": "没有基准配置，无法检测变更"
        }

    def _build_report(self) -> Dict[str, Any]:
        """构建报告"""
        # 统计变更
        summary = {
            "added": 0,
            "removed": 0,
            "modified": 0
        }

        for change in self.changes:
            if change.get("type") == "added":
                summary["added"] += len(change.get("lines", []))
            elif change.get("type") == "removed":
                summary["removed"] += len(change.get("lines", []))

        return {
            "device": extract_device_name(self.new_config),
            "timestamp": get_iso_timestamp(),
            "changes": self.changes,
            "summary": summary,
            "has_changes": summary["added"] > 0 or summary["removed"] > 0
        }

