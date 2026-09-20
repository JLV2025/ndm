# NDM 配置审计（资深专家评审）—— 实施计划

## Context（背景与目标）

公司网络团队已有 `F:\projects\allright\netstd`（用户自有项目）：一套 **Cisco/Aruba 配置加固检查器** ——
26 条定稿规则 + 12 个判定器 + 75 条研究级厂商基线，跑过 35 台现网配置、产出 211 条建议。
但它与 NDM 割裂：数据靠目录文件、自带一个 stdlib 网页、规则只能改 YAML 文本、结果不落库。

**要达到的效果（用户定调）**：

> 「把设备的配置发给我们公司一位资深网络工程专家，他会结合公司的要求、惯例、业界标准、业界推荐，给建议。」

所以验收标准不是"N 条规则命中"，而是输出**像一位资深网络工程师看过这台设备后的评审意见**：

| 专家会做的事 | 功能里对应的设计 |
|---|---|
| 先搞清"这台设备是什么、在哪、干什么用" | 设备上下文分族：平台（CX/Cisco）× 角色（接入/核心/路由器）× **站点适用域**（OSAT 六站 + BJD 豁免 VLAN/地址类）× 型号/版本 |
| 看配置本身是否缺配套、自相矛盾 | **组合规则**：`all_of`（命令组必须齐备，缺项点名）· `requires`（有 A 必须有 B）· `conflict`（有 A 不该有 B）· **端口级作用域**（NDM 独有：用 neighbors + STP 角色 + 聚合 + 描述判端口角色） |
| 拿同族设备横向比 | **现网共识/离群**：同平台同角色机群里本机缺什么；全网普遍缺什么 → **集体性漏配**单独成类，不产生 18 条重复 |
| 结合公司规范 | 规则分两层来源：**公司规范**（命名/VLAN/网段，7 条）+ **厂商基线**（官方 + STIG/CIS，19 条起） |
| 抓重点、不数芝麻 | 档位 = 强烈建议 / 风险提示 / 改进建议 / 可选优化 / 需人工判断（**保持"建议非强制"，不打合规分、不进告警表**）；同主题多处问题**聚合成一条** |
| 给可执行的整改动作 | 每条给**可复制修复命令** + 前置条件/副作用提示 + 如何验证（show 命令） |
| 会说"这条你得确认" | 忽略 / 已确认 / 例外机制（二期）；无法静态判定的归「需人工判断」 |

**判定一律由确定性规则引擎做**（可审计、零幻觉）；AI 只负责"讲成人话"（二期，复用日志分析的 LLM 配置与脱敏）。

## 用户已定案（2026-09-18）

| 决策点 | 定案 |
|---|---|
| 标准的形态与编辑 | **页面可视化编辑 + YAML 存盘**（规则文件为唯一权威，`config/compliance/*.yaml`，git 可追踪）：按来源/平台/档位分组、启停、字段表单编辑、新增、加例外；保存前校验 + 原子写入 + 备份 |
| 审计触发与存储 | **按需 + 全量入库**：查看器点「审计」即时算；一键「全网审计」结果入库（趋势二期）；采集后可选自动跑 |
| 一期范围 | **标准页 + 查看器审计**（含引擎移植、规则库、按需审计、全量入库基础链路） |
| AI 专家简报 | **二期** |

**保持既有决策不翻案**：不采纳项（SNMP 团体字绑 ACL、Cisco 远程 syslog、enable secret 逐台独立、https/ssh 收敛 mgmt VRF）不上线；
挂起项（NTP 认证、password complexity、登录锁定、DAI、vty access-class、login block-for、CX 远程 syslog 等）
**只作为配套组的一部分出现**（如"配了 DAI 才检查 DHCP snooping 配套"），避免 18 台 × N 条的噪声。

## 一、规则库：两层来源 + 配套组合

**现有 26 条已天然分层**（可直接沿用）：

- **公司规范（7 条）**：设备名格式、hostname 与设备名一致、VLAN 名纯用途、非标 VLAN ID、SVI 第三段=VLAN ID、VLAN 1 是否真在用、allow-fail-through 保留（缺才提示）。
- **厂商基线（19 条）**：VSF 脑裂检测、enable password 禁用、明文 Web 关闭、vty 仅 SSH、BPDU Guard（Cisco/CX）、DHCP snooping（Cisco/CX）、storm-control、no ip source-route、SNMPv3 用户、REST 只读、Telnet 关闭、Smart Install 关闭、banner motd、enable secret type8、port-security（Cisco/CX，仅 ZGN）、移除 service password-encryption。

**本次新核实的"配套"关系**（已查互联网 + 用现网配置验证，用于二期扩规则；一期把组合判定器做出来）：

