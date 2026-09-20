"""内置判定器 —— 规则通过 `check` 名 + `params` 引用这里面的函数。

移植自 allright/netstd 的 engine.py 判定器部分，改造点：
  - make_finding 增加 lines / locatable（前端标红的契约：只认行号，禁止文本匹配）
  - 去掉证据截断（原 check_vlan1_in_use 的 ev[:14] / ev[:8]）
  - line:0 改为 line:None（原命名类判定器用 0 表示"无行号"，与真实行号 1 起冲突）
  - check_enable_secret_type 由 params.pattern 驱动（原实现硬编码 `^enable secret 5`）
"""
from __future__ import annotations

import datetime
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


def make_finding(rule: dict, evidence: list[dict], current: str | None = None,
                 **extra) -> dict:
    """构造一条审计发现。

    lines：证据涉及的配置行号（去重升序，剔除 None）。前端**只按行号标红**——
    实测 35/36 台配置带行尾空格，"拿证据文本回配置里搜"必然错位。
    locatable：是否可定位到行。命名类、全局策略类判定没有具体行，为 False，
    此时前端禁用「定位到行」按钮。
    extra：组合判定器补充的字段（check_kind / missing / satisfied / detail / expect）。
    """
    lines = sorted({e["line"] for e in evidence if e.get("line")})
    finding = {
        "rule_id": rule["id"],
        "title": rule["title"],
        "level": rule.get("level", "改进建议"),
        "source": rule.get("source", ""),
        "severity": rule.get("severity", ""),
        "controls": rule.get("controls", []),
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
    finding.update(extra)
    return finding


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


def check_min_count(dev: Device, rule: dict, std: dict) -> list[dict]:
    """命中条数少于阈值即出建议。

    用于"至少两台 XXX"这类要求（总部基线第 5/9/10 章都要求 ≥2：AAA 服务器、
    NTP 服务器、syslog 收集器）——简单正则表达不了"几条"。
    """
    p = rule.get("params", {})
    ev = matches(dev, p["pattern"])
    want = int(p.get("min", 2))
    if len(ev) >= want:
        return []
    return [make_finding(rule, ev, "(未配置)" if not ev else None,
                         detail=f"实际 {len(ev)} 条，要求至少 {want} 条"
                                + (f"：{p['label']}" if p.get("label") else ""))]


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


def check_config_drift(dev: Device, rule: dict, std: dict) -> list[dict]:
    """运行配置与启动配置不一致 → 有改动没保存，设备重启会丢。

    与采集后告警（anomaly_detector 的 config_drift）**共用同一套归一化**
    （utils/config_diff），否则会出现「告警说没问题、审计说有差异」的自相矛盾。

    没采到 startup 就不判 —— 绝不能因为"没采到"报一条假问题。
    """
    if not dev.startup_config:
        return []
    from utils.config_diff import diff_configs
    d = diff_configs(dev.text, dev.startup_config)
    if not d["differ"]:
        return []

    ev = [{"line": x["line"], "text": x["text"]} for x in d["only_running"][:10]]
    if not ev:      # 只有 startup 侧多出来的行（运行配置被删了内容）
        ev = [{"line": None, "text": "（运行配置缺少了启动配置中已有的内容）"}]

    detail = f"有 {d.get('total_running_only', 0)} 行改动尚未保存"
    if d.get("total_startup_only"):
        detail += f"；另有 {d['total_startup_only']} 行只在启动配置里"
    if d.get("truncated"):
        detail += "（仅列出前 10 行）"

    return [make_finding(rule, ev, **{
        "check_kind": "config_drift",
        "detail": detail,
        "unsaved_lines": d.get("total_running_only", 0),
    })]


# ---------------------------------------------------------------- 生命周期判定器
#
# 数据来自 eol_models / device_lifecycle 两张表（source.load_lifecycle 装到 dev.lifecycle）。
# 这是**资产事实**而不是配置文本，所以判定器不出配置行号（locatable=False）。
# 档位语义：已公告 EoL / 保修过期或临近 → 风险提示（时效风险，不是配置错误）；
# 信息未登记或登记陈旧 → 需人工判断（"待查"，由 runner 折叠成一条网络级条目）。

def _lifecycle(dev) -> dict:
    return getattr(dev, "lifecycle", None) or {}


def _warranty_rows(life: dict) -> list[dict]:
    """保修行 = 当前采集到的序列号 + **登记了但当前采集不到的**（extra_rows）。

    后者不能丢：成员换件、采集缺了序列号时，登记过的保修期仍应参与判定。
    """
    return list(life.get("serials") or []) + list(life.get("extra_rows") or [])


def _fmt_date(value) -> str:
    return str(value or "")[:10]


def check_eol_announced(dev: Device, rule: dict, std: dict) -> list[dict]:
    """型号已公布停止销售 / 停止支持。"""
    hits = [e for e in _lifecycle(dev).get("model_eol") or []
            if e.get("end_of_sale") or e.get("end_of_support")]
    if not hits:
        return []
    parts = []
    for e in hits:
        seg = f"型号 {e.get('model', '')}"
        if e.get("end_of_sale"):
            seg += f"：停止销售 {_fmt_date(e['end_of_sale'])}"
        if e.get("end_of_support"):
            seg += f"，停止支持 {_fmt_date(e['end_of_support'])}"
        if e.get("bulletin"):
            seg += f"（公告 {e['bulletin']}）"
        parts.append(seg)
    return [make_finding(rule, [], "\n".join(parts))]


def check_warranty_expired(dev: Device, rule: dict, std: dict) -> list[dict]:
    """保修已过期，或 warn_days 天内到期（该续保 / 该报预算了）。"""
    params = rule.get("params") or {}
    try:
        warn_days = int(params.get("warn_days", 90))
    except (TypeError, ValueError):
        warn_days = 90
    today = datetime.date.today()
    parts = []
    for s in _warranty_rows(_lifecycle(dev)):
        end = s.get("warranty_end")
        if not end:
            continue
        try:
            d = datetime.date.fromisoformat(str(end)[:10])
        except ValueError:
            continue                     # 坏日期由 DAL 挡住，这里再兜一层
        left = (d - today).days
        if left < 0:
            parts.append(f"{s.get('serial', '')}：保修已于 {_fmt_date(end)} 过期（{-left} 天前）")
        elif left <= warn_days:
            parts.append(f"{s.get('serial', '')}：保修将于 {_fmt_date(end)} 到期（剩余 {left} 天）")
    return [make_finding(rule, [], "\n".join(parts))] if parts else []


def check_lifecycle_unknown(dev: Device, rule: dict, std: dict) -> list[dict]:
    """生命周期信息未登记 / 登记已陈旧 —— "待查"，需人工去核实。

    判定看的是"有没有**可用**的核实信息"，而不是"有几条记录"：
      · 型号 EoL 与保修期都缺 → 待查（这台的时效风险完全未知）
      · 只缺一项 → 待查（列出缺的那项）
      · 都有但最近核实时间超过 stale_days → 待查（两年前抄的日期不能一直冒充"已确认"）
    """
    params = rule.get("params") or {}
    try:
        stale_days = int(params.get("stale_days", 365))
    except (TypeError, ValueError):
        stale_days = 365

    life = _lifecycle(dev)
    eol_rows = life.get("model_eol") or []
    serials = _warranty_rows(life)
    has_eol = any(e.get("end_of_sale") or e.get("end_of_support") for e in eol_rows)
    has_warranty = any(s.get("warranty_end") for s in serials)

    missing = [name for name, ok in (("型号 EoL", has_eol), ("保修期", has_warranty)) if not ok]
    if missing:
        detail = ("尚未登记：" + "、".join(missing)
                  + "。请在设备详情页「生命周期」中登记（Aruba 手工；Cisco 配好 API 凭据后可自动刷新）")
        if not life.get("models"):
            detail += "；当前连型号都没采到"
        return [make_finding(rule, [], detail)]

    # 信息齐全 → 只在陈旧时提示复核
    stamps = [s.get("verified_at") for s in serials if s.get("verified_at")]
    stamps += [e.get("fetched_at") for e in eol_rows if e.get("fetched_at")]
    newest = max((_fmt_date(x) for x in stamps), default="")
    if not newest:
        return [make_finding(rule, [], "生命周期信息没有核实时间，无法判断是否过期，请复核后重新登记")]
    try:
        age = (datetime.date.today() - datetime.date.fromisoformat(newest)).days
    except ValueError:
        age = stale_days + 1
    if age > stale_days:
        return [make_finding(rule, [], f"生命周期信息最近核实于 {newest}（{age} 天前），"
                                       f"已超过 {stale_days} 天 —— 请复核保修与 EoL 状态")]
    return []


# ---------------------------------------------------------------- 组合判定器
#
# 一条规则表达"配套关系"，而不是"某条命令在不在"——这是审计从「逐条查命令」
# 升级到「查配套」的关键。三种语义共用一个作用域求值：
#   all_of   命令组必须齐备，缺项点名
#   requires 配了 A 就必须有 B（如配了 DAI 就必须有 DHCP snooping）
#   conflict 有 A 就不该在**同一处**出现 B（默认按接口块判定）
# params.scope = block 时按接口块逐个判定，否则整份配置当一个作用域。

def _eval_scope(dev: Device, params: dict) -> list[dict]:
    if params.get("scope") == "block":
        return [{"header": b["header"], "line": b["line"], "items": b["body"]}
                for b in dev.if_blocks]
    return [{"header": None, "line": None,
             "items": [{"text": t, "line": i} for i, t in enumerate(dev.lines, start=1)]}]


def _hit(items: list[dict], pattern: str) -> list[dict]:
    rx = compile_re(pattern)
    return [it for it in items if rx.search(it["text"])]


def _command_set_all_of(dev: Device, rule: dict, p: dict) -> list[dict]:
    items = p.get("items") or []
    group = p.get("group", "命令组")
    out = []
    for sc in _eval_scope(dev, p):
        satisfied, missing, ev = [], [], []
        for it in items:
            hits = _hit(sc["items"], it["pattern"])
            if hits:
                satisfied.append(it.get("label", it["pattern"]))
                ev.extend(hits[:1])
            else:
                missing.append(it.get("label", it["pattern"]))
        if missing:
            out.append(make_finding(rule, ev,
                                    check_kind="all_of", group=group,
                                    satisfied=satisfied, missing=missing,
                                    detail=f"{group}：已配 {len(satisfied)}/{len(items)}，"
                                           f"缺 {'、'.join(missing)}"))
    return out


def _command_set_requires(dev: Device, rule: dict, p: dict) -> list[dict]:
    trig = p.get("trigger") or {}
    reqs = p.get("required") or []
    out = []
    for sc in _eval_scope(dev, p):
        tev = _hit(sc["items"], trig["pattern"])
        if not tev:
            continue
        satisfied, missing = [], []
        for r in reqs:
            (satisfied if _hit(sc["items"], r["pattern"]) else missing).append(
                r.get("label", r["pattern"]))
        if not missing:
            continue
        out.append(make_finding(rule, tev[:1],
                                check_kind="requires",
                                trigger=trig.get("label", ""),
                                satisfied=satisfied, missing=missing,
                                detail=f"配了 {trig.get('label','')}，但缺少配套："
                                       f"{'、'.join(missing)}"))
    return out


def _scope_port(sc: dict) -> str:
    """从接口块表头取出归一化端口名；全局作用域返回空串。"""
    m = re.match(r"^interface\s+(\S+)$", sc.get("header") or "")
    if not m:
        return ""
    from utils.port_names import normalize_port_name
    return normalize_port_name(m.group(1))


def _command_set_conflict(dev: Device, rule: dict, p: dict) -> list[dict]:
    trig = p.get("trigger") or {}
    forb = p.get("forbidden") or []
    when_role = p.get("when_role")
    when_neighbor = [x.lower() for x in (p.get("when_neighbor") or [])]
    out: list[dict] = []
    undetermined: list[str] = []

    for sc in _eval_scope(dev, p):
        tev = _hit(sc["items"], trig["pattern"])
        if not tev:
            continue

        # 按端口角色判定：角色来自生成树/邻居/LAG/描述/配置形态，
        # **只在 high 置信时下结论**——低置信宁可说"拿不准"，也不瞎报警。
        if when_role:
            port = _scope_port(sc)
            pr = dev.port_roles.get(port) if port else None
            # 判断不出角色、或已明确是另一种角色 → 不提示。
            # 完全判断不出的端口不列进"拿不准"：没有任何线索指向上行口，
            # 把它们泼进报告只会让电话口淹掉真问题。
            if pr is None or pr.role != when_role:
                continue
            # 按对端类型过滤：区分「对端是交换机」（会发 BPDU，真风险）
            # 与「对端是三层设备」（不发 BPDU，无害但无意义）——两者档位不同
            if when_neighbor and pr.peer_class not in when_neighbor:
                continue
            if not pr.is_confident:
                undetermined.append(f"{port}（疑似上行，置信 {pr.confidence}）")
                continue
            out.append(make_finding(rule, tev[:1],
                                    check_kind="conflict",
                                    trigger=trig.get("label", ""),
                                    conflict=[when_role],
                                    detail=f"{port} 是上行口（{'；'.join(pr.reasons)}），"
                                           f"{trig.get('label','')} 不应配在这里"))
            continue
            out.append(make_finding(rule, tev[:1],
                                    check_kind="conflict",
                                    trigger=trig.get("label", ""),
                                    conflict=[when_role],
                                    detail=f"{port} 是上行口（{'；'.join(pr.reasons)}），"
                                           f"{trig.get('label','')} 不应配在这里"))
            continue

        # 模式二：同处不应同时出现 A 与 B
        bad = []
        for f in forb:
            for hit in _hit(sc["items"], f["pattern"]):
                bad.append((f.get("label", f["pattern"]), hit))
        if not bad:
            continue
        ev = ([{"line": sc["line"], "text": sc["header"]}] if sc["header"] else [])
        ev += tev[:1] + [h for _, h in bad[:4]]
        labels = sorted({lbl for lbl, _ in bad})
        out.append(make_finding(rule, ev,
                                check_kind="conflict",
                                trigger=trig.get("label", ""),
                                conflict=labels,
                                detail=f"{trig.get('label','')} 与 {'、'.join(labels)} "
                                       f"不应同时出现"))

    # 有端口配了命令、但角色判断不出高置信结论 → 聚合成一条「需人工判断」，
    # 而不是每个端口报一条。宁可讲清"我拿不准哪些口"，也不制造噪声。
    if undetermined and not out:
        out.append(make_finding(rule, [],
                                level="需人工判断",
                                check_kind="conflict",
                                trigger=trig.get("label", ""),
                                undetermined=undetermined,
                                current=f"（{len(undetermined)} 个端口配了 "
                                        f"{trig.get('label','')}，但端口角色无法确定）",
                                detail=f"以下端口配了 {trig.get('label','')}，"
                                       "但缺少生成树/邻居佐证、判断不出是否为上行口，"
                                       "需人工确认："
                                       + "、".join(undetermined[:10])
                                       + ("…" if len(undetermined) > 10 else "")))
    return out


def check_command_set(dev: Device, rule: dict, std: dict) -> list[dict]:
    mode = (rule.get("params") or {}).get("mode")
    if mode == "all_of":
        return _command_set_all_of(dev, rule, rule["params"])
    if mode == "requires":
        return _command_set_requires(dev, rule, rule["params"])
    if mode == "conflict":
        return _command_set_conflict(dev, rule, rule["params"])
    return []


CHECKS: dict[str, callable] = {
    "command_set": check_command_set,
    "absent_regex": check_absent_regex,
    "present_flag": check_present_flag,
    "present_regex": check_present_regex,
    "enable_secret_type": check_enable_secret_type,
    "min_count": check_min_count,
    "vty_transport": check_vty_transport,
    "vlan_name_pure": check_vlan_name_pure,
    "vlan_id_standard": check_vlan_id_standard,
    "addr_third_octet": check_addr_third_octet,
    "vlan1_in_use": check_vlan1_in_use,
    "device_name_format": check_device_name_format,
    "hostname_match": check_hostname_match,
    "vsf_split_detect": check_vsf_split_detect,
    "config_drift": check_config_drift,
    "eol_announced": check_eol_announced,
    "warranty_expired": check_warranty_expired,
    "lifecycle_unknown": check_lifecycle_unknown,
}
