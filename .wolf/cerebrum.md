# Cerebrum — NDM 跨会话记忆（2026-09-22 精简版）

> 细节与逐会话原文：`.wolf/archive/`（`cerebrum-full`=803 行全文；`cerebrum-merged`=178 行合并版）。grep 它们。
> 维护：条目追加到对应章节，**禁止重开同名章节**；旧条目改在原地；单条一行。
> 归档三档（2026-09-22 整理）：`.wolf/archive/cerebrum-full-2026-09-22.md`（803 行全文）、`cerebrum-merged-2026-09-22.md`（178 行合并版）、本文件（精简版，目标 ≤10KB）；更早的逐条编辑流水在 `archive/memory-before-2026-09-22.md`（3149 行）。
> 自动记录：OpenWolf 自动 buglog **已关**（`.wolf/config.json` → `openwolf.buglog.auto_log=false`，改 true 恢复）；anatomy/memory 只收项目内文件（跨盘 `path.relative` 会回退绝对路径，判定要 `..` + `isAbsolute`）；memory.md 只留最近 500 行（滚动）。

## Do-Not-Repeat

### 工具与流程
- buglog 按 `error_message` 匹配改，**不按 id**（钩子条目会撞名）。
- bash 不写大段内容（heredoc/f-string 裸花括号/反引号）与**内联一行命令**（`$()`、引号 JSON）→ 0 字节怪文件（bug-151，11 次）；Markdown/JSON/代码用 Write/Edit；读 .wolf 用 Read 工具（别打到 GBK 控制台）；`git add` 前 `git status --short`，兜底 `%TEMP%\wolf_sweep.py`。
- 测试与提交同链：`pytest > /tmp/x.log 2>&1; echo exit=$?`（管道吃退出码）。
- 规则变更同步多处：设备名正则 3 处（前端 `parseDeviceName` / `neighbor_parser.DEVICE_NAME_RE` / `role_verifier`）；版本号 5 处（VERSION/start.bat/package.json/README/使用文档）；类型提取以 `neighbor_parser._extract_type` 为准。
- 删函数/常量前 grep；改画布前确认真实际组件（`PortTopologyCanvas` 真、`TopologyCanvas` 死）；新 i18n 键先 grep；零调用方 export 直接删。
- 新列三件套：v1 CREATE TABLE + `_migrate_vN` + **升 SCHEMA_VERSION**；迁移只在 init_db 跑（脚本前先 `init_db('./data')`）。
- `_save_data`/`_save_to_sqlite` 新参数加**末尾带默认值**；Python 默认值参数不能在无默认值前。
- 测试 `cd backend && python -m pytest tests/ -q`；前端改后必须 `npx tsc --noEmit`（vite build 不查类型）。
- NDM 脚本在**项目根**跑（`data_root: ./data` 相对路径）。
- 停后端：netstat 取 PID + `taskkill //PID X //F`（Git Bash 双斜杠）；别 `kill $!`；别 `//IM node.exe`（杀 MCP）。
- 判"是 bug"前先 grep 注释确认设计意图（双轨保留曾被误判）。
- 不为"看起来该可配置"的东西建配置层（C9500 排除规则硬编码）。
- `zip()` 展开成员字段是陷阱（member_ids 空时 0 条）→ **以序列号为主轴**。
- 迁移回填与采集写入的拆分规则逐项对齐（v18 漏 member_versions，bug-287）。

### 数据与解析
- 数据形态用程序统计判断，别看被截断的输出（栽过两次）；断言前先跑统计脚本。
- 周是 `YYYY-WW`（`2026-38`）；`{年}-{周}` 两段定序，**先排序再取前 N**；周目录严格 `^\d{4}-\d{2}$`。
- 真机输出 CRLF → 先归一化再解析（否则 `^...$` 全废）。
- 计数器列**不过 `_safe_str`**（None 落 NULL，"读到 0"与"没采到"要可分）。
- `present_regex` = **应该有**（未命中才报）；`absent_regex`/`present_flag` 才是命中即报。
- FastAPI 默认参数别用 `Query(...)`；`/{name}` 路由注册在固定路径**之后**。
- 静默失效用"异常组合探针"抓（status=unknown 却带计数器 / is_uplink 全 0 / 路由器快照 0 条）。
- 同数据多消费方同口径同改：config_diff（告警+审计）、版本不一致（报告+anomaly）、`_envelope`+`runner` 两条路径都要接线。
- OneDrive 占位文件先 `cp` 到本地再给 Python 处理。
- 验证生产用**只读**：`sqlite3 file:...?mode=ro`、`curl GET`。