| 配套 | 要点 | 现网实测（NDM 库，2026-09-18） |
|---|---|---|
| Cisco L2 安全栈 | DHCP snooping（建绑定表）→ DAI → IP Source Guard，后两者依赖绑定表；上联口 trust、非信任口 rate limit、绑定表持久化 | `ip dhcp snooping` 1/18、DAI 0、IPSG 0 |
| Cisco SNMPv3 三件套 | view + group v3 + user v3 **缺一不可** | group **18/18** 但 user **0/18** → 有组无用户，实际不可用 |
| Cisco NTP 认证三件套 | authentication-key + trusted-key + authenticate | 0/18 |
| Cisco 日志三件套 | logging host + logging trap + service timestamps（show-timezone msec） | 10/18 vs 18/18 |
| Cisco BPDU Guard | 与 PortFast 配套用于**接入口**，不应出现在上行/干道口；errdisable recovery 决定能否自恢复 | 全局 2 + 逐口 11 = 13/18；errdisable 8/18 |
| Cisco AAA 配套 | tacacs server + group + 方法列表以 `local` 结尾 + **本地账号必须存在**（否则锁死）+ 防爆破 | 见 STANDARD.md 7.2 |
| Cisco 802.1X 三件套 | aaa authentication dot1x + dot1x system-auth-control + 接口 port-control auto | — |
| Cisco SSH | `ip ssh version 2` + RSA 密钥（审计基线 2048）+ transport input ssh | ip ssh version 2：15/18 |
| CX DHCP 防护 | dhcpv4-snooping + **上联口 trust** + 绑定库持久化；`ipv4 source-lockdown` 要求绑定库已填充 | snooping 13/18、**trust 仅 2/18** ← 典型"配了一半" |
| CX BPDU Guard | 官方命令 `spanning-tree bpdu-guard`（"bpdus-guard" 是误传，现网 0/18 佐证），可带 timeout；只配接入口 | bpdu-guard 9/18、loop-protect 17/18 |
| CX 管理面 | REST 只在配了 `https-server vrf <x>` 的 VRF 可用；rest access-mode read-only；cli-session timeout | rest read-only 13/18 |

**NDM 独有增强**：端口角色可交叉验证 —— `neighbors`（CDP/LLDP，36 台全有）+ `stp_snapshots`（STP 角色）
+ 端口通道成员 + 描述关键字 + `devices.uplink_ports` → 让"BPDU guard 不该出现在上行口""DHCP snooping trust 只应在上联口"这类**端口级配套规则**真正可达（netstd 做不到）。

## 二、引擎移植：数据契约与改造点（已核实）

**好消息**：证据 `evidence: [{line, text}]` **已带行号**；`analyze(name, text, std) -> dict` 是"字符串进、dict 出"，
NDM 从库里取名字 + 配置文本直接调即可，**不用**它的 HTTP 服务与前端。

**改造点清单**（源：`F:\projects\allright\netstd`）：

| # | 位置 | 改什么 |
|---|---|---|
| 1-2 | `analyze()` / `parse_device()` | **增加显式 site/location 入参**（现 `dev.site` 只由设备名套 naming 正则派生；NDM 以 `devices.location` 为准，正则兜底） |
| 3-4 | `parse_device()` VLAN/块解析 | `vlans[vid]` 补 `name_line`；块补 `end` 行号（标红区间用） |
| 5 | `_finding()` | 补 `lines` 汇总字段（去重排序行号）—— 前端标红的契约 |
| 6-7 | `check_vlan1_in_use` / 两个命名判定器 | 去掉证据截断；`line:0` 改真实行号 |
| 8 | `_applies()` | `exempt_sites` 只取 `exempt[0]` 的缺陷；统一 `only_sites`（字面站点）与 `exempt_sites`（分组名）语义 |
| 9 | `CHECKS` + 新判定器 | **组合规则**：`params` 已是自由 dict，加 1-2 个通用判定器（`{present, require}`、`{all_of:[…]}`），守卫式仿 `vsf_split_detect` |
| 10 | `--batch` / `_print_report` | 不搬（NDM 循环调 `analyze()`） |
| 11 | 报告渲染（原在前端 JS） | NDM 服务端重实现（Markdown/HTML 导出）+ 行号标红 |
| 12 | 规则保存 | 现校验很薄 → 补 level 枚举、platforms、params 与 check 匹配、站点分组存在性；**原子写入 + 备份** |
| 13 | `GET /api/rules` 投影 | 现丢 `params/note/exempt_sites`，规则编辑器不能用 |
| 14 | `Device.lines` | 由 `splitlines()` 改 **`split("\n")`** —— 与前端完全同源；实测 **18/36 台配置以换行结尾**，两种分行差一个尾部空元素（索引仍对齐，但行数显示差 1，且前端若顺手 `.filter(Boolean)` 就全错位） |
| 15 | `_finding()` 的 `line:0` | 统一改 `line: None` + **`locatable: bool`**（涉及 `check_device_name_format` / `check_hostname_match`） |
| 16 | `_matches()` | 加 `functools.lru_cache` 正则编译缓存（原实现每设备重复编译） |
| 17 | `check_enable_secret_type` | 去掉硬编码 `enable secret 5`，改由 `params.pattern` 驱动 |
| 18 | 端口名归一化 | `_CISCO_PORT_SHORT` / `_normalize_port_name` 现为 `collector_service.py:_save_data` 内的**嵌套闭包**，外部不可导入 → 抽到 `backend/utils/port_names.py`（**本任务唯一触及既有采集代码的重构**，必须 238 项测试全绿） |

