"""设备身份助手 —— 物理名格式的唯一实现（spec 第四节）。

物理名 = f"{stack_name}-{suffix}"，编号不补零、跳号原样；
成员号优先级：member_ids（Aruba VSF `Member ID` / Cisco show version 成员表第 1 组）
> 端口名前缀（见 port_names.member_no_from_port）> 顺序号兜底。

顺序号仅在拿不到真实号时兜底 —— 跳号场景（成员 2 拆走后成员 3 会被标成 -2）
会让成员行"改名"、历史与保修断链，所以真实号必须优先（spec 第六节铁律 1）。
"""
import re


def member_suffixes(serial_count: int, member_ids: str) -> list[str]:
    """成员后缀列表（与序列号同序 1:1）。真实号全为数字且数量一致才采用，否则顺序号。"""
    mids = [m.strip() for m in (member_ids or "").split(",") if m.strip()]
    if len(mids) == serial_count and all(m.isdigit() for m in mids):
        return mids
    return [str(i + 1) for i in range(serial_count)]


def physical_name(stack_name: str, suffix: str) -> str:
    return f"{stack_name}-{suffix}"


def display_name(stack_name: str, suffix: str, member_count: int) -> str:
    """展示名：成员数 ≥2 → 物理名；=1 → 基础名（与单机一致）。存储名恒定。"""
    return physical_name(stack_name, suffix) if member_count >= 2 else stack_name


# 堆叠/VSF 配置特征行：Aruba `vsf member 1`、Cisco `switch 1 provision ...`
_STACK_CONFIG_RE = re.compile(r'^\s*(vsf\s+member\s+\d+|switch\s+\d+\s)',
                              re.MULTILINE | re.IGNORECASE)


def kind_from_config(config_text: str, member_count: int) -> str:
    """kind 判定按**配置**（有堆叠/VSF 配置即 stack，哪怕只有 1 个成员）——

    不按成员数猜：拆到只剩一台的 VSF 配置里 `vsf member 1` 仍在，
    它仍是 stack；重刷成独立设备后才是 standalone。
    """
    if _STACK_CONFIG_RE.search(config_text or ""):
        return "stack"
    return "stack" if member_count >= 2 else "standalone"
