# Cerebrum — NDM 跨会话记忆（2026-09-22 合并版）

> 逐会话原文（含演进过程与当时的细节）归档：`.wolf/archive/cerebrum-full-2026-09-22.md`，需要历史细节就 grep 它。
> **维护约定**：新条目按日期追加到对应章节，**不要重开同名章节**；已被后续定案覆盖的旧条目**改在原地**；单条 ≤ 3 行。

## Do-Not-Repeat

### 工具与流程
- [2026-09-22] 改 buglog **按 `error_message` 内容匹配，不能按 id** —— 钩子自动条目会与手工条目撞名（bug-151/bug-201 各撞过，已犯两次）。
- [2026-09-22] bash 里不写大段内容（heredoc / f-string 裸花括号 / 反引号）—— 会生成 0 字节怪文件（bug-151，**已 11 次**；`git add` 前必跑 `git status --short` 拦；兜底清扫脚本 `%TEMP%\wolf_sweep.py` 删根目录 0 字节文件）。**探针/仿真命令一律写成临时 .py 文件再跑，不写内联一行命令** —— 含 `$()` 替换、单引号 JSON 载荷、回显数字的批次全部中招，而 Write 工具写的脚本零复现。Markdown/JSON/代码一律用 Write/Edit；查 .wolf 文件用 Read 工具，**别 cat/python print 到控制台**（GBK 乱码同样触发）。
- [2026-09-22] 测试与提交同链时必须 `pytest > /tmp/x.log 2>&1; echo exit=$?` —— 管道会吃掉退出码（曾带病提交一次，amend 修正）。
- [2026-09-22] 规则变更要同步**多处**：设备名正则 3 处（前端 `parseDeviceName` / `neighbor_parser.DEVICE_NAME_RE` / `role_verifier._parse_device_name`）；版本号 5 处（`VERSION`/`start.bat`/`package.json`/`README` 徽章/使用文档）；类型提取 4 处（以 `neighbor_parser._extract_type` 为唯一事实来源）。漏一处就漂移。
- [2026-09-22] 删函数/常量前 grep 全仓；改前端画布前先确认**实际使用**的组件（`PortTopologyCanvas` 真、`TopologyCanvas` 是死代码）；新 i18n 键先 grep（防 TS1117 重复键）；发现零调用方的 export 直接删，不要往里加逻辑。
- [2026-09-22] 新数据库列三件套：v1 CREATE TABLE + `_migrate_vN` + **递增 SCHEMA_VERSION**；迁移只在 `init_db()` 执行 —— 跑依赖新列的脚本前先 `init_db('./data')` 把主库升到最新。
- [2026-09-22] 给 `_save_data`/`_save_to_sqlite` 加参数必须**加在末尾带默认值**（有位置传参调用点，中间插会全线错位）；Python 带默认值参数不能放无默认值参数前。
- [2026-09-22] 后端测试必须 `cd backend && python -m pytest tests/ -q`（pytest.ini 在 backend/）；前端改动必须显式 `npx tsc --noEmit`（`vite build` 不跑 tsc，存量错误见代码）。
- [2026-09-22] NDM 脚本一律**在项目根目录**跑（`settings.yaml` 的 `data_root: ./data` 是相对路径；在 backend/ 下跑会新建空库，现象极具误导性）。
- [2026-09-22] 停后端：`netstat -ano | findstr ":8002" | findstr LISTENING` 取真实 PID + `taskkill //PID <pid> //F`（Git Bash 双斜杠）；**别用 `kill $!`**；`taskkill //IM node.exe` 会误杀 MCP 服务。
- [2026-09-22] 下"这是 bug"的结论前先 grep 代码注释确认设计意图（曾把双轨保留策略误判成"落盘坏了"，被用户纠正）。
- [2026-09-22] 别为"看起来该可配置"的东西建配置层（C9500 的 `Po*`/`Hu*` 排除**硬编码** —— 单例 + 短命；先问规模与生命周期）。
- [2026-09-22] `zip()` 展开成员字段是陷阱：member_ids 为空时静默产出 0 条 → 一律以**序列号为主轴**，其余字段按数量是否对齐决定用或退回。
- [2026-09-22] 迁移回填与采集写入的拆分规则必须**逐项对齐**（v18 回填漏拆 member_versions → 报告静默丢成员级版本差异，bug-287）；写迁移时拿采集路径的拆分清单逐项核。