**两个"别踩"的事实**（Plan agent 实测）：`devices.type` 是 Netmiko 驱动名（`aruba_aoscx`/`cisco_ios`/`cisco_ios_router`），
**不是命名规范里的 SWI/RTW/QIS** —— 命名类规则只能从**设备名**解析；`devices.platform` 有 4 种取值
（aruba_aoscx 18 / cisco_ios 14 / cisco_ios_router 3 / cisco_ios_xe 1），与规则的 `platforms: [cx|cisco]` 不是同一套枚举
→ 平台判定仍以**配置文本**为准，`devices.platform` 只做交叉校验。

另：`rules/standard.yaml` 里 `default_present`/`in_use_requires`/`resource_type`/`wifi_*`/`address_pattern`/`segments`/`site_codes`
**写了但引擎不消费** → 移植时要么实现、要么删掉。

## 三、实施步骤（分期，每期可独立验证）

### 第一期：引擎 + 规则库 + 标准页 + 查看器审计

**A. 引擎移植与改造（后端）**
1. 新建 `backend/analyzers/compliance/`：`engine.py`（移植 + 上表 13 处改造）、`checks.py`（12 + 组合判定器）、`loader.py`（规则加载 + 校验）。
2. 规则文件：`config/audit/` 下三个 —— `_scopes.yaml`（**共用段唯一一份**：meta/sites/naming/vlans，避免两处各写站点表导致漂移）
   + `vendor-baseline.yaml`（厂商基线）+ `company-standard.yaml`（公司规范）；加载器按固定顺序合并、每条注入 `source_file`（决定保存时写回哪个文件）；
   **启停 = 规则里的 `enabled: true|false` 字段**（写回 YAML，不引入 DB 状态位）。
3. 数据源：新增 `backend/analyzers/compliance/source.py`，取「最新一次采集的 running-config」
   （`collections.running_config`，`ORDER BY collections.id DESC`；跳过采集失败文本 `% 收集失败:`）。
4. 组合判定器：`check_group_all_of`（命令组齐备，缺项点名）、`check_requires`（有 A 必须有 B）、`check_conflict`（可选，端口级）。
5. 端口角色：新增 `port_roles.py`（neighbors + stp_snapshots + lag 成员 + description → uplink/access/unknown），供端口级规则使用（一期先只做判定函数 + 单测，规则可后接）。

**B. 存储（v13 迁移）**（Plan agent 修正：审计结果**自包含**，不引用会被保留策略清空的配置全文；启停不引入 DB 状态位）
6. `backend/storage/database.py`：`SCHEMA_VERSION 12 → 13`；`_migrate_v13` 建两张表：
   - `audit_runs(id, started_at, finished_at, trigger(manual|scheduled|post_collect), ruleset_hash, ruleset_version, device_count, finding_count, status)` —— 趋势的基座
   - `audit_findings(id, run_id, device_id, collection_id, week, rule_id, level, source, title, detail, current_text, fix_text, why_text, note_text, evidence_json, missing_json, config_hash, created_at)` + 索引 `(run_id, level)`、`(device_id, rule_id)`
   - **不建规则状态表**：启停直接写回 YAML 的 `enabled: true|false`（YAML 保持唯一权威，与用户定案一致）

**C. API**
7. `backend/api/audit.py`（`main.py` 注册，照 `reports_router` 写法）：
   - `GET /api/audit/device/{name}` → **单台即时审计（不落库）**，返回 **envelope**：
     `{device, config, config_hash, findings, counts, port_roles, ruleset_hash, generated_at}`
     —— **必须带 `config` 原文**：前端行号对齐只认这一份；`analyze()` 的原 dict 直接喂前端不够用（缺配置原文、`evidence` 有截断、`line:0` 非法）
   - `POST /api/audit/run` → 全网审计入库（**实测 512 ms / 36 台，同步返回即可**，无需后台任务）；`GET /api/audit/runs`、`/runs/{id}` → 历史与明细
   - `GET /api/audit/standards` → 规则树（按来源/平台/档位分组）+ 共用段；`PUT /api/audit/standards/{file}` → 校验 → 备份 → **原子写入** → 清缓存
   - `GET /api/audit/device/{name}/export?format=md|html` → **服务端渲染**导出（前端拼会与 i18n/排序两处逻辑漂移）
   - 边界：区分"配置全文已按保留策略清理"与"从未采集"，给可读提示
