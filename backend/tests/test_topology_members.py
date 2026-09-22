"""多设备拓扑的物理成员命名（spec 第四节：物理名统一 -N 不补零）。

旧行为是固定两位 -01/-02（与仪表盘/报告分叉）；2026-09-22 统一到
device_identity.member_suffixes（真实号优先、顺序号兜底、不补零）。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from api.topology import _expand_physical_devices  # noqa: E402


def _dev(name, serial, member_ids="", model="", version=""):
    return {"name": name, "serial_number": serial, "member_ids": member_ids,
            "model": model, "version": version}


def test_cisco回退号不补零():
    out = _expand_physical_devices([_dev("PVGD1SWI05", "FCW1, FCW2")])
    assert [d["expanded_name"] for d in out] == ["PVGD1SWI05-1", "PVGD1SWI05-2"]


def test_aruba真实号跳号原样():
    out = _expand_physical_devices([_dev("UCDD1SWI01", "SN1, SN2", member_ids="1, 3")])
    assert [d["expanded_name"] for d in out] == ["UCDD1SWI01-1", "UCDD1SWI01-3"]


def test_单机不展开():
    out = _expand_physical_devices([_dev("PVGD1SWI02", "SN9")])
    assert [d["expanded_name"] for d in out] == ["PVGD1SWI02"]
    assert out[0]["stack_group"] == ""
    assert out[0]["physical_count"] == 1


def test_成员保留逻辑名与序号供画布分组():
    out = _expand_physical_devices([_dev("PVGD1SWI05", "FCW1, FCW2")])
    assert all(d["logical_name"] == "PVGD1SWI05" for d in out)
    assert [d["physical_index"] for d in out] == [1, 2]
    assert all(d["stack_group"] == "PVGD1SWI05" for d in out)