### 数据与解析
- [2026-09-22] 判断数据形态用**程序统计**（`Counter(len(l.split()))`），不能看被 `cut -c1-N`/终端截断的输出 —— 已栽两次（"样本行尾被截断"实为显示假象）。
- [2026-09-22] 写断言前先跑统计脚本，别照抄计划里的估计值（路由器 stats 38 节/31 子接口 vs 计划写的 39/31）。
- [2026-09-22] 周编号 `{年}-{周}` 是**两段各自定序**：先排序再取前 N 个（`2026-23` 比 `2026-13` 新）。
- [2026-09-22] 周格式是 `YYYY-WW`（`2026-38`），不是 ISO 的 `2026-W38`；周目录识别必须严格正则 `^\d{4}-\d{2}$`（否则 `2026-M09` 被当周目录）。
- [2026-09-22] 真机输出是 CRLF：解析前先 `\r\n → \n` 归一化，否则 `^...$` 锚点全部失效。
- [2026-09-22] 计数器列**绝不能过 `_safe_str`** —— None 必须原样落 NULL，这是"读到 0"与"本轮没采到"可区分的唯一保证。
- [2026-09-22] `present_regex` 语义是「该配置**应该有**」（未命中才出建议）；`absent_regex`/`present_flag` 才是"命中即报"。写规则/测试前先看 `checks.py` 的 docstring，别按名字猜。
- [2026-09-22] FastAPI 端点默认参数**别写 `Query(...)`**（直接调用测试时会传 Query 对象进 SQL）；参数化路由 `/{name}` 必须注册在批量/固定路径**之后**。
- [2026-09-22] 静默失效要靠"异常组合探针"抓，读代码看不出来：`status='unknown' 且 in_octets IS NOT NULL`（命名不一致）、`is_uplink=1` 全库 0 行（字段没传）、路由器端口快照 0 条（类型判断失效）。
- [2026-09-22] 同一份数据的多个消费方必须同口径同改：告警与审计共用 `utils/config_diff.py`；"版本不一致"比较（`api/reports.py` 与 `anomaly_detector._check_version_mismatch`）两处一起改；单台审计 `_envelope` 与全量 `runner` 两条路径都要接线（漏一条 → 单台一直报"待查"，bug-200）。
- [2026-09-22] OneDrive 占位文件：Python 可能 `PermissionError` / `PackageNotFoundError`（`isfile()` 却是 True）→ 先 bash `cp` 到本地再处理副本。
- [2026-09-22] 读运行中的实例做验证是可行的且只读：`sqlite3 file:...?mode=ro` 查库、`curl GET` 查端点 —— 不要为了验证去动生产库。

## User Preferences

### 界面与交互
- [2026-09-22] **编辑字段放编辑弹窗里，不要放页面工具栏**（生命周期页「核实人」已从工具栏移进维保弹窗，并记住本次会话上次填写）。
- [2026-09-17] 报告/数据类页面 = **扁平大表 + 位置过滤 + 列头排序 + CSV 导出**；不做分组卡片、不做 Top N 硬截断；能排序就不再加筛选下拉；表格只保留页面级滚动条（不要容器内 maxHeight 滚动）。
- [2026-09-21] 可点入口要**显式**（图标/下划线/tooltip 三选一）—— 把可点元素做成无提示纯文本按钮，用户必然找不到。
- [2026-09-21] 字体规则：业务数据（设备名/型号/序列号/IP/时间戳）用主题正文（IBM Plex Sans）；程序性内容（配置文本/命令/日志/端口名/版本号）用 `"Fira Code", monospace` 唯一合法等宽写法；**画布保持等宽不动**（用户定案，不要"顺手统一"）；禁止裸 `monospace` 与 `JetBrains Mono`。
- [2026-09-17] 图表配色按**数据键**不按显示名（i18n 文案一变就撞色）。
- [2026-06-12] 拓扑图：导航名"端口连接图"；图例在画布左侧纵排；方向键盘在左下 zoom 上方；设备框显示 名字+型号+IP；连线颜色 WAN>核心>接入；**布局右对齐**（用户 2026-06-18 定案，非居中）；端点设备聚合为一个节点标注数量。
- [2026-09-22] 生命周期页筛选/排序放前端（约 50 行量级）；**型号 EoL 保持"点型号格 → 型号级编辑"**（改一次全型号行同步）；行内编辑只提交该序列号，不动兄弟成员；两个编辑入口（详情页卡片 + 生命周期页）并存。
- [2026-06-30] 告警详情渲染中文标签键值对，不要 `JSON.stringify` 原始 JSON。
- [2026-09-17] 英文模式不留半成品 key（en.ts 缺段要补齐）。