8. 请求/响应类型写进 `frontend/src/types/index.ts`（一次性定义契约，别让补丁散落在 React 组件里）；
   响应结构可参考既有先例 `analyzers/role_verifier.py` 的 `audit_location()`。

**D. 前端**
9. `pages/Viewer.tsx` 加「审计」按钮 + 审计模式：**复用 Compare 模式的逐行渲染 + 左右双栏同步滚动**
   （`DIFF_COLORS` 扩展一个 `problem` 色；行号列；`rowRefs` + `scrollIntoView({block:'center'})` 做双向定位），
   右侧为问题卡片（档位徽章 + 现状片段 + 建议命令 + 依据 why + 注意 note），顶部按档位/来源筛选 + 导出按钮。
10. 新增 `pages/ComplianceStandard.tsx`：按来源/平台/档位分组列规则，启停开关、字段表单编辑（**照 `LogAnalyzer.tsx` 的 `LLMSettingsDialog` 形态**）、新增规则、保存校验提示。
11. `App.tsx` 注册导航与路由（navItems L87-97 / Route L346-360）+ `services/api.ts` 加 `complianceApi` + i18n（`audit.*` / `auditRules.*`，zh/en 两份）。

**E. 测试**
12. `backend/tests/test_compliance_engine.py`（规则/组合判定/站点作用域/行号）、`test_compliance_api.py`（端点）、
    `test_port_roles.py`；样本进 `backend/tests/fixtures/`（netstd 的样例 + 现网片段）。

### 第二期（本计划不含，先记下）

趋势图表（哪些问题在收敛/恶化）、忽略/已确认/例外回写标准、AI 专家简报、端口级规则接上端口角色、
用 `research/` 的 75 条按 CONSOLIDATION 对账流程扩规则。

## 四、关键复用清单

| 需要什么 | 复用现成的 |
|---|---|
| 逐行渲染 + 左右同步滚动 + 行级高亮 | `frontend/src/pages/Viewer.tsx` Compare 模式（L396-455、L181-202）+ `DIFF_COLORS`（L21-26） |
| "选中一个 → 其余变暗 / 滚到对应位置" | `components/topology/PortTopologyCanvas.tsx` L838-871 的选中联动思路 |
| 列表 + 编辑对话框 + 保存反馈 | `pages/LogAnalyzer.tsx` 的 `LLMSettingsDialog`（L654-733）+ `DeviceList.tsx` 的对话框链路 |
| 表单校验范式 | `pages/DeviceForm.tsx`（react-hook-form + zod） |
| 读写 YAML 配置（校验/保留未改字段/写回） | `backend/api/logs.py` GET/PUT `/api/settings/llm`（L246-303） |
| 审计发现的响应结构 | `backend/analyzers/role_verifier.py` 的 `RoleWarning` / `audit_location()` |
| 迁移与种子数据 | `storage/database.py` `_migrate_vN` / `_seed_remediation_hints` |
| 配置全文读取 | `backend/api/data.py` L244-253（改造成"取最新一次"，去掉 week 条件） |

## 五、验证方式

- **单测**：`cd backend && python -m pytest tests/ -q`（新增用例覆盖：组合规则 A→B / all_of、站点作用域 OSAT 豁免、行号正确性、采集失败文本跳过）。
- **真实性核对（回归基准）**：全网 Cisco `snmp-server group v3` 18/18 而 `user v3` 0/18 → 审计必须报"有组无用户"；
  CX `dhcpv4-snooping` 13/18 但 `trust` 仅 2/18 → 必须报"配了一半"。
- **端到端（浏览器实测）**：查看器打开一台设备 → 点「审计」→ 左侧标红行与右侧条目一一对应、点条目滚到对应行、建议命令可复制；
  标准页停用/改一条规则 → 重新审计结果随之变化；导出 Markdown/HTML 打开正常。
- **回归**：现有 238 项测试全绿；`cd frontend && npx tsc --noEmit` 无新增错误；`npm run build` 通过。

## 六、风险与坑

1. **行号映射链有三个断裂点，必须一起治**（Plan agent 实测更正）：
   - **入库**：DB 全文无 CR（netmiko `normalize` 已归一为 LF）✓；但 **35/36 台配置带行尾空格** → **标红只认行号，禁止"拿证据文本回配置里搜"**；**18/36 台以换行结尾** → `splitlines()` 与 `split("\n")` 差一个尾部空元素（索引仍对齐，行数显示差 1；前端绝不能顺手 `.filter(Boolean)` / `.trim()`，否则从此全部错位）。
   - **不同源**：**磁盘 `running-config.raw` 是 CRLF**（Python 文本模式写出），与 DB 全文（LF）不是同一份 → 审计面板**禁止**用 `dataApi.getFile`/`getRawData` 的磁盘内容做对齐，必须渲染审计接口 envelope 返回的 `config`（同一次读取、同一份文本）。
   - **展示**：`pre-wrap` 下长行视觉折行 ≠ 逻辑行，不要用行高×行号做像素定位。
