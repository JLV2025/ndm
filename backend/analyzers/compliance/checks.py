"""内置判定器 —— 规则通过 `check` 名 + `params` 引用这里面的函数。

移植自 allright/netstd 的 engine.py 判定器部分，改造点：
  - make_finding 增加 lines / locatable（前端标红的契约：只认行号，禁止文本匹配）
  - 去掉证据截断（原 check_vlan1_in_use 的 ev[:14] / ev[:8]）
  - line:0 改为 line:None（原命名类判定器用 0 表示"无行号"，与真实行号 1 起冲突）
  - check_enable_secret_type 由 params.pattern 驱动（原实现硬编码 `^enable secret 5`）
"""
from __future__ import annotations

import re

from .parser import Device, compile_re

# 档位顺序 = 报告排序顺序，也决定 UI 上的展示次序
LEVEL_ORDER = ["强烈建议", "风险提示", "改进建议", "可选优化", "需人工判断"]


def matches(dev: Device, pattern: str) -> list[dict]:
    """返回配置文本中命中该正则的 [{line, text}]。"""
    rx = compile_re(pattern)
    return [{"line": i, "text": raw} for i, raw in enumerate(dev.lines, start=1) if rx.search(raw)]


def rule_platform(rule: dict) -> str:
    plats = rule.get("platforms", ["all"])
    return "全部" if plats == ["all"] else " / ".join(plats)


def make_finding(rule: dict, evidence: list[dict], current: str | None = None) -> dict:
    """构造一条审计发现。

    lines：证据涉及的配置行号（去重升序，剔除 None）。前端**只按行号标红**——
    实测 35/36 台配置带行尾空格，"拿证据文本回配置里搜"必然错位。
    locatable：是否可定位到行。命名类、全局策略类判定没有具体行，为 False，
    此时前端禁用「定位到行」按钮。
    """
    lines = sorted({e["line"] for e in evidence if e.get("line")})
    return {
        "rule_id": rule["id"],
        "title": rule["title"],
        "level": rule.get("level", "改进建议"),
        "source": rule.get("source", ""),
        "severity": rule.get("severity", ""),
        "platform": rule_platform(rule),
        "hit": True,
        "evidence": evidence,
        "lines": lines,
        "locatable": bool(lines),
        "current": current if current is not None else "\n".join(e["text"] for e in evidence),
        "fix": rule.get("fix", ""),
        "why": rule.get("why", ""),
        "note": rule.get("note", ""),
    }


# ---------------------------------------------------------------- 通用判定器

def check_absent_regex(dev: Device, rule: dict, std: dict) -> list[dict]:
    """命中 pattern 即出建议（用于"不应该出现"的配置）。"""
    ev = matches(dev, rule["params"]["pattern"])
    return [make_finding(rule, ev)] if ev else []


def check_present_flag(dev: Device, rule: dict, std: dict) -> list[dict]:
    """同 absent_regex，命名表达"标记其存在"。保留两种名字是为了规则可读性。"""
    ev = matches(dev, rule["params"]["pattern"])
    return [make_finding(rule, ev)] if ev else []


def check_present_regex(dev: Device, rule: dict, std: dict) -> list[dict]:
    """未命中 pattern 即出建议（用于"应该有"的配置）。"""
    ev = matches(dev, rule["params"]["pattern"])
    if ev:
        return []
    return [make_finding(rule, [], "(未配置)")]


def check_enable_secret_type(dev: Device, rule: dict, std: dict) -> list[dict]:
    pattern = rule.get("params", {}).get("pattern", r"(?m)^enable secret 5 ")
    ev = matches(dev, pattern)
    return [make_finding(rule, ev)] if ev else []


def check_vty_transport(dev: Device, rule: dict, std: dict) -> list[dict]:
    out = []
    for blk in dev.vty_blocks:
        texts = [b["text"] for b in blk["body"]]
        bad = []
        inputs = [t for t in texts if re.match(r"^transport input\s", t, re.I)]
        outputs = [t for t in texts if re.match(r"^transport output\s", t, re.I)]
        if not inputs or any(re.search(r"\b(all|telnet)\b", t, re.I) for t in inputs):
            bad.extend(inputs or ["(无 transport input —— 继承平台默认，老版本默认允许 telnet)"])
        for t in outputs:
            if re.search(r"\btelnet\b", t, re.I):
                bad.append(t)
        if bad:
            ev = [{"line": blk["line"], "text": blk["header"]}]
            for b in blk["body"]:
                if b["text"] in bad:
                    ev.append(b)
            out.append(make_finding(rule, ev))
    return out


# ---------------------------------------------------------------- VLAN 类判定器

def check_vlan_name_pure(dev: Device, rule: dict, std: dict) -> list[dict]:
    standard = {int(k): v for k, v in std["vlans"]["standard"].items()}

    def norm(s: str) -> str:
        return re.sub(r"[\s\-_/]+", "", s).lower()

    def alternatives(vid: int) -> list[str]:
        # 标准名里用 " / " 分隔的是备选写法，任一匹配即算合规
        return [a.strip() for a in str(standard[vid]).split("/") if a.strip()]

    rows = []
    for vid, info in sorted(dev.vlans.items()):
        if vid not in standard or not info["name"]:
            continue
        name = info["name"]
        reasons = []
        if re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", name):
            reasons.append("名称内嵌网段")
        if not any(norm(name) == norm(a) for a in alternatives(vid)):
            reasons.append(f"与标准用途名「{standard[vid]}」不一致")
        if reasons:
            rows.append((vid, name, "；".join(reasons)))
    if not rows:
        return []
    ev = [{"line": dev.vlans[vid].get("name_line") or dev.vlans[vid]["line"],
           "text": f"vlan {vid} / name {name}  —— {why}"}
          for vid, name, why in rows]
    current = "\n".join(f"vlan {vid}\n    name {name}" for vid, name, _ in rows)
    return [make_finding(rule, ev, current) | {"detail": f"共 {len(rows)} 个 VLAN 名称需统一"}]