### 数据与语义
- [2026-09-22] 位置身份 = 名字 + IP（采集/审计/告警挂它）；硬件身份 = 序列号 + 物理名 `名字-编号`（画图/保修/软件版本挂它）。
- [2026-09-22] 物理成员必须**真正成为 `devices` 行**（kind + stack_name + member_no）；配置类外键语义不变（刻意不做"-1 是主成员"约定）。
- [2026-08-31] 成员命名：真实 Member ID 优先、不补零（跳号原样）；≤9 个不补零、≥10 才补；1 成员/单机展示名不加后缀（存储名恒定）。
- [2026-09-17] 软件版本报告按物理成员展开；**只有同一堆叠内成员版本不一致才报警**（跨设备同型号差异正常）。
- [2026-09-22] 生命周期三色：维保阈值 2 个月、EoS/EoL 阈值 6 个月（**日历月**）；未登记维保 = 橙、未登记且备注 `Unavailable` = 红（出保）；EoS/EoL 两日期取最严重、全未登记 = 灰。判定在后端纯函数（唯一来源），前端只做状态→颜色。
- [2026-09-22] 保修按**管理体**记账（成员行的保修归到所属堆叠名）；生命周期数据进 DB，`source=api|manual` 且 manual 不被 api 刷新覆盖。
- [2026-09-15] 流量口径 = **周锚定**：周流量 = 本周最早一次采集读数 − 上周最早一次采集读数，**一周内锁死**；窗口 3 档 `1/4/13` 周；默认只统计上行链路（`is_uplink=1`，一条都没有才回退全部）。
- [2026-09-15] 保留策略是**分层规则不是配置项**（见 Key Learnings）；"配置取月末、流量取周初"方向相反但都对。
- [2026-09-22] 备件/报废等**意图**类信息人工标注，不要系统猜。
- [2026-09-20] 标准 = 页面可视化编辑 + YAML 存盘（规则文件唯一权威）；规则层优先级 **总部要求 > 厂商推荐 > 配置惯例**（重复只在高层写、挂 controls 溯源；冲突时低层 `enabled: false` + `superseded_by`，**不删**）。
- [2026-09-20] 审计语义：**建议非强制**，界面不出现"违规/合规分/pass-fail"；导出 `status` = 五档建议强度 + 另加 `severity`(shall/should/vendor/convention) 列。
- [2026-09-20] 例外登记：独立 `_exceptions.yaml`（不进规则文件）；**保留可见 + 单列一类**；过期自动失效 + 页内提醒（不进告警表）；理由/批准人/到期日必填（默认 180 天，不允许永久）。
- [2026-09-18] 脱敏红线：凭据值（v2c 团体字/ciphertext/各类密钥）**绝不写进文档、绝不外发**（`utils/redact.py` 按行打码，保留命令与加密类型）。
- [2026-09-18] 文档分工：总部标准完整版/配置范例只放 **OneDrive**；项目内只放简化检查清单（`docs/standards/`）；配置范例只取用户指定站点、共性写实际值、站点相关留空、密钥一律占位。
- [2026-09-20] 使用文档章节编号是**中英连续**一条序列：英文段插一章，中文段全部 +1（补章流程固化为脚本 + 编号连续性断言）。
- [2026-09-20] 版本号方案 = `2 + 月份 + 日期`（`2.9.21` = 2026-09-21），**不是 semver**。

## Decision Log