2. **配置全文只有最近 2 次**（`CONFIG_KEEP=2`，更早置 NULL）→ 审计只保证最近 2 次采集可跑；全量审计要在采集后跑或提示"该设备无可用全文"。
3. **采集失败文本**（`% 收集失败: …`，`running_lines=0`）必须跳过，否则整台设备会被误判成"配置全缺"。
4. **规则热更新与并发**：现有 settings 读改写无锁；规则保存需**原子写（临时文件 + 替换）+ 备份 + 失败回滚**，保存后清规则缓存。
5. **性能**：36 台 × 数十条正则可接受（单台配置 ~100KB，逐行正则；`analyze()` 是纯 CPU 毫秒级）；全网审计放后台任务 + 进度反馈，别阻塞请求。
6. **语义别走样**：五档是"建议强度"，UI 上不要出现"违规/合规分/pass-fail"字样（用户明确"标准是建议，不是强制"），也不进 alerts 表。
7. **不翻既有决策**：不采纳项不得作为新规则上线；挂起项只能以配套组形式出现。
8. **安全注意**：`main.py` 把 `data_root` 挂到了 `/data` 静态目录（免登录），审计端点不要依赖它取配置；规则文件读写要防路径穿越（规则文件名白名单）。

## 七、Plan agent 复核补充（2026-09-18，实施时按此执行）

1. **组合规则只做一个判定器**：新增单个 `command_set`，用 `params.mode` 覆盖三种语义（`all_of` / `requires` / `conflict`），三种 mode 复用同一个 `_eval_scope()`；
   `_finding()` 扩展 `check_kind / missing[] / satisfied[]`（`satisfied` 让 UI 能显示"三件套已配 2/3"的进度感，而不是非黑即白）。
   **一期只落地 3 条样板规则**验证模型：`cx_snmpv3_group`（all_of）、`cs_dai_requires_dhcp_snooping`（requires）、`cs_bpduguard_not_on_uplink`（conflict + 端口角色）；其余 23 条原样不动。
2. **端口角色（`backend/audit/port_role.py`）信号优先级**（覆盖率已实测）：
   STP `role='root'`（19/36 台，只有 root/designated，无 alternate）→ `neighbors.neighbor_type='switch'`（**36/36 台**）→
   `collections.lag_membership` JSON（222 次采集有值）→ `devices.uplink_ports`（**仅 4/36，只作佐证**）→ 接口 description 关键词。
   `port_snapshots.is_uplink` **实测仅 14 行为 1（4.5 万行）→ 不可用**。
   conflict 类判定**只在 `confidence: high`**（有 STP root 或 switch 邻居佐证）时出 finding；低置信降级为「需人工判断」并注明"无法确定端口角色"。
3. **移植等价性基线**：用库里 36 台真机配置跑一遍，**锁定总命中数 205**（14.2 ms/台、全网 512 ms、0 异常）—— 移植前后必须一致，作为引擎回归的硬断言。
4. **YAML 保存的工程细节**：`config/manager.py` 是交互式菜单、不是可复用的原子写 helper → 新写：同目录 tmp + `os.replace`（同分区才原子）；
   **Windows 上目标文件被占用会抛 `PermissionError` → 必须带重试**；备份加时间戳并限制保留份数；并发用 `base_hash`（前端带上打开时的 mtime/hash）做乐观锁拒绝后写。
5. **YAML 注释**：环境里装了 `ruamel.yaml` 但 `requirements.txt` 未声明 → **一期用 PyYAML**（保存会丢注释，在规则文件顶部声明"注释由 git 保留"），保注释的往返编辑列二期。
6. **审计面板渲染禁令**：左侧必须渲染审计接口返回的 `config`（唯一同源），**禁止**用 `dataApi.getFile`/`getRawData`（磁盘 raw 是 CRLF，行号会整体错位）；标红**只认行号查表**（`Map<line, findings[]>`），禁止文本匹配（35/36 台有行尾空格）；`line: null` 的条目禁用"定位到行"按钮。
7. **采集后自动跑**：放最后做，默认**关闭**（`config/settings.yaml` 开关），避免影响既有采集耗时。
8. **语义与文案**：五档若配 red/amber 色块 + "问题条目"字样会被读成违规清单 → 标题用「评审意见/建议」、常驻"本页为建议，非强制"提示、避免用 `error` severity 的 Alert 承载；规则正文（title/fix/why）**不入 i18n**（英文环境显示中文规则可接受，胜过维护两份规则副本）。

## 八、落地安排

- **2026-09-18（今天）**：只出计划，落到 `docs/superpowers/plans/2026-09-18-compliance-audit.md`（项目既有约定），提交留档，不动代码。
- **周日开发**：按 §三 第一期 A→E 顺序做，每步单独提交（项目约定），先跑通"标准页 + 单台审计"，再补全量入库。

