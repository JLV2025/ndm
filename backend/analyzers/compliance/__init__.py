"""配置合规审计模块（移植自 allright/netstd，NDM 版）。

- parser      —— 配置文本 → 设备模型（VLAN / 接口块 / SVI / 站点）
- checks      —— 内置判定器，规则通过 check + params 引用
- port_roles  —— 端口角色推断（端口级规则的基础）
- loader      —— 规则库加载、合并与校验（config/audit/*.yaml）
- engine      —— 判定引擎，对外入口 analyze()
- source      —— 数据源：从 NDM 库取配置与端口上下文

规则是数据不是代码：新增同类标准只改 YAML，新增判定方式才动 checks.py。
"""
from . import checks, engine, loader, parser, port_roles, source  # noqa: F401

__all__ = ["checks", "engine", "loader", "parser", "port_roles", "source"]