### 身份与生命周期（2026-09-22）
- 设备身份模型：`kind`(stack/standalone/member) + 物理成员行（`stack_name` + `member_no`，name 物化 `{堆叠名}-{编号}`）；否决布尔列与全量重构。spec：`docs/superpowers/specs/2026-09-22-device-identity-design.md`。
- 物理名格式唯一实现 `utils/device_identity.py`（`member_suffixes`/`physical_name`/`display_name`/`kind_from_config`）。
- 硬件变更检测：指纹 (platform, 型号集合, SN 集合, 成员数, slots) diff；成员级自动处理+留痕，整机级（平台变/SN 零交集）只记录只提示；**意图不自动化**。
- 三色判定放**后端纯函数** `backend/services/lifecycle_status.py`（可 pytest、覆盖未来第三个消费方）；颜色映射唯一处 `frontend/src/shared/constants.ts::STATUS_COLOR`。
- 生命周期双轨：Cisco EoX API（凭据未到位，手工兜底）+ Aruba 手工（**无公开 API**，已核实）；保修手工是主路径（Cisco SN2INFO 仅 SNTC 客户/PSS 伙伴）。
- 共用对话框提取到 `components/LifecycleDialogs.tsx`（卡片与页面共用，避免交互两份）。

### 审计与标准（2026-09-20）
- 移植 allright/netstd 的审计引擎进 NDM（自家项目）；**采纳《AUTOMATION-Cisco》的输出契约，不采纳其 Ansible 实现**（NDM 已有采集/存储/UI，重复建设）。
- 一期不扩标准源（三层：总部/厂商/惯例）；EoL/CVE、流程合规、例外机制记二期（例外已完成）；RFC/IEEE 作为 `why` 的技术依据而非标准来源。
- 规则文件编辑用 **ruamel.yaml**（注释是机构记忆）：`indent(mapping=2, sequence=4, offset=2)` + `width=4096`（禁折行）+ `preserve_quotes=True`；跨行 `why`/`note` 必须写 `>-` 折叠块。两道闸门测试：改一字段只许 1 行差异、全文件往返零改动。
- 状态型告警必须有去重与自动消除（`config_drift`：未处理不重复新增、恢复自动 resolve）；事件型（`config_changed`）不折叠。
- AI 专家简报：**判定归引擎、叙事归 AI**（prompt 硬约束不得新增问题/命令/日期）；不喂配置原文；发送前过 `redact`；**不落库**；LLM 不可用给可读 400。
- 批量执行边界：可下发配置 + **三层保护**（危险命令静态拦截以服务端为准 / 逐台预览 / 配置模式二次确认）；串行、**编排在前端**、留痕落库、凭据绝不入库；保存配置默认不勾。
- 采集后自动跑审计：服务端**去抖**（每台成功重置 60s 定时器，静默后跑一轮）；失败隔离是硬要求；开关 `settings.yaml → audit.run_after_collect`。

### 数据与保留（2026-09-15）
- 流量改造：只加 2 列**原始读数**（`in_octets`/`out_octets`），派生值读时算；窗口增减是纯前端 + 一个查询参数的事。
- 分层保留（用户确认）：
  | 对象 | 规则 |
  |---|---|
  | 配置文本文件 `running-config.raw` | 最近 **16 周**按周；更早按月收缩（该月**最后一个**版本移入 `archive/{Y}-M{MM}/`，其余删） |
  | DB `collections.running_config` / `device_logs` / `stp_snapshots` | 最近 **2 次** |
  | `port_snapshots` / `neighbors` 等 | **16 周** |
  - 动机是**可查看性不是省空间**（约 140 MB/年：running 76 + logs 47 + port_snapshots 13）；归档不可逆 → 必须 `--dry-run`；在采集结束时触发，>16 周才动作；不做 `collections` 行删除（7 张表外键挂它，无 CASCADE）。