## User Preferences
- 编辑字段放**编辑弹窗**（不放页面工具栏）；可点入口要显式（图标/下划线/tooltip）。
- [2026-09-22] **页面名三处统一**（用户定案"为了完美，都改"）：**侧栏标签 = 使用文档章节名 = README 用词**。定案：数据查看器/Viewer、网络拓扑图/Network Topology、端口连接图/Port Topology、告警中心/Alerts、自定义报告/Custom Reports、设备管理/Device Management、配置审计/Configuration Audit、审计标准/Audit Standards、批量执行/Batch Execution、设备生命周期/Device Lifecycle。页面 H1 与侧栏同源（`viewer.title`、`topology.title`、`topology.stpTitle`、`batch.title` 均已对齐）；改动落在 i18n（zh/en）+ 使用文档 HTML + README 三处，改名前先 grep 全部引用点。
- 侧栏导航**分组折叠**（2026-09-22 用户定案）：顶层留高频 3 项（仪表盘 / 设备管理 / 配置查看器），其余分 4 组（拓扑视图 / 审计与合规 / 监控与报告 / 资产与操作）。**当前路由所在组一律展开**（进站/跳转自动打开，避免深链进来看不到高亮）；其余组开合由点击决定、存 localStorage（键 `ndm_nav_groups`），首次进站展开第一组。否决"合并二级页"方案（要动路由与书签）。
- 报告类页面 = 扁平大表 + 位置过滤 + 列头排序 + CSV 导出；能排序就不加筛选；页面级滚动。
- 字体：业务数据正文体；程序性内容 `"Fira Code", monospace`；**画布保持等宽**（勿"顺手统一"）。
- 图表配色**按数据键**不按显示名。
- 拓扑：名为"端口连接图"；图例左侧纵排；方向键盘在 zoom 上方；设备框 名+型号+IP；连线色 WAN>核心>接入；**布局右对齐**；端点聚合标注数量。
- 位置身份 = 名字+IP（采集）；硬件身份 = 序列号+物理名 `名-编号`（画图/保修/版本）；成员必须成为 devices 行；成员号真实优先、不补零（≥10 才补）；1 成员/单机展示不带后缀。
- 版本不一致**只在同一堆叠内**报警。
- 生命周期：维保 2 月 / EoS·EoL 6 月（**日历月**）；未登记橙、`Unavailable` 红；判定在后端纯函数、前端只映射颜色；保修按**管理体**记账；EoL 是**型号级**（点型号格编辑，全型号同步）；两个编辑入口并存。
- 流量 = **周锚定**（本周最早 − 上周最早，周内锁死）；窗口 1/4/13 周；默认只上行口。
- 意图（备件/报废）人工标注，不系统猜。
- 标准 = 可视化编辑 + YAML 唯一权威；层优先级 总部>厂商>惯例（冲突时低层 `disabled`+`superseded_by` 不删）。
- 审计**建议非强制**（无 pass/fail）；导出 `status`=五档 + `severity`(shall/should/vendor/convention)；例外独立 `_exceptions.yaml`（保留可见+单列、过期自动失效、理由/批准人/到期日必填 180 天）。
- 凭据**绝不入文档/不外发**（redact 打码）；总部标准完整版只放 OneDrive，项目内放简化清单。
- 使用文档章节编号**中英连续**（英文插章 → 中文全 +1）。
- 版本号 = `2+月+日`（`2.9.21` = 2026-09-21），**不是 semver**。

