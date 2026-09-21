# 发现汇总视图 + 批量执行命令 —— 设计与实施计划

> 上游：`docs/superpowers/plans/2026-09-18-compliance-audit.md`（配置审计总计划）
> 本文件 = 设计稿 + 实施计划（沿用本项目做法，二者合一）。

## 一、背景与目标

审计（一期）与趋势/例外/生命周期/简报（二期）都已落地。用户提出两个新需求：

1. **按发现看设备**（反向视图）：现在审计是"按设备看发现"，用户要反过来 ——
   "用了外部 NTP 的交换机一共几台？都是谁？" 数据已全在 `audit_findings`
   （每次审计 × 每台设备 × 每条规则一行），缺的只是聚合视图与设备名单下钻。
2. **批量执行命令**：从发现拉出设备清单（或自由选择）→ 用户输入命令 →
   用登录会话的凭据逐台 SSH 执行 → 结果留痕。与审计形成"发现 → 修复"闭环
   （审计条目的 `fix_text` 可直接带入命令）。

### 用户定案（2026-09-21）

| # | 决策 | 定案 |
|---|---|---|
| 1 | 命令边界 | **可下发配置，带三层保护**：① 危险命令静态拦截（服务端为准）② 执行前逐台预览 ③ 配置模式二次确认 |
| 2 | 保存配置 | 「执行后保存」复选框，**默认不勾**（保守）；勾选时服务端按平台执行 `write memory` |
| 3 | 留痕 | **落库**（谁 / 何时 / 哪台 / 什么命令 / 结果与输出）；输出不截断；历史可删 |
| 4 | 查询模式 | 也过黑名单（`reload` 在 exec 模式就能执行，不能只看命令种类） |
| 5 | 执行编排 | **串行**逐台（与采集一致：前端逐台调端点，实时进度、可中断）；一期不做并发 |
| 6 | 凭据 | 复用登录会话（`sessionManager`，与采集同一模式）：表单传参、不落盘、不落库、不进日志 |

## 二、需求 1：发现汇总视图

### 后端（`api/audit.py`）

| 端点 | 说明 |
|---|---|
| `GET /api/audit/runs/{run_id}/by-rule`（新） | 按规则聚合：`[{rule_id, title, level, source, count, exempt_count, devices: [设备名...]}]`，按 count 降序。设备名单随行返回（36 台规模，无需按需拉） |
| `GET /api/audit/runs/{run_id}?rule=`（扩展） | 明细加按 `rule_id` 过滤（与 level/device 并列） |

口径与趋势页一致：**count = 未豁免命中台数**（`exempt_case()`），`exempt_count` = 豁免台数（生效中 + 即将到期）。

### 前端（`ComplianceAudit.tsx`）

新增「发现排行」卡片（放在收敛/恶化榜之后）：每行一条发现
（标题 + 档位 + `N 台` + 豁免数），**点击展开设备名单**（chips，点击跳查看器）；
排序按台数降序 —— "6 台用了外部 NTP"直接可见。行尾带「批量处理」按钮（衔接需求 2）。

## 三、需求 2：批量执行命令

### 页面（新独立页 `BatchExec.tsx`，路由 `/batch-exec`，导航「批量执行」）

```
① 选设备              ② 写命令               ③ 预检 → 确认 → 执行 → 留痕
┌────────────────┐   ┌──────────────────┐   ┌──────────────────────────────┐
│ 筛选：站点/类型 │   │ 模式：查询/配置   │   │ 黑名单硬拦截（命中即拒绝）    │
│ 复选 + 全选     │   │ 命令文本框（多行）│   │ 锁死风险黄色警告（可继续）    │
│ ← 审计带入      │   │ ← fix_text 带入   │   │ 配置模式：二次确认对话框      │
│                │   │ ☐ 执行后保存配置  │   │ 逐台执行（实时进度，可停止）  │
└────────────────┘   └──────────────────┘   │ 结果落库；每台输出可展开/复制 │
                                            └──────────────────────────────┘
底部：历史批次列表 → 点开看每台结果（含输出全文）→ 可删除批次
```

设备选择复用现有设备清单（`deviceApi`）与站点筛选习惯；从审计带入经路由 state
（`navigate('/batch-exec', {state: {devices, commands, mode}})`），不塞 URL。

### 命令安全（`services/batch_exec.py`）

**硬拦截**（服务端拒绝执行，前端预检也会展示）：

| 模式 | 命中即拒绝 |
|---|---|
| 重启/擦除 | `reload`、`erase`、`delete`、`format`、`squeeze`、`factory-reset`/`factory_reset`、`write erase`、`clear config`/`clear startup` |
| 引导 | `boot`（boot system / boot loader 等一切 boot 开头）、`config-register`、`tftpdnld`、`usb` |

