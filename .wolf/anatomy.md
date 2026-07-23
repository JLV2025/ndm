# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-07-23T01:02:44.136Z
> Files: 63 tracked | Anatomy hits: 0 | Misses: 0

## ../../../../


## ../../../../../../tmp/


## ../../../../.claude/


## ../../../../.claude/plans/


## ../../../../.claude/projects/C--Users-jingl-Desktop-CC-Workspace-projects-ndm/


## ../../../../.claude/projects/C--Users-jingl-Desktop-CC-Workspace-projects-ndm/memory/


## ../../../../.claude/rules/


## ../../../../.claude/skills/ui-ux-pro-max/


## ../../../../.claude/skills/wrap-up/


## ../../downloads/claude-fable-5-system-prompt-main/


## ../../downloads/claude-fable-5-system-prompt-main/highlights/


## ../../downloads/claude-fable-5-system-prompt-main/system-prompt/


## ../../downloads/claude-fable-5-system-prompt-main/system-prompt/analysis/


## ../../temp/

- `gen_vsdx_tests.py` — 生成多个 VSDX 变体用于对比诊断 (~3267 tok)

## ./

- `.gitignore` — Git ignore rules (~317 tok)
- `README_EN.md` — NDM — Network Device Manager (~1953 tok)
- `README.md` — Project documentation (~1410 tok)
- `start.bat` (~1019 tok)
- `VERSION` (~2 tok)

## .claude/

- `settings.json` (~481 tok)

## .claude/plans/


## .claude/rules/


## .claude/skills/port-topology-canvas/


## .claude/skills/work-wrap-up/

- `SKILL.md` — 收工 (~417 tok)

## .claude/skills/天龙五步/


## .gitnexus/


## C:/Users/jingl/.claude/


## C:/Users/jingl/.claude/plans/

- `1-windows-ai-witty-fox.md` — 日志分析页面改版计划 (~1132 tok)
- `bug-zgn-0-tingly-haven.md` — 修复 ConfigParser 无法识别 GTS 服务器和自定义设备名 (~648 tok)
- `crispy-percolating-bubble.md` — 拓扑图端点端口标签重构 (~667 tok)
- `no-no-no-sqlite-running-config-raw-runni-twinkly-sutherland.md` — 配置查看器重构：SQLite 数据源 + 直接显示 + 复制按钮 (~801 tok)
- `parallel-stargazing-rocket.md` — 拓扑图 PNG 导出浅色主题 (~543 tok)
- `soft-dazzling-orbit.md` — 计划：设备管理 YAML → SQLite 统一迁移 (~806 tok)
- `vdx-visio-velvety-pillow.md` — VSDX Visio 导出修复计划 (~1241 tok)

## agents/


## backend/

- `main.py` — API: 3 endpoints (~1254 tok)
- `requirements.txt` — Python dependencies (~45 tok)

## backend/analyzers/

- `change_detector.py` — ChangeDetector: detect (~1181 tok)
- `config_parser.py` — class: parse (~2402 tok)
- `neighbor_parser.py` — CDP / LLDP 邻居解析器 (~4211 tok)
- `role_verifier.py` — class: devices, device_map, verify_device, audit_location (~3408 tok)

## backend/api/

- `alerts.py` — 告警 API 路由 (~1603 tok)
- `auth.py` — 认证 API 路由 (~863 tok)
- `collector.py` — 配置收集 API 路由 (~1654 tok)
- `data.py` — 数据文件 API 路由 (~3884 tok)
- `devices.py` — 设备管理 API 路由 — SQLite 唯一数据源 (~2818 tok)
- `logs.py` — 日志分析 API 路由 (~2560 tok)
- `reports.py` — 自定义报告 API 路由 (~1780 tok)
- `stats.py` — Dashboard 统计 API — 全量从 SQLite 读取 (~1839 tok)
- `topology_visio.py` — Visio .vsdx 拓扑图导出 (~4536 tok)
- `topology.py` — 拓扑图 API 路由 (~9869 tok)

## backend/collectors/

- `base.py` — DeviceConnection: connect, send_command, collect_config, collect_logs + 11 more (~2496 tok)

## backend/models/


## backend/scripts/

- `manage_devices.py` — 设备清单管理工具 — SQLite 数据源 (~1692 tok)

## backend/services/

- `collector_service.py` — 配置收集服务 (~13427 tok)
- `log_analyzer.py` — 日志 AI 分析服务 (~3096 tok)

## backend/storage/

- `database.py` — init_db, get_connection, close_connection (~4092 tok)
- `device_dal.py` — get_all_devices, get_device_by_name, device_exists, create_device (~1824 tok)

## backend/tests/


## backend/utils/

- `settings_loader.py` — 配置加载器 (~527 tok)

## config/

- `settings.example.yaml` — NDM 全局配置模板 (~218 tok)
- `settings.yaml` (~175 tok)

## data/


## docker/


## frontend/

- `package.json` — Node.js package manifest (~421 tok)
- `vite.config.ts` (~239 tok)

## frontend/src/

- `App.tsx` — DRAWER_WIDTH — renders modal (~3019 tok)
- `main.tsx` — 字体自托管（打包进 dist，无需外网） (~3007 tok)

## frontend/src/components/


## frontend/src/components/devices/

- `BatchCollectionPanel.tsx` — 由父组件更新设备的实时进度（0-100） (~1903 tok)
- `CollectionProgress.tsx` — CollectionProgress (~964 tok)
- `DeviceTable.tsx` — DeviceTable — renders table (~2494 tok)

## frontend/src/components/topology/

- `LabeledSmoothstepEdge.tsx` — 带端点端口标签的 smoothstep 边。 (~695 tok)
- `LocationTopologyCanvas.tsx` — NODE_H (~7282 tok)
- `PortTopologyCanvas.tsx` — 解析设备命名规范：PVGD1SWI02 → { site: "PVG", room: "D1", typeCode: "SWI", num: 2 } (~14159 tok)
- `TopologyCanvas.tsx` — 判断端口拓扑是否符合三层结构：有 WAN 设备 + 中心交换机 + 终端设备 (~6637 tok)

## frontend/src/i18n/

- `en.ts` — Declares en (~4573 tok)
- `zh.ts` — Declares zh (~3923 tok)

## frontend/src/pages/

- `Alerts.tsx` — 字段中文标签映射 (~4026 tok)
- `Dashboard.tsx` — DevicesLink (~10054 tok)
- `DeviceList.tsx` — 单个设备的完整收集流程（Ping → Collect） (~4189 tok)
- `LogAnalyzer.tsx` — 严重级别 → 颜色 (数字→hex) (~8010 tok)
- `Reports.tsx` — ReportsPage — renders form, table (~2500 tok)
- `Viewer.tsx` — 语义颜色常量 — 对应 MUI OLED Dark 主题 (~6450 tok)

## frontend/src/services/

- `api.ts` — Visio 导出 — 发送拓扑数据，返回 .vsdx 文件 Blob (~1854 tok)

## frontend/src/shared/

- `constants.ts` — 全局共享常量 — 设备颜色、图例、端点前缀 (~1384 tok)
- `exportUtils.ts` — 端点标签碰撞避免 — 贪心分配垂直行。 (~1525 tok)

## frontend/src/test/


## frontend/src/types/

- `index.ts` — 物理设备（堆叠拆分后的展示用对象） (~552 tok)

## tests/