- startup-config：DB 与 running 同策略（2 次）；**文件只留最新一份覆盖写**（变化极少）；running/startup 比对做**双轨**（即时告警 `config_drift` + 审计项 `ops_config_not_saved`），消费方共用同一套归一化。
- `max_versions: 10` 已移除（原读取函数零调用，且 10 周 < 最大窗口 13 周）；`CONFIG_KEEP` 不能 < 2（变更检测要"倒数第二次"）。
- is_uplink **自动推导**：多层站点用 STP 根端口、单机站点用对端 SD-WAN 的 LAN 口；刻意不把"对端是交换机"算上行；聚合口要展开。真机 34/36 台（原手工字段仅 4 台）。
- 端口角色推断**按信号优先级分层，不做信号投票**：`vlan trunk allowed <列举>` 不是上行信号（现网 214 处其实是电话口）、`allowed all` 才是干道；弱信号不能推翻强证据（CDP 报 SD-WAN 的 access 口）；完全判断不出的**不进"拿不准"清单**。

## Key Learnings

### 采集命令（真机验证；改采集前必读）
- 四类设备的端口清单/流量计数器：

  | 设备 | 端口清单 | 流量计数器 |
  |---|---|---|
  | Cisco 2960X / IOS-XE | `show interface status` | `show int counters` |
  | Cisco **C9500** | 同上 | 同上 **+ 排除 `Po*`/`Hu*`** |
  | Cisco **路由器** | `show interfaces description`（`show interface status` 在路由器上返回空） | `show interfaces stats`（取 `Total` 行 Chars In/Out） |
  | **Aruba AOS-CX** | `show interface physical`（`brief` 会把 lag/vlan 一起列） | `show interface statistics`（**绝不能加** `non-zero`/`human-readable`） |
- [2026-09-15] 计数器命令**自带端口名且覆盖完整物理口**（C9500 58=58、Aruba 52=52）→ 流量路径不 join 端口清单，索引错位那类 bug 从根上消失。
- [2026-09-17] `Po*` 在**所有** Cisco 平台都是逻辑口（计数器=成员聚合，双计数）；排除必须**两侧同时做**（`is_excluded_port` + `_parse_cisco_ios` skip_prefixes）；路由器只算父口（过滤 `:` 与 `.`，两侧都过滤）。
- [2026-08-31] Aruba VSF：`show vsf detail`（逐成员 Member ID / Type=SKU / Model=系列名 / Serial Number）；`show vsf` 无序列号。成员级型号/SN 必须从这里解析；**绝不去重**（1:1 对齐）。
- [2026-09-17] Cisco 堆叠成员表 `_CISCO_MEMBER_TABLE_ROW` **第 1 组 = Switch 成员号**；逐成员软件版本只在 **classic IOS 堆叠**有（IOS-XE 成员段无版本列，bug-123 待真机确认 `Mode` 列）；Aruba 成员级唯一逐成员字段是 **ROM Version**。
- [2026-09-18] C9500 **SVL 是特例**（无成员表/无 Switch Uptime）：用 `show logging onboard switch active|standby RP active uptime` 取；判定按**型号**（platform 与 C9200L 共用区分不开）。
- [2026-09-18] Cisco ROM/引导版本在 `show version`（`BOOTLDR:` 优先）；只报主交换机 → 解析后按成员数复制；2960X 的 `ROM:` 行无版本号要跳过。
- [2026-09-22] 成员级运行时间只在 ≥2 成员时落库 → 报告侧对**单成员**设备回退设备级 uptime；多成员拿不到就留空（复制设备级是错的）。
- [2026-06-22] CDP/LLDP 端口名归一化：`Gi1/1/2` ↔ `GigabitEthernet1/1/2`（`_normalize_port_name` 统一短名再去重）；Cisco 25G 有 `Tw`/`Twe` 变体（映射顺序：`Twe` 在 `Tw` 之前）；Aruba 用 `show lldp neighbor-info detail`（分块解析，PORT-ID 就是远端端口）。
- [2026-07-27] LAG 成员关系：Aruba `show lacp aggregates` / Cisco `show etherchannel summary`；端口名归一化 `lag14→lag 14`、`port-channel48→po 48`。
- [2026-07-01] 日志：Cisco `show logging | tail 300`（已恢复收集）；Aruba 是 3 字段格式（Cisco 4 字段）；Cisco 时间戳无年份 → 用收集时间年份补全；按上次 `collected_at` 去重。
- [2026-09-17] STP：两平台同一条 `show spanning-tree`；**跨厂商认根必须比归一化 MAC**（不比优先级数值）；落库行数 = 真机 summary 的 "STP Active" 列；同层双根桥真实存在（后端按角色定向 + 前端底部下弧线）。
- [2026-05-13] 驱动：Aruba CX（6300/6400/8320/8xxx）用 `aruba_aoscx` 驱动、提示符 `#`；`DeviceConnection` 必须传 `platform`；Netmiko 4.6.0 已移除 `look_for_keys`/`allow_agent`；`terminal length 0` 在 connect 时发一次即可。
- [2026-09-15] 真机基数锚点（回归用）：2960X **151/150**、C9500 **57/48**、路由器 **7 父口**、Aruba **52**；`counters ⊆ status` 恒成立。累计计数器会出现"链路已断但读数巨大"（正常，新口径下周差值为 0 自然出局）。

