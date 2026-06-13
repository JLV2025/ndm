# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-06-13T05:53:08.162Z
> Files: 135 tracked | Anatomy hits: 0 | Misses: 0

## ../../../../

- `.mcp.json` (~46 tok)
- `.npmrc` (~15 tok)

## ../../../../../../tmp/

- `_export.py` — write_row (~2446 tok)

## ../../../../.claude/

- `CLAUDE.md` — OpenWolf (~218 tok)
- `settings.json` (~216 tok)

## ../../../../.claude/plans/

- `cheerful-kindling-creek.md` — NDM 全面改进方案（含老板需求） (~2678 tok)
- `cryptic-sleeping-pie.md` — Matrix Rain — 侧边栏绿色代码瀑布背景 (~249 tok)
- `distributed-stargazing-pelican.md` — 端口连接图重构 — 阶段一：布局 (~534 tok)
- `gentle-dazzling-treasure.md` — Dashboard 可视化第1批 — 实施计划 (高密度版) (~904 tok)
- `immutable-orbiting-barto.md` — DeviceList 组件拆分 (~729 tok)
- `snappy-wibbling-gosling.md` — 设备端口连接图 — 实施计划 v3 (~1126 tok)
- `swift-drifting-backus.md` — Location 多设备拓扑图 — 实施计划 v3 (~1317 tok)

## ../../../../.claude/projects/C--Users-jingl-Desktop-CC-Workspace-projects-ndm/

- `MEMORY.md` (~32 tok)

## ../../../../.claude/projects/C--Users-jingl-Desktop-CC-Workspace-projects-ndm/memory/

- `dashboard-charts-v1.md` — Dashboard 图表可视化 (第1批) (~262 tok)
- `design-audit-done.md` — 设计审查改进 (2026-06-06 已完成) (~207 tok)

## ../../../../.claude/rules/

- `auto-compact.md` (~45 tok)

## ../../../../.claude/skills/ui-ux-pro-max/

- `SKILL.md` — UI/UX Pro Max - Design Intelligence (~703 tok)

## ../../../../.claude/skills/wrap-up/

- `SKILL.md` — 收工 (~755 tok)

## ./

- `.gitignore` — Git ignore rules (~281 tok)
- `CLAUDE.md` — CLAUDE.md (~954 tok)
- `README_EN.md` — NDM — Network Device Manager (~1707 tok)
- `README.md` — Project documentation (~1232 tok)
- `security-review-report.md` — 后端代码安全审查报告 (~1406 tok)
- `start.bat` (~1031 tok)
- `用户手册.html` — QCNDM 网络配置管理系统 - 用户手册 (~6364 tok)

## .claude/

- `settings.json` (~469 tok)

## .claude/plans/

- `cisco-aruba-running-start-readme-md-90-synchronous-peacock.md` — 网络交换机配置收集系统 - 实施计划 (~883 tok)

## .claude/rules/

- `openwolf.md` (~313 tok)

## .gitnexus/

- `config.json` (~38 tok)

## agents/

- `backend-dev.md` — Backend Development Specialist (~653 tok)
- `frontend-dev.md` — Frontend Development Specialist (~657 tok)
- `integration-manager.md` — Integration Manager (~1046 tok)
- `qa-tester.md` — Quality Assurance & Testing Specialist (~829 tok)
- `README.md` — Project documentation (~666 tok)
- `security-reviewer.md` — Security Code Review Specialist (~1194 tok)
- `start-team.sh` — Start sub-agent development team (~650 tok)

## backend/

- `main.py` — API: 2 endpoints (~1035 tok)
- `pytest.ini` (~66 tok)
- `requirements.txt` — Python dependencies (~38 tok)
- `setup.cfg` (~70 tok)

## backend/analyzers/

