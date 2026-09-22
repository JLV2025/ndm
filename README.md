# NDM — 网络设备配置管理系统

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.9.22-2DD46E" alt="Version 2.9.22">
  <img src="https://img.shields.io/badge/Python-3.10%2B-2DD46E" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/React-18-2DD46E" alt="React 18">
  <img src="https://img.shields.io/badge/Backend-FastAPI-2DD46E" alt="FastAPI">
  <img src="https://img.shields.io/badge/Storage-SQLite-2DD46E" alt="SQLite">
  <img src="https://img.shields.io/badge/SSH-Netmiko-2DD46E" alt="Netmiko">
  <img src="https://img.shields.io/badge/i18n-%E4%B8%AD%E6%96%87%20%2F%20English-2DD46E" alt="中 / English">
  <img src="https://img.shields.io/github/v/release/JLV2025/ndm?color=2DD46E" alt="Latest Release">
  <img src="https://img.shields.io/github/last-commit/JLV2025/ndm?color=2DD46E" alt="Last Commit">
</p>

通过 SSH 批量收集 Cisco IOS / Aruba OS 交换机与路由器配置和日志，SQLite 存储，Web 前端可视化查看、对比、分析；支持 AI 日志诊断，并内置**配置审计**——按公司标准、厂商加固建议与现网惯例，像资深网络工程师那样给出评审意见；审计发现可直接带入**批量命令执行**（带三层保护）完成整改。

## 功能特性