### 数据模型与迁移
- [2026-09-22] **v18**（身份模型）：devices 加 `kind`/`stack_name`/`member_no`，物理成员成为行；生产实测 36 → **61 行**（12 stack / 24 standalone / 25 member），物理设备 **49 台**（成员 25 + 单机 24），幂等。
- [2026-09-17] **v12** 成员级三列（`member_versions`/`member_rom_versions`/`member_uptimes`，与 serial 同序）；**历史不可回填**（`show version` 原文不入库）→ 修解析逻辑要重新采集才见效。
- [2026-09-20] v13 startup_config、v15 例外快照与 runs 指纹、v16 `device_lifecycle`+`eol_models`、v17 `batch_runs`/`batch_results`。
- [2026-09-22] `devices.serial_number`/`model` 是**逗号拼接的成员串**（`SG30LMQ17K, SG30LMQ108`）；`lifecycle_dal.split_serials()` 拆分、大写归一化匹配（保修台账按管理体记账）。
- [2026-09-15] 配置在 DB 里**也存一份全文**（`collections.running_config`，约占 DB 53%），`config_changes` 变更检测用的就是 DB 那份不是文件。
- [2026-07-07] 采集写 SQLite **不回写 YAML**；`device_dal.py` 是唯一数据源；`list_managed()`/`list_physical()` 是 devices 查询的两个入口（**禁止新代码裸查 devices**）；`get_all_devices()` 是 list_managed 的兼容别名。
- [2026-09-22] `port_snapshots.member_no` 已落库（成员级端口查询的数据基础）。
- [2026-06-30] `alerts.py`/`reports.py`/`topology.py`/`data.py`/`stats.py` 均已切 SQLite（原双轨文件系统 → 库）。

