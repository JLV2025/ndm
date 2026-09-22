"""生命周期三色判定 —— 唯一实现（spec 第十三节）

判定顺序即优先级（红 > 橙 > 绿）；月份按**日历月**计算（now + N 个月，
目标月无此日时夹到月末），不是 60/180 天。前端只做「状态 → 颜色」映射，
不再重复判一次（生命周期页与详情页卡片共用本模块）。
"""
import calendar
from datetime import date

# 抄自 Cisco/HPE 保修查询页：查无结果的占位文案
WARRANTY_UNKNOWN_NOTE = "unavailable"

WARRANTY_SOON_MONTHS = 2    # 维保临近阈值（用户定：2 个月内橙色）
EOL_SOON_MONTHS = 6         # EoS/EoL 临近阈值（用户定：6 个月内橙色）


def _parse(value: str) -> date | None:
    """解析 YYYY-MM-DD；空串/非法格式 = 未登记（返回 None）。"""
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _add_months(today: date, months: int) -> date:
    """日历月偏移；目标月天数不足时夹到月末（12-31 + 2 月 → 2-28/2-29）。"""
    m = today.month - 1 + months
    year, month = today.year + m // 12, m % 12 + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def _trend(end: date, today: date, soon_months: int) -> str:
    if end < today:
        return "expired"
    return "soon" if end <= _add_months(today, soon_months) else "ok"


def warranty_status(warranty_end: str, note: str, today: date | None = None) -> str:
    """维保三色：ok（绿）/ soon（橙，≤2 月）/ missing（橙，未登记）/ expired（红）。

    未登记到期日但备注等于 Unavailable = 查无此机 → 按出保处理。
    """
    today = today or date.today()
    end = _parse(warranty_end)
    if end:
        return _trend(end, today, WARRANTY_SOON_MONTHS)
    if (note or "").strip().lower() == WARRANTY_UNKNOWN_NOTE:
        return "expired"
    return "missing"


def eol_status(end_of_sale: str, end_of_support: str, today: date | None = None) -> str:
    """EoS/EoL 状态：两日期分别判定后取最严重（expired > soon > ok > none）。"""
    today = today or date.today()
    ranks = {"expired": 3, "soon": 2, "ok": 1, "none": 0}
    results = []
    for raw in (end_of_sale, end_of_support):
        end = _parse(raw)
        results.append(_trend(end, today, EOL_SOON_MONTHS) if end else "none")
    return max(results, key=lambda s: ranks[s])
