# OpenWolf

@.wolf/OPENWOLF.md

This project uses OpenWolf for context management. Read and follow .wolf/OPENWOLF.md every session. Check .wolf/cerebrum.md before generating code. Check .wolf/anatomy.md before reading files.


# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NDM（QCNDM）：通过 SSH 批量收集 Cisco IOS / IOS-XE / Router 与 Aruba OS / CX 的配置、日志、
接口状态与计数器、邻居/生成树/聚合等信息，存 SQLite，React 前端可视化；内置**配置审计**
（确定性规则引擎，"像资深网络工程师评审"）与 AI 辅助（日志诊断、专家简报）。
（2026-09-20 更正：本文件此前描述的 `cli_main.py` / `lib/collector.py` / `utils/storage.py` /
根级 `analyzers/` 均已不存在，实际结构见下。）

## Architecture

- **入口**：`backend/main.py`（FastAPI；同时托管 `frontend/dist` 静态前端，默认 8002）
- **采集**：`backend/services/collector_service.py::collect_device`（Netmiko；
  SSH 连接封装在 `backend/collectors/base.py`）。批量采集由**前端 worker 队列**逐台调
  `POST /api/collect/{device}`（没有服务端批量端点）
- **存储**：SQLite 为唯一数据源（`backend/storage/database.py` 管迁移与 schema_version，
  `file_manager.py` 管分层保留，`device_dal.py` 是设备清单的唯一入口
  —— `list_managed()`（管理体：stack+standalone）/ `list_physical()`（物理：member+standalone），
  `lifecycle_dal.py` 管 EoL 与保修台账）；`data/YYYY-WW/{设备}/` 保留原始文件
- **分析**：`backend/analyzers/`（performance / config_validator / change_detector / hardware_change /
  neighbor_parser / stp_parser / counter_parser / anomaly_detector / role_verifier）
  \- **配置审计**在 `backend/analyzers/compliance/`：`parser`（配置→设备模型）、`checks`（判定器）、
  `engine`（判定 + 例外豁免 + 集体性折叠）、`loader`（规则库校验）、`port_roles`、
  `source`（从库装配输入）、`runner`（全量审计落库）、`trends`（趋势/榜查询核心）
- **审计规则库**：`config/audit/*.yaml`（**标准是数据不是代码**；三层来源 + 例外登记
  `_exceptions.yaml`；页面可视化编辑写回 YAML）
- **API**：`backend/api/`（devices / collector / data / auth / stats / topology / alerts /
  reports / logs / audit / lifecycle）
- **前端**：`frontend/src`（React 18 + MUI + recharts；页面在 `pages/`；构建产物 `dist/` 入库）。
  侧栏导航结构在 `App.tsx`：顶层 3 项 + 4 个可折叠组（拓扑 / 审计 / 监控 / 资产），
  **当前路由所在组自动展开**，开合状态存 localStorage（键 `ndm_nav_groups`）；新增页面时按类别加进对应组
- **文档**：设计与实施计划在 `docs/superpowers/plans/`；跨会话决策与教训在 `.wolf/cerebrum.md`

**Data flow：**

1. 前端「收集」→ `POST /api/collect/{device}`（先 Ping 预检）
2. 依次采集 running/startup-config、日志、接口状态与累计计数器、路由、版本、CDP/LLDP、STP、LACP
3. 落库（collections / port_snapshots / neighbors / stp_snapshots …）+ 写设备目录原始文件，按分层策略清理
4. 异常检测（anomaly_detector）写 alerts；**采集批次静默 60 秒后自动跑一轮全网审计**（可关）
5. 前端各页面经 API 读库（仪表盘 / 查看器 / 配置审计 / 审计标准 …）

## Configuration

- `config/devices.yaml` / SQLite `devices` 表 —— 设备清单（name/IP/type/platform/location/uplink_ports…）
- `config/settings.yaml` —— 全局设置（data_root、SSH 超时、分析开关、LLM providers、audit）；
  **已 gitignore**，API key 用环境变量 `LLM_API_KEY_N` 覆盖
