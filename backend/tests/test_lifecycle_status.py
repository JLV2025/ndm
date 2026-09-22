"""三色状态判定测试（spec 第十三节：绿在保 / 橙临近 / 红出保）

维保阈值 2 个月、EoS/EoL 阈值 6 个月，按日历月计算。边界必须钉死：
阈值当天算橙、超一天算绿、月末日期不越界（12-31 加 2 月要夹到 2-28，
不能构造出 2-31 直接崩）。未登记维保 = 橙；未登记且备注 Unavailable = 红。
"""
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.lifecycle_status import eol_status, warranty_status  # noqa: E402

TODAY = date(2026, 9, 22)


def test_在保_剩余超两个月():
    assert warranty_status("2027-01-01", "", TODAY) == "ok"     # 剩 3 个月+


def test_临近_两个月内():
    assert warranty_status("2026-11-21", "", TODAY) == "soon"   # 阈值前一天
    assert warranty_status("2026-11-22", "", TODAY) == "soon"   # 恰好 +2 月
    assert warranty_status("2026-11-23", "", TODAY) == "ok"     # 超出一天即绿


def test_已过期():
    assert warranty_status("2026-09-21", "", TODAY) == "expired"


def test_未登记为橙色():
    assert warranty_status("", "", TODAY) == "missing"
    assert warranty_status("", "在保", TODAY) == "missing"
    assert warranty_status("N/A", "", TODAY) == "missing"       # 非法格式按未登记


def test_unavailable按出保():
    assert warranty_status("", "Unavailable", TODAY) == "expired"
    assert warranty_status("", " unavailable ", TODAY) == "expired"    # 去空格/忽略大小写
    assert warranty_status("", "unavailable info", TODAY) == "missing"  # 等于才算，包含不算


def test_月末不越界():
    """12-31 加月要夹到目标月最后一天，不能构造出 2-31 崩掉"""
    month_end = date(2026, 12, 31)
    assert warranty_status("2027-02-28", "", month_end) == "soon"   # 夹到 2-28
    assert warranty_status("2027-03-01", "", month_end) == "ok"


def test_eol_六个月阈值():
    assert eol_status("2027-04-01", "", TODAY) == "ok"          # 超 6 个月
    assert eol_status("2026-12-01", "", TODAY) == "soon"        # ≤ 6 个月


def test_eol_取最严重():
    assert eol_status("2026-01-01", "2028-01-01", TODAY) == "expired"   # 停止销售已过
    assert eol_status("2026-12-01", "2028-01-01", TODAY) == "soon"      # 一个临近
    assert eol_status("2027-04-01", "", TODAY) == "ok"


def test_eol_全未登记为灰():
    assert eol_status("", "", TODAY) == "none"
    assert eol_status("N/A", "", TODAY) == "none"
