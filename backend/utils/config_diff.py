"""running-config 与 startup-config 的差异比对。

两个消费方**必须共用这一套归一化**：
  - 采集后告警（anomaly_detector 的 config_drift）——"改了没保存，去处理"
  - 审计检查项（compliance 的 config_drift）——"这台设备状态不健康"
各写一套的话，迟早出现「告警说没问题、审计说有差异」的自相矛盾。

**归一化必须剥掉的东西**（不剥就会 100% 误报，而一条总在误报的检查等于没有）：
  · 头部标识行：`Current configuration:` / `Startup configuration:` /
    `Using 1234 out of 524288 bytes` —— 两边输出格式本来就不同
  · 空行与 `!` 分隔行 —— 两边数量本来就可能不一样
  · 末尾 `end`
  · 每行**行尾空格** —— 实测 35/36 台配置带行尾空格
留下的就是"有内容的配置行序列"，只有它才代表真正的配置差异。
"""
from __future__ import annotations

import difflib
import re

# 头部区（前若干行）里的元信息 —— 两条命令的输出本来就不同，一律剥掉
_HEADER_META_RE = re.compile(
    r"^(Building configuration|Current configuration|Startup configuration"
    r"|Using \d+ out of \d+ bytes|!Version\s"
    r"|!?\s*Last configuration change|!?\s*NVRAM config last updated"
    r"|!Time:)", re.I)

# 命令行回显（采集时终端回显混进来的，如 `BJQD1SWI01#` 或 `SWI01# show running-config`）
_PROMPT_RE = re.compile(r"^\S+[#>]\s*(\S.*)?$")

# 证书块：running 是 `certificate ca 01` + 数十行 hex + `quit`；
# startup 只有 `certificate ca 01 nvram:xxx.cer` 一行（无 hex）。
# 同一条证书两种表示，不忽略必然每次误报。代价是证书本身的变更检测不到，
# 但证书不属于"改了没保存"的典型场景，这个取舍可以接受。
_CERT_RE = re.compile(r"^\s*certificate\s", re.I)


def _is_cert_body(t: str) -> bool:
    """证书块正文行：hex 数据行或结束标记 quit。

    要求**整行只由 hex 组构成**且（组数 ≥ 2 或单组 ≥ 16 字符）——
    这样 `D697DF7F 28` 这类末尾短片段能命中，而正常配置行不会误伤。
    """
    s = t.strip()
    if s.lower() == "quit":
        return True
    tokens = s.split()
    if not tokens or not all(re.fullmatch(r"[0-9A-Fa-f]+", tok) for tok in tokens):
        return False
    return len(tokens) >= 2 or len(tokens[0]) >= 16

# 归一化时忽略的行：空行、纯分隔符、结束标记
_IGNORE_EXACT = {"", "!", "end", "!" * 3}

# IOS 自动维护的 NTP 时钟周期校准值：NTP 每次重新校准时都会改写 running，
# 而 startup 里是上次保存的旧值 —— 差异必然出现，但**不是人工配置改动**，属噪声。
# （设备重启后会重新学习，没有影响。）
_NTP_CLOCK_RE = re.compile(r"^ntp clock-period\s", re.I)


def normalized_lines(text: str, header_scan: int = 12) -> list[tuple[int, str]]:
    """返回 [(原始行号, 归一化文本)]，已剥离头部元信息/命令行回显/证书块/
    空行/`!`/`end` 与行尾空格。

    保留原始行号是为了让差异能映射回配置正文——前端标红只认行号。
    """
    out: list[tuple[int, str]] = []
    in_cert = False
    for i, raw in enumerate((text or "").split("\n"), start=1):
        t = raw.rstrip()                      # 行尾空格：实测 35/36 台都有
        if t in _IGNORE_EXACT or set(t) <= {"!", "-", "=", " "}:
            continue
        if _NTP_CLOCK_RE.match(t):
            continue
        if i <= header_scan and (_HEADER_META_RE.match(t) or _PROMPT_RE.match(t)):
            continue
        if _CERT_RE.match(t):
            in_cert = True                    # 进入证书块，连后面的 hex 与 quit 一起丢
            continue
        if in_cert:
            if _is_cert_body(t):
                continue
            in_cert = False                   # 非证书正文 → 块结束，这行要保留
        out.append((i, t))
    return out


def diff_configs(running: str, startup: str, limit: int = 20) -> dict:
    """比较两份配置，返回差异摘要。

    only_running：running 里有、startup 里没有的行 —— **即"改了没保存"的内容**，
                  每条带 running 侧的原始行号（供前端标红）。
    only_startup：startup 里有、running 里没有的行 —— 通常意味着"保存过但后来被改掉/删了"。
    truncated：差异条数超过 limit 时置 True（只回传前 limit 条，避免一份报告塞几千行）。
    """
    a = normalized_lines(running)
    b = normalized_lines(startup)
    at = [t for _, t in a]
    bt = [t for _, t in b]

    result = {"differ": False, "running_lines": len(at), "startup_lines": len(bt),
              "only_running": [], "only_startup": [], "truncated": False}

    # 快路径：绝大多数情况两边完全一致，直接返回，不必进 SequenceMatcher
    if at == bt:
        return result
    result["differ"] = True

    sm = difflib.SequenceMatcher(None, at, bt, autojunk=False)
    only_running: list[dict] = []
    only_startup: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            for i in range(i1, i2):
                only_running.append({"line": a[i][0], "text": a[i][1]})
        if tag in ("insert", "replace"):
            for j in range(j1, j2):
                only_startup.append({"line": None, "text": b[j][1]})

    result["only_running"] = only_running[:limit]
    result["only_startup"] = only_startup[:limit]
    result["truncated"] = len(only_running) > limit or len(only_startup) > limit
    result["total_running_only"] = len(only_running)
    result["total_startup_only"] = len(only_startup)
    return result