## Decision Log
- 身份模型：`kind`(stack/standalone/member) + 成员行（`stack_name`+`member_no`，name 物化）；否决布尔列与全量重构（spec `docs/superpowers/specs/2026-09-22-device-identity-design.md`）；物理名唯一实现 `utils/device_identity.py`。
- 硬件变更：指纹 (platform, 型号集, SN 集, 成员数, slots) diff；成员级自动+留痕，整机级只记录；**意图不自动化**。
- 三色判定 `services/lifecycle_status.py`；颜色 `shared/constants.ts::STATUS_COLOR`；共用对话框 `components/LifecycleDialogs.tsx`。
- 生命周期双轨：Cisco EoX API（凭据未到位，手工兜底）+ Aruba 手工（无公开 API）；保修手工是主路径（SN2INFO 仅 SNTC/PSS）；数据进 DB（v16 两表，`source=api|manual`，manual 不被覆盖）。
- 审计移植 netstd 引擎；采纳《AUTOMATION-Cisco》输出契约、不采纳其 Ansible 实现；一期不扩标准源。
- 规则文件用 ruamel.yaml（`indent 2/4/2` + `width=4096` + `preserve_quotes`；跨行 why 用 `>-`）。
- 状态型告警去重 + 自动消除；事件型不折叠。
- AI 简报：判定归引擎、叙事归 AI；不喂配置原文；不落库。
- 批量执行：三层保护（静态拦截/逐台预览/二次确认）；串行、前端编排、留痕、凭据不入库。
- 采集后自动跑审计：服务端**去抖 60s**，失败隔离。
- 保留（分层）：配置文本 16 周→按月归档；DB running_config/device_logs/stp_snapshots 各留 2 次；port_snapshots/neighbors 16 周；归档不可逆要 `--dry-run`；不做 collections 行删除。
- startup-config：DB 同 running（2 次）；文件只留最新覆盖写；running/startup 比对**双轨**（`config_drift` 告警 + `ops_config_not_saved` 审计）。
- is_uplink 自动推导（STP 根端口 → 对端 SD-WAN → 描述关键词 → 手工覆盖 + LAG 展开），真机 34/36。
- 端口角色**按信号优先级分层不投票**：`vlan trunk allowed <列举>` 不是上行（电话口），`allowed all` 才是干道；判断不出的不进"拿不准"。
- 流量改造只加 2 列原始读数（`in_octets`/`out_octets`），派生值读时算。

## Key Learnings

### 采集命令（改采集前必读）
| 设备 | 端口清单 | 计数器 |
|---|---|---|
| Cisco 2960X/IOS-XE | `show interface status` | `show int counters` |
| Cisco C9500 | 同上 | 同上 **+ 排除 `Po*`/`Hu*`** |
| Cisco 路由器 | `show interfaces description` | `show interfaces stats`（Total 行 Chars In/Out） |
| Aruba AOS-CX | `show interface physical` | `show interface statistics`（**勿加** non-zero/human-readable） |

- 计数器命令**自带端口名且覆盖完整**（C9500 58=58、Aruba 52=52）→ 流量不 join 端口清单。
- `Po*` 在所有 Cisco 都是逻辑口（双计数）；排除**两侧同时做**；路由器只算父口（过滤 `:`/`.`）。
- Aruba VSF 用 `show vsf detail`（Member ID/Type=SKU/Model/Serial 逐成员），`show vsf` 无序列号；成员解析**绝不去重**。
- Cisco 成员表正则第 1 组 = 成员号；成员级软件版本只在 **classic IOS 堆叠**；C9500 SVL 特例用 onboard logging，判定按型号。
- ROM 版本在 `show version`（BOOTLDR 优先）按成员数复制；成员级运行时间只在 ≥2 成员落库（单成员回退设备级）。
- 端口名归一化 `Gi1/1/2` ↔ `GigabitEthernet1/1/2`（Tw/Twe 顺序）；Aruba `show lldp neighbor-info detail`（PORT-ID = 远端端口）。
- LAG：`show lacp aggregates` / `show etherchannel summary`；归一化 `lag14→lag 14`、`port-channel48→po 48`。
- 日志：Cisco `show logging | tail 300`；Aruba 3 字段；Cisco 时间戳无年份用收集年份补。
- STP：两平台同 `show spanning-tree`；认根比**归一化 MAC**；落库行数 = "STP Active"；同层双根桥存在。
- 驱动：Aruba CX 用 `aruba_aoscx`；`DeviceConnection` 必传 platform；Netmiko 4.6 无 look_for_keys。
- 真机回归锚点：2960X 151/150、C9500 57/48、路由器 7 父口、Aruba 52；`counters ⊆ status`。

