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

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

router = APIRouter()

from analyzers.compliance import engine, loader, source  # noqa: E402
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
    }
    if not snap.usable:
        return result
    analysis = engine.analyze(snap.name, snap.config, std,
                              site=snap.location, port_context=item.port_context)
    result.update({
        "findings": analysis["findings"],
        "counts": analysis["counts"],
        "port_roles": analysis["port_roles"],
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
async def audit_device(name: str, include_config: bool = Query(True)):
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


@router.get("/api/audit/device/{name}/export")
async def export_audit(name: str, format: str = Query("md", pattern="^(md|json)$")):
    """导出审计结果。md 便于贴进工单/邮件，json 便于二次处理。"""
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
