"""配置文本解析 —— 从 running-config 文本构建判定所需的设备模型。

移植自 allright/netstd 的 engine.parse_device，改造点（见
docs/superpowers/plans/2026-09-18-compliance-audit.md §二）：
  - lines 用 split("\\n") 而非 splitlines()：与前端渲染同源。实测 18/36 台配置以换行结尾，
    两种分行差一个尾部空元素（索引仍对齐，但行数显示差 1）。
  - VLAN 增加 name_line：标红时能定位到 name 那一行，而不是 vlan 那一行。
  - 接口块增加 end：记录块结束行号，供标红区间使用。
  - 站点支持显式传入：NDM 以 devices.location 为准，设备名正则兜底
    （netstd 只能从设备名派生，站点豁免会因命名不规范而悄悄失效）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache


@lru_cache(maxsize=512)
def compile_re(pattern: str) -> re.Pattern:
    """正则编译缓存 —— netstd 原实现每次匹配都重新编译（每设备数十条正则）。"""
    return re.compile(pattern)


@dataclass
class Device:
    name: str
    text: str
    lines: list[str] = field(default_factory=list)
    platform: str = "unknown"          # cx / cisco / unknown
    hostname: str = ""
    site: str = ""
    dc: str = ""
    dtype: str = ""
    num: str = ""
    role: str = "access"               # access / core / router
    site_source: str = ""              # location / name / ""（来源，便于排障）
    vlans: dict[int, dict] = field(default_factory=dict)   # id -> {name, line, name_line}
    svis: list[dict] = field(default_factory=list)         # {vlan, ip, mask, line, text}
    svi_blocks: list[dict] = field(default_factory=list)   # 所有 interface vlan N 块
    vty_blocks: list[dict] = field(default_factory=list)   # {header, line, body[], end}
    if_blocks: list[dict] = field(default_factory=list)    # {header, line, body[], end}
    port_roles: dict = field(default_factory=dict)         # 端口名 -> PortRole（analyze 时注入）
    startup_config: str = ""                               # 启动配置（analyze 时注入，用于"改了没保存"）


def _detect_platform(text: str) -> str:
    if re.search(r"ArubaOS-CX", text) or re.search(r"CX\s+[A-Z]{2}\.\d", text):
        return "cx"
    if re.search(r"(?m)^version \d", text):
        return "cisco"
    return "unknown"


def _parse_vlans(dev: Device) -> None:
    """VLAN 定义块：vlan <id|id-id|id,id> ，其后的 name 行归属该 VLAN。"""
    cur: int | None = None
    for i, raw in enumerate(dev.lines, start=1):
        t = raw.strip()
        m = re.match(r"^vlan\s+([\d,\-]+)\s*$", t, re.I)
        if m:
            cur = None
            for part in m.group(1).split(","):
                rng = re.match(r"^(\d+)-(\d+)$", part)
                if rng:
                    for vid in range(int(rng.group(1)), int(rng.group(2)) + 1):
                        dev.vlans[vid] = {"name": "", "line": i, "name_line": None}
                        cur = vid
                elif part.isdigit():
                    dev.vlans[int(part)] = {"name": "", "line": i, "name_line": None}
                    cur = int(part)
            continue
        if cur is not None and raw[:1].isspace():
            m = re.match(r'^name\s+(.+?)\s*$', t, re.I)
            if m:
                dev.vlans[cur]["name"] = m.group(1).strip('"')
                dev.vlans[cur]["name_line"] = i
                cur = None
                continue
        if raw and not raw[0].isspace():
            cur = None


def _parse_blocks(dev: Device) -> None:
    """接口块与 vty 块。块从顶层 `interface ...` / `line vty ...` 起，
    到下一个顶层行结束；块内为缩进行。"""
    block: dict | None = None
    last = 0

    def close() -> None:
        nonlocal block
        if block:
            block["end"] = last or block["line"]
            (dev.vty_blocks if block.get("kind") == "vty" else dev.if_blocks).append(block)
            block = None

    for i, raw in enumerate(dev.lines, start=1):
        if re.match(r"^interface\s+\S", raw):
            close()
            block = {"kind": "if", "header": raw.strip(), "line": i, "body": []}
        elif re.match(r"^line\s+vty\s", raw):
            close()
            block = {"kind": "vty", "header": raw.strip(), "line": i, "body": []}
        elif block and raw[:1].isspace():
            block["body"].append({"text": raw.strip(), "line": i})
            last = i
        elif raw and not raw[0].isspace():
            close()
    close()


def _parse_svis(dev: Device) -> None:
    for blk in dev.if_blocks:
        m = re.match(r"^interface\s+[Vv]lan\s*(\d+)$", blk["header"])
        if not m:
            continue
        vlan_id = int(m.group(1))
        dev.svi_blocks.append({"vlan": vlan_id, "line": blk["line"],
                               "body": blk["body"], "end": blk["end"]})
        for item in blk["body"]:
            m2 = re.match(
                r"^ip address\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
                r"(?:/(\d{1,2})|\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))?",
                item["text"],
            )
            if m2:
                dev.svis.append({
                    "vlan": vlan_id,
                    "ip": m2.group(1),
                    "mask": ("/" + m2.group(2)) if m2.group(2) else (m2.group(3) or ""),
                    "line": item["line"],
                    "text": item["text"],
                })


def parse_device(name: str, text: str, naming_cfg: dict, site: str | None = None) -> Device:
    """解析设备配置文本。

    site：显式站点（NDM 传 devices.location）。为空时回退到设备名解析，
    并记录来源到 site_source，便于判定「站点豁免为何未生效」。
    """
    dev = Device(name=name, text=text, lines=text.split("\n"))
    dev.platform = _detect_platform(text)

    m = re.search(r"(?mi)^hostname\s+(\S+)", text)
    dev.hostname = m.group(1) if m else ""

    m = re.match(naming_cfg["pattern"], name)
    if m:
        derived_site, dev.dc, dev.dtype, dev.num = m.groups()
        dev.site = site or derived_site
        dev.site_source = "location" if site else "name"
        if dev.dtype == "RTW":
            dev.role = "router"
        elif dev.dc in naming_cfg.get("core_dc_codes", []):
            dev.role = "core"
    else:
        dev.site = site or ""
        dev.site_source = "location" if site else ""

    _parse_vlans(dev)
    _parse_blocks(dev)
    _parse_svis(dev)
    return dev
