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

另：`rules/standard.yaml` 里 `default_present`/`in_use_requires`/`resource_type`/`wifi_*`/`address_pattern`/`segments`/`site_codes`
**写了但引擎不消费** → 移植时要么实现、要么删掉。

## 三、实施步骤（分期，每期可独立验证）

### 第一期：引擎 + 规则库 + 标准页 + 查看器审计

**A. 引擎移植与改造（后端）**
1. 新建 `backend/analyzers/compliance/`：`engine.py`（移植 + 上表 13 处改造）、`checks.py`（12 + 组合判定器）、`loader.py`（规则加载 + 校验）。
2. 规则文件：`config/compliance/vendor_baseline.yaml`（厂商基线）+ `config/compliance/company_standard.yaml`（公司规范）
   —— 从 netstd `standard.yaml` 拆两层（`source` 字段仍在，文件分层更直观）；`sites`/`naming`/`vlans` 等组织参数放公司规范文件。
3. 数据源：新增 `backend/analyzers/compliance/source.py`，取「最新一次采集的 running-config」
   （`collections.running_config`，`ORDER BY collections.id DESC`；跳过采集失败文本 `% 收集失败:`）。
4. 组合判定器：`check_group_all_of`（命令组齐备，缺项点名）、`check_requires`（有 A 必须有 B）、`check_conflict`（可选，端口级）。
5. 端口角色：新增 `port_roles.py`（neighbors + stp_snapshots + lag 成员 + description → uplink/access/unknown），供端口级规则使用（一期先只做判定函数 + 单测，规则可后接）。

**B. 存储（v13 迁移）**
6. `backend/storage/database.py`：`SCHEMA_VERSION 12 → 13`；`_migrate_v13` 建两张表：
   - `compliance_findings(id, collection_id, device_id, rule_id, level, source, platform, lines, current, fix, why, note, created_at)`
   - `compliance_rules_state(rule_id, enabled, exceptions, updated_at)`（规则本体仍在 YAML，此表只存启停/例外）

**C. API**
7. `backend/api/compliance.py`（`main.py` 注册，照 `devices.py` 风格）：
   - `POST /api/compliance/audit/{device}` → 单台即时审计（返回配置全文行 + findings + counts，**行号由后端按 `splitlines()` 算好**，1-based）
   - `POST /api/compliance/audit-all` → 全网审计并入库；`GET /api/compliance/findings?device=&location=&level=` → 读库
   - `GET /api/compliance/rules` → 规则完整结构（含 params/note/scope）；`PUT /api/compliance/rules` → 校验 + 原子写 + 备份
     （**照抄 `backend/api/logs.py` 的 GET/PUT `/api/settings/llm` 读写模式**）
   - `GET /api/compliance/export/{device}?format=md|html` → 左右对照报告（服务端渲染）
8. 返回结构参考既有先例 `analyzers/role_verifier.py` 的 `audit_location()`（`{location, devices[], warnings[], summary{total/passed/warnings/errors}}`）。

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

1. **行号口径**：实测库内配置文本无 CR、无末尾空行，`running_config_lines == splitlines() == split('\n')`（PVGD1SWI01 = 585 行三者一致）→ 行号可信；
   但仍**由后端算好行号返回**（1-based），前端按 index 对齐；`pre-wrap` 下长行视觉折行 ≠ 逻辑行，不要用行高×行号做像素定位。
2. **配置全文只有最近 2 次**（`CONFIG_KEEP=2`，更早置 NULL）→ 审计只保证最近 2 次采集可跑；全量审计要在采集后跑或提示"该设备无可用全文"。
3. **采集失败文本**（`% 收集失败: …`，`running_lines=0`）必须跳过，否则整台设备会被误判成"配置全缺"。
4. **规则热更新与并发**：现有 settings 读改写无锁；规则保存需**原子写（临时文件 + 替换）+ 备份 + 失败回滚**，保存后清规则缓存。
5. **性能**：36 台 × 数十条正则可接受（单台配置 ~100KB，逐行正则；`analyze()` 是纯 CPU 毫秒级）；全网审计放后台任务 + 进度反馈，别阻塞请求。
6. **语义别走样**：五档是"建议强度"，UI 上不要出现"违规/合规分/pass-fail"字样（用户明确"标准是建议，不是强制"），也不进 alerts 表。
7. **不翻既有决策**：不采纳项不得作为新规则上线；挂起项只能以配套组形式出现。
8. **安全注意**：`main.py` 把 `data_root` 挂到了 `/data` 静态目录（免登录），审计端点不要依赖它取配置；规则文件读写要防路径穿越（规则文件名白名单）。

## 七、落地安排

- **2026-09-18（今天）**：只出计划，落到 `docs/superpowers/plans/2026-09-18-compliance-audit.md`（项目既有约定），提交留档，不动代码。
- **周日开发**：按 §三 第一期 A→E 顺序做，每步单独提交（项目约定），先跑通"标准页 + 单台审计"，再补全量入库。
