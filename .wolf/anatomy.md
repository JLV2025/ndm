# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-08-31T06:35:31.055Z
> Files: 29 tracked | Anatomy hits: 0 | Misses: 0

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

- `README.md` — Project documentation (~1434 tok)

## .claude/


## .claude/plans/


## .claude/rules/


## .claude/skills/port-topology-canvas/


## .claude/skills/work-wrap-up/


## .claude/skills/天龙五步/


## .gitnexus/


## C:/Users/jingl/.claude/


## C:/Users/jingl/.claude/plans/

- `silly-weaving-hearth.md` — VSF 成员编号透传 + 物理设备档案 + 离线设备视图 实施计划 (~1286 tok)

## agents/


## backend/

- `_verify_version.py` — 临时验证脚本：检查 FastAPI 应用版本号动态读取（验证后删除） (~76 tok)
- `main.py` — API: 3 endpoints (~1274 tok)

## backend/analyzers/

- `neighbor_parser.py` — CDP / LLDP 邻居解析器 (~6462 tok)

## backend/api/

- `devices.py` — 设备管理 API 路由 — SQLite 唯一数据源 (~3287 tok)
- `topology.py` — 拓扑图 API 路由 (~11910 tok)

## backend/collectors/


## backend/models/


## backend/scripts/


## backend/services/

- `collector_service.py` — 配置收集服务 (~16453 tok)

## backend/storage/

- `database.py` — init_db, get_connection, close_connection (~4484 tok)
- `device_dal.py` — get_all_devices, get_device_by_name, device_exists, create_device (~1851 tok)

## backend/tests/

- `conftest.py` — test_password_manager (~78 tok)
- `test_collector_service.py` — collector_service 型号/序列号/成员ID提取测试 — 重点：Aruba CX VSF 堆叠 (~1644 tok)
- `test_collector_service.py` — extract_model/extract_serial_number 测试（重点 VSF 堆叠成员型号，4 用例） (~500 tok)
- `test_neighbor_parser.py` — CDP/LLDP 邻居解析器测试 — 重点：Aruba AP 名识别 (~1543 tok)

## backend/utils/


## config/


## data/


## docker/


## docs/superpowers/plans/

- `2026-08-04-aruba-ap-recognition.md` — Aruba AP 识别实现计划 (~3717 tok)

## docs/superpowers/specs/

- `2026-08-04-aruba-ap-recognition-design.md` — Aruba AP 识别设计（2026-08-04） (~910 tok)

## frontend/

- `package.json` — Node.js package manifest (~421 tok)

## frontend/src/


## frontend/src/components/


## frontend/src/components/devices/

- `deviceUtils.ts` — 判断设备是否为堆叠设备 (~802 tok)

## frontend/src/components/topology/

- `LabeledSmoothstepEdge.tsx` — 带端点端口标签的 smoothstep 边。 (~1026 tok)
- `LocationTopologyCanvas.tsx` — NODE_H (~7754 tok)
- `PortTopologyCanvas.tsx` — 解析设备命名规范：PVGD1SWI02 → { site: "PVG", room: "D1", typeCode: "SWI", num: 2 } (~14392 tok)
- `TopologyCanvas.tsx` — 判断端口拓扑是否符合三层结构：有 WAN 设备 + 中心交换机 + 终端设备 (~6637 tok)

## frontend/src/i18n/


## frontend/src/pages/

- `Dashboard.tsx` — DevicesLink (~10191 tok)
- `DeviceList.tsx` — 单个设备的完整收集流程（Ping → Collect） (~5901 tok)
- `Login.tsx` — Login (~2283 tok)

## frontend/src/services/

- `api.ts` — Visio 导出 — 发送拓扑数据，返回 .vsdx 文件 Blob (~1907 tok)

## frontend/src/shared/

- `constants.ts` — 全局共享常量 — 设备颜色、图例、端点前缀 (~1414 tok)

## frontend/src/test/


## frontend/src/types/

- `index.ts` — 离线物理设备档案（device_members 表） (~637 tok)
- `topology.ts` — 端口物理断开（status_up=0），图上显示红叉警告 (~540 tok)

## tests/