### 审计与规则
- [2026-09-18] **现网实测缺口（2026-09 最新采集，36 台）**：Cisco `snmp-server group v3` 18/18 但 `snmp-server user` **0/18**（SNMPv3 实际不可用，头号必报）；4 台明文团体字（1 个 RW）；`MGMT_ACL` 0/18；`logging host` 10/18、`logging source-interface` 1/18；明文 HTTP 未关约 11/18；`exec-timeout 15 0` 18/18 达标；NTP 全内部源但只配 1 台。Aruba：syslog **0/18**、任何 ACL **0/18**、`cli-session` **0/18**、`dhcpv4-snooping` 13/18 但 trust **仅 2/18**、7 台混配公网 NTP。
- [2026-09-18] **AOS-CX 命令勘误**：`ssh server idle-timeout` **不存在**（CLI 空闲超时在 `cli-session` 上下文 `timeout <分钟>`）；`snmpv3 enable` **不存在**（用 `snmp-server vrf` / `snmp-server snmpv3-only`）；BPDU Guard 官方拼写 `spanning-tree bpdu-guard`；管理 ACL 必须 `apply access-list ip X control-plane vrf Y`（**末尾隐式 deny** → 路由协议要预留 permit；**先在带外 mgmt VRF 验证再配 default**，避免自我锁死）；SNMPv3 改算法必须同时指定 `access-level ro`。
- [2026-09-18] CFG-CISCO 基线是 **NX-OS 为主**（现网 18 台 Cisco 全是 IOS/IOS-XE，零 Nexus）→ 检查必须同时认两种命令形式，IOS 侧命令要自己补。
- [2026-09-20] AAA 方法列表顺序：`group X local`（先集中后本地）；现网两种顺序并存是真实偏离。
- [2026-09-18] "厂商配套使用"是审计最值钱的部分：L2 安全栈（DHCP snooping→DAI→IPSG）、SNMPv3 三件套（view+group+user）、NTP 认证三件套、日志三件套、AAA 配套（含"本地账号必须存在"）、802.1X 三件套、BPDU Guard+PortFast 且**不上行/干道**、CX `dhcpv4-snooping trust` + `ipv4 source-lockdown`。
- [2026-09-20] **等价性回归做法**：`git worktree add <tmp> HEAD` 拉改动前代码 → 同一脚本（显式设 `dbmod._db_path` 指向主库、不走 init_db）两侧跑 → diff JSON。判据：按 netstd 原 26 条规则 id 过滤 **207 = 207**（规则库扩充不影响这条回归）。
- [2026-09-20] 规则库 59 条（总部 29 / 厂商基线 21 / 组织规范 9）；全网 36 台约 486 命中、741 ms；规则 `fix` 已**全面命令化**（流程类首行 `# ` 前缀，`split_commands` 跳过；占位符保留，未替换时给黄警）。
- [2026-09-20] `collapse_collective`：`collective: true` 的规则全网命中 ≥3（阈值）折叠成一条网络级条目（`device_name='全网'`）；runner 顺序固定 **先收集 → 折叠 → 落库**。
- [2026-09-20] 趋势口径：每周取该周**最后一次**运行；榜与图同基准；本周无运行不画该周；建议数 = 未豁免 findings（`json_extract(exempt_json,'$.status')` 排除 active/expiring）。
- [2026-09-20] 例外两处守卫最易写反：**已撤销的不参与匹配**（设备级撤销后站点级重新生效）；**生效中优先于已过期**。状态由日期**推导**不存字段。
- [2026-09-20] CUI 线索：现网 25/36 台登录横幅自称可能承载 CUI（NIST 800-171/CMMC 可能成硬要求；中国站点还可能要等保 2.0）—— **待用户向合规口确认**，是"要不要加合规框架"的关键线索。

### 前端与采集编排
- [2026-09-15] 批量收集进度：React 18 auto-batching 让 N=2 时进度条卡死 → 改为**步骤级加权** `overallPct = sum(progress)/totalCount`（每台 SSE/轮询实时汇总）；SSE 在 Vite 代理下不可靠（缓冲流式响应）→ 改 **800ms 轮询** `GET /progress/{name}`；`setBatchStatus` 必须 spread `prev[name]` 保留字段；`_set_progress(...)` 必须传当前 pct（默认 0 会让进度回退）。
- [2026-07-02] `for` 循环里 `queue.length` 每次迭代重求值（`shift()` 递减）→ **预计算** `const n = queue.length`；`try { await Promise.all() }` 必须有 `finally` 清 running（否则 UI 永久卡死）。
- [2026-06-10] 下载 Blob：`URL.revokeObjectURL()` 不能紧跟 `a.click()`（要先 `appendChild` 再延迟 1s 释放）；CSV 导出三件套 = 前置 BOM（Excel 中文）+ CRLF/RFC4180 + Blob 时机。
- [2026-09-18] SPA 缓存：`index.html` 一律 `no-cache`；前端比对自身 bundle 名与 `/index.html` 引用不一致时弹"已更新"提示（focus + 5 分钟轮询）；`/assets/` 404 **不回落** index.html（回退会把 HTML 当 JS 交付）。
- [2026-06-10] 设备批量导入 CSV：`POST /devices/batch-import` + 模板端点（路由必须在 `/{name}` 之前注册）；重名跳过不覆盖。
- [2026-07-23] PNG 导出（暗色画布）：Emotion 的 boxShadow 无法内联覆盖；`html-to-image` 的 `includeStyleProperties` 白名单是终极方案（要含 100+ 属性、排除 box-shadow/text-shadow 反而用于"无发光"场景——需要发光时要显式保留）；SVG 序列化读的是 `getAttribute('style')` 属性串。
- [2026-07-16] VSDX 导出：颜色用 `#rrggbb` 是对的（旧诊断有误）；程序生成的 VSDX 被 Visio 严格校验（Cell 名要对）；对照 `bpmn-to-visio` 结构；Visio Y 轴自下而上需翻转；1-D Shape 用 BeginX/EndX 定位。
- [2026-06-07] ReactFlow 要点：自定义节点 Handle 必须是节点直接子元素（不能嵌绝对定位 Box 内）；节点必须含 `<Handle>`（哪怕 hidden）；`useReactFlow` 需要 `ReactFlowProvider`；`nodesDraggable` 与 `panOnDrag` 冲突（关前者）；`fitView` prop 与交互冲突 → 受控 `useEffect` 替代；Vite 8 + emotion 11.14 不兼容（降级 Vite 7.2.7 + emotion 11.13.5）。
- [2026-06-13] 端口连接图三步规则（布局三层折叠 / Handle 上下两排 / 管道+`buildRoundedPath` 半径 12 / 过滤 LAG+自身+堆叠线）与 `LocationTopologyCanvas` 遗留问题（Handle 匹配、多条边多 Handle、切站 fitView remount）——细节见归档原文。
- [2026-08-17] 版本号禁止写死；`VERSION` 文件是唯一事实来源（后端 `GET /api/version`，前端动态显示）。

