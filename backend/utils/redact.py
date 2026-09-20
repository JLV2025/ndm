"""凭据打码 —— 发给 LLM 之前，把配置证据里的凭据值替换掉。

为什么单独一个工具并单独测：项目纪律是「**凭据值绝不外发**」。审计发现的现状/证据文本
直接来自配置（例如 ``snmp-server community QorvoRW RO``），原样发给第三方 LLM 等于外发凭据。

原则：**宁可多打一点，不可漏打** —— 误伤只是可读性差一点，漏打是安全事故。
打码保留命令本身（"配了团体字"这个事实要留给 LLM），只打掉值。
"""
from __future__ import annotations

import re

_REDACTED = "<REDACTED>"

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # SNMP 团体字：snmp-server community <字串> [RO|RW] [acl]
    (re.compile(r"(?i)^(\s*snmp-server community\s+)\S+"), rf"\1{_REDACTED}"),
    # SNMPv3 用户的认证/加密口令：auth sha <值> / priv aes <值>
    (re.compile(r"(?i)(\bauth\s+(?:md5|sha)\s+)\S+"), rf"\1{_REDACTED}"),
    (re.compile(r"(?i)(\bpriv\s+(?:aes|des)(?:\s+\d+)?\s+)\S+"), rf"\1{_REDACTED}"),
    # enable password/secret（可能带加密类型数字）
    (re.compile(r"(?i)^(\s*(?:enable\s+)?(?:password|secret)\s+(?:\d+\s+)?)\S+"), rf"\1{_REDACTED}"),
    # username <名> [privilege N] password|secret [类型] <值>
    (re.compile(r"(?i)^(\s*username\s+\S+\s+(?:privilege\s+\d+\s+)?(?:password|secret)\s+(?:\d+\s+)?)\S+"),
     rf"\1{_REDACTED}"),
    # 各类 key（AAA / RADIUS / TACACS / NTP 认证 / key-string）
    (re.compile(r"(?i)^(\s*(?:key|key-string|authentication-key|encryption-key)\s+(?:\d+\s+)?)\S+"),
     rf"\1{_REDACTED}"),
    (re.compile(r"(?i)(\b(?:radius-server|tacacs-server|aaa\s+group\s+server\s+\S+)\s+[^\n]*?\bkey\s+)\S+"),
     rf"\1{_REDACTED}"),
    # Cisco 类型 5/8/9 哈希值本体（单独出现时）
    (re.compile(r"\$[5789]\$[^\s]*"), _REDACTED),
    # Aruba / HPE 的 ciphertext
    (re.compile(r"(?i)(\bciphertext\s+)\S+"), rf"\1{_REDACTED}"),
]


def redact_secrets(text: str | None) -> str:
    """逐行打码；None / 空串原样返回（空串返回空串）。"""
    if not text:
        return text or ""
    out = []
    for line in str(text).splitlines():
        for rx, repl in _PATTERNS:
            line = rx.sub(repl, line)
        out.append(line)
    return "\n".join(out)


def redact_finding(finding: dict) -> dict:
    """对一条审计发现的可发送字段打码（不改原字典）。"""
    out = dict(finding)
    for key in ("current", "fix", "detail"):
        if isinstance(out.get(key), str):
            out[key] = redact_secrets(out[key])
    if isinstance(out.get("evidence"), list):
        out["evidence"] = [
            {**e, "text": redact_secrets(e.get("text"))} if isinstance(e, dict) else e
            for e in out["evidence"]
        ]
    return out
