"""批量命令执行 —— 危险命令预检 + 单台执行器。

与采集共用 DeviceConnection（netmiko 封装：自动关分页、Aruba timing 兼容），
但流程更轻：连接 → 执行 → 断开。执行是**前端逐台调端点**（与采集同一编排模式），
本模块只负责"一台"：预检（服务端兜底）→ 连接 → （配置模式可提权）→ 执行 →（可选保存）。

三层保护的第一层在这里：**危险命令一律拒绝执行**（前端预检展示 + 服务端执行前兜底，
两处都调 check_commands，即使前端被绕过服务端也拦得住）。

凭据纪律：用户名密码只在本调用栈内使用，绝不写库 / 写文件 / 进日志。
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 危险命令黑名单
#
# 判定前先 collapse 空白（"no  shutdown" 与 "no shutdown" 同判）。
# **一律不锚定行首**：命令可能以 `no `/空格开头（与 redact 的教训同源：行首锚定会漏判）。
# 只读命令（show / display / do show 开头）整行放行 —— `show boot` 是无害的，
# 不能因为含 boot 就拦。
_BLOCK_PATTERNS = [
    (r"\breload\b", "重启设备"),
    (r"\berase\b", "擦除配置 / 文件系统"),
    (r"\bdelete\b", "删除文件"),
    (r"\bformat\b", "格式化文件系统"),
    (r"\bsqueeze\b", "压缩 Flash（执行期间影响读写）"),
    (r"\bfactory[-_ ]?reset\b", "恢复出厂设置"),
    (r"\bwrite\s+erase\b", "擦除启动配置"),
    (r"\bclear\s+(config|startup)", "清除配置"),
    (r"\bboot\b", "修改引导 / 启动（重启类）"),
    (r"\bconfig-register\b", "修改配置寄存器（引导行为）"),
    (r"\btftpdnld\b", "TFTP 灾难恢复刷机"),
    (r"^usb\b", "从 USB 启动"),
]

# 警告（黄色，可继续）—— 可能锁死自己或断链路，由操作者判断。
# shutdown 要用 (?<!no ) 排除 `no shutdown`（那是**开启**端口，安全且常见）。
_WARN_PATTERNS = [
    (r"\bno\s+username\b|\busername\s+\S+\s+privilege\b", "改动账号 / 权限（可能删掉自己的登录账号）"),
    (r"\bno\s+aaa\b|\baaa\s+authentication\b", "改动 AAA 认证（配置错误可能锁死登录）"),
    (r"\bno\s+enable\b", "删除特权口令"),
    (r"\bno\s+ip\s+(route|default-gateway)\b", "删除路由 / 网关（可能断开管理路径）"),
    (r"\bno\s+interface\s+(vlan|mgmt|management)\b", "删除管理接口"),
    (r"\bno\s+vlan\b", "删除 VLAN"),
    (r"(?<!no )\bshutdown\b", "关闭端口 / 接口"),
    (r"\bno\s+spanning-tree\b", "关闭生成树（可能成环）"),
]

_READONLY_RE = re.compile(r"(?i)^(show|display|do\s+(show|display))\b")

# 未替换的占位符（`<公网地址>`、`<NTP_SERVER_2>`、`10.xx.<id>.x` …）。
# 设备 CLI 的命令参数不用尖括号，命中即"还没填值"——直接执行会把占位符字面发出去
# （`hostname <设备名>` 真会把主机名改成那个字面量），必须警示。
_PLACEHOLDER_RE = re.compile(r"<[^<>\n]{1,40}>")


def split_commands(text: str) -> list[str]:
    """把前端的多行文本拆成命令列表（忽略空行与 `!` / `#` 注释行）。

    `#` 用于**说明性建议**（流程类规则的 fix，如"规划替换…"）——
    带入批量执行页时天然不会被执行，与 `!` 同一语义。
    """
    return [ln.strip() for ln in (text or "").splitlines()
            if ln.strip() and not ln.strip().startswith(("!", "#"))]


def check_commands(commands: list[str]) -> dict:
    """逐行预检。返回 `{blocked: [{cmd, reason}], warnings: [{cmd, reason}]}`。

    blocked 非空 = 拒绝执行。同一行重复出现只报一次（去重按原文）。
    """
    blocked: list[dict] = []
    warnings: list[dict] = []
    seen: set[str] = set()
    for raw in commands:
        line = (raw or "").strip()
        if not line or line.startswith("!"):
            continue
        norm = re.sub(r"\s+", " ", line)
        if _READONLY_RE.match(norm):
            continue                      # 只读命令放行（`show boot` 之类）
        for pat, reason in _BLOCK_PATTERNS:
            if re.search(pat, norm, re.I):
                if line not in seen:
                    seen.add(line)
                    blocked.append({"cmd": line, "reason": reason})
                break
        else:
            ph = _PLACEHOLDER_RE.search(norm)
            if ph and line not in seen:
                # 占位符优先：先填值，填完重新预检再看锁死风险（那时占位符已消失）
                seen.add(line)
                warnings.append({"cmd": line,
                                 "reason": f"含未替换的占位符 {ph.group(0)}，执行前请替换为实际值"})
                continue
            for pat, reason in _WARN_PATTERNS:
                if re.search(pat, norm, re.I):
                    if line not in seen:
                        seen.add(line)
                        warnings.append({"cmd": line, "reason": reason})
                    break
    return {"blocked": blocked, "warnings": warnings}


def execute_on_device(device, username: str, password: str, commands: list[str],
                      mode: str = "show", save: bool = False,
                      settings: dict | None = None) -> dict:
    """对**单台**设备执行命令。返回 `{status, output, error}`。

    status：success | failed | blocked（服务端兜底拦截）。
    任何异常都转成 failed 返回（不抛出）—— 单台失败由前端记录后继续下一台。
    mode='config' 时走 send_config_set（自动进出配置模式）；save=True 追加 write memory。
    """
    settings = settings or {}
    commands = [c for c in commands if c and c.strip()]
    if not commands:
        return {"status": "failed", "output": "", "error": "命令为空"}

    verdict = check_commands(commands)
    if verdict["blocked"]:
        detail = "；".join(f"{b['cmd']}（{b['reason']}）" for b in verdict["blocked"])
        return {"status": "blocked", "output": "", "error": f"危险命令被拦截，未执行：{detail}"}

    from collectors.base import DeviceConnection    # 延迟导入（测试可 mock）

    conn = DeviceConnection({
        "name": device.name, "ip": device.ip, "type": device.type,
        "platform": getattr(device, "platform", "") or "",
        # 与采集侧一致硬编码 120 —— **别**改成 settings["ssh_timeout"]：
        # 那是 dict（{connect, read, write}），整块传给 netmiko 会在连接时炸
        # "unsupported operand type(s) for +: 'float' and 'dict'"（2026-09-21 真机踩过）
        "port": 22, "timeout": 120,
    })
    output_parts: list[str] = []
    try:
        if not conn.connect(username, password):
            return {"status": "failed", "output": "",
                    "error": getattr(conn, "_last_error", "") or "SSH 连接失败"}

        if mode == "config":
            if not conn.connection.check_enable_mode():
                # 多数设备用 privilege 15 账号直连即特权模式；少数需要 enable。
                # 用同一密码尝试提权（常见约定），失败则如实报错（不静默）。
                try:
                    conn.connection.secret = password
                    conn.connection.enable()
                except Exception as e:
                    return {"status": "failed", "output": "",
                            "error": "设备当前不在特权模式，自动提权失败（可能需要 enable 密码）："
                                     f"{type(e).__name__}: {str(e)[:150]}"}
            output_parts.append(conn.connection.send_config_set(commands, read_timeout=60) or "")
            if save:
                try:
                    resp = conn.send_command("write memory", read_timeout=60)
                    output_parts.append(f"[save] write memory\n{resp}")
                except Exception as e:
                    # 配置已下发、保存失败是**需要处理**的状态 —— 如实说清"已下发"
                    output_parts.append(f"⚠ [保存失败] write memory 未完成：{type(e).__name__}: {str(e)[:200]}")
        else:
            for cmd in commands:
                out = conn.send_command(cmd, read_timeout=60)
                output_parts.append(f"{cmd}\n{out}")

        return {"status": "success", "output": "\n".join(output_parts).strip(), "error": ""}
    except Exception as e:
        # 失败时把**已拿到的部分输出**带回（前几条命令的结果仍然有用）
        return {"status": "failed", "output": "\n".join(output_parts).strip(),
                "error": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass
