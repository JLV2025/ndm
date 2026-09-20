"""规则库加载与校验。

规则库布局（config/audit/）：
    _scopes.yaml           共用段：meta / sites / naming / vlans（唯一一份，避免站点表漂移）
    company-standard.yaml  公司总部要求（CFG-Aruba / CFG-CISCO）
    vendor-baseline.yaml   厂商加固建议
    org-convention.yaml    组织惯例（我们自己的使用习惯）

合并顺序固定（company → vendor → org），每条规则注入 source_file（决定保存时写回哪个文件）。
校验一次性收集全部问题再抛出——规则编辑页需要一次看到所有错误，而不是改一个报一个。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .checks import CHECKS, LEVEL_ORDER

SCOPES_FILE = "_scopes.yaml"
RULE_FILES = ["company-standard.yaml", "vendor-baseline.yaml", "org-convention.yaml"]
PLATFORMS = {"all", "cx", "cisco"}
SEVERITIES = {"shall", "should", "vendor", "convention"}

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "config" / "audit"

# 需要 params.pattern 的判定器
PATTERN_CHECKS = {"absent_regex", "present_flag", "present_regex", "enable_secret_type"}

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
        key = "required" if mode == "requires" else "forbidden"
        entries = p.get(key) or []
        if not entries:
            errs.append(f"{rid}: command_set({mode}) 需要 params.{key}（至少一项）")
        for it in entries:
            need_item(it, f"params.{key}")

    if p.get("scope") not in (None, "block", "global"):
        errs.append(f"{rid}: params.scope 只能是 block 或 global")
    return errs


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
        for p in rule.get("platforms", ["all"]):
            if p not in PLATFORMS:
                errors.append(f"{rid}: 平台 '{p}' 不在 {sorted(PLATFORMS)}")
        site_tokens_ok(rule.get("only_sites"), f"{rid}.only_sites")
        site_tokens_ok(rule.get("exempt_sites"), f"{rid}.exempt_sites")

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