- `__init__.py` — 配置分析模块 (~64 tok)
- `_helpers.py` — 分析器公共辅助函数 (~142 tok)
- `change_detector.py` — ChangeDetector: detect (~1120 tok)
- `config_parser.py` — class: parse (~2177 tok)
- `config_validator.py` — ConfigValidator: validate, check_completeness, check_critical_items, check_syntax (~1129 tok)
- `neighbor_parser.py` — CDP / LLDP 邻居解析器 (~3795 tok)
- `performance.py` — PerformanceAnalyzer: analyze (~5856 tok)

## backend/api/

- `__init__.py` — API 路由模块 (~141 tok)
- `auth.py` — 认证 API 路由 (~846 tok)
- `collector.py` — 配置收集 API 路由 (~1796 tok)
- `data.py` — 数据文件 API 路由 (~1942 tok)
- `devices.py` — 设备管理 API 路由 (~3834 tok)
- `stats.py` — Dashboard 统计 API (~2031 tok)
- `topology_visio.py` — Visio .vdx 拓扑图导出 (~1695 tok)
- `topology.py` — 拓扑图 API 路由 (~6316 tok)

## backend/collectors/

- `__init__.py` — 网络设备连接和配置收集模块 (~26 tok)
- `base.py` — DeviceConnection: connect, send_command, collect_config, collect_logs + 10 more (~2275 tok)

## backend/models/

- `__init__.py` — 数据模型模块 (~26 tok)
- `devices.py` — 设备数据模型 (~1046 tok)

## backend/scripts/

- `manage_devices.py` — 设备清单管理工具 (~1888 tok)
- `run_frontend.sh` (~26 tok)
- `run_server.sh` (~23 tok)
- `test_password_simple.py` — test_password (~380 tok)

## backend/services/

- `__init__.py` — 服务模块 (~70 tok)
- `collector_service.py` — 配置收集服务 (~7272 tok)
- `config_saver.py` — 配置保存服务 (~724 tok)

## backend/storage/

- `__init__.py` — 数据存储服务模块 (~74 tok)
- `file_manager.py` — get_week_dir, get_device_path, create_device_dir, keep_latest_versions_per_device (~766 tok)

## backend/tests/

- `_main.py` — API: 1 endpoints (~453 tok)
- `conftest.py` — mock_netmiko_connection, mock_file_system, test_password_manager, mock_device (~1046 tok)
- `README.md` — Project documentation (~142 tok)
- `test_devices_api.py` — test_config_file, test_list_devices_empty, test_list_devices_with_data, test_get_device_success (~3627 tok)
- `test_password.py` — TestPasswordManager: test_encrypt_decrypt_roundtrip, test_encrypt_different_passwords, test_encrypt_ (~650 tok)
- `test_services.py` — TestCollectorService: mock_device, mock_global_settings, test_collect_device_success, test_collect_d (~1356 tok)

## backend/utils/

- `__init__.py` — 工具函数模块 (~24 tok)
- `password.py` — PasswordManager: encrypt, decrypt (~742 tok)
- `settings_loader.py` — 配置加载器 (~256 tok)

## config/

- `devices.yaml` (~305 tok)
- `manager.py` — -*- coding: utf-8 -*- (~2601 tok)
- `settings.yaml` — 数据存储根目录 - 使用绝对路径避免工作目录问题 (~129 tok)

## data/

- `.gitkeep` — Data directory for collected device configurations (~15 tok)

## docker/

- `docker-compose.yml` — Docker Compose services (~146 tok)
- `Dockerfile` — Docker container definition (~276 tok)
- `nginx.conf` (~148 tok)

## frontend/

