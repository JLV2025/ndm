"""
设备角色核查模块

交叉验证 YAML devices.yaml 中的交换机角色标注与 LLDP 邻居拓扑数据，
检测标注缺失、连接不一致、命名冲突等问题。

用法：
    verifier = RoleVerifier(data_root="data")
    warnings = verifier.verify_device("PVGD1SWI01")
    audit = verifier.audit_location("PVG")
"""

import os
import re
import yaml
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class RoleWarning:
    """角色核查警告"""
    device: str
    rule: str          # 规则名称
    message: str        # 警告信息
    severity: str       # 'error' | 'warning' | 'info'


class RoleVerifier:
    """设备角色核查器"""

    # 角色关键词映射（英文不区分大小写）
    CORE_KEYWORDS = ["核心", "core"]
    ACCESS_KEYWORDS = ["接入", "access"]
    CASCADE_KEYWORDS = ["串接", "cascade"]

    def __init__(self, data_root: str = "data", config_root: str = "config"):
        """
        Args:
            data_root: 数据目录根路径
            config_root: 配置文件目录根路径
        """
        self.data_root = data_root
        self.config_root = config_root
        self._devices_yaml: Optional[List[dict]] = None
        self._device_map: Optional[Dict[str, dict]] = None

    @property
    def devices(self) -> List[dict]:
        """加载 devices.yaml"""
        if self._devices_yaml is None:
            yaml_path = os.path.join(self.config_root, "devices.yaml")
            if not os.path.exists(yaml_path):
                self._devices_yaml = []
            else:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    self._devices_yaml = data.get("devices", []) if data else []
        return self._devices_yaml

    @property
    def device_map(self) -> Dict[str, dict]:
        """设备名 → 设备配置映射"""
        if self._device_map is None:
            self._device_map = {d.get("name", ""): d for d in self.devices}
        return self._device_map

    def _get_switches(self) -> List[dict]:
        """获取所有交换机设备"""
        return [
            d for d in self.devices
            if d.get("type", "") in ("aruba_aoscx", "cisco_ios", "cisco_ios_xe")
        ]

    def _get_switch_neighbors(self, device_name: str) -> List[str]:
        """
        获取指定交换机的 LLDP 邻居设备名列表（从 SQLite 查询）

        查询 neighbors 表的最新采集数据，返回 neighbor_name 列表
        """
        neighbors = []
        try:
            from storage.database import get_connection as _get_db
            db = _get_db()
            if db:
                rows = db.execute("""
                    SELECT DISTINCT n.neighbor_name
                    FROM neighbors n
                    JOIN devices d ON n.device_id = d.id
                    WHERE d.name = ?
                      AND n.collection_id = (
                          SELECT c.id FROM collections c
                          WHERE c.device_id = n.device_id
                          ORDER BY c.id DESC LIMIT 1
                      )
                """, (device_name,)).fetchall()
                neighbors = [r["neighbor_name"] for r in rows if r["neighbor_name"]]
        except Exception:
            pass
        return list(set(neighbors))  # 去重

    def _get_role(self, device: dict) -> Optional[str]:
        """
        从设备 YAML notes 字段提取角色

        Returns:
            'core' | 'access' | 'cascade' | None
        """
        notes = (device.get("notes") or "").lower()
        if any(kw in notes for kw in self.CORE_KEYWORDS):
            return "core"
        if any(kw in notes for kw in self.CASCADE_KEYWORDS):
            return "cascade"
        if any(kw in notes for kw in self.ACCESS_KEYWORDS):
            return "access"
        return None

    def _parse_device_name(self, name: str) -> Optional[dict]:
        """
        解析设备命名：PVGD1SWI02 → {site, room, typeCode, num}
        GTS服务器例外：GTSPEKESX01 → {site: GTS, room: PEK, typeCode: ESX, num: 1}
        """
        # GTS 服务器
        if name.startswith('GTS'):
            m = re.match(r"^GTS([A-Z]{3})(ESX|SRV)(\d*)$", name)
            if m:
                return {
                    "site": "GTS",
                    "room": m.group(1),
                    "type_code": m.group(2),
                    "num": int(m.group(3) or "0"),
                }
            return None
        m = re.match(r"^([A-Z]{3})(D\d)([A-Z]{3})(\d{2})$", name)
        if not m:
            return None
        return {
            "site": m.group(1),
            "room": m.group(2),
            "type_code": m.group(3),
            "num": int(m.group(4)),
        }

    def _is_switch(self, device: dict) -> bool:
        """判断设备是否为交换机（基于类型字段）"""
        t = device.get("type", "")
        return t in ("aruba_aoscx", "cisco_ios", "cisco_ios_xe")

    # ------------------------------------------------------------------
    # 核查规则
    # ------------------------------------------------------------------

    def _check_missing_annotation(self, device: dict) -> Optional[RoleWarning]:
        """核查：交换机是否缺少角色标注"""
        name = device.get("name", "")
        role = self._get_role(device)
        if role is None:
            return RoleWarning(
                device=name,
                rule="标注缺失",
                message=f"交换机 {name} 缺少角色标注（notes 字段不含 Core/Access/Cascade）",
                severity="warning",
            )
        return None

    def _check_core_consistency(self, device: dict, neighbors: List[str]) -> Optional[RoleWarning]:
        """核查：核心交换机下游不应有其他核心"""
        name = device.get("name", "")
        if self._get_role(device) != "core":
            return None
        for nb_name in neighbors:
            nb_dev = self.device_map.get(nb_name)
            if nb_dev and self._get_role(nb_dev) == "core":
                return RoleWarning(
                    device=name,
                    rule="核心一致性",
                    message=f"核心交换机 {name} 的下游 {nb_name} 也标注为核心交换机",
                    severity="error",
                )
        return None

    def _check_access_uplink(self, device: dict, neighbors: List[str]) -> Optional[RoleWarning]:
        """核查：接入交换机应直连核心交换机"""
        name = device.get("name", "")
        if self._get_role(device) != "access":
            return None
        has_core_uplink = any(
            self._get_role(self.device_map.get(nb_name, {})) == "core"
            for nb_name in neighbors
        )
        if not has_core_uplink:
            # 检查是否有核心邻居（从 neighbors.json）
            has_any_core = any(
                self._get_role(self.device_map.get(nb_name, {})) == "core"
                for nb_name in neighbors
            )
            return RoleWarning(
                device=name,
                rule="接入确认",
                message=f"接入交换机 {name} 未直连任何核心交换机，请确认角色标注是否正确",
                severity="warning",
            )
        return None

    def _check_cascade_no_core(self, device: dict, neighbors: List[str]) -> Optional[RoleWarning]:
        """核查：串接交换机不应直连核心交换机"""
        name = device.get("name", "")
        if self._get_role(device) != "cascade":
            return None
        for nb_name in neighbors:
            nb_dev = self.device_map.get(nb_name)
            if nb_dev and self._get_role(nb_dev) == "core":
                return RoleWarning(
                    device=name,
                    rule="串接确认",
                    message=f"串接交换机 {name} 直连了核心交换机 {nb_name}，应改为接入交换机",
                    severity="error",
                )
        return None

    def _check_naming_consistency(self, device: dict) -> Optional[RoleWarning]:
        """核查：同机房内交换机编号应符合 core < access < cascade 顺序"""
        name = device.get("name", "")
        parsed = self._parse_device_name(name)
        if not parsed:
            return None
        role = self._get_role(device)
        if role is None:
            return None

        # 查找同机房交换机
        same_room = []
        for d in self._get_switches():
            p = self._parse_device_name(d.get("name", ""))
            if p and p["site"] == parsed["site"] and p["room"] == parsed["room"]:
                r = self._get_role(d)
                same_room.append((d.get("name", ""), p["num"], r))

        if len(same_room) < 2:
            return None

        # 排序：core < access < cascade
        role_order = {"core": 1, "access": 2, "cascade": 3}
        for other_name, other_num, other_role in same_room:
            if other_name == name or other_role is None or role is None:
                continue
            # 如果编号更大但角色更高 → 倒挂
            if parsed["num"] > other_num and role_order.get(role, 99) < role_order.get(other_role, 99):
                return RoleWarning(
                    device=name,
                    rule="命名一致性",
                    message=f"编号倒挂：{name}(#{parsed['num']}) 编号大于 {other_name}(#{other_num})"
                            f"但角色层级更高（{role} vs {other_role}）",
                    severity="warning",
                )
        return None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def verify_device(self, device_name: str) -> List[RoleWarning]:
        """
        核查单台交换机

        Args:
            device_name: 设备名称

        Returns:
            警告列表，空列表表示通过核查
        """
        dev = self.device_map.get(device_name)
        if not dev:
            return [RoleWarning(
                device=device_name,
                rule="设备不存在",
                message=f"设备 {device_name} 不在 devices.yaml 中",
                severity="error",
            )]
        if not self._is_switch(dev):
            return []  # 非交换机跳过

        neighbors = self._get_switch_neighbors(device_name)
        warnings: List[RoleWarning] = []

        checks_no_neighbors = [
            self._check_missing_annotation,
            self._check_naming_consistency,
        ]
        checks_with_neighbors = [
            self._check_core_consistency,
            self._check_access_uplink,
            self._check_cascade_no_core,
        ]
        for check in checks_no_neighbors:
            result = check(dev)
            if result:
                warnings.append(result)
        for check in checks_with_neighbors:
            result = check(dev, neighbors)
            if result:
                warnings.append(result)

        return warnings

    def audit_location(self, location: str) -> Dict:
        """
        整站审计

        Args:
            location: 站点代码，如 "PVG"、"BJQ"

        Returns:
            {
                "location": "PVG",
                "devices": [...],
                "warnings": [{"device": "...", "rule": "...", "message": "...", "severity": "..."}],
                "summary": {"total": 5, "passed": 3, "warnings": 1, "errors": 1}
            }
        """
        site_switches = [
            d for d in self._get_switches()
            if d.get("location", "").upper() == location.upper()
        ]

        all_warnings: List[dict] = []
        results: List[dict] = []

        for dev in site_switches:
            name = dev.get("name", "")
            dev_warnings = self.verify_device(name)
            results.append({
                "device": name,
                "role": self._get_role(dev) or "未标注",
                "notes": dev.get("notes") or "",
                "passed": len(dev_warnings) == 0,
                "warnings": [{"rule": w.rule, "message": w.message, "severity": w.severity} for w in dev_warnings],
            })
            for w in dev_warnings:
                all_warnings.append({
                    "device": w.device,
                    "rule": w.rule,
                    "message": w.message,
                    "severity": w.severity,
                })

        total = len(site_switches)
        passed = sum(1 for r in results if r["passed"])
        errors = sum(1 for w in all_warnings if w["severity"] == "error")
        warn_count = sum(1 for w in all_warnings if w["severity"] == "warning")

        return {
            "location": location,
            "devices": results,
            "warnings": all_warnings,
            "summary": {
                "total": total,
                "passed": passed,
                "warnings": warn_count,
                "errors": errors,
            },
        }
