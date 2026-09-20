"""配置合规审计模块（移植自 allright/netstd，NDM 版）。

- parser  —— 配置文本 → 设备模型（VLAN / 接口块 / SVI / 站点）
- checks  —— 内置判定器，规则通过 check + params 引用
- loader  —— 规则库加载、合并与校验（config/audit/*.yaml）
- engine  —— 对外入口 analyze()

规则是数据不是代码：新增同类标准只改 YAML，新增判定方式才动 checks.py。
"""
from . import checks, engine, loader, parser  # noqa: F401

__all__ = ["checks", "engine", "loader", "parser"]
