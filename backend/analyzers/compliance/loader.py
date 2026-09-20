"""规则库加载与校验。

规则库布局（config/audit/）：
    _scopes.yaml           共用段：meta / sites / naming / vlans（唯一一份，避免站点表漂移）
    company-standard.yaml  公司总部要求（CFG-Aruba / CFG-CISCO）
    vendor-baseline.yaml   厂商加固建议
    org-convention.yaml    组织惯例（我们自己的使用习惯）
    _exceptions.yaml       例外登记表（已批准的偏离；可选文件）

合并顺序固定（company → vendor → org），每条规则注入 source_file（决定保存时写回哪个文件）。
校验一次性收集全部问题再抛出——规则编辑页需要一次看到所有错误，而不是改一个报一个。

例外登记表**不参与 ruleset_hash**（登记例外不算"标准变了"，趋势里两者分开判断），
有独立的 exceptions_hash。例外的校验同样从严：rule_id 拼错、站点码写错都会让豁免
静默失效（审计照报，没人发现登记没生效），所以必须在加载期拦住。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path

import yaml

from .checks import CHECKS, LEVEL_ORDER

SCOPES_FILE = "_scopes.yaml"
EXCEPTIONS_FILE = "_exceptions.yaml"
RULE_FILES = ["company-standard.yaml", "vendor-baseline.yaml", "org-convention.yaml"]
PLATFORMS = {"all", "cx", "cisco"}
SEVERITIES = {"shall", "should", "vendor", "convention"}
SCOPE_TYPES = {"device", "site", "all"}
EXC_ID_RE = re.compile(r"^exc-\d{3,}$")

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "config" / "audit"

# 需要 params.pattern 的判定器
PATTERN_CHECKS = {"absent_regex", "present_flag", "present_regex", "enable_secret_type",
                  "min_count"}

_cache: dict[str, dict] = {}


class RuleError(ValueError):
    """规则库校验失败，message 为逐行问题清单。"""


def clear_cache() -> None:
    _cache.clear()


def _read(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _validate_command_set(rid: str, p: dict) -> list[str]:
    """组合判定器的 params 校验 —— 报错要指到具体缺哪个字段，规则编辑页直接展示。"""
    errs: list[str] = []
    mode = p.get("mode")
    if mode not in ("all_of", "requires", "conflict"):
        return [f"{rid}: command_set 的 mode 必须是 all_of / requires / conflict，当前 {mode!r}"]

    def need_item(item, where: str) -> None:
        if not isinstance(item, dict) or not item.get("pattern"):
            errs.append(f"{rid}: {where} 的每一项都需要 pattern（可带 label）")

    if mode == "all_of":
        items = p.get("items") or []
        if not items:
            errs.append(f"{rid}: command_set(all_of) 需要 params.items（至少一项）")
        for it in items:
            need_item(it, "params.items")
    else:
        if not (p.get("trigger") or {}).get("pattern"):
            errs.append(f"{rid}: command_set({mode}) 需要 params.trigger.pattern")
        if mode == "requires":
            entries = p.get("required") or []
            if not entries:
                errs.append(f"{rid}: command_set(requires) 需要 params.required（至少一项）")
            for it in entries:
                need_item(it, "params.required")
        else:  # conflict：要么给 forbidden（同处不该共存），要么给 when_role（不该出现在该角色的端口上）
            entries = p.get("forbidden") or []
            when_role = p.get("when_role")
            if not entries and not when_role:
                errs.append(f"{rid}: command_set(conflict) 需要 params.forbidden "
                            f"或 params.when_role 之一")
            for it in entries:
                need_item(it, "params.forbidden")
            if when_role and when_role not in ("uplink", "access", "unknown"):
                errs.append(f"{rid}: params.when_role 只能是 uplink / access / unknown")
            wn = p.get("when_neighbor")
            if wn is not None and (not isinstance(wn, list) or not all(isinstance(x, str) for x in wn)):
                errs.append(f"{rid}: params.when_neighbor 必须是字符串列表"
                            f"（如 [switch] 或 [sdwan, router, firewall]）")

    if p.get("scope") not in (None, "block", "global"):
        errs.append(f"{rid}: params.scope 只能是 block 或 global")
    return errs


def _parse_date(value) -> datetime.date | None:
    """宽容解析 YYYY-MM-DD；解析不了返回 None（由调用方决定报什么错）。"""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def _validate_exceptions(std: dict, errors: list[str]) -> None:
    """例外登记表校验（与规则校验合并到同一次报错里）。"""
    known_rules = {r.get("id") for r in std.get("rules", [])}
    site_codes = set((std.get("naming") or {}).get("site_codes") or [])
    seen_ids: set[str] = set()
    seen_scopes: dict[tuple, str] = {}

    for idx, e in enumerate(std.get("exceptions") or [], start=1):
        where = f"{EXCEPTIONS_FILE} 第 {idx} 条"
        eid = str(e.get("id") or "")
        if not eid:
            errors.append(f"{where}: 缺少 id")
        else:
            where = eid
            if not EXC_ID_RE.match(eid):
                errors.append(f"{where}: id 需形如 exc-NNN（如 exc-001）")
            if eid in seen_ids:
                errors.append(f"{where}: 例外 id 重复")
            seen_ids.add(eid)

        rid = str(e.get("rule_id") or "")
        if not rid:
            errors.append(f"{where}: 缺少 rule_id")
        elif rid not in known_rules:
            errors.append(f"{where}: rule_id '{rid}' 不在规则库中（拼错会让豁免静默失效）")

        scope = e.get("scope") or {}
        stype, svalue = scope.get("type"), scope.get("value")
        if stype not in SCOPE_TYPES:
            errors.append(f"{where}: scope.type 必须是 device / site / all，当前 {stype!r}")
        elif stype == "all":
            if svalue:
                errors.append(f"{where}: scope.type=all 是全网例外，不应填 value")
        elif not svalue:
            errors.append(f"{where}: scope.type={stype} 需要 scope.value")
        elif stype == "site" and svalue not in site_codes:
            errors.append(f"{where}: scope.value '{svalue}' 不是已知站点码")
        if rid and stype in SCOPE_TYPES:
            key = (rid, stype, str(svalue or ""))
            if key in seen_scopes:
                errors.append(f"{where}: 与 {seen_scopes[key]} 重复登记同一 (rule_id, scope)："
                              f"{rid} @ {stype}={svalue or '全网'}")
            seen_scopes[key] = eid or where

        for field in ("reason", "approved_by"):
            if not str(e.get(field) or "").strip():
                errors.append(f"{where}: 缺少 {field}")
        approved_at = _parse_date(e.get("approved_at"))
        expires_at = _parse_date(e.get("expires_at"))
        for field, parsed in (("approved_at", approved_at), ("expires_at", expires_at)):
            if not e.get(field):
                errors.append(f"{where}: 缺少 {field}")
            elif parsed is None:
                errors.append(f"{where}: {field} 需为 YYYY-MM-DD 日期")
        if approved_at and expires_at and expires_at <= approved_at:
            errors.append(f"{where}: expires_at 必须晚于 approved_at（不允许当天就失效）")

        revoked = e.get("revoked")
        if revoked is not None:
            if not isinstance(revoked, dict):
                errors.append(f"{where}: revoked 需为 {{at, by, reason}}")
            else:
                for field in ("at", "by", "reason"):
                    if not revoked.get(field):
                        errors.append(f"{where}: revoked 缺少 {field}")
                if revoked.get("at") and _parse_date(revoked["at"]) is None:
                    errors.append(f"{where}: revoked.at 需为 YYYY-MM-DD 日期")


def _validate(std: dict, rule_files_used: list[str]) -> None:
    errors: list[str] = []
    sites = std.get("sites", {}) or {}

    def site_tokens_ok(tokens, where: str) -> None:
        for t in tokens or []:
            if t not in sites:
                # 字面站点码：必须是站点码列表里的值
                if t not in (std.get("naming", {}) or {}).get("site_codes", []):
                    errors.append(f"{where}: 站点令牌 '{t}' 既不是 sites 分组名也不是已知站点码")

    seen_ids: dict[str, str] = {}
    for rule in std.get("rules", []):
        rid = rule.get("id", "")
        src = rule.get("source_file", "?")
        if not rid:
            errors.append(f"{src}: 存在缺少 id 的规则")
            continue
        if rid in seen_ids:
            errors.append(f"规则 id 重复: {rid}（{seen_ids[rid]} 与 {src}）")
        seen_ids[rid] = src

        for f in ("title", "check", "level"):
            if not rule.get(f):
                errors.append(f"{rid}: 缺少必填字段 {f}")
        check = rule.get("check")
        if check and check not in CHECKS:
            errors.append(f"{rid}: 未知判定器 '{check}'（可用：{', '.join(sorted(CHECKS))}）")
        if check in PATTERN_CHECKS and not (rule.get("params") or {}).get("pattern"):
            errors.append(f"{rid}: 判定器 {check} 需要 params.pattern")
        if check == "command_set":
            errors.extend(_validate_command_set(rid, rule.get("params") or {}))
        level = rule.get("level")
        if level and level not in LEVEL_ORDER:
            errors.append(f"{rid}: 档位 '{level}' 不在 {LEVEL_ORDER}")
        sev = rule.get("severity")
        if sev and sev not in SEVERITIES:
            errors.append(f"{rid}: severity '{sev}' 不在 {sorted(SEVERITIES)}")
        if "enabled" in rule and not isinstance(rule["enabled"], bool):
            errors.append(f"{rid}: enabled 必须是 true / false")
        if "collective" in rule and not isinstance(rule["collective"], bool):
            errors.append(f"{rid}: collective 必须是 true / false"
                          f"（标记后：全量审计命中多台时折叠成一条网络级条目）")
        if rule.get("enabled") is False and not rule.get("superseded_by") \
                and not rule.get("disabled_reason"):
            errors.append(f"{rid}: 停用的规则要写明 superseded_by（被哪条高层规则取代）"
                          f"或 disabled_reason —— 否则以后没人知道为什么关掉它")
        ctrls = rule.get("controls")
        if ctrls is not None and (not isinstance(ctrls, list)
                                  or not all(isinstance(x, str) for x in ctrls)):
            errors.append(f"{rid}: controls 必须是字符串列表（NIST 控制编号，如 [AC-17, IA-2]）")
        for p in rule.get("platforms", ["all"]):
            if p not in PLATFORMS:
                errors.append(f"{rid}: 平台 '{p}' 不在 {sorted(PLATFORMS)}")
        site_tokens_ok(rule.get("only_sites"), f"{rid}.only_sites")
        site_tokens_ok(rule.get("exempt_sites"), f"{rid}.exempt_sites")

    _validate_exceptions(std, errors)

    for f in ("naming", "vlans"):
        if not std.get(f):
            errors.append(f"{SCOPES_FILE}: 缺少 {f} 段")
    if std.get("rules") is None:
        errors.append("规则文件未提供 rules 列表")
    if not rule_files_used:
        errors.append("未找到任何规则文件")

    if errors:
        raise RuleError("规则库校验未通过：\n  - " + "\n  - ".join(errors))


def load_standard(base_dir: Path | str | None = None, use_cache: bool = True) -> dict:
    """加载合并全部规则文件并校验。失败抛 RuleError（含完整问题清单）。"""
    base = Path(base_dir) if base_dir else DEFAULT_DIR
    key = str(base)
    if use_cache and key in _cache:
        return _cache[key]

    scopes = _read(base / SCOPES_FILE)
    std: dict = {
        "meta": scopes.get("meta", {}),
        "sites": scopes.get("sites", {}),
        "naming": scopes.get("naming", {}),
        "vlans": scopes.get("vlans", {}),
        "rules": [],
        "not_adopted": [],
        "exceptions": [],
        "source_dir": str(base),
    }

    used: list[str] = []
    for fname in RULE_FILES:
        path = base / fname
        if not path.exists():
            continue
        data = _read(path)
        used.append(fname)
        for rule in data.get("rules") or []:
            rule = dict(rule)
            rule["source_file"] = fname
            std["rules"].append(rule)
        for item in data.get("not_adopted") or []:
            item = dict(item)
            item["source_file"] = fname
            std["not_adopted"].append(item)

    # 例外登记表（可选文件）：单独一份，不参与 ruleset_hash
    exceptions_path = base / EXCEPTIONS_FILE
    if exceptions_path.exists():
        for e in _read(exceptions_path).get("exceptions") or []:
            e = dict(e)
            e["source_file"] = EXCEPTIONS_FILE
            std["exceptions"].append(e)

    _validate(std, used)
    std["rule_files"] = used
    if use_cache:
        _cache[key] = std
    return std


def ruleset_hash(std: dict) -> str:
    """规则集指纹 —— 审计结果入库时随结果保存，用于判断"标准是否变过"。"""
    payload = {
        "sites": std.get("sites", {}),
        "naming": std.get("naming", {}),
        "vlans": std.get("vlans", {}),
        "rules": sorted(
            ({"id": r.get("id"), "check": r.get("check"), "params": r.get("params"),
              "level": r.get("level"), "platforms": r.get("platforms"),
              "only_sites": r.get("only_sites"), "exempt_sites": r.get("exempt_sites"),
              "severity": r.get("severity")} for r in std.get("rules", [])),
            key=lambda x: x["id"] or "",
        ),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def exceptions_hash(std: dict) -> str:
    """例外集指纹 —— **独立于 ruleset_hash**。

    为什么必须分开：登记/撤销一条例外不应该让历史审计看起来"标准变过"。
    两者各自变化时，趋势分析才能说清"是标准变了，还是豁免变了"。
    与 ruleset_hash 同规格：按 id 排序后取内容（条目顺序不敏感）。
    """
    payload = sorted(
        ({"id": e.get("id"), "rule_id": e.get("rule_id"), "scope": e.get("scope"),
          "reason": e.get("reason"), "compensating_control": e.get("compensating_control"),
          "approved_by": e.get("approved_by"), "approved_at": e.get("approved_at"),
          "expires_at": e.get("expires_at"), "revoked": e.get("revoked")}
         for e in std.get("exceptions") or []),
        key=lambda x: x["id"] or "",
    )
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