---

## 九、补充：总部《AUTOMATION-Cisco》对审计输出的约束（2026-09-18 晚，评估后新增）

总部另有一份 **`AUTOMATION-Cisco.docx`**（《Qorvo Cisco Configuration Automation — Working Guide》，v1.0，2026-06-30）。它用 Ansible 描述了同一件事：Deploy → Validate → **Audit** → **Report** → **Dashboard** 五段生命周期。**NDM 的审计功能正好是这份指南里 Audit + Report + Dashboard 三段的自研实现**，因此它规定的输出契约应当对齐——不是要采纳 Ansible，而是要**让 NDM 的导出能被总部设想的报告层直接消费**。

需要并入本计划的约束：

1. **CSV 表头对齐**（原文第 8、10 章给出两版）：
   - 第 8 章：`hostname,section,status,remediation_note`
   - 第 10 章：`hostname,section,status,observed_value,remediation_note`
   - → 审计导出的 CSV **采用第 10 章的列**（含 `observed_value`，信息更全且是两版中的超集）。
2. **每行证据的必备字段**：主机名、检查段（section）、状态、修复建议；文本证据应含**观测值**（便于排障）。
3. **表头必须稳定**：原文明确"CSV 列名要稳定，否则电子表格与仪表盘导入会中断"。
4. **安全红线（原文第 9 章）**：**证据文件不得包含可复用的密钥、密钥串或口令**。→ 现网配置里存在 `ciphertext` 口令、TACACS 密钥、以及 4 台设备的明文 v2c 团体字（含 1 个 RW），**导出前必须过滤这些内容**；`current_text` / `evidence` 字段要做脱敏。
5. **只读原则**：Validate / Audit 一律只读；**Dashboard 层只消费证据，绝不能回写设备配置或改写审计证据**。→ NDM 的审计功能天然只读，保持即可；但"忽略/已确认"这类回写（二期）要落在**规则文件/独立表**，不能改写已生成的证据快照。
6. **已批准的例外不得判为不合规**：原文第 6 章工程注记——"站点特有的、已批准的可选 ACL 条目不应导致合规失败"。→ 与计划里"挂起项只作配套组出现"的决策一致，**规则实现时要显式支持例外豁免**。
7. **容器/仪表盘定位**：原文把仪表盘定位为**纯报告层**。→ NDM 的审计页面同样只做展示与导出，不提供"一键修复下发"入口（避免与变更管理流程冲突）。

**⚠️ 待定案（需要用户拍板）**：总部自动化指南的证据模型是 **PASS/FAIL**（`status` 列），而本计划第一期已定调「建议非强制、UI 不出现违规/合规分/pass-fail 字样」。两者需要调和，可选：

- **A（推荐）**：CSV 的 `status` 列承载**五档建议强度**（强烈建议/风险提示/改进建议/可选优化/需人工判断），另加一列 `severity` 区分 `shall` / `should`；界面保持建议语义。
- **B**：对 `shall` 类检查项给 PASS/FAIL，对 `should` 类给建议档位；导出同时满足总部格式与本地语义。
- **C**：完全按总部 PASS/FAIL 输出，放弃"建议非强制"的界面语义（与已批准决策冲突，不推荐）。

在周日动手前需确认采用哪一版。

---

## 十、定案：审计导出的 `status` 语义（2026-09-20）

**采用方案 A**（§九 待定案事项关闭）：

- **导出的 CSV 列** = `hostname,section,status,severity,observed_value,remediation_note`
  —— 在总部《AUTOMATION-Cisco》第 10 章版基础上**增加 `severity` 列**。
- **`status` 列承载五档建议强度**：强烈建议 / 风险提示 / 改进建议 / 可选优化 / 需人工判断。
  **不输出 PASS/FAIL**，界面与导出均为"建议非强制"语义（与已批准决策一致）。
- **`severity` 列承载要求的强度来源**：`shall`（公司基线强制项）/ `should`（公司基线建议项）/ `vendor`（厂商加固）/ `convention`（现网惯例）。
  这样总部若要按 PASS/FAIL 消费，可自行用 `severity = shall` 过滤；本地看到的仍然是建议。

---

## 十一、标准来源的讨论（2026-09-20，开工前）

现有三层判定来源：**公司总部要求**（CFG-Aruba / CFG-CISCO）+ **厂商加固建议** + **现网惯例**。用户提问"还有什么别的要考虑的标准"。讨论后确认的边界：

**判断**：现有三层都是"配置该长什么样"的**静态标准**；缺的是**时间维度**。以下按处理方式分三类。

### 一期顺手做掉