- **多厂商支持** — Cisco IOS、Cisco IOS XE、Cisco IOS Router、Aruba OS、Aruba OS CX
- **Web 管理面板** — React + MUI OLED Dark 主题，专为网络运维设计；侧栏把全部入口收进**四个可折叠分区**（拓扑视图 / 审计与合规 / 监控与报告 / 资产与操作），最常用的三项（仪表盘 / 设备管理 / 数据查看器）固定在上方——**当前页所在分区自动展开**，手动开合状态跨会话记忆
- **设备管理** — 添加、编辑、删除、批量导入（CSV）设备，按类型 / 位置筛选；VSF 堆叠成员按真实成员编号展示（如 SWI01-1 / SWI01-2，跳号准确）。**位置身份与硬件身份分离**：采集 / 审计 / 告警按"名字 + IP"的管理体进行，序列号 / 型号 / 保修 / 软件版本按**物理设备**逐台记录——堆叠成员在库里就是独立设备行（`kind` + `stack_name` + `member_no`），成员换件、增减、整机换代都会被识别并留痕
- **离线设备** — 物理设备档案自动建档（序列号唯一追踪，**堆叠按物理成员逐台建档**，Cisco 堆叠也在内），超过 30 天未收集即显示为离线（拆机搬运/闲置），重新上线自动恢复，可彻底删除档案
- **配置收集** — 一键收集 running-config、日志、接口状态、端口累计计数器、路由表、版本信息
- **AI 日志分析** — 用户自配 LLM API Key，自动提取错误助记符 + 优先级链降级（DeepSeek / Qwen），本地缓存常见错误，脱敏保护网络安全
- **配置审计（资深专家评审）** — 三层标准库：**公司总部要求**（CFG-Aruba / CFG-CISCO）＞**厂商加固建议**＞**现网惯例**，冲突时高层优先；判定全部由**确定性规则引擎**完成（零幻觉），输出像资深工程师的评审意见：五档建议强度（强烈建议 / 风险提示 / 改进建议 / 可选优化 / 需人工判断，**是建议不是打分**）、可复制的修复命令、每条附依据（含 NIST 控制项标签）。单台即时审计：配置行标红 ↔ 建议卡片**双向定位**（只认行号查表，不受行尾空格影响）、一键导出 Markdown/JSON；全网审计入库（36 台 <1 秒），**采集后自动跑一轮**（去抖 60 秒，可关）
- **审计标准可编辑** — 规则库是 YAML（`config/audit/*.yaml`，**标准是数据不是代码**），页面上按来源/平台/档位分组浏览、启停、编辑字段；保存走「乐观锁 → 备份 → 原子替换 → 校验失败回滚」，注释与 git 历史完整保留
- **例外登记** — 已批准的偏离可正式登记（理由 / 补偿控制 / 批准人 / 到期日，**不允许永久例外**），命中即标注「已批准例外」并单列，不计入建议统计；**到期自动失效**回到普通统计、撤销走软删除（历史可追溯）
- **审计趋势与历史** — 独立页「配置审计」：趋势曲线（**每周取该周最后一次**运行，建议数与已批准例外分列；可切按档位/来源拆分、按站点筛选）、**收敛/恶化榜**（最新周 vs 上一周，按规则对比命中设备数）、历史运行列表与单次明细下钻；标准或例外变过时标记指纹变化，避免把"口径变了"误读成"设备变差了"
- **设备生命周期** — 型号 EoL（Cisco 走 **EoX API**，配好凭据自动刷新型号生命周期；Aruba 无公开 API 手工登记）+ 逐序列号保修期（支持**批量粘贴导入**，自动按序列号匹配设备）。审计里：已停止支持/保修过期 → 风险提示；未登记 → 「待查」（多台自动**折叠成一条**，不淹没真问题；超过 365 天未复核重新算待查）
- **生命周期页（三色看板）** — 侧栏独立页：**全部物理设备一行一台**（堆叠成员逐台 + 单机），物理名 / 序列号 / 位置 / 型号 / 停止销售 / 停止支持 / 维保到期一目了然，带**三色状态**（绿在保、橙临近或未登记、红出保；维保阈值 2 个月、EoS/EoL 阈值 6 个月，按日历月；备注为 `Unavailable` 的"查无此机"按出保处理）。支持按状态 / 位置 / 型号筛选与点列头排序；行内改维保（日期 + 备注 + 核实人）、点型号格改型号 EoL（**型号级属性，改一次全部同型号设备同步**）、批量粘贴导入；与设备详情页卡片**同源判定、同一接口**
- **AI 专家简报** — 把确定性审计结论**讲成人话**（单台 / 全网两档，管理层视角）：识别"这几条其实是同一件事的三个面"、指出配套关系（如 DAI 依赖 DHCP snooping）、如实报告数据缺口；prompt 硬约束**不得新增任何未列出的问题**，发送前凭据值打码（`utils/redact.py`）
- **发现汇总视图（按发现看设备）** — 审计页「发现排行」把"按设备看发现"反过来：一条发现命中多少台、都是谁（如"用了公网 NTP 的一共 5 台"，展开即见设备名单与站点、点击进查看器），按命中台数排序；行尾「批量处理」一键带入批量执行页
- **批量执行命令** — 对选中的设备逐台 SSH 执行命令：查询（show / display）或配置两种模式，配置模式可选「执行后保存（write memory）」。**三层保护**：① 危险命令静态拦截（`reload` / `erase` / `format` / `boot` 等直接拒绝，服务端兜底——前端被绕过也拦得住）② 未替换占位符与锁死风险警示 ③ 配置变更二次确认（设备清单 + 命令全文预览）。命令框与「设备当前配置」参照容器左右并列，对着现状把占位符填成实际值；执行逐台进行、实时进度、可随时停止、输出可展开；支持从审计发现一键带入（设备清单 + 修复命令 + 现状）；执行记录（谁 / 何时 / 哪台 / 命令 / 输出）全部留痕可回查，**凭据绝不落盘**
- **在线查看** — 代码高亮查看配置内容，支持版本对比（diff）
- **告警与报告** — 端口 DOWN / 配置变更 / **堆叠成员版本不一致**等异常检测，自动生成修复建议；支持按当前筛选条件**全部清除**（批量标记已处理，带确认框）。版本一致性只比**同一堆叠内部**：跨设备同型号版本不同属正常（分站点、分批次升级），不报警
- **自定义报告** — 两张大表（**设备运行状态** / 带宽利用率），统一支持**按位置过滤 + 点列头排序 + 导出 CSV**（带 UTF-8 BOM，Excel 直接打开）。设备运行状态报告按**物理成员**展开（SZXD1SWI01-1/-2/-3），逐台显示序列号、型号、版本、ROM 版本与运行时间——单机设备回退设备级运行时间，C9500 StackWise Virtual 用 onboard logging 单独取成员运行时间；堆叠内成员版本不一致时点名告警（升级未完成的信号）
- **Dashboard 图表** — Recharts 可视化：设备类型环形图、端口状态柱状图、流量排行、配置变更趋势折线图 + 热力图；端口统计区分转发 / 空闲 / 管理关闭（Disabled），逻辑口（Port-Channel / lag）与成员口不重复计数；设备数按**双口径**显示（管理设备 36 / 物理交换机 49）
- **区间流量排行** — 取端口**累计计数器**的周差值（本周最早读数 − 上周最早读数），而非设备上报的瞬时速率：采集间隔实测从 13 分钟到 21 天不等，5 分钟瞬时值代表一周没有意义。**一周内锁死**（周中再采多少次结果都不变，可直接用于周报对比），支持近 1 周 / 近 1 个月 / 近 3 个月三档时间窗——窗口越长，单个异常周（假期、备份周）的影响越小
- **前端面板可视化** — 交换机端口状态前面板 + 路由器接口层级树，支持堆叠设备、子接口缩进，10Gb 端口红色数字标识
- **端口连接图** — CDP/LLDP + ConfigParser 双数据源合并，React Flow 管道走线拓扑画布，四层自动布局（WAN→核心→接入→端点），堆叠展开 + 奇偶端口上下 Handle + 端点聚合计数，管道圆弧转角 + 自动居中适配；LAG/Port-Channel 逻辑端口聚合（物理成员隐藏），端口 DOWN 红色 ✕ 警告（有邻居条目但物理断开的端口）
- **多设备网络拓扑图** — CDP + LLDP 邻居自动发现 + ConfigParser 端口描述补充，三层分层布局（WAN → 核心 → 接入），智能连线最短路由，PNG/Visio 导出；端口 DOWN 红色 ✕ 警告，链路保留不删除（设备可能离线/故障）
- **STP 生成树拓扑图** — 采集 `show spanning-tree`（AOS-CX RPVST / Cisco Rapid-PVST 双平台解析，跨厂商 MAC 归一化认根），按站点绘制：交换机按 STP 深度分层（根桥第一层、金色高亮；多根桥并排顶层），每个 VLAN 是一个彩色伪端口（★ 根 / ✕ 阻塞、悬停看端口角色/优先级/根 MAC），链路按 VLAN 着色、转发实线 / 阻塞虚线、**连线形态自适应**（两端列对齐走直线，星型等走管道折线），左侧 VLAN 图例点击高亮单棵生成树，PNG 导出；站点 STP 模式一致性检查（同族 RPVST ≡ Rapid-PVST，混用告警），根在站点外时自动标注。同一对设备的多条物理链路按 VLAN 取真实跑 STP 的端口成边
- **基础分析** — 配置完整性验证、接口状态统计、利用率分析、变更检测
- **SQLite 全量存储** — running-config 双轨（文件 + 库），其余数据全量入 SQLite，日志按时间戳自动去重
- **双语文案** — 中 / 英文界面一键切换
- **单一端口部署** — 前端静态文件由 FastAPI 直接托管，一个命令启动

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + MUI v5 + Recharts + React Flow (@xyflow/react) + Vite 7 |
| 后端 | Python FastAPI + Netmiko (SSH) + SQLite |
| AI | OpenAI 兼容接口（DeepSeek / Qwen 等），优先级链降级，本地缓存；用于日志诊断与**审计专家简报**（发送前凭据打码） |
| 审计 | 自研确定性规则引擎（标准是 YAML 数据），Python 判定器 + 端口角色推断 + 集体性折叠 |
| 主题 | OLED Dark (#020617 底色, #2DD46E 强调色)，IBM Plex Sans + JetBrains Mono 字体 |
| 多语言 | React Context i18n (zh / en) |

## 快速开始

### 环境要求

- Python 3.10+（部分系统命令为 `python3`）
- Node.js 18+
- 可 SSH 访问的目标网络设备

### 安装

> **注意：** 所有命令在项目根目录下执行。GitHub 克隆后文件夹名为 `ndm-master`，建议重命名为 `ndm`（或直接进入该目录操作）。

```bash
# 1. 创建 Python 虚拟环境（避免系统级安装冲突）
python3 -m venv venv

# 2. 激活虚拟环境
# Linux / macOS:
source venv/bin/activate
# Windows (CMD):
venv\Scripts\activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 3. 安装后端依赖
pip install -r backend/requirements.txt

# 4. 安装前端依赖
cd frontend && npm install && cd ..
```

### 开发模式

```bash
# 确保虚拟环境已激活，在项目根目录执行

# 终端 1：启动后端 (端口 8002)
python backend/main.py

# 终端 2：启动前端 (端口 3000，自动代理 /api 到后端)
cd frontend && npm run dev
```

浏览器访问 `http://localhost:3000`。

### 生产部署

```bash
# 确保虚拟环境已激活，在项目根目录执行

# 1. 构建前端
cd frontend && npm run build && cd ..

# 2. 启动（前端 + 后端同一端口）
python backend/main.py
```

浏览器访问 `http://localhost:8002`，局域网内均可使用。

Windows 下可直接双击 `start.bat`，脚本会自动构建前端（如未构建）并启动后端。

### 卸载

项目完全自包含，不写入注册表、不安装系统服务、不创建计划任务。完整卸载只需删除项目文件夹：

```bash
# 删除整个项目目录即可
# Windows (资源管理器): 右键删除 ndm/ 文件夹
# Windows (CMD):
rmdir /s /q ndm
# Linux / macOS:
rm -rf ndm/
```

> 如果专门为此项目安装了 Python 或 Node.js，可在系统"应用和功能"中单独卸载。

## 配置

### 设备清单 (`config/devices.yaml`)

```yaml
devices:
  # Cisco IOS 交换机示例
  - name: "BJQD1SWI01"
    ip: "10.210.255.100"
    type: "cisco_ios"
    platform: "cisco_ios"
    location: "北京"
    notes: "核心交换机"

  # Aruba CX 交换机示例
  - name: "BJQD1SWI02"
    ip: "10.210.255.101"
    type: "aruba_aoscx"
    platform: "aruba_6300"
    location: "北京"
    notes: "汇聚交换机"

  # Cisco IOS 路由器示例
  - name: "BJQD1RTW01"
    ip: "10.0.0.1"
    type: "cisco_ios_router"
    platform: "cisco_ios_router"
    location: "北京"
    notes: "WAN 路由器"
```

### 设备类型说明

| type | 说明 | 适用设备 |
|------|------|----------|
| `cisco_ios` | Cisco IOS 交换机 | Catalyst 2960/3560/3750 等 |
| `cisco_ios_xe` | Cisco IOS XE | Catalyst 9200/9300/9500 等 |
| `cisco_ios_router` | Cisco IOS 路由器 | ISR 1900/2900/4300、ASR 等 |
| `aruba_aoscx` | Aruba CX | CX 6100/6200/6300/6400 等 |

### 全局设置 (`config/settings.yaml`)

```yaml
data_root: "./data"        # 数据存储目录
ssh_timeout: 30             # SSH 连接超时（秒）
# 数据保留为分层规则，见「数据存储」一节（周目录 16 周 + 更早按月归档、
# DB 配置全文与日志各留 2 次），无单一 max_versions 配置项

# LLM 配置（可选，用于日志 AI 分析）
llm:
  timeout: 30
  providers:
    - name: "DeepSeek"
      base_url: "https://api.deepseek.com/v1"
      api_key: ""           # 空则从前端设置页填写
      model: "deepseek-chat"
    - name: "Qwen"
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key: ""
      model: "qwen-turbo"
```

## 使用流程

1. 在 Web 面板添加设备（名称、IP、类型、位置）
2. 进入设备详情页，点击「收集配置」
3. 输入设备的 SSH 用户名和密码
4. 系统自动通过 SSH 登录设备，收集配置和日志
5. 在 Viewer 页面查看、对比历史版本

## 数据存储

所有采集数据统一存入 SQLite（`data/ndm.db`），仅 running-config 保留文件副本供紧急恢复（双轨策略）。

```
data/
├── ndm.db                       # SQLite 数据库（所有数据主存储）
└── {设备名称}/
    ├── YYYY-WW/                 # 按周归档
    │   └── running-config.raw   # 双轨保留（唯一文件）
    └── archive/
        └── YYYY-M{MM}/          # 超过 16 周的按月收缩
            └── running-config.raw
```

### 数据保留（分层规则）

| 对象 | 规则 |
|------|------|
| 配置文本文件 | 最近 **16 周**按周保留；更早的**按月收缩**——该月最后一个版本移入 `archive/{YYYY}-M{MM}/`，该月其余版本删除 |
| `collections.running_config` | 每设备留最近 **2 次**采集的全文，更早的置 NULL |
| `device_logs` | 每设备留最近 **2 次**采集的日志 |
| `stp_snapshots` | 每设备留最近 **2 次**采集的生成树快照（最新一轮画图，上一轮作根桥/阻塞变化对比基线）|
| `audit_runs` / `audit_findings` | 审计结果**自包含**留档（证据、行号、指纹随结果保存），历史运行可回看与下钻 |
| `eol_models` / `device_lifecycle` | 型号 EoL 与逐序列号保修登记（手工值不被自动刷新覆盖） |
| `batch_runs` / `batch_results` | 批量执行的留痕（命令全文存一份、逐台结果与输出；**凭据绝不入库**） |
| `devices`（`kind` / `stack_name` / `member_no`）/ `device_members` / `device_change_events` | 设备身份：位置行（stack / standalone）+ **物理成员行**；离线物理档案（序列号唯一追踪）；硬件变更事件留痕（换件 / 增减成员 / 整机换代） |

- **16 周** = 流量排行最大窗口 13 周 + 余量：区间流量需要 13 周前的计数器读数作基线
- 配置全文留 **2 次**即可：变更检测只用「上一次采集」作基线（按记录数而非时间，不受采集间隔不均影响）
- 归档的动机是**可查看性**，不是省空间（实测约 140 MB/年）
- 「配置取月末」与「流量取周初」方向相反但都对：配置是状态快照，流量是累计值需最早读数作基线

采集结束后自动执行，只有确实存在过期周目录时才动手。也可手动触发——**归档是不可逆删除**，先跑 `--dry-run` 看清单：

```bash
python backend/scripts/retention.py --dry-run   # 只列清单，不改任何文件与数据
python backend/scripts/retention.py             # 执行归档 + DB 收缩
python backend/scripts/retention.py --db-only   # 只收缩 DB，不碰文件
```

## 日志 AI 分析

1. 侧边栏进入「日志分析」→ 选择设备 → 勾选日志条目 → 点击「AI 分析」
2. 首次使用需在设置页面（⚙ 图标）配置 LLM API Key
3. 支持多个 LLM Provider 优先级链：按顺序尝试，第一个失败自动降级
4. 分析结果自动缓存到本地知识库，同类型错误下次秒级命中
5. 发送前自动脱敏（设备名 / IP 替换为占位符），回复后再还原

## 配置审计

**单台**：数据查看器 → 切到「审计」模式 → 选择设备 → 点「审计」。左侧配置标红、右侧建议卡片，点卡片跳到对应行、点行跳到卡片；可导出 Markdown / JSON；「生成专家简报」让 AI 把这些结论讲成一段评审意见。

**全网**：侧边栏「配置审计」→ 点「全网审计」跑一轮（也可等采集后自动跑）。页面上：
- **趋势**：每周取该周最后一次运行，看建议数与已批准例外数的走向（收敛还是恶化）；标准或例外变过会标出来
- **收敛/恶化榜**：最新周 vs 上一周，按规则列出命中设备数的增减
- **历史运行**：点任一条看明细（按档位/设备筛选，豁免条目带标注）

**维护标准**：侧边栏「审计标准」→ 三层规则库按来源分组；开关启停（停用必须写原因——被哪条高层规则取代，或为什么）、编辑标题/建议/依据。**「例外登记」页签**登记已批准的偏离（理由、补偿控制、批准人、到期日），命中后审计会标注豁免并单列。

**设备生命周期**：设备详情页「生命周期」卡片 → 登记型号 EoL 与各序列号保修到期日（Aruba 手工；Cisco 配好 `CISCO_API_CLIENT_ID` / `CISCO_API_CLIENT_SECRET` 后可点「刷新 EoL」自动拉取）；支持从厂商保修查询页**整段粘贴批量导入**。**侧栏「生命周期」页**则是全局视角：全部物理设备一行一台、三色状态（绿在保 / 橙临近或未登记 / 红出保）、按状态与站点筛选、行内编辑维保与型号 EoL——改型号 EoL 会同步到所有同型号设备。未登记的信息会以「待查」出现在审计报告里。

> 审计输出是**建议**，不是强制整改项；档位只表示建议强度。判定全部来自规则引擎，AI 只负责把结论讲成人话。

## 批量执行（命令下发）

侧边栏「批量执行」——对选中的设备逐台执行命令，三步走：

1. **选设备** — 按站点筛选 / 搜索 / 全选；也可从「配置审计 → 发现排行」点「批量处理」直接带入（设备清单 + 修复命令 + 设备当前配置）
2. **写命令** — 查询（show / display）或配置两种模式；右侧「设备当前配置」显示带入的现状，**对着它把命令里的占位符（如 `<公网地址>`）替换成实际值**；配置模式可勾选「执行后保存（write memory）」，默认不勾
3. **预检 → 执行** — 预检会**拦截**危险命令（reload / erase / format / boot 等，红色，禁止执行）、**警示**未替换占位符与锁死风险（黄色，确认后可继续）；配置模式执行前弹确认框（设备清单 + 命令全文 + 保存状态）。执行逐台进行、实时进度、可随时停止，每台输出可展开查看

所有执行记录进「历史记录」（时间 / 操作者 / 模式 / 结果 / 输出全文），可回查与删除。**凭据只在登录会话与请求中流转，从不落盘、不落库。**

## API 文档

后端运行后访问 `http://localhost:8002/docs` 查看 Swagger 文档。

## 项目结构

```
ndm/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 入口，含前端静态托管及 SPA 回退
│   ├── api/                 # 路由：设备、收集、数据、认证、统计、拓扑、告警、报告、日志、
│   │                        #       审计（audit）、生命周期（lifecycle）、批量执行（batch）
│   ├── services/            # 业务逻辑：SSH 收集、日志分析、审计简报、采集后自动审计调度、
│   │                        #   批量命令执行（危险命令黑名单 + 单台执行器）
│   ├── analyzers/           # 分析：配置验证、性能、变更检测、硬件变更指纹、端口/计数器/邻居/生成树解析、
│   │   └── compliance/      # 配置审计引擎：解析、判定器、规则加载、端口角色、
│   │                        #   数据源装配、全量执行器、趋势查询
│   ├── collectors/          # Netmiko SSH 连接层
│   ├── storage/             # SQLite 建表迁移 + 数据保留与归档 + 设备清单入口（device_dal）+ 生命周期数据访问
│   ├── scripts/             # 运维脚本：设备管理、YAML 迁移、数据保留
│   ├── tests/               # pytest（含 tests/fixtures/ 真机输出样本）
│   └── utils/               # 密码管理、配置加载、端口名归一化、配置比对、凭据打码、设备身份（device_identity）
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # 页面：Dashboard, DeviceList, DeviceDetail, Viewer, Login,
│       │                    #       Topology, Alerts, Reports, LogAnalyzer,
│       │                    #       配置审计（ComplianceAudit）、审计标准（ComplianceStandard）、
│       │                    #       批量执行（BatchExec）、生命周期（Lifecycle）
│       ├── services/        # API 调用 + 认证管理
│       ├── components/      # 通用组件（MatrixRain 背景、FrontPanel 前面板、TopologyCanvas、
│       │                    #   例外登记/专家简报/生命周期卡片 等）
│       └── i18n/            # 多语言文案（zh / en）
├── config/                  # YAML 配置文件
│   └── audit/               # 审计规则库（三层来源 + 例外登记），页面可编辑，YAML 为唯一权威
├── data/                    # 收集数据（SQLite + 按周归档）
├── docs/superpowers/plans/  # 设计与实施计划（含审计一期/二期各分项）
├── start.bat                # Windows 一键启动脚本
└── README.md
```

## 许可证

本项目仅供内部网络运维使用。
