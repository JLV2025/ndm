"""设备身份助手测试（spec 第四节：物理名格式的唯一规则）。

规则一旦漂移，仪表盘/报告/拓扑/保修四处显示就会再次分叉（本模块的存在
就是为了消灭 4 处各自拼名）。跳号、1 成员、无真实号三类边界必须钉死。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from utils.device_identity import (  # noqa: E402
    display_name,
    kind_from_config,
    member_suffixes,
    physical_name,
)
from utils.port_names import member_no_from_port  # noqa: E402


def test_真实成员号优先且不补零():
    """Aruba VSF 跳号（1、3）——原样，不补 -2、不补零"""
    assert member_suffixes(3, "1, 3, 4") == ["1", "3", "4"]


def test_数量不一致回退顺序号():
    assert member_suffixes(2, "1") == ["1", "2"]
    assert member_suffixes(2, "") == ["1", "2"]


def test_非数字成员号回退顺序号():
    assert member_suffixes(2, "1, 未知") == ["1", "2"]


def test_物理名不补零():
    assert physical_name("SZXD1SWI01", "3") == "SZXD1SWI01-3"


def test_展示名_单成员不加后缀():
    """1 成员（含 1 成员堆叠）显示基础名；≥2 成员才带后缀。存储名恒定。"""
    assert display_name("SZXD1SWI01", "1", 1) == "SZXD1SWI01"
    assert display_name("SZXD1SWI01", "1", 3) == "SZXD1SWI01-1"


def test_kind按配置判定():
    """有堆叠/VSF 配置即 stack（哪怕只有 1 个成员）——不按成员数猜。"""
    assert kind_from_config("vsf member 1\n type jl726b\n", 1) == "stack"
    assert kind_from_config("switch 1 provision ws-c2960x\n", 2) == "stack"
    assert kind_from_config("hostname SWI\ninterface Gi0/1\n", 1) == "standalone"


def test_端口名前缀取成员号():
    """Aruba `1/1/14` 首段；Cisco `Gi2/0/1` 首个数字段；逻辑口 → None。"""
    assert member_no_from_port("1/1/14", "aruba_aoscx") == 1
    assert member_no_from_port("Gi2/0/1", "cisco_ios") == 2
    assert member_no_from_port("Te1/1/1", "cisco_ios") == 1
    assert member_no_from_port("TwentyFiveGigE1/0/2", "cisco_ios") == 1
    assert member_no_from_port("Po1", "cisco_ios") is None
    assert member_no_from_port("Hu1/0/27", "cisco_ios") is None
    assert member_no_from_port("lag1", "aruba_aoscx") is None
    assert member_no_from_port("", "cisco_ios") is None