1. **运维就绪度核查**（不是安全标准，但资深工程师必看，且数据大多现成）
   - `running-config` 与 `startup-config` 是否一致 → "存在未保存的配置变更"
   - ⚠️ **前置条件**：当前采集链路**已不含 startup-config**（`backend/collectors/base.py` / `collector_service.py` 中无 startup 相关代码；磁盘上仅有 2026-24~27 的历史 `startup-config.raw`，说明以前采过、后来移除）。**要恢复该检查需先把 `show startup-config` 重新纳入采集**。
   - NTP 是否真的同步（`show ntp status` 属运行态，需单独采集或降级为"需人工判断"）
   - 接口错误计数（`port_errors` 表已有数据，可直接用）

### 记入二期（不在一期扩标准源）

2. **厂商安全公告与生命周期（EoL/EoS + CVE/PSIRT）**——回答"这个版本还能不能用"
   - 与"厂商加固建议"不同：加固建议管**配置怎么写**，公告管**版本还能不能用**（Cisco EoL、Cisco PSIRT/openVuln、Aruba 安全公告）
   - 数据基础现成：`devices.member_versions` / `collections.software_version` 已存版本号
   - 归类到五档的**「风险提示」**——它不是配置错误，是时效性风险（现网那台"快退休的 C9500"正属此类）
3. **流程合规**：用现有变更检测能力（`change_detector`）发现"没有对应变更单的配置改动"——从"配置对不对"进到"改得合不合规"
4. **例外登记与豁免机制**（总部基线第 3 章要求）——没有它审计结果会退化成噪声

### 只做标签，不新增判定

5. **合规框架映射**：总部文档已把每条要求映射到 NIST 800-53（AC-17 / IA-2 / AU-2 / CM-6 / SC-7 …）。**沿用该标签**，让审计报告可按控制族汇总，直接用于应对总部审计或客户问询。
   - **待用户确认**：现网 **25/36 台**设备的登录横幅自称可能承载 **CUI（Controlled Unclassified Information）**（aruba 10 台 / cisco_ios 12 台 / cisco_ios_router 2 台 / cisco_ios_xe 1 台）。若确实涉及 CUI，则 **NIST SP 800-171 / CMMC** 很可能是硬要求；中国站点（BJQ/SHA/SZX/PEK/ZGN 等）是否还适用**等保 2.0** 也需确认。二者若适用，会往规则库追加具体条目（如 FIPS 加密、审计留存期）。

### 不作为"标准来源"，而作为规则的**技术依据**

6. **RFC / IEEE 协议标准**（802.1D/w STP、802.1AB LLDP、802.3ad LACP、RFC 3046 option 82、RFC 3579 RADIUS/EAP、RFC 5905 NTP、RFC 3411-3418 SNMPv3、RFC 8907 TACACS+ 等）
   - 用途：写进规则的 `why` 字段，让每条建议有出处——这是"资深专家评审"与"规则引擎跑分"的区别所在。

**范围纪律**：**一期不扩标准源**，判定仍只用三层（公司规范 / 厂商基线 / 现网惯例），保证"标准页 + 单台审计"最小闭环能按时完成。

### 定案 1（2026-09-20）：运维就绪度检查**纳入一期**，含 startup 一致性

用户定案：**做，含 startup 一致性**。落地要点：

1. **恢复 `show startup-config` 采集**——`backend/collectors/base.py` 增加 `collect_startup_config()`，`backend/services/collector_service.py` 的 collect 流程接上。**这是本任务第二处触及既有采集代码的改动**（原计划改造点 #18「端口名归一化抽 utils/port_names.py」是第一处），两处都必须保 238 项测试全绿。
2. **存储**：v13 迁移里给 `collections` 增加 `startup_config` 列（与 `running_config` 同规格），并纳入既有分层保留策略（`CONFIG_KEEP = 2`，更早置 NULL）。
3. **检查项**：`running-config` 与 `startup-config` 不一致 → "存在未保存的配置变更"（如设备重启会丢失）。**归 OPS 类、`severity = convention`**（运维惯例，非公司基线强制项）。注意：两份文本行尾/空行差异会造成假阳性，比对前需归一化（参考计划 §六 的"行号链"教训：DB 文本为 LF、35/36 台有行尾空格、18/36 台以换行结尾）。
4. **顺带修正**：`CLAUDE.md` 中"采集 `show startup-config`"的描述与实际代码不符，恢复采集后即重新成立，无需改文档。

### 定案 2（2026-09-20）：厂商安全公告与生命周期 —— **二期做，先只做 EoL**

用户定案：**接入生命周期检查，但只做 EoL/EoS，CVE 暂不做**。

