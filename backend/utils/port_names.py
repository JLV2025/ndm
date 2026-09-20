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
