"""端口名归一化测试。

这个模块是从 collector_service 的嵌套闭包抽出来的（2026-09-20），
采集与配置审计共用同一套规则——一旦规则漂移，审计看到的上行口
就会与入库的邻居/生成树角色对不上，所以行为必须钉死。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from utils.port_names import CISCO_PORT_SHORT, norm_lag_name, normalize_port_name  # noqa: E402


def test_cisco_long_names_are_shortened():
    assert normalize_port_name("GigabitEthernet1/1/2") == "Gi1/1/2"
    assert normalize_port_name("TenGigabitEthernet1/0/1") == "Te1/0/1"
    assert normalize_port_name("TwentyFiveGigE1/0/2") == "Twe1/0/2"
    assert normalize_port_name("HundredGigE1/0/1") == "Hu1/0/1"
    assert normalize_port_name("FortyGigE1/0/1") == "Fo1/0/1"
    assert normalize_port_name("FastEthernet0/1") == "Fa0/1"
    assert normalize_port_name("Port-channel3") == "Po3"
    assert normalize_port_name("Loopback0") == "Lo0"


def test_short_names_are_idempotent():
    """已经归一化过的名字再归一化不能变形（CDP 输出多是短名，会被重复处理）。"""
    for name in ["Gi1/1/2", "Te1/0/1", "Twe1/0/2", "Po3", "Hu1/0/1"]:
        assert normalize_port_name(normalize_port_name(name)) == normalize_port_name(name)


def test_tw_variants_both_map_to_twe():
    """'show etherchannel summary' 输出 Tw1/0/2，LLDP 长名归一化得到 Twe1/0/2，
    两者必须对齐；'Twe' 必须排在 'Tw' 之前，否则已被 Tw 匹配后再拼接会出错。"""
    assert normalize_port_name("Tw1/0/2") == "Twe1/0/2"
    assert normalize_port_name("Twe1/0/2") == "Twe1/0/2"
    assert normalize_port_name("TwentyFiveGigE1/0/2") == normalize_port_name("Tw1/0/2")


def test_aruba_cx_names_pass_through():
    """Aruba CX 的 member/slot/port 形式没有前缀，应原样返回。"""
    for name in ["1/1/1", "1/1/50", "2/1/51", "vlan 255", "mgmt", "lag 1"]:
        assert normalize_port_name(name) == name


def test_twentyfivegige_prefix_order():
    """字典顺序陷阱的回归：'TwentyFiveGigE' 不能被 'Tw' 抢先匹配。"""
    keys = list(CISCO_PORT_SHORT)
    assert keys.index("Twe") < keys.index("Tw")
    assert keys.index("TwentyFiveGigE") < keys.index("Tw")


def test_lag_name_normalization():
    assert norm_lag_name("lag14") == "lag 14"
    assert norm_lag_name("Lag1") == "lag 1"
    assert norm_lag_name("LAG 3") == "lag 3"
    assert norm_lag_name("Port-channel3") == "po 3"
    assert norm_lag_name("Po3") == "po 3"
    assert norm_lag_name("Gi1/1/2") == "Gi1/1/2"