- 保留策略是分层规则不是配置项 —— 见 `backend/storage/file_manager.py`

## Common Commands

```bash
# 启动后端（同时托管已构建的前端）—— **必须在项目根目录跑**：data_root 是相对路径，
# 在 backend/ 下跑会新建一个空库（现象极具误导性，曾踩过）
python backend/main.py

# 后端测试（从 backend 目录跑；项目根目录没有 tests/）
cd backend && python -m pytest tests/ -q

# 改完前端要重新构建（dist 入库）
cd frontend && npm run build

# 设备清单管理（交互式菜单）
python config/manager.py
```

## Key Design Patterns

1. **Context manager** —— `DeviceConnection` 用 `__enter__`/`__exit__` 自动断开
2. **依赖注入的上下文** —— 审计数据源 `source.py` 把端口上下文、生命周期上下文装配好传给引擎
   （`analyze(..., port_context=, lifecycle=)`），判定器不直接查库
3. **标准是数据不是代码** —— 新增标准 = 加一条 YAML；新增判定方式 = 加一个 `checks.py` 函数
4. **指纹贯穿** —— `config_hash` / `ruleset_hash` / `exceptions_hash` 用于判断"配置/标准/豁免变没变"
5. **分层保留** —— 配置文本按周留 16 周，更早按月归档；DB 配置全文与日志各留最近 2 次；
   采集结束时执行，也可跑 `backend/scripts/retention.py`
6. **身份模型：位置身份 vs 硬件身份** —— `devices.kind`（stack / standalone / member）：
   配置、采集、审计、告警挂**位置行**（stack/standalone，用名字 + IP）；序列号、型号、保修、
   软件版本挂**物理设备**（member 行有 `stack_name` + `member_no`，或 standalone 行）。
   物理名 `{堆叠名}-{编号}` 的唯一实现是 `backend/utils/device_identity.py`；
   **查设备清单必须用 `device_dal` 的两个入口，禁止裸查 `devices`**（成员行不得混入管理体视角）。
   硬件变更（换件/加成员/整机换代）由 `analyzers/hardware_change.py` 的指纹 diff 判定并留痕

## Important Notes

- 密码交互式输入，不落盘（`config/settings.yaml` 亦 gitignore，绝不提交）
- **凭据值绝不外发**：发给 LLM 的文本（日志分析、专家简报）必须先过 `backend/utils/redact.py`
- 设备目录名优先用 `show version` 里的序列号；堆叠按物理成员逐台建档
- **生命周期三色判定的唯一来源是 `backend/services/lifecycle_status.py`**（维保 2 个月 / EoS·EoL
  6 个月，按日历月）；前端只做「状态 → 颜色」（`frontend/src/shared/constants.ts`），不重复判一次
- 采集时自动跑配置校验与性能分析；采集后自动跑审计（去抖）
- 改 schema 要加 `_migrate_vN` 并升 `SCHEMA_VERSION`；服务只在 `init_db()`（启动）时迁移

## Workflow

- 架构决策前先询问
- 做最小改动，不重构无关代码
- 每次变更后跑测试，失败先修复再继续
- 每个逻辑变更单独提交
- 两种方案之间拿不准时，两个都解释，让我来选

## Out of scope

- migrations/ → 由 ORM CLI 管理，不要手动创建
- public/assets/ → 静态文件，不要修改
- .github/workflows/ → CI/CD，未经询问不要改动

## Language Rules

* All communication, comments, and documentation must be in **Simplified Chinese**
* Code comments must be in Chinese
* Commit messages must be in Chinese
* Professional English terms/abbreviations allowed

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **ndm** (6933 symbols, 12446 relationships, 259 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/ndm/context` | Codebase overview, check index freshness |
| `gitnexus://repo/ndm/clusters` | All functional areas |
| `gitnexus://repo/ndm/processes` | All execution flows |
| `gitnexus://repo/ndm/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