**警告**（黄色提示，可继续 —— 可能锁死自己或断链路）：
`no username` / `username ... privilege`、`no aaa`、`aaa authentication`、`no enable`、
`no ip route` / `no ip default-gateway`、`no interface vlan` / `no interface mgmt`、
`no vlan`、`shutdown`、`no spanning-tree`。

匹配规则：逐行、不区分大小写、按词边界；**不锚定行首**（`no reload` 这类前缀也要命中——
与 redact 的教训同源：命令可能以 `no `/空格开头）。两种模式都查。

### 执行器

复用 `DeviceConnection`（netmiko 封装：自动关分页、Aruba timing 兼容、超时处理）：
- 连接 → `check_enable_mode()`，不在特权模式时设 `secret=password` 后 `enable()`（失败给可读报错）
- 查询模式：逐条 `send_command(cmd, read_timeout=60)`，输出按 `cmd` 分段拼接
- 配置模式：`send_config_set(commands, read_timeout=60)`（自动进出 config 模式）；勾选保存则追加 `write memory`
- 任何异常 → `{status: failed, error: ...}`，单台失败不影响队列

### 存储（v17 迁移）

```sql
batch_runs(id, batch_id TEXT UNIQUE, created_at, username, mode, save_config,
           command_text, device_count, note)          -- 命令全文只存一份
batch_results(id, batch_id, device_name, status,      -- success|failed|blocked|skipped
              output, error, started_at, finished_at, UNIQUE(batch_id, device_name))
```

### API（`api/batch.py`，注册进 `main.py`）

| 端点 | 说明 |
|---|---|
| `POST /api/batch/check`（JSON） | 命令预检：返回 `{blocked: [{cmd, reason}], warnings: [...]}` |
| `POST /api/batch/execute`（Form） | 单台执行：`device_name / username / password / commands / mode / save / batch_id / note`。首台到达时 upsert `batch_runs`；执行前**服务端再查一次黑名单**（防御） |
| `GET /api/batch/history?limit=` | 批次列表（含每批成功/失败台数） |
| `GET /api/batch/history/{batch_id}` | 批次详情 + 每台结果 |
| `DELETE /api/batch/history/{batch_id}` | 删除批次与结果 |

## 四、实施步骤（每步单独提交）

1. 本计划文档
2. 需求 1 后端：`by-rule` 端点 + `get_run` 的 rule 参数 + 测试
3. 需求 1 前端：「发现排行」卡片（展开设备名单 + 批量处理入口占位）+ i18n + 构建
4. v17 迁移（两张表）+ 迁移测试
5. `services/batch_exec.py`（黑名单 + 执行器）+ 测试
6. `api/batch.py`（check / execute / history / delete）+ 注册 + 测试
7. 前端 `BatchExec.tsx` + 导航 + 路由 + api.ts/types + i18n + 构建
8. 审计页「批量处理」联动接线（带入设备 + fix_text）+ 浏览器端到端
9. `.wolf` 记录（memory/anatomy/cerebrum/buglog）

## 五、验证方式

- 单测：by-rule 聚合口径（豁免不计入 count）、黑名单（拦截/警告/放行三态 + `no reload` 前缀、
  大小写、词边界不误伤 `no ntp server`）、执行器（mock netmiko：查询/配置/保存/提权/异常各一条）、
  API（check/execute/history/delete + 服务端拦截兜底）
- 回归：现有测试全绿（**当前 481 项**）；审计等价性不受影响（本项不动引擎）
- 端到端（浏览器）：审计页展开某发现 → 设备名单正确 → 点「批量处理」跳转带入设备与命令 →
  输入查询命令 → 预检 → 执行 2-3 台真实设备 → 进度与输出、历史留痕
- 危险命令实测：`reload` 被拦截（前端红字 + 服务端拒绝）

## 六、风险与坑

1. **`fix_text` 可能含占位符**（如 `<vlan-id>`）：带入后**不自动执行**，用户必须在预览里过一遍 —— 文案要写清。
2. **enable 提权**：现网账号多为 privilege 15（采集 `show running-config` 能成功即证明权限够）；
   少数设备可能卡在 `>`，报错要指名"可能缺 enable 密码"，不静默。
3. **输出可能含敏感信息**（`show run` 的密码行）：落库仅在本机 SQLite，可接受；**不进日志、不外发**。
4. **批量误操作面**：三层保护之外，执行按钮在配置模式下必须过确认对话框；停止按钮只停"未开始的"，
   已连接中的那台等它跑完（断开要干净）。
5. **UI 语义**：这是运维工具不是审计 —— 页面文案用「执行」而非「修复」，「批量执行」入口
   不要在审计页营造"一键修复"的错觉（发现排行里的按钮文案让用户确认后自行带入）。
6. **迁移只在 `init_db()` 时跑**：开发/回归前先确认主库迁到 v17（既有教训，别在旧 schema 上跑新查询）。
