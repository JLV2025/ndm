"""端口名归一化 —— CDP/LLDP/STP/配置文本之间的端口名对齐。

为什么需要：同一台设备的同一个端口，在不同数据源里写法不同——
  CDP 输出    多已是短名  Gi1/1/2
  LLDP 输出   长名       GigabitEthernet1/1/2
  etherchannel Tw1/0/2（且 'Tw' 与 'Twe' 都要归到 'Twe'）
  配置文本     interface GigabitEthernet1/1/2
不归一化就无法把邻居、生成树角色、LAG 成员与配置里的接口块对上。

原为 `collector_service._save_data` 内的嵌套闭包（外部不可导入），
2026-09-20 抽到本模块，供采集与配置审计共用——两边必须用同一套规则，
否则审计看到的上行口与采集入库的邻居/生成树角色会对不上。
"""
from __future__ import annotations

import re

# 长名 → 短名。注意顺序：'Twe' 必须排在 'Tw' 之前，否则 'Twe1/0/2' 会被 'Tw' 先匹配成 'Twe' 再拼接出错。
# 'Twe': 'Twe' 的作用是让已经归一化过的名字保持幂等。
CISCO_PORT_SHORT: dict[str, str] = {
    'GigabitEthernet': 'Gi', 'TenGigabitEthernet': 'Te',
    'TwentyFiveGigE': 'Twe', 'HundredGigE': 'Hu',
    'FortyGigE': 'Fo', 'FastEthernet': 'Fa',
    'Port-channel': 'Po', 'Loopback': 'Lo',
    'Twe': 'Twe', 'Tw': 'Twe',
}


def normalize_port_name(port: str) -> str:
    """Cisco 长接口名归一化为短名：GigabitEthernet1/1/2 → Gi1/1/2。

    已归一化的名字保持幂等；Aruba CX 的 `1/1/1` 形式原样返回。
    """
    for long_pfx, short_pfx in CISCO_PORT_SHORT.items():
        if port.startswith(long_pfx):
            return short_pfx + port[len(long_pfx):]
    return port


def norm_lag_name(port: str) -> str:
    """LAG 名归一化：lag14 → 'lag 14'，Lag1 → 'lag 1'，Port-channel3 → 'po 3'。"""
    m = re.match(r'^(lag|po|port-channel)\s*(\d+)$', port, re.IGNORECASE)
    if m:
        pfx = m.group(1).lower().replace('port-channel', 'po')
        return f'{pfx} {m.group(2)}'
    return port


# 逻辑口不属于任何物理成员（Po 是成员口聚合、Hu 是堆叠背板口、vlan 是虚接口）
_LOGICAL_PORT_RE = re.compile(r'^(po|hu|lag|vlan)\s*\d', re.IGNORECASE)
_ARUBA_MEMBER_RE = re.compile(r'^(\d+)/')                      # 1/1/49 → 成员 1
_CISCO_MEMBER_RE = re.compile(r'^[A-Za-z][A-Za-z\-]*(\d+)/')   # Gi1/0/1 → 成员 1


def member_no_from_port(port_name: str, platform: str = "") -> int | None:
    """端口名 → 所属堆叠成员号（1-based）。

    Aruba VSF（`1/1/49`）与 Cisco 堆叠（`Gi1/0/1`、`TwentyFiveGigE1/0/2`）的
    首个数字段都是成员号 —— 这是"端口属于哪个物理成员"的平台无关事实来源
    （画图靠端口编号定位成员）。

    逻辑口（Po*/Hu*/lag*/vlan*）→ None；认不出来（空串、0 号槽）→ None，
    **不猜**——默认归到成员 1 会把 unknown 悄悄画到错误的成员上。

    规则迁自 api/topology._member_slot_for_port（2026-09-22），那边保留
    同名包装（`or 1`）维持既有的"认不出按成员 1 分组"行为。
    """
    port = (port_name or "").strip()
    if not port or _LOGICAL_PORT_RE.match(port):
        return None
    m = _ARUBA_MEMBER_RE.match(port) or _CISCO_MEMBER_RE.match(port)
    if not m:
        return None
    slot = int(m.group(1))
    return slot if slot >= 1 else None