- `index.html` — 网络交换机配置收集系统 (~97 tok)
- `node_modules/` — 151 packages installed (~200 tok)
- `package.json` — Node.js package manifest (~324 tok)
- `preview-comparison.html` — 配色方案预览对比 — 方案 A vs 方案 D (~4075 tok)
- `tsconfig.json` — TypeScript configuration (~161 tok)
- `tsconfig.node.json` (~61 tok)
- `vite.config.ts` (~239 tok)
- `vitest.config.ts` — /*.tsx'], (~147 tok)

## frontend/src/

- `App.tsx` — DRAWER_WIDTH — renders modal (~2607 tok)
- `index.css` — Stylesheet (~182 tok)
- `index.tsx` — theme (~141 tok)
- `main.tsx` — 字体自托管（打包进 dist，无需外网） (~2880 tok)
- `vite-env.d.ts` — / <reference types="vite/client" /> (~11 tok)

## frontend/src/components/

- `ErrorBoundary.tsx` — dictionaries (~728 tok)
- `MatrixRain.tsx` — MATRIX_CHARS (~773 tok)

## frontend/src/components/devices/

- `BatchCollectionPanel.tsx` — BatchCollectionPanel (~1174 tok)
- `CollectionProgress.tsx` — STEP_KEYS (~1114 tok)
- `CollectResultDialog.tsx` — CollectResultDialog — renders modal (~1063 tok)
- `DeleteConfirmDialog.tsx` — DeleteConfirmDialog — renders modal (~431 tok)
- `DeviceCardGrid.tsx` — DeviceCardGrid (~1791 tok)
- `DeviceTable.tsx` — DeviceTable — renders table (~2306 tok)
- `deviceUtils.ts` — Exports getDeviceColor, getTypeLabel (~192 tok)
- `FrontPanel.tsx` — 端口状态 → 颜色映射 (~6128 tok)
- `ImportDialog.tsx` — ImportDialog — renders table, modal (~2782 tok)
- `LocationFilter.tsx` — LocationFilter (~524 tok)

## frontend/src/components/topology/

- `DirectionPad.tsx` — DirectionPad (~444 tok)
- `FrontPanelNode.tsx` — 为 true 时只显示计数，不画端口视觉元素（端点聚合用） (~2701 tok)
- `LocationTopologyCanvas.tsx` — NODE_W (~6013 tok)
- `PortTopologyCanvas.tsx` — 堆叠成员标签格式化：PVGD1SWI01-M1 → PVGD1SWI01 (Member 1) (~10596 tok)
- `TopologyCanvas.tsx` — TYPE_COLORS (~5109 tok)

## frontend/src/i18n/

- `en.ts` — en: location (~3768 tok)
- `index.tsx` — dictionaries (~427 tok)
- `zh.ts` — Declares zh (~2916 tok)

## frontend/src/pages/

- `Dashboard.tsx` — DevicesLink (~9807 tok)
- `DeviceDetail.tsx` — DeviceDetail (~6954 tok)
- `DeviceForm.tsx` — deviceSchema — renders form (~3628 tok)
- `DeviceList.tsx` — DeviceList (~4160 tok)
- `Login.tsx` — Login (~2286 tok)
- `NetworkTopology.tsx` — LEGEND_ITEMS (~2124 tok)
- `PortTopology.tsx` — fadeIn (~2121 tok)
- `Topology.tsx` — LEGEND_ITEMS (~2527 tok)
- `Viewer.tsx` — 语义颜色常量 — 对应 MUI OLED Dark 主题 (~8256 tok)

## frontend/src/services/

- `api.ts` — API routes: GET, POST, DELETE, PATCH (12 endpoints) (~1239 tok)
- `auth.ts` — Exports sessionManager (~826 tok)

## frontend/src/shared/

- `constants.ts` — 全局共享常量 — 设备颜色、图例、端点前缀 (~1234 tok)

## frontend/src/test/

- `setup.ts` — Mock window.matchMedia (~137 tok)
- `test_login.tsx` — showButton (~476 tok)

## frontend/src/types/

- `index.ts` — Exports Device, CollectResult, BatchItemStatus, Session + 2 more (~429 tok)
- `topology.ts` — Exports NeighborNode, TopologyData, LocationNode, LocationEdge, LocationTopologyData (~473 tok)

## tests/

- `PortTopologyCanvas.tsx` — 端口连接图独立画布：分层布局(交换机体+端口Handle+邻居设备)、click高亮、方向键偏移、PNG/Visio导出 (~5800 tok)
- `README.md` — Project documentation (~197 tok)