def check_vlan_id_standard(dev: Device, rule: dict, std: dict) -> list[dict]:
    standard = {int(k) for k in std["vlans"]["standard"]}
    rows = [(vid, info) for vid, info in sorted(dev.vlans.items()) if vid not in standard]
    if not rows:
        return []
    ev = [{"line": info["line"],
           "text": f"vlan {vid}  {('name ' + info['name']) if info['name'] else '(未命名)'}"}
          for vid, info in rows]
    current = "\n".join(
        f"vlan {vid}\n    name {info['name'] or '(未命名)'}" for vid, info in rows)
    return [make_finding(rule, ev, current)
            | {"detail": f"共 {len(rows)} 个非标 VLAN：{', '.join(str(v) for v, _ in rows)}"}]


def check_addr_third_octet(dev: Device, rule: dict, std: dict) -> list[dict]:
    out = []
    for svi in dev.svis:
        o = svi["ip"].split(".")
        if int(o[2]) != svi["vlan"]:
            out.append(make_finding(
                rule,
                [{"line": svi["line"], "text": svi["text"]}],
                f"interface vlan {svi['vlan']}\n    {svi['text']}",
            ) | {"detail": f"第三段 {o[2]} ≠ VLAN ID {svi['vlan']}",
                 "expect": f"10.{o[1]}.{svi['vlan']}.x"})
    return out


def check_vlan1_in_use(dev: Device, rule: dict, std: dict) -> list[dict]:
    if 1 not in dev.vlans:
        return []
    ev = []
    for blk in dev.svi_blocks:
        if blk["vlan"] == 1:
            ev.append({"line": blk["line"], "text": "interface vlan 1"})
            for b in blk["body"]:
                ev.append({"line": b["line"], "text": "    " + b["text"]})
    for i, raw in enumerate(dev.lines, start=1):
        if re.search(r"^\s*(vlan access 1|switchport access vlan 1)\s*$", raw, re.I):
            ev.append({"line": i, "text": raw.strip()})
    if not ev:
        return []
    ports = len([e for e in ev if "access" in e["text"]])
    has_svi = any("interface vlan 1" in e["text"] for e in ev)
    parts = []
    if has_svi:
        parts.append("配置了 interface vlan 1")
    if ports:
        parts.append(f"{ports} 处端口划分在 VLAN 1")
    return [make_finding(rule, ev, "\n".join(e["text"] for e in ev))
            | {"detail": "；".join(parts)}]


# ---------------------------------------------------------------- 命名类判定器

def check_device_name_format(dev: Device, rule: dict, std: dict) -> list[dict]:
    naming = std["naming"]
    if dev.name in naming.get("known_name_exceptions", []):
        return []
    if re.match(naming["pattern"], dev.name):
        if dev.dtype not in naming["type_codes"]:
            return [make_finding(rule, [{"line": None, "text": f"设备名 {dev.name}"}],
                                 f"设备名 {dev.name}") | {"detail": f"类型码 {dev.dtype} 不在标准类型内"}]
        return []
    return [make_finding(rule, [{"line": None, "text": f"设备名 {dev.name}"}],
                         f"设备名 {dev.name}") | {"detail": "不符合 站点码+机房/层级+类型+编号 格式"}]


def check_hostname_match(dev: Device, rule: dict, std: dict) -> list[dict]:
    if not dev.hostname or dev.name in std["naming"].get("known_name_exceptions", []):
        return []
    if dev.hostname != dev.name:
        return [make_finding(rule, [{"line": None, "text": f"hostname {dev.hostname}"}],
                             f"hostname {dev.hostname}")
                | {"detail": f"应为 {dev.name}", "expect": dev.name}]
    return []


# ---------------------------------------------------------------- 平台特性判定器

def check_vsf_split_detect(dev: Device, rule: dict, std: dict) -> list[dict]:
    """VSF 脑裂检测：只对真正的堆叠设备判定（存在 member 2 或 secondary-member 2）。"""
    stacked = bool(re.search(r"(?mi)^vsf\s+(secondary-member|member\s+2)\b", dev.text))
    if not stacked:
        return []
    if re.search(r"(?mi)^\s*vsf\s+split-detect\s+mgmt", dev.text):
        return []
    ev = matches(dev, r"(?mi)^vsf\s+(secondary-member|member)\s+\d+")
    return [make_finding(rule, ev, "\n".join(e["text"] for e in ev))
            | {"detail": "该机是 VSF 堆叠，但未启用 mgmt 口脑裂检测"}]


CHECKS: dict[str, callable] = {
    "absent_regex": check_absent_regex,
    "present_flag": check_present_flag,
    "present_regex": check_present_regex,
    "enable_secret_type": check_enable_secret_type,
    "vty_transport": check_vty_transport,
    "vlan_name_pure": check_vlan_name_pure,
    "vlan_id_standard": check_vlan_id_standard,
    "addr_third_octet": check_addr_third_octet,
    "vlan1_in_use": check_vlan1_in_use,
    "device_name_format": check_device_name_format,
    "hostname_match": check_hostname_match,
    "vsf_split_detect": check_vsf_split_detect,
}
