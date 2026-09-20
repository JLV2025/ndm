"""配置审计 —— 判定引擎（对外入口）。

设计原则（沿用 netstd）：**标准是数据，不是代码**。
  - config/audit/*.yaml 是唯一权威来源
  - 引擎只提供「内置判定器」，规则通过 check + params 引用它
  - 新增同类标准 = 加一条 YAML；新增判定方式 = 加一个 check 函数

典型用法：
    from backend.analyzers.compliance import loader, engine
    std = loader.load_standard()
    result = engine.analyze("BJQD1SWI01", config_text, std, site="BJQ")
"""
from __future__ import annotations

from .checks import CHECKS, LEVEL_ORDER
from .parser import Device, parse_device


def resolve_sites(tokens, std: dict) -> set[str]:
    """站点令牌解析：既接受字面站点码（如 ZGN），也接受 sites 段的分组名（如 exempt_vlan_address）。

    netstd 原实现只读 `exempt[0]`，写成两个分组时第二个会静默失效——
    这类"悄悄不生效"最容易在审计里造成假阴性，故统一为展开全部令牌。
    """
    out: set[str] = set()
    groups = std.get("sites", {}) or {}
    for t in tokens or []:
        if t in groups:
            out.update(groups[t])
        else:
            out.add(t)
    return out


def rule_applies(rule: dict, dev: Device, std: dict) -> bool:
    """规则是否适用于本设备：平台 + 站点作用域。"""
    plats = rule.get("platforms", ["all"])
    if plats != ["all"] and dev.platform not in plats:
        return False
    only = resolve_sites(rule.get("only_sites"), std)
    if only and dev.site not in only:
        return False
    exempt = rule.get("exempt_sites") or []
    if isinstance(exempt, str):          # 容忍 YAML 里写成字符串
        exempt = [exempt]
    if dev.site and dev.site in resolve_sites(exempt, std):
        return False
    return True


def analyze(name: str, text: str, std: dict, site: str | None = None) -> dict:
    """对一台设备的配置文本执行全部适用规则。

    site：显式站点（NDM 传 devices.location）。为空时回退到设备名解析——
    netstd 只能从设备名派生站点，命名不规范的设备会让站点豁免悄悄失效。
    """
    dev = parse_device(name, text, std["naming"], site=site)
    findings: list[dict] = []
    for rule in std["rules"]:
        if not rule_applies(rule, dev, std):
            continue
        fn = CHECKS.get(rule["check"])
        if fn is None:                   # 未知判定器：跳过（loader 已校验，正常不会走到）
            continue
        findings.extend(fn(dev, rule, std))
    findings.sort(key=lambda f: (
        LEVEL_ORDER.index(f["level"]) if f["level"] in LEVEL_ORDER else 9, f["rule_id"]))

    sites = std.get("sites", {}) or {}
    return {
        "device": {
            "name": dev.name,
            "platform": dev.platform,
            "hostname": dev.hostname,
            "site": dev.site,
            "site_source": dev.site_source,
            "dc": dev.dc,
            "type": dev.dtype,
            "role": dev.role,
            "vlans": len(dev.vlans),
            "svis": len(dev.svis),
            "exempt": bool(dev.site and dev.site in (sites.get("exempt_vlan_address") or [])),
        },
        "findings": findings,
        "counts": {lv: sum(1 for f in findings if f["level"] == lv) for lv in LEVEL_ORDER},
    }
