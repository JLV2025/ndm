# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-09-22T08:11:11.963Z
> Files: 158 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitignore` — Git ignore rules (~335 tok)
- `CLAUDE.md` — OpenWolf (~1664 tok)
- `NDM用户使用文档.html` — NDM User Guide / 用户使用文档 — Network Device Management (~14443 tok)
- `README.md` — Project documentation (~3136 tok)
- `start.bat` (~1023 tok)
- `VERSION` (~3 tok)

## .claude/


## .claude/plans/


## .claude/rules/


## .claude/skills/port-topology-canvas/


## .claude/skills/work-wrap-up/


## .claude/skills/天龙五步/


## .gitnexus/


## agents/


## backend/

- `_verify_version.py` — 临时验证脚本：检查 FastAPI 应用版本号动态读取（验证后删除） (~76 tok)
- `main.py` — API: 3 endpoints (~1466 tok)
- `tmp_stp_check.py` — 临时诊断：用真实库数据模拟前端层带判定（跑完即删） (~889 tok)

## backend/analyzers/

- `anomaly_detector.py` — AnomalyDetector: detect_all, detect_and_save, resolve_recovered_drift (~4618 tok)
- `counter_parser.py` — 端口累计计数器解析器 (~3198 tok)
- `hardware_change.py` — 硬件变更检测 —— 指纹 diff 与事件（spec 第六节）。 (~1001 tok)
- `neighbor_parser.py` — CDP / LLDP 邻居解析器 (~6462 tok)
- `performance.py` — PerformanceAnalyzer: analyze (~7668 tok)
- `stp_parser.py` — 生成树（STP）输出解析器 (~2662 tok)

## backend/analyzers/compliance/

- `__init__.py` — 配置合规审计模块（移植自 allright/netstd，NDM 版）。 (~144 tok)
- `checks.py` — 内置判定器 —— 规则通过 `check` 名 + `params` 引用这里面的函数。 (~6434 tok)
- `engine.py` — 配置审计 —— 判定引擎（对外入口）。 (~2632 tok)
- `loader.py` — 规则库加载与校验。 (~3810 tok)
- `parser.py` — 配置文本解析 —— 从 running-config 文本构建判定所需的设备模型。 (~1697 tok)
- `port_roles.py` — 端口角色推断 —— 让端口级规则真正可达。 (~2561 tok)
- `runner.py` — 全网审计执行器 —— API 端点与「采集后自动跑」共用同一实现。 (~1180 tok)
- `source.py` — 审计数据源 —— 从 NDM 库取"这次审计要审什么"。 (~1713 tok)
- `trends.py` — 审计趋势的查询核心 —— 从 api/audit.py 抽出（API 与 AI 简报共用）。 (~1612 tok)

## backend/api/

- `alerts.py` — 告警 API 路由 (~2091 tok)
- `audit.py` — 配置审计 API 路由。 (~7591 tok)
- `batch.py` — 批量命令执行 API —— 预检 / 单台执行 / 历史留痕。 (~1494 tok)
- `collector.py` — 配置收集 API 路由 (~1810 tok)
- `data.py` — 数据文件 API 路由 (~3944 tok)
- `devices.py` — 设备管理 API 路由 — SQLite 唯一数据源 (~3323 tok)
- `lifecycle.py` — 设备生命周期 API —— EoL 与保修期的登记、批量导入、刷新与概况。 (~1770 tok)
- `logs.py` — 日志分析 API 路由 (~2638 tok)
- `reports.py` — 自定义报告 API 路由 (~2500 tok)
- `stats.py` — Dashboard 统计 API — 全量从 SQLite 读取 (~2665 tok)
- `topology.py` — 拓扑图 API 路由 (~15402 tok)

## backend/collectors/

- `base.py` — DeviceConnection: connect, send_command, collect_config, collect_logs + 13 more (~3612 tok)

## backend/models/


## backend/scripts/

- `retention.py` — 数据保留与归档工具 (~560 tok)

## backend/services/

- `audit_briefing.py` — AI 专家简报 —— 让 AI 把**确定性审计结论**讲成人话。 (~3067 tok)
- `audit_scheduler.py` — 采集后自动审计（去抖）。 (~580 tok)
- `batch_exec.py` — 批量命令执行 —— 危险命令预检 + 单台执行器。 (~1954 tok)
- `collector_service.py` — 配置收集服务 (~22575 tok)
- `eox_client.py` — Cisco EoX 客户端 —— 按型号批量查生命周期（停止销售 / 停止支持）。 (~1502 tok)
- `lifecycle_status.py` — 生命周期三色判定 —— 唯一实现（spec 第十三节） (~550 tok)
- `log_analyzer.py` — 日志 AI 分析服务 (~3102 tok)

## backend/storage/

- `__init__.py` — 数据存储服务模块 (~162 tok)
- `database.py` — init_db, get_connection, close_connection (~9436 tok)
- `device_dal.py` — list_managed, list_physical, get_all_devices, get_device_by_name (~2849 tok)
- `file_manager.py` — 存储管理模块 (~2820 tok)
- `lifecycle_dal.py` — 设备生命周期数据访问 —— EoL 型号缓存 + 逐序列号保修登记。 (~3785 tok)

## backend/tests/

- `conftest.py` — test_password_manager (~78 tok)
- `test_alerts_resolve_all.py` — 「全部清除」端点测试 —— 批量把未处理告警标记为已处理 (~812 tok)
- `test_anomaly_config_drift.py` — 未保存配置告警测试 —— 重点是**状态型告警的去重与自动消除**。 (~1086 tok)
- `test_anomaly_version_mismatch.py` — 异常检测：堆叠成员版本不一致告警 (~693 tok)
- `test_audit_api.py` — 审计 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）。 (~3397 tok)
- `test_audit_briefing.py` — AI 专家简报测试 —— prompt 构建（纯函数）+ 调用链 + 数据装配。 (~3164 tok)
- `test_audit_scheduler.py` — 采集后自动审计（去抖）测试。 (~793 tok)
- `test_audit_trends.py` — 审计趋势端点测试 —— 周聚合、统计口径、对比榜。 (~2963 tok)
- `test_batch_api.py` — 批量执行 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）+ 假 SSH 连接。 (~2012 tok)
- `test_batch_exec.py` — 批量命令执行测试 —— 黑名单三态 + 单台执行器（mock netmiko）。 (~3034 tok)
- `test_collector_service.py` — collector_service 型号/序列号/成员ID提取测试 — 重点：Aruba CX VSF 堆叠 (~1644 tok)
- `test_collector_service.py` — extract_model/extract_serial_number 测试（重点 VSF 堆叠成员型号，4 用例） (~500 tok)
- `test_compliance_engine.py` — 配置审计引擎测试 —— 解析、判定器、站点作用域、行号契约。 (~5955 tok)
- `test_compliance_exceptions.py` — 例外登记机制测试 —— 登记表校验 + 豁免判定。 (~3137 tok)
- `test_compliance_source.py` — 审计数据源测试 —— 重点在三条边界： (~1862 tok)
- `test_config_diff.py` — running/startup 配置比对测试。 (~1673 tok)
- `test_counter_parser.py` — 端口累计计数器解析器测试 (~4010 tok)
- `test_database_migration.py` — 数据库迁移测试（重点 v10 计数器列 / v11 生成树快照表） (~4643 tok)
- `test_device_identity.py` — 设备身份助手测试（spec 第四节：物理名格式的唯一规则）。 (~560 tok)
- `test_devices_api.py` — 设备列表 API 测试：managed / physical 两个视图（HTTP 层之下直接调端点函数）。 (~590 tok)
- `test_eox_client.py` — Cisco EoX 客户端测试 —— mock HTTP（凭据到位前无法实盘验证，如实标注）。 (~1565 tok)
- `test_hardware_change.py` — 硬件变更检测测试（spec 第六节）：指纹 diff 各情形 + 事件落库 + 调拨。 (~1718 tok)
- `test_kind_filters.py` — kind 过滤纪律测试：成员行不得混入管理体视角（每类页面防漏网）。 (~1253 tok)
- `test_lifecycle_api.py` — 生命周期 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）。 (~3021 tok)
- `test_lifecycle_checks.py` — 生命周期判定器与「集体性折叠」测试。 (~2561 tok)
- `test_lifecycle_dal.py` — 设备生命周期数据层测试。 (~2272 tok)
- `test_lifecycle_status.py` — 三色状态判定测试（spec 第十三节：绿在保 / 橙临近 / 红出保） (~608 tok)
- `test_member_parser.py` — 堆叠成员级解析测试 —— 编号 / 序列号 / 版本 / ROM / 运行时间 (~3301 tok)
- `test_member_rows.py` — 成员行维护测试（spec 第五节）：成功 upsert / 失败保护 / 离线保留。 (~1072 tok)
- `test_migration_v18.py` — v18 迁移测试：设备身份模型（kind + 物理成员行） (~1306 tok)
- `test_neighbor_parser.py` — CDP/LLDP 邻居解析器测试 — 重点：Aruba AP 名识别 (~1543 tok)
- `test_performance_aruba.py` — Aruba show interface brief 解析测试 (~389 tok)
- `test_performance_counters.py` — 端口累计计数器与端口详情合并测试（PerformanceAnalyzer 接线） (~2443 tok)
- `test_port_names.py` — 端口名归一化测试。 (~660 tok)
- `test_port_roles.py` — 端口角色推断测试 —— 让「BPDU Guard 不该配在上行口」这类端口级规则可信。 (~3983 tok)
- `test_port_snapshot_write.py` — port_snapshots 落库测试 —— 重点：累计计数器列（in_octets / out_octets） (~1265 tok)
- `test_port_snapshot_write.py` — port_snapshots 落库测试 —— 重点：累计计数器列（in_octets / out_octets） (~1043 tok)
- `test_redact.py` — 凭据打码测试 —— 纪律项：发给 LLM 的文本里绝不带凭据值。 (~865 tok)
- `test_reports_api.py` — 自定义报告端点测试 —— 临时库直接调端点函数（HTTP 层之下） (~2265 tok)
- `test_retention.py` — 分层保留与归档测试 (~3006 tok)
- `test_stats_overview.py` — Dashboard 端口统计口径测试 —— Disabled 单独计数 (~952 tok)
- `test_stats_window.py` — 区间流量 Top10 周锚定测试（16 用例，**核心：周中再采一次结果完全不变**） (~1900 tok)
- `test_stats_window.py` — 区间流量 Top10 测试 —— 周锚定口径 (~2078 tok)
- `test_stp_api.py` — STP 端点集成测试 —— 临时库 + 真机样本 → 完整 JSON（HTTP 层之下） (~1658 tok)
- `test_stp_graph.py` — 站点级 STP 图构建测试 —— 纯函数 _build_stp_graph（真机样本驱动） (~3076 tok)
- `test_stp_parser.py` — stp_parser 测试 — 两个平台的真机样本（backend/tests/fixtures/） (~1610 tok)
- `test_stp_snapshot_write.py` — stp_snapshots 落库测试 —— 生成树快照（站点 STP 拓扑图的数据源） (~1391 tok)
- `test_topology_members.py` — 多设备拓扑的物理成员命名（spec 第四节：物理名统一 -N 不补零）。 (~408 tok)
- `test_uptime_parser.py` — 运行时间解析测试 —— extract_uptime_seconds（Cisco show version / Aruba boot-history） (~1040 tok)

## backend/utils/

- `config_diff.py` — running-config 与 startup-config 的差异比对。 (~1228 tok)
- `device_identity.py` — 设备身份助手 —— 物理名格式的唯一实现（spec 第四节）。 (~428 tok)
- `port_names.py` — 端口名归一化 —— CDP/LLDP/STP/配置文本之间的端口名对齐。 (~700 tok)
- `redact.py` — 凭据打码 —— 发给 LLM 之前，把配置证据里的凭据值替换掉。 (~686 tok)

## config/

- `settings.example.yaml` — NDM 全局配置模板 (~268 tok)
- `settings.yaml` (~197 tok)

## config/audit/

- `_exceptions.yaml` — NDM 配置审计 —— 例外登记表 (~283 tok)
- `_scopes.yaml` — NDM 配置审计 —— 共用段（唯一一份，所有规则文件共享） (~792 tok)
- `company-standard.yaml` — NDM 配置审计 —— 公司总部要求层（CFG-Aruba / CFG-CISCO） (~4337 tok)
- `org-convention.yaml` — NDM 配置审计 —— 组织惯例层（我们自己的使用习惯） (~1360 tok)
- `vendor-baseline.yaml` — NDM 配置审计 —— 厂商基线层（厂商加固建议） (~3207 tok)

## data/


## docker/


## docs/standards/

- `CFG-Aruba-checklist.md` — CFG-Aruba 合规检查项（公司标准简化版） (~1512 tok)
- `CFG-Cisco-checklist.md` — CFG-CISCO 合规检查项（公司标准简化版） (~2086 tok)

## docs/superpowers/plans/

- `2026-08-04-aruba-ap-recognition.md` — Aruba AP 识别实现计划 (~3717 tok)
- `2026-09-14-traffic-counter-delta.md` — 端口流量排行：改用「周锚定」累计计数器差值 (~5604 tok)
- `2026-09-20-ai-briefing.md` — AI 专家简报（二期收官）—— 设计与实施计划 (~644 tok)
- `2026-09-20-audit-trends.md` — 审计趋势与历史（二期）—— 设计与实施计划 (~889 tok)
- `2026-09-20-device-lifecycle.md` — 设备生命周期（EoL + 保修期）（二期）—— 设计与实施计划 (~1466 tok)
- `2026-09-20-exceptions-registry.md` — 例外登记机制（二期）—— 设计与实施计划 (~1236 tok)
- `2026-09-21-batch-exec.md` — 发现汇总视图 + 批量执行命令 —— 设计与实施计划 (~1318 tok)
- `2026-09-22-device-identity-model.md` — 设备身份模型 Implementation Plan（Plan 1 / 共 2 份） (~10067 tok)
- `2026-09-22-lifecycle-page.md` — 生命周期页 Implementation Plan（Plan 2 / 共 2 份） (~2946 tok)

## docs/superpowers/specs/

- `2026-08-04-aruba-ap-recognition-design.md` — Aruba AP 识别设计（2026-08-04） (~910 tok)
- `2026-09-22-device-identity-design.md` — 设备身份模型设计：逻辑名退役、物理成员成行 (~2397 tok)
- `2026-09-22-device-identity-design.md` — 设备身份模型设计：逻辑名退役、物理成员成行 (~2018 tok)

## frontend/

- `package.json` — Node.js package manifest (~421 tok)

## frontend/src/

- `App.tsx` — DRAWER_WIDTH — renders modal (~3707 tok)
- `index.css` — Stylesheet (~206 tok)

## frontend/src/components/

- `AuditExceptionDialog.tsx` — 登记例外对话框（查看器与标准页共用；到期日默认 +180 天） (~1652 tok)
- `BriefingDialog.tsx` — 极简 Markdown 渲染：标题行加粗、`- ` 列表、**加粗** —— 不引第三方依赖 (~983 tok)
- `LifecycleCard.tsx` — 设备生命周期卡片 —— EoL 与保修期（维保行三色状态，与生命周期页同源） (~3788 tok)
- `LifecycleDialogs.tsx` — 生命周期对话框 —— 详情页卡片与生命周期页**共用**（两处写同一 API）。 (~1732 tok)

## frontend/src/components/devices/

- `DeleteConfirmDialog.tsx` — 自定义提示文案；不传则用 devices.deleteWarning 并把 {name} 替换为 deviceName (~462 tok)
- `DeviceTable.tsx` — DeviceTable — renders table (~2483 tok)
- `deviceUtils.ts` — Exports getDeviceColor, getTypeLabel (~192 tok)
- `ImportDialog.tsx` — ImportDialog — renders table, modal (~2775 tok)

## frontend/src/components/topology/

- `LabeledSmoothstepEdge.tsx` — 带端点端口标签的 smoothstep 边。 (~1026 tok)
- `LocationTopologyCanvas.tsx` — NODE_H (~7754 tok)
- `PortTopologyCanvas.tsx` — 解析设备命名规范：PVGD1SWI02 → { site: "PVG", room: "D1", typeCode: "SWI", num: 2 } (~14388 tok)
- `StpTopologyCanvas.tsx` — 边的运行时数据（buildLayout 注入；finalEdges 里刷新高亮/明细态） (~6774 tok)
- `TopologyCanvas.tsx` — 判断端口拓扑是否符合三层结构：有 WAN 设备 + 中心交换机 + 终端设备 (~6637 tok)

## frontend/src/i18n/

- `en.ts` — Declares en (~10162 tok)
- `zh.ts` — Declares zh (~7637 tok)

## frontend/src/pages/

- `Alerts.tsx` — 字段中文标签映射 (~4641 tok)
- `BatchExec.tsx` — 执行队列的一项 (~7102 tok)
- `ComplianceAudit.tsx` — 与仪表盘一致的图表配色（深色主题） (~8413 tok)
- `ComplianceStandard.tsx` — 档位 → 配色，与查看器审计模式保持一致（刻意不用红色系：这是建议强度不是违规等级） (~7840 tok)
- `Dashboard.tsx` — 区间流量 Top10 —— 周锚定计数器差值算出的区间平均速率，不是瞬时速率 (~10850 tok)
- `DeviceDetail.tsx` — DeviceDetail (~6839 tok)
- `DeviceList.tsx` — 单个设备的完整收集流程（Ping → Collect） (~5680 tok)
- `Lifecycle.tsx` — 生命周期页 —— 全部物理设备（堆叠成员逐台 + 单机）一行一台。 (~4842 tok)
- `LogAnalyzer.tsx` — 严重级别 → 颜色 (数字→hex) (~7989 tok)
- `Login.tsx` — Login (~2283 tok)
- `Reports.tsx` — 两张表的默认排序：型号字母序 / 吞吐降序 (~4427 tok)
- `StpTopology.tsx` — StpTopology (~1434 tok)
- `Viewer.tsx` — 语义颜色常量 — 对应 MUI OLED Dark 主题 (~12866 tok)

## frontend/src/services/

- `api.ts` — Visio 导出 — 发送拓扑数据，返回 .vsdx 文件 Blob (~3967 tok)

## frontend/src/shared/

- `constants.ts` — 全局共享常量 — 设备颜色、图例、端点前缀 (~1793 tok)

## frontend/src/test/


## frontend/src/types/

- `index.ts` — 离线物理设备档案（device_members 表） (~3287 tok)
- `topology.ts` — 端口物理断开（status_up=0），图上显示红叉警告 (~1043 tok)

## tests/

