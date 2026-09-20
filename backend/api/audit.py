"""配置审计 API 路由。

设计要点（见 docs/superpowers/plans/2026-09-18-compliance-audit.md §三 C）：
  - 单台即时审计**不落库**，返回完整 envelope（含**配置原文**）
  - 为什么必须带 config 原文：前端标红**只认行号**，而行号只对同一份文本有意义。
    实测磁盘上的 running-config.raw 是 CRLF、库里的全文是 LF，两者行号对不上 ——
    所以面板必须渲染接口返回的这一份，不能用 dataApi 读盘。
  - "配置不可用"（采集失败 / 全文已被保留策略清理 / 从未采集）**不是错误**，
    照样返回 200 + usable=false + 原因，让界面能说清"为什么这台没结果"。
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter()

from analyzers.compliance import engine, loader, runner, source  # noqa: E402
from storage.database import get_connection as _get_db  # noqa: E402


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _envelope(item: source.AuditInput, std: dict) -> dict:
    """装配单台审计的完整返回体。"""
    snap = item.snapshot
    result = {
        "device": snap.name,
        "location": snap.location,
        "platform": snap.platform,
        "model": snap.model,
        "week": snap.week,
        "collected_at": snap.collected_at,
        "config": snap.config,
        "config_hash": snap.config_hash,
        "usable": snap.usable,
        "reason": snap.reason,
        "ruleset_hash": loader.ruleset_hash(std),
        "generated_at": _now(),
        "findings": [],
        "counts": {},
        "port_roles": {},
        "exempt_count": 0,
    }
    if not snap.usable:
        return result
    analysis = engine.analyze(snap.name, snap.config, std, site=snap.location,
                              port_context=item.port_context,
                              startup_config=snap.startup_config)
    result.update({
        "findings": analysis["findings"],
        "counts": analysis["counts"],
        "port_roles": analysis["port_roles"],
        "exempt_count": analysis["exempt_count"],
        "device_info": analysis["device"],
    })
    return result


@router.get("/api/audit/ruleset")
async def get_ruleset():
    """规则库概览：供标准页展示与筛选。含**已停用**的规则（要能重新启用）。"""
    std = loader.load_standard(use_cache=False)
    rules = []
    for r in std["rules"]:
        rules.append({
            "id": r["id"],
            "title": r.get("title", ""),
            "level": r.get("level", ""),
            "source": r.get("source", ""),
            "severity": r.get("severity", ""),
            "platforms": r.get("platforms", ["all"]),
            "controls": r.get("controls", []),
            "check": r.get("check", ""),
            "params": r.get("params", {}),
            "only_sites": r.get("only_sites", []),
            "exempt_sites": r.get("exempt_sites", []),
            "fix": r.get("fix", ""),
            "why": r.get("why", ""),
            "note": r.get("note", ""),
            "enabled": r.get("enabled", True) is not False,
            "superseded_by": r.get("superseded_by", ""),
            "disabled_reason": r.get("disabled_reason", ""),
            "source_file": r.get("source_file", ""),
        })
    return {
        "rules": rules,
        "rule_files": std.get("rule_files", []),
        "ruleset_hash": loader.ruleset_hash(std),
        "layer_priority": engine.LAYER_PRIORITY,
        "levels": engine.LEVEL_ORDER,
        "platforms": sorted(loader.PLATFORMS),
        "sites": std.get("sites", {}),
        "naming": std.get("naming", {}),
        "vlans": std.get("vlans", {}),
    }


@router.get("/api/audit/device/{name}")
async def audit_device(name: str, include_config: bool = True):
    """单台设备的即时审计（不落库）。"""
    std = loader.load_standard()
    item = source.load_audit_input(_get_db(), name)
    if item is None:
        raise HTTPException(status_code=404, detail=f"设备不存在：{name}")
    env = _envelope(item, std)
    if not include_config:
        env.pop("config", None)      # 大配置（百 KB）在只看结论时可省掉
    return env


# ---------------------------------------------------------------- 导出

def _render_md(env: dict) -> str:
    """服务端渲染 Markdown —— 前端拼会在 i18n / 排序两处与这里漂移。"""
    lines = [f"# 配置审计报告 —— {env['device']}", ""]
    lines.append(f"- 站点：{env['location']}　平台：{env['platform']}　型号：{env['model']}")
    lines.append(f"- 配置采集：{env['week']}　{env['collected_at']}")
    lines.append(f"- 配置指纹：`{env['config_hash']}`　规则集指纹：`{env['ruleset_hash']}`")
    lines.append(f"- 生成时间：{env['generated_at']}")
    lines.append("")
    if not env["usable"]:
        lines += [f"> ⚠️ 本次未能审计：{env['reason']}", ""]
        return "\n".join(lines)

    counts = {k: v for k, v in (env.get("counts") or {}).items() if v}
    lines += ["## 建议统计", ""]
    lines += [f"- {k}：{v} 条" for k, v in counts.items()] or ["- 未发现可改进项"]
    if env.get("exempt_count"):
        lines.append(f"- 已批准例外：{env['exempt_count']} 条（单列，不计入上方统计）")
    lines.append("")

    for level in engine.LEVEL_ORDER:
        items = [f for f in env["findings"] if f["level"] == level]
        if not items:
            continue
        lines += [f"## {level}（{len(items)} 条）", ""]
        for f in items:
            lines.append(f"### {f['title']}")
            lines.append("")
            lines.append(f"- 规则：`{f['rule_id']}`　来源：{f['source']}　"
                         f"适用：{f['platform']}")
            if f.get("exempt"):
                ex = f["exempt"]
                tag = "例外已过期" if ex.get("status") == "expired" else "已批准例外"
                lines.append(f"- **{tag}**：`{ex.get('exception_id', '')}`　"
                             f"批准人：{ex.get('approved_by', '')}　到期：{ex.get('expires_at', '')}")
            if f.get("controls"):
                lines.append(f"- 对应控制项：{', '.join(f['controls'])}")
            if f.get("detail"):
                lines.append(f"- 说明：{f['detail']}")
            if f.get("current"):
                lines += ["", "**现状**", "", "```text", f["current"], "```"]
            if f.get("fix"):
                lines += ["", "**建议**", "", "```text", f["fix"].rstrip(), "```"]
            if f.get("why"):
                lines += ["", f"> {f['why']}"]
            if f.get("note"):
                lines += ["", f"> 注意：{f['note']}"]
            lines.append("")
    lines += ["---", "", "本报告为**建议**，非强制整改项；档位只表示建议强度。"]
    return "\n".join(lines)


# ---------------------------------------------------------------- 全量审计入库

@router.post("/api/audit/run")
async def run_audit(trigger: str = "manual"):
    """全网审计并入库。

    实测 36 台约 0.7 秒，**同步返回即可**，不需要后台任务与进度条。
    不可用的设备（采集失败/全文已清理）照样计入 device_count，但单独列出原因 ——
    静默跳过会让人以为"这些都审过了、没问题"。
    """
    if trigger not in ("manual", "scheduled", "post_collect"):
        raise HTTPException(status_code=400,
                            detail="trigger 只能是 manual / scheduled / post_collect")
    # 实际执行在 analyzers/compliance/runner.py —— 采集后自动跑走同一实现
    return runner.run_full_audit(_get_db(), loader.load_standard(), trigger)


@router.get("/api/audit/runs")
async def list_runs(limit: int = 20):
    """审计历史（趋势的基座）。"""
    db = _get_db()
    db.row_factory = __import__("sqlite3").Row
    rows = db.execute(
        "SELECT id, started_at, finished_at, trigger, ruleset_hash, device_count, "
        "finding_count, status FROM audit_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"runs": [dict(r) for r in rows]}


@router.get("/api/audit/runs/{run_id}")
async def get_run(run_id: int, level: str | None = None, device: str | None = None):
    """某次审计的明细，可按档位 / 设备过滤。"""
    db = _get_db()
    db.row_factory = __import__("sqlite3").Row
    run = db.execute("SELECT * FROM audit_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise HTTPException(status_code=404, detail=f"审计记录不存在：{run_id}")
    sql = ("SELECT device_name, rule_id, level, source, severity, title, detail, lines_json, "
           "controls_json, exempt_by, exempt_json FROM audit_findings WHERE run_id = ?")
    params: list = [run_id]
    if level:
        sql += " AND level = ?"
        params.append(level)
    if device:
        sql += " AND device_name = ?"
        params.append(device)
    sql += " ORDER BY device_name, level, rule_id"
    findings = []
    for r in db.execute(sql, params):
        d = dict(r)
        d["lines"] = json.loads(d.pop("lines_json") or "[]")
        d["controls"] = json.loads(d.pop("controls_json") or "[]")
        d["exempt"] = json.loads(d.pop("exempt_json") or "null")
        findings.append(d)
    return {"run": dict(run), "findings": findings}


# ---------------------------------------------------------------- 规则编辑
#
# 写入必须：乐观锁 → 备份 → 原子替换（临时文件 + os.replace）→ 校验失败回滚 → 清缓存。
# 用 ruamel.yaml 做往返编辑（**保留注释**）——规则文件里的注释记录着每条规则"为什么存在"，
# 那是这个库最值钱的部分，不能用 PyYAML 回写丢掉。

BACKUP_DIRNAME = ".backups"
BACKUP_KEEP = 10


class RuleUpdate(BaseModel):
    """规则可编辑字段。只开放这几个 —— check / params 改动风险高，走文件编辑+评审。"""
    enabled: bool | None = None
    level: str | None = None
    title: str | None = None
    fix: str | None = None
    why: str | None = None
    note: str | None = None
    superseded_by: str | None = None
    disabled_reason: str | None = None
    base_hash: str | None = None      # 乐观锁：前端带上打开时的文件指纹


def _file_hash(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _find_rule_in_file(path: Path, rule_id: str):
    """用 ruamel 载入（保留注释），返回 (data, rule_dict)。"""
    with open(path, "r", encoding="utf-8") as fh:
        data = _yaml_rt().load(fh)
    for r in data.get("rules") or []:
        if r.get("id") == rule_id:
            return data, r
    return None, None


def _yaml_rt():
    """规则文件的往返读写器（保留注释）。

    ⚠️ 三个参数必须设，否则 ruamel 会**把整个文件重新排版**——
    改一个字段看起来像全文重写，git 历史直接报废：
      · indent(sequence=4, offset=2)：让列表项写成 ``  - id:``（与现有文件一致）
      · width 调大：**禁止折行**，否则长 why/note 行会被拆成多行
      · preserve_quotes：保留 '...' 引号写法
    """
    from ruamel.yaml import YAML
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _atomic_dump(data, path: Path) -> None:
    """原子写入：同目录临时文件 + os.replace。Windows 上目标被占用会 PermissionError，需重试。"""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        _yaml_rt().dump(data, fh)
    last_err = None
    for _ in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:      # 杀毒/编辑器/OneDrive 短暂占用
            last_err = e
            time.sleep(0.2)
    tmp.unlink(missing_ok=True)
    raise HTTPException(status_code=503, detail=f"文件被占用，写入失败：{last_err}")


def _backup(path: Path) -> Path:
    bdir = path.parent / BACKUP_DIRNAME
    bdir.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = bdir / f"{path.name}.{stamp}"
    shutil.copy2(path, dest)
    old = sorted(bdir.glob(f"{path.name}.*"))
    for f in old[:-BACKUP_KEEP]:          # 只留最近几份，避免堆积
        f.unlink(missing_ok=True)
    return dest


@router.put("/api/audit/standards/rule/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate):
    """编辑一条规则并写回它的来源文件。"""
    std = loader.load_standard(use_cache=False)
    rule = next((r for r in std["rules"] if r["id"] == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"规则不存在：{rule_id}")
    path = Path(std["source_dir"]) / rule["source_file"]
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"来源文件不存在：{path}")

    if body.base_hash and _file_hash(path) != body.base_hash:
        raise HTTPException(status_code=409,
                            detail="规则文件已被其他人修改，请刷新后重试（乐观锁拦截）")

    data, target = _find_rule_in_file(path, rule_id)
    if target is None:
        raise HTTPException(status_code=500, detail=f"在 {path.name} 中找不到规则 {rule_id}")

    changes = body.model_dump(exclude_none=True, exclude={"base_hash"})
    if not changes:
        raise HTTPException(status_code=400, detail="没有需要修改的字段")
    for key, value in changes.items():
        target[key] = value
    # 停用必须留原因（loader 也会校验，这里提前给出可读错误）
    if target.get("enabled") is False and not (target.get("superseded_by")
                                               or target.get("disabled_reason")):
        raise HTTPException(status_code=400,
                            detail="停用规则必须填写 superseded_by（被哪条高层规则取代）"
                                   "或 disabled_reason，否则以后没人知道为什么关掉它")

    backup = _backup(path)
    _atomic_dump(data, path)
    loader.clear_cache()
    try:
        loader.load_standard(use_cache=False)
    except loader.RuleError as e:         # 校验失败 → 回滚
        shutil.copy2(backup, path)
        loader.clear_cache()
        raise HTTPException(status_code=400, detail=f"规则库校验未通过，已回滚：\n{e}")
    return {"ok": True, "rule_id": rule_id, "changed": list(changes),
            "file": rule["source_file"], "backup": backup.name}


# ---------------------------------------------------------------- 例外登记
#
# 与规则编辑走同一条写入链（乐观锁 → 备份 → 原子替换 → 校验失败回滚 → 清缓存）。
# 文件里只存**事实**（批准日期、到期日、撤销块），status 一律由 engine.exception_status
# 推导 —— 存了字段就会和日期打架。
# 不提供物理删除：撤销即软删除（写 revoked 块），历史审计里的 exempt_by 要能永远查到出处。

DEFAULT_EXPIRY_DAYS = 180


class ExceptionCreate(BaseModel):
    rule_id: str
    scope_type: str = "device"        # device | site | all
    scope_value: str = ""
    reason: str = ""
    compensating_control: str = ""
    approved_by: str = ""
    approved_at: str | None = None    # 缺省 = 今天
    expires_at: str | None = None     # 缺省 = 批准日 + 180 天
    base_hash: str | None = None      # 乐观锁


class ExceptionUpdate(BaseModel):
    """可编辑字段限于"同一条例外的属性"。

    改 scope / rule_id 等于换了一条例外，应撤销后重新登记 ——
    否则历史审计里的 exempt_by 指向的就不是同一件事了。
    """
    reason: str | None = None
    compensating_control: str | None = None
    approved_by: str | None = None
    expires_at: str | None = None
    base_hash: str | None = None


class ExceptionRevoke(BaseModel):
    by: str = ""
    reason: str = ""
    base_hash: str | None = None


def _exceptions_path(std: dict) -> Path:
    return Path(std["source_dir"]) / loader.EXCEPTIONS_FILE


def _load_exceptions_file(path: Path):
    """载入例外表（ruamel，保留文件头注释）；文件不存在时返回内存骨架。"""
    data = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            data = _yaml_rt().load(fh) or {}
    if not data.get("exceptions"):
        data["exceptions"] = []
    return data


def _find_exception(data, exc_id: str):
    for e in data.get("exceptions") or []:
        if e.get("id") == exc_id:
            return e
    return None


def _next_exception_id(data) -> str:
    nums = [int(m.group(1)) for e in data.get("exceptions") or []
            if (m := re.match(r"^exc-(\d+)$", str(e.get("id") or "")))]
    return f"exc-{max(nums, default=0) + 1:03d}"


def _write_exceptions(path: Path, data) -> None:
    """备份 → 原子写 → 校验（失败回滚）。新文件先落骨架再备份，保证回滚有原件。"""
    if not path.exists():
        _atomic_dump({"exceptions": []}, path)
    backup = _backup(path)
    _atomic_dump(data, path)
    loader.clear_cache()
    try:
        loader.load_standard(use_cache=False)
    except loader.RuleError as e:
        shutil.copy2(backup, path)
        loader.clear_cache()
        raise HTTPException(status_code=400,
                            detail=f"例外登记表校验未通过，已回滚：\n{e}")


def _check_exception_lock(path: Path, base_hash: str | None) -> None:
    if base_hash and _file_hash(path) != base_hash:
        raise HTTPException(status_code=409,
                            detail="例外登记表已被其他人修改，请刷新后重试（乐观锁拦截）")


def _exception_view(e: dict, titles: dict, today=None) -> dict:
    """登记表条目的对外形态：附加推导状态、规则标题、剩余天数。"""
    today = today or datetime.date.today()
    days_left = None
    try:
        days_left = (datetime.date.fromisoformat(str(e.get("expires_at"))) - today).days
    except ValueError:
        pass
    return {**e, "status": engine.exception_status(e, today),
            "rule_title": titles.get(e.get("rule_id"), ""), "days_left": days_left}


@router.get("/api/audit/exceptions")
async def list_exceptions(state: str = "all"):
    """例外登记表。state：all（默认）/ active / expiring / expired / revoked。"""
    if state not in ("all", "active", "expiring", "expired", "revoked"):
        raise HTTPException(status_code=400,
                            detail="state 只能是 all / active / expiring / expired / revoked")
    std = loader.load_standard(use_cache=False)
    path = _exceptions_path(std)
    titles = {r["id"]: r.get("title", "") for r in std["rules"]}
    today = datetime.date.today()
    items = [_exception_view(e, titles, today) for e in std.get("exceptions") or []]
    counts = {s: sum(1 for i in items if i["status"] == s)
              for s in ("active", "expiring", "expired", "revoked")}
    if state != "all":
        items = [i for i in items if i["status"] == state]
    return {"exceptions": items, "counts": counts,
            "base_hash": _file_hash(path) if path.exists() else ""}


@router.post("/api/audit/exceptions")
async def create_exception(body: ExceptionCreate):
    """登记一条例外。到期日缺省 = 批准日 + 180 天；**不允许永久例外**。"""
    std = loader.load_standard(use_cache=False)
    path = _exceptions_path(std)
    _check_exception_lock(path, body.base_hash)
    data = _load_exceptions_file(path)

    approved_at = body.approved_at or datetime.date.today().isoformat()
    expires_at = body.expires_at
    if not expires_at:
        try:
            base = datetime.date.fromisoformat(approved_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="approved_at 需为 YYYY-MM-DD 日期")
        expires_at = (base + datetime.timedelta(days=DEFAULT_EXPIRY_DAYS)).isoformat()

    scope = {"type": body.scope_type}
    if body.scope_type != "all":
        scope["value"] = body.scope_value
    entry = {
        "id": _next_exception_id(data),
        "rule_id": body.rule_id,
        "scope": scope,
        "reason": body.reason,
        "compensating_control": body.compensating_control,
        "approved_by": body.approved_by,
        "approved_at": approved_at,
        "expires_at": expires_at,
    }
    data["exceptions"].append(entry)
    _write_exceptions(path, data)
    titles = {r["id"]: r.get("title", "") for r in std["rules"]}
    return {"ok": True, "exception": _exception_view(entry, titles),
            "base_hash": _file_hash(path)}


@router.put("/api/audit/exceptions/{exc_id}")
async def update_exception(exc_id: str, body: ExceptionUpdate):
    """编辑一条例外（续期 / 改理由 / 换批准人）。"""
    std = loader.load_standard(use_cache=False)
    path = _exceptions_path(std)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"例外不存在：{exc_id}")
    _check_exception_lock(path, body.base_hash)
    data = _load_exceptions_file(path)
    target = _find_exception(data, exc_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"例外不存在：{exc_id}")

    changes = body.model_dump(exclude_none=True, exclude={"base_hash"})
    if not changes:
        raise HTTPException(status_code=400, detail="没有需要修改的字段")
    for key, value in changes.items():
        target[key] = value
    _write_exceptions(path, data)
    titles = {r["id"]: r.get("title", "") for r in std["rules"]}
    return {"ok": True, "exception": _exception_view(dict(target), titles),
            "changed": list(changes), "base_hash": _file_hash(path)}


@router.post("/api/audit/exceptions/{exc_id}/revoke")
async def revoke_exception(exc_id: str, body: ExceptionRevoke):
    """撤销一条例外（软删除：写 revoked 块，条目保留供历史审计追溯）。"""
    std = loader.load_standard(use_cache=False)
    path = _exceptions_path(std)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"例外不存在：{exc_id}")
    _check_exception_lock(path, body.base_hash)
    data = _load_exceptions_file(path)
    target = _find_exception(data, exc_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"例外不存在：{exc_id}")
    if target.get("revoked"):
        raise HTTPException(status_code=400, detail=f"{exc_id} 已经撤销过了")
    if not body.by.strip() or not body.reason.strip():
        raise HTTPException(status_code=400, detail="撤销需要填写 by 与 reason（谁撤的、为什么）")
    target["revoked"] = {"at": datetime.date.today().isoformat(),
                         "by": body.by.strip(), "reason": body.reason.strip()}
    _write_exceptions(path, data)
    titles = {r["id"]: r.get("title", "") for r in std["rules"]}
    return {"ok": True, "exception": _exception_view(dict(target), titles),
            "base_hash": _file_hash(path)}


@router.get("/api/audit/device/{name}/export")
async def export_audit(name: str, format: str = "md"):
    """导出审计结果。md 便于贴进工单/邮件，json 便于二次处理。"""
    if format not in ("md", "json"):
        raise HTTPException(status_code=400, detail="format 只能是 md 或 json")
    std = loader.load_standard()
    item = source.load_audit_input(_get_db(), name)
    if item is None:
        raise HTTPException(status_code=404, detail=f"设备不存在：{name}")
    env = _envelope(item, std)
    if format == "json":
        return PlainTextResponse(
            json.dumps(env, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="audit-{name}.json"'})
    return PlainTextResponse(
        _render_md(env), media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="audit-{name}.md"'})
