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
from .port_roles import build_port_roles


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


# 层优先级：总部要求 > 厂商推荐 > 配置惯例。
# 重复或冲突时以高层为准 —— 高层规则照常判定，低层规则应显式置 enabled: false
# 并写明 superseded_by，而不是删掉（删掉会丢掉"讨论过、因冲突而让位"的记录）。
LAYER_PRIORITY = {"公司总部": 0, "厂商基线": 1, "组织规范": 2}


def layer_rank(rule: dict) -> int:
    """数值越小优先级越高；未知来源排在最后。"""
    return LAYER_PRIORITY.get(rule.get("source", ""), 9)


def active_rules(std: dict) -> list[dict]:
    """当前启用的规则（规则管理页需要看到全部，判定只用启用的）。"""
    return [r for r in std.get("rules", []) if r.get("enabled") is not False]


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


def analyze(name: str, text: str, std: dict, site: str | None = None,
            port_context=None, startup_config: str = "") -> dict:
    """对一台设备的配置文本执行全部适用规则。

    site：显式站点（NDM 传 devices.location）。为空时回退到设备名解析——
    netstd 只能从设备名派生站点，命名不规范的设备会让站点豁免悄悄失效。
    port_context：端口角色所需的辅助数据（邻居/生成树/LAG/上行口清单）。
    不传也能跑，只是端口级规则的置信度上不去，会降级为「需人工判断」。
    """
    dev = parse_device(name, text, std["naming"], site=site)
    dev.port_roles = build_port_roles(dev, port_context)
    dev.startup_config = startup_config or ""
    findings: list[dict] = []
    for rule in std["rules"]:
        if rule.get("enabled") is False:      # 停用：与更高优先层冲突、或用户手动关掉
            continue
        if not rule_applies(rule, dev, std):
            continue
        fn = CHECKS.get(rule["check"])
        if fn is None:                   # 未知判定器：跳过（loader 已校验，正常不会走到）
            continue
        findings.extend(fn(dev, rule, std))
    # 排序：档位 → 层优先级（总部在前）→ 规则 id
    findings.sort(key=lambda f: (
        LEVEL_ORDER.index(f["level"]) if f["level"] in LEVEL_ORDER else 9,
        LAYER_PRIORITY.get(f.get("source", ""), 9),
        f["rule_id"]))

    sites = std.get("sites", {}) or {}
    # 只回传判定出角色的端口（unknown 的省略），避免 48 口交换机把响应撑大
    port_roles = {p: {"role": r.role, "confidence": r.confidence, "reasons": r.reasons}
                  for p, r in dev.port_roles.items() if r.role != "unknown"}
    return {
        "port_roles": port_roles,
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