### 环境与工具
- [2026-08-17] 当前模型**不支持图像输入**（read_image 失败）：看页面用 Playwright `--dump-dom` 或截图给用户看。
- [2026-09-21] UI 实测可注入假会话：`sessionStorage.setItem('ndm_session', ...)`（后端端点不校验会话）——**凭据填假值、绝不点"开始执行"**（会真连生产设备）。
- [2026-09-21] MUI multiline 渲染两个 textarea（第二个是隐藏测量元素）→ Playwright 用 `textarea:not([readonly])`。
- [2026-09-21] 浏览器实测是这类功能的必过关卡：纯单测全绿挡不住"接线/真实数据形态"问题（`is_uplink` 字段名、聚合口展开都是真机才暴露）。
- [2026-09-22] OpenWolf 钩子现状（本次整理后）：自动 buglog **已关**（`.wolf/config.json` → `openwolf.buglog.auto_log=false`，要恢复改 true）；anatomy/memory 不再收录**项目外**文件（跨盘 `path.relative` 会回退绝对路径，判定要 `..` + `isAbsolute` 两条）；anatomy 是"读文件前先查"的索引，memory.md 是逐条编辑流水（收尾只读尾部）。
- [2026-09-20] 报告/长文本：`git diff` 里中文在 GBK 控制台显示乱码 → 用 Read 工具看，不要 `sys.stdout` 打中文。

## 最近会话
- **2026-09-21（三期）**：审计发现汇总视图（`/by-rule` 按规则聚合 + 现状参照带入）+ **批量执行页** `/batch-exec`（选设备→命令→预检→二次确认→队列→留痕）+ fix 全面命令化 + 未替换占位符警示 + 发布 **2.9.21**。测试 550 项。
- **2026-09-22（身份模型 + 生命周期页）**：Plan 1 身份模型 14 任务（kind/成员行/物理名统一/硬件变更指纹/v18 迁移/统计双口径/拓扑 `-N`）；Plan 2 生命周期页 5 任务（三色纯函数 → 物理清单 API → 新页面 + 导航 + i18n → 卡片同源 → 验收）。提交链 `66b1789`…`6a64aae` + 后续（`5807235`/`8988747` 核实人进弹窗、`cd35ab5`/`cc40693` 狼记整理）。测试 **613 全绿**。

## 当前状态（2026-09-22）
- 版本 **2.9.21**；schema **v18**；后端测试 **613 全绿**；前端已构建入库（`frontend/dist`）。
- 生产库：devices **61 行**（12 stack / 24 standalone / 25 member）→ 物理设备 **49 台**；生命周期状态分布：维保 missing 36 / ok 7 / expired 6；EoL none 40 / soon 1 / expired 8。
- 待办：① Cisco EoX 凭据（未到位，型号 EoL 走手工）；② SNTC 订阅待确认（决定保修能否自动化）；③ **CUI/CMMC/等保** 待用户向合规口确认；④ 生命周期数据待登记（Aruba EoL + 各家保修，走批量导入）；⑤《NDM用户使用文档》「批量执行」章节未补。
