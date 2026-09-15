# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-09-15T02:25:02.470Z
> Files: 50 tracked | Anatomy hits: 0 | Misses: 0

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


## ./

- `.gitignore` — Git ignore rules (~335 tok)
- `NDM用户使用文档.html` — NDM User Guide / 用户使用文档 — Network Device Management (~11324 tok)
- `README.md` — Project documentation (~1670 tok)
- `start.bat` (~981 tok)
- `VERSION` (~2 tok)

## .claude/


## .claude/plans/


## .claude/rules/


## .claude/skills/port-topology-canvas/


## .claude/skills/work-wrap-up/


## .claude/skills/天龙五步/


## .gitnexus/


## C:/Users/jingl/.claude/


## C:/Users/jingl/.claude/plans/

- `cisco-precious-thompson.md` — 端口流量排行：改用累计计数器差值 (~4284 tok)
- `silly-weaving-hearth.md` — VSF 成员编号透传 + 物理设备档案 + 离线设备视图 实施计划 (~1286 tok)

## agents/


## backend/

- `_verify_version.py` — 临时验证脚本：检查 FastAPI 应用版本号动态读取（验证后删除） (~76 tok)
- `main.py` — API: 3 endpoints (~1274 tok)

## backend/analyzers/

- `counter_parser.py` — 端口累计计数器解析器 — 三平台解析器（Cisco 交换机 `show int counters` / Cisco 路由器 `show interfaces stats` / Aruba `show interface statistics`）+ `normalize_port_name`（全称→缩写，区分 SE/Se）+ C9500 排除规则 + `compute_week_deltas` 周锚定差值 (~3129 tok)
- `neighbor_parser.py` — CDP / LLDP 邻居解析器 (~6462 tok)
- `performance.py` — PerformanceAnalyzer: analyze (~7585 tok)

## backend/api/

- `devices.py` — 设备管理 API 路由 — SQLite 唯一数据源 (~3116 tok)
- `stats.py` — Dashboard 统计 API — 全量从 SQLite 读取 (~2386 tok)
- `topology.py` — 拓扑图 API 路由 (~11910 tok)

## backend/collectors/

- `base.py` — DeviceConnection: connect, send_command, collect_config, collect_logs + 15 more (~3152 tok)

## backend/models/


## backend/scripts/


## backend/services/

- `collector_service.py` — 配置收集服务 (~16822 tok)

## backend/storage/

- `database.py` — init_db, get_connection, close_connection (~4762 tok)
- `device_dal.py` — get_all_devices, get_device_by_name, device_exists, create_device (~2142 tok)

## backend/tests/

- `conftest.py` — test_password_manager (~78 tok)
- `test_collector_service.py` — collector_service 型号/序列号/成员ID提取测试 — 重点：Aruba CX VSF 堆叠 (~1644 tok)
- `test_collector_service.py` — extract_model/extract_serial_number 测试（重点 VSF 堆叠成员型号，4 用例） (~500 tok)
- `test_counter_parser.py` — 端口累计计数器解析器测试（47 用例）— 真机样本读 fixtures，覆盖重复表头 / C9500 排除 / CRLF / 全 0 端口 / 大数值精度 / 周锚定差值各边界 (~3836 tok)
- `test_database_migration.py` — 数据库迁移测试（重点 v10：port_snapshots 增加累计计数器列） (~1165 tok)
- `test_neighbor_parser.py` — CDP/LLDP 邻居解析器测试 — 重点：Aruba AP 名识别 (~1543 tok)
- `test_performance_aruba.py` — Aruba show interface brief 解析测试 (~389 tok)
- `test_performance_counters.py` — 端口累计计数器与端口详情合并测试（PerformanceAnalyzer 接线，四类设备端到端基数 151/57/7/52） (~1894 tok)
- `test_port_snapshot_write.py` — port_snapshots 落库测试（21 列 INSERT / NULL 与读数 0 区分 / 大数据精度） (~900 tok)
- `test_port_snapshot_write.py` — port_snapshots 落库测试 —— 重点：累计计数器列（in_octets / out_octets） (~1043 tok)
- `test_stats_window.py` — 区间流量 Top10 周锚定测试（16 用例，**核心：周中再采一次结果完全不变**） (~1900 tok)
- `test_stats_window.py` — 区间流量 Top10 测试 —— 周锚定口径 (~2078 tok)

## backend/utils/


## config/


## data/


## docker/


## docs/superpowers/plans/

- `2026-08-04-aruba-ap-recognition.md` — Aruba AP 识别实现计划 (~3717 tok)
- `2026-09-14-traffic-counter-delta.md` — 端口流量排行：改用「周锚定」累计计数器差值 (~5604 tok)

## docs/superpowers/specs/

- `2026-08-04-aruba-ap-recognition-design.md` — Aruba AP 识别设计（2026-08-04） (~910 tok)

## frontend/

- `package.json` — Node.js package manifest (~421 tok)

## frontend/src/


## frontend/src/components/


## frontend/src/components/devices/

- `DeleteConfirmDialog.tsx` — 自定义提示文案；不传则用 devices.deleteWarning 并把 {name} 替换为 deviceName (~462 tok)
- `deviceUtils.ts` — 解析堆叠成员编号后缀（每成员一个后缀，与序列号同序） (~408 tok)

## frontend/src/components/topology/

- `LabeledSmoothstepEdge.tsx` — 带端点端口标签的 smoothstep 边。 (~1026 tok)
- `LocationTopologyCanvas.tsx` — NODE_H (~7754 tok)
- `PortTopologyCanvas.tsx` — 解析设备命名规范：PVGD1SWI02 → { site: "PVG", room: "D1", typeCode: "SWI", num: 2 } (~14392 tok)
- `TopologyCanvas.tsx` — 判断端口拓扑是否符合三层结构：有 WAN 设备 + 中心交换机 + 终端设备 (~6637 tok)

## frontend/src/i18n/

- `en.ts` — Declares en (~4900 tok)
- `zh.ts` — Declares zh (~4151 tok)

## frontend/src/pages/

- `Dashboard.tsx` — 区间流量 Top10 —— 周锚定计数器差值算出的区间平均速率，不是瞬时速率 (~10929 tok)
- `DeviceList.tsx` — 单个设备的完整收集流程（Ping → Collect） (~5691 tok)
- `Login.tsx` — Login (~2283 tok)

## frontend/src/services/

- `api.ts` — Visio 导出 — 发送拓扑数据，返回 .vsdx 文件 Blob (~1907 tok)

## frontend/src/shared/

- `constants.ts` — 全局共享常量 — 设备颜色、图例、端点前缀 (~1414 tok)

## frontend/src/test/


## frontend/src/types/

- `index.ts` — 离线物理设备档案（device_members 表） (~515 tok)
- `topology.ts` — 端口物理断开（status_up=0），图上显示红叉警告 (~540 tok)

## tests/