- **范围**：按 `devices.model` 查厂商生命周期状态（Cisco 官方 **EoX API** 按产品型号查；Aruba 侧查对应公告），报告"该型号已停止支持/临近停止支持"。
- **不做 CVE 的原因（重要，别回头忘）**：版本号 → 漏洞公告的映射是 fuzzy 的，**误报会直接毁掉审计的可信度**（资深专家评审最忌讳瞎报警）。要做的话必须配套核实机制，不在一期二期范围。
- **归类**：五档里的**「风险提示」**——它不是配置错误，是时效性风险；`severity` 归 `vendor`。
- **附带价值**：这条正好解释了"为什么那台老 C9500 该换"，比单纯报配置问题更有说服力。
- **产出位置**：`devices.model` 已有型号、`collections.software_version` 已有版本号，无需改采集链路。

### 定案 3（2026-09-20）：规则增加 NIST 控制族标签

用户定案：**加**。规则 YAML 增加 `controls: [AC-17, IA-2, ...]` 字段，取值直接沿用总部 CFG-Aruba / CFG-CISCO 各章已有的 NIST Control Mapping（第 4 章 AC-17/IA-2/AU-2/CM-6/SC-7；第 5 章 AC-2/AC-3/AC-6/IA-2/IA-5/AU-2/AU-12；第 6 章 AC-4/AC-17/SC-7/CM-6；第 7 章 SC-8/IA-2/AC-17；第 8 章 SC-12/SC-13/AC-17/AU-2；第 9 章 AU-8/SC-45/CM-6；第 10 章 AU-2/AU-3/AU-12）。
→ 审计报告可按控制族汇总，**直接用于应对总部审计或客户问询**；成本几乎为零。现网惯例类规则（无对应章节）可不带该字段。

### 收回的建议（2026-09-20）：变更单比对**不做**

上周五提出的"用变更检测能力发现没有变更单的配置改动"——**放弃**。原因：变更单数据不在 NDM 内（在 ITSM 系统里），要做必须对接外部系统，成本远超收益。已从二期候选清单移除。

### 待确认项（不阻塞开发）：CUI / CMMC / 等保

现网 **25/36 台**设备登录横幅自称可能承载 **CUI（Controlled Unclassified Information）**（aruba 10 / cisco_ios 12 / cisco_ios_router 2 / cisco_ios_xe 1）。若确实涉及 CUI，则 **NIST SP 800-171 / CMMC** 可能是硬要求；中国站点（BJQ/SHA/SZX/PEK/ZGN 等）是否适用**等保 2.0** 也需确认。
→ **需用户向公司合规口确认**，不阻塞一期开发。若适用，后续往规则库追加具体条目（如 FIPS 加密、审计留存期），并复用定案 3 的 `controls` 字段承载框架映射。

### 定案 4（2026-09-20）：例外登记机制 —— 二期做

用户定案：**二期做**。一期先跑通审计闭环；一期内的噪声问题用已定的**「集体性漏配单独成类」**处理（如 Syslog 0/18、MGMT_ACL 0/18 各归 1 条而非 18 条）。二期再做"已批准例外的登记 + 豁免"（按设备/站点/规则 ID 登记，含理由、补偿控制、批准人、到期日；命中时豁免并标注「已批准例外」），落地位置仍遵循"YAML 为唯一权威"原则。

---

## 十二、开工前讨论总结（2026-09-20）

**参与讨论的四项标准来源问题全部定案**，对一期范围的影响：

| # | 事项 | 定案 | 对今天的影响 |
|---|---|---|---|
| 1 | 运维就绪度（running vs startup） | **一期做**，含 startup 一致性 | **扩了一期范围**：需恢复 `show startup-config` 采集（第二处动既有采集代码） |
| 2 | 厂商安全公告与生命周期 | **二期做**，只做 EoL（按型号查 EoX API），不做 CVE | 无（不动采集链路） |
| 3 | NIST 控制族标签 | **加** —— 规则 YAML 增 `controls` 字段 | 规则 schema 多一个字段（成本极低） |
| 4 | 例外登记机制 | **二期做** | 无 |
| — | 变更单比对 | **收回，不做**（需对接 ITSM，成本超收益） | 从二期候选移除 |
| — | CUI / CMMC / 等保 | **待用户向合规口确认**，不阻塞 | 无 |

**判定来源最终仍为三层**：公司总部要求（CFG-Aruba / CFG-CISCO）+ 厂商加固建议 + 现网惯例。**RFC / IEEE 协议标准不作为标准来源**，只写进规则的 `why` 字段作为技术依据。

**一期最终范围（在周四批准的 A→E 基础上）**：
- **新增**：恢复 startup-config 采集 + 保存（v13 迁移加 `collections.startup_config` 列，纳入 `CONFIG_KEEP = 2` 保留策略）+ 一致性检查规则（OPS 类，`severity = convention`）。比对前需归一化行尾与空行，避免假阳性。
- **新增**：规则 YAML 的 `controls` 字段（NIST 控制族）。
- **不变**：其余按 §三 第一期 A→E 执行，步骤顺序 A 引擎移植 → B v13 迁移 → C `api/audit.py` → D 前端 → E 测试；每步单独提交；回归基准 238 项测试全绿、移植等价性 205 条命中一致。