### 审计与规则
- 现网缺口（2026-09，36 台）：Cisco `user v3` 0/18、`MGMT_ACL` 0/18、明文团体字 4 台、HTTP 未关 ~11/18；Aruba syslog/ACL/cli-session 各 0/18、dhcpv4-snooping trust 2/18。
- AOS-CX 勘误：`ssh server idle-timeout`、`snmpv3 enable` **不存在**；BPDU Guard 拼写 `bpdu-guard`；管理 ACL 要 `apply ... control-plane`（隐式 deny、路由协议留 permit、先带外验证）。
- AAA 顺序 `group X local`（先集中后本地）。
- "配套使用"是审计最值钱部分（L2 安全栈 / SNMPv3 三件套 / NTP 认证 / 日志三件套 / AAA 配套 / 802.1X / BPDU+PortFast 不上干道 / CX trust + source-lockdown）。
- 等价性回归：`git worktree add` 旧码 + 同脚本（显式设 `_db_path`）→ diff；判据 26 规则 id 过滤 **207 = 207**。
- 规则库 59 条（总部 29/厂商 21/惯例 9）；全网 ~486 命中 / 741ms；fix 已命令化（流程类 `# ` 前缀）。
- `collapse_collective`：collective 规则 ≥3 台折叠成一条；顺序 **收集→折叠→落库**。
- 趋势：每周取该周**最后一次**运行；榜图同基准；本周无运行不画。
- 例外两处易写反：**已撤销不参与匹配**；**生效中优先于已过期**；状态由日期推导。
- CUI 线索：25/36 台登录横幅自称可能含 CUI → 待合规口确认（NIST/CMMC/等保）。

### 前端与编排
- 批量收集进度用**步骤级加权** `sum(progress)/total`（React 18 批处理会让 N=2 卡死）；SSE 在 Vite 代理不可靠 → **800ms 轮询**；`setBatchStatus` 要 spread 保留字段；`_set_progress` 传当前 pct。
- `for` 循环别用 `queue.length`（预计算）；`Promise.all` 必须有 `finally`。
- Blob 下载延迟 1s revoke（先 appendChild）；CSV 三件套 = BOM + CRLF/RFC4180 + Blob 时机。
- SPA 缓存：index.html no-cache + bundle 名比对提示；`/assets/` 404 **不回落** index.html。

### 环境
- 模型**不支持图像输入**（看页面用 `--dump-dom` 或截图给用户）。
- UI 实测可注入假会话 `sessionStorage['ndm_session']`（凭据填假值、**绝不点执行**）。
- MUI multiline 两个 textarea（Playwright 用 `textarea:not([readonly])`）。
- **浏览器实测是必过关**（单测挡不住接线/真实数据形态问题）。
- OpenWolf 钩子：auto buglog 已关（`config.json` → `openwolf.buglog.auto_log`）；anatomy/memory 不收项目外文件。

## 当前状态（2026-09-22）
- **发布 2.9.22**：版本号 6 处同步（VERSION / start.bat / package.json / README 徽章 / 使用文档页头+页脚）；
  README 与 CLAUDE.md 已同步身份模型、生命周期页与三色判定唯一来源。
- 版本 **2.9.22**；schema **v18**；测试 **613 全绿**；dist 已入库。
- 生产库 61 行（12 stack / 24 standalone / 25 member）→ 物理 **49 台**。
- 使用文档：**中英章节编号已全量修正**（此前中文子标题号整体错位，如 17 章下挂 15.1）；已补
  「批量执行」「设备生命周期」两章中英各一（编号 15/16 与 33/34，其余整段顺延）；数据存储章节
  的"最多 10 个周版本"过期内容已改为分层保留。
- 待办：Cisco EoX 凭据；SNTC 确认；CUI/CMMC/等保 待合规口；生命周期数据待登记。
