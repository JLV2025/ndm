"""端口角色推断 —— 让端口级规则真正可达。

没有它，只能写"全设备有没有配 BPDU Guard"；有了它，才能写
「BPDU Guard 不该配在上行口」这类真正有专家价值的判定。

信号优先级（覆盖率均为现网实测，见计划 §七.2）：
  高置信  STP 角色 = root           朝向上游（19/36 台有数据，且只有 root/designated 两种）
  高置信  邻居类型 = switch/router/firewall/sdwan   基础设施对端（36/36 台，1732 条 switch 记录）
  中置信  是 LAG 成员 / 出现在 devices.uplink_ports（后者仅 4/36 台，只作佐证）
  中置信  邻居类型 = server/AP/wireless（终端对端）
  中置信  配置里是 vlan access / switchport access vlan
  低置信  接口描述关键词（UPLINK / TO_ / _TO_ 等）、配置里只有 vlan trunk

**不可用信号**：port_snapshots.is_uplink —— 实测 4.5 万行里仅 14 行为 1。

低置信结论不能直接下判定：conflict 类规则只在 high 时出 finding，
否则降级为「需人工判断」——宁可说"我拿不准"，也不要瞎报警。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import Device

# 对端是基础设施 → 本端是上行
UPLINK_NEIGHBORS = {"switch", "router", "firewall", "sdwan"}
# 对端是终端 → 本端是接入口
ACCESS_NEIGHBORS = {"server", "ap", "wireless", "phone"}

# 描述关键词（置信度最低，只作佐证）
# 注意 `to[_-]` 必须带分隔符：否则 "total"/"storage" 这类词会被误命中
UPLINK_DESC = re.compile(r"(?i)(uplink|上行|多链路|multi-?link|\bto[_-]|_to_|-to-)")
ACCESS_DESC = re.compile(r"(?i)\b(phone|ap|printer|camera|pc|user|desk)\b")


@dataclass
class PortContext:
    """审计所需的、配置文本之外的辅助数据（由 source 层从 NDM 库装载）。"""
    stp_roles: dict[str, str] = field(default_factory=dict)        # 端口 → root/designated/...
    neighbor_types: dict[str, str] = field(default_factory=dict)   # 端口 → switch/server/...
    lag_members: set[str] = field(default_factory=set)             # 属于任一 LAG 的物理口
    uplink_ports: set[str] = field(default_factory=set)            # devices.uplink_ports

    @classmethod
    def from_lag_membership(cls, membership: dict | None) -> "PortContext":
        """从 collections.lag_membership（{"lag 1": ["1/1/51", ...]}）取出所有成员口。"""
        members: set[str] = set()
        for _lag, ports in (membership or {}).items():
            members.update(ports or [])
        ctx = cls()
        ctx.lag_members = members
        return ctx


@dataclass
class PortRole:
    port: str
    role: str              # uplink / access / unknown
    confidence: str        # high / medium / low
    reasons: list[str] = field(default_factory=list)

    @property
    def is_confident(self) -> bool:
        return self.confidence == "high"


def _config_hint(block: dict) -> str:
    """从接口块正文判断二层形态：trunk（上行）/ access（接入）/ ''（看不出）。

    ⚠️ 关键区分（现网实测）：CX 上**电话口也是 trunk**——
        `vlan trunk native 16 / vlan trunk allowed 8,16` 是"语音 VLAN + 数据 VLAN"，
        不是上行口。全网 `vlan trunk allowed all` 仅 50 处（真干道），
        而 `allowed <列举>` 有 214 处（绝大多数是电话口）。
    所以**只有 `allowed all` 才算上行信号**；列举形式保持中性，交给
    邻居/生成树/LAG/描述去判断——宁可判不出来，也不要把电话口当上行口报出去。
    """
    texts = [b["text"] for b in block.get("body", [])]
    if any(re.match(r"^(vlan trunk allowed all|switchport mode trunk)\b", t, re.I)
           for t in texts):
        return "trunk"
    if any(re.match(r"^(vlan access \S|switchport access vlan|switchport mode access)", t, re.I)
           for t in texts):
        return "access"
    return ""


def infer_port_role(port: str, *, stp_role: str = "", neighbor_type: str = "",
                    in_lag: bool = False, in_uplink_list: bool = False,
                    description: str = "", config_hint: str = "") -> PortRole:
    """按信号**优先级分层**推断端口角色：取最高一层有信号的结论。

    为什么分层而不是"信号投票"：不同证据的强度差着量级。对端 CDP 报出的是
    一台 SD-WAN 路由器，这是硬证据；而"配置里写了 vlan access"只是形态提示——
    那台 SD-WAN 的 LAN 口本来就落在某个 access VLAN 上。用弱信号去推翻强证据，
    会把真实的上行口降级成"拿不准"，反而制造噪声。
    """
    nt = (neighbor_type or "").lower()
    reasons: list[str] = []

    # 第一层：生成树根端口 / 对端是基础设施 —— 硬证据
    if stp_role == "root":
        reasons.append("生成树根端口（朝向上游）")
    if nt in UPLINK_NEIGHBORS:
        reasons.append(f"对端是 {nt}（基础设施）")
    if reasons:
        return PortRole(port, "uplink", "high", reasons)

    # 第二层：对端是终端
    if nt in ACCESS_NEIGHBORS:
        return PortRole(port, "access", "medium", [f"对端是 {nt}（终端）"])

    # 第三层：LAG 成员 / 设备档案的上行口清单 / 配置形态
    if in_lag:
        reasons.append("是 LAG 成员")
    if in_uplink_list:
        reasons.append("在设备档案的上行口清单里")
    if reasons:
        return PortRole(port, "uplink", "medium", reasons)
    if config_hint == "access":
        return PortRole(port, "access", "medium", ["配置为接入口（vlan access）"])
    if config_hint == "trunk":
        return PortRole(port, "uplink", "medium", ["配置为干道（vlan trunk allowed all）"])

    # 第四层：描述关键词 —— 只作佐证，置信度最低
    if description and UPLINK_DESC.search(description):
        return PortRole(port, "uplink", "low", [f"描述含上行关键词（{description}）"])
    if description and ACCESS_DESC.search(description):
        return PortRole(port, "access", "low", [f"描述含终端关键词（{description}）"])

    return PortRole(port, "unknown", "low", [])


def build_port_roles(dev: Device, ctx: PortContext | None = None) -> dict[str, PortRole]:
    """为配置里每个接口块推断角色。键为归一化端口名（与邻居/STP 表口径一致）。"""
    from utils.port_names import normalize_port_name

    ctx = ctx or PortContext()
    out: dict[str, PortRole] = {}
    for blk in dev.if_blocks:
        m = re.match(r"^interface\s+(\S+)$", blk["header"])
        if not m:
            continue
        raw_name = m.group(1)
        port = normalize_port_name(raw_name)
        desc = ""
        for b in blk["body"]:
            m2 = re.match(r"^description\s+(.+)$", b["text"], re.I)
            if m2:
                desc = m2.group(1).strip()
                break
        out[port] = infer_port_role(
            port,
            stp_role=ctx.stp_roles.get(port, ""),
            neighbor_type=ctx.neighbor_types.get(port, ""),
            in_lag=port in ctx.lag_members,
            in_uplink_list=port in ctx.uplink_ports,
            description=desc,
            config_hint=_config_hint(blk),
        )
    return out
