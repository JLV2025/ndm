# 例外登记机制（二期）—— 设计与实施计划

> 上游：`docs/superpowers/plans/2026-09-18-compliance-audit.md`（配置审计总计划）
> 本文件 = 设计稿 + 实施计划（沿用一期做法，二者合一）。

## 一、背景与目标

总部基线第 3 章要求「已批准的例外不得判为不合规」。一期用「规则写得克制」控制噪声，
但**逐条接受偏离**没有正规出口：把已批准的偏离一直报成建议会让人对报告脱敏。

本机制解决三件事：

1. **登记**：按 设备 / 站点 / 规则 登记已批准例外，含理由、补偿控制、批准人、到期日；
2. **豁免**：审计命中时标注「已批准例外」，**保留可见但单列一类**，不计入建议统计；
3. **生命周期**：到期自动失效（回到普通统计并显著标注），撤销走软删除（历史可追溯）。

### 关键设计决策（2026-09-20 与用户逐条确认）

| # | 决策 | 定案 |
|---|---|---|
| 1 | 存储位置 | **独立文件 `config/audit/_exceptions.yaml`**（不动规则文件；`ruleset_hash` 不被例外增删污染，趋势里「标准变没变」与「豁免变没变」可分开判断） |
| 2 | 命中语义 | **保留可见 + 单列一类**：findings 仍出现在报告里（带徽章与依据），但不计入建议统计，单独归「已批准例外 N 条」 |
| 3 | 过期处理 | **自动失效 + 页内提醒**：到期回到普通统计并显著标注；标准页有「即将到期（30 天内）/ 已过期」视图。**不进告警表**（审计重跑会重新报出来，避免两套提醒打架） |
| 4 | 字段约束 | **理由 + 批准人 + 到期日必填**（默认 180 天）；「永久豁免」不允许——长期不适用属**标准问题**，应改标准（`exempt_sites` / 停用规则），走 git 评审 |

### 与既有机制的分工（写进 `_exceptions.yaml` 文件头）

- 标准对本组织某类设备**根本不适用** → 改标准（`exempt_sites` / `enabled: false`），有评审记录
- 标准适用、但**这里的偏离暂时被接受** → 登记例外，必有到期日，到期复核

## 二、设计

### 数据模型 `config/audit/_exceptions.yaml`

```yaml
meta:
  version: 1

exceptions:
  - id: exc-001
    rule_id: hq_cs_no_snmp_community        # 必须存在于规则库
    scope: {type: device, value: SHAD1SWI01}  # device | site | all
    reason: 该设备为上联汇聚，改造前无法满足…
    compensating_control: 已用 ACL 限制管理网段访问   # 选填
    approved_by: 张工
    approved_at: 2026-09-20
    expires_at: 2027-03-20
    revoked:                                 # 选填；撤销 = 软删除
      at: 2026-12-01
      by: 李工
      reason: 设备已下线
```

- **状态是推导的，不存字段**：有 `revoked` → 已撤销；`expires_at < 今天` → 已过期；
  30 天内到期 → 即将到期；否则生效中。过期判断用**审计运行日**（豁免是"现在"的状态）。
- **撤销 = 软删除**：历史审计结果里的 `exempt_by` 要能永远查到出处。
- `scope: all` 保留，但仅用于"全网暂时都做不到、限期重审"；长期不适用应改标准。

### 加载与校验（`loader.py` 扩展）

- `EXCEPTIONS_FILE = "_exceptions.yaml"`，可选文件；随 `load_standard()` 载入 → `std["exceptions"]`
- 校验（一次报全部）：
  - `id` 必填、格式 `^exc-\d{3,}$`、唯一
  - `rule_id` 必须存在于规则库（含已停用规则）—— 防拼写错误导致豁免静默失效
  - `scope.type ∈ {device, site, all}`；device/site 必须有 value；site 值必须是已知站点码
  - `reason` / `approved_by` 非空；`approved_at` / `expires_at` 为合法 `YYYY-MM-DD`
  - `expires_at > approved_at`
  - 同一 `(rule_id, scope.type, scope.value)` 不允许重复登记
  - `revoked`（选填）需含 at / by / reason，at 为合法日期
- `exceptions_hash(std)` 独立指纹；**`ruleset_hash` 不含例外**

### 引擎（`engine.py`）

- `analyze()` 末步逐条匹配例外；签名不变，读 `std.get("exceptions") or []`（向后兼容）
- 匹配：rule_id 相同 + scope 命中；**最具体者优先**（device > site > all）；
  **已撤销的条目不参与匹配**（设备级被撤销后站点级仍可生效）
- 命中生效中/即将到期 → finding 挂
  `exempt: {exception_id, approved_by, reason, compensating_control, expires_at, status}`
- 命中但**已过期** → 同样挂 `exempt` 但 `status: "expired"`，**仍计入普通建议统计**
- `counts` 五档**只数未豁免的**；新增 `exempt_count`（生效中 + 即将到期）
- 新增 `exception_status(exc, today=None)` 供引擎与 API 共用

### 存储（v15 迁移）

- `audit_findings` 加 `exempt_by TEXT`（例外 id，可索引）+ `exempt_json TEXT`（当时快照：
  批准人/依据/到期日/状态）—— 历史审计要能回答"那次审计时它被谁批的豁免"
- `audit_runs` 加 `exceptions_hash TEXT`（趋势的下一期要用）
- 旧数据两列 NULL，兼容

### API（`api/audit.py` 增补）

| 端点 | 说明 |
|---|---|
| `GET /api/audit/exceptions` | 列表 + 推导状态；`state=active\|expiring\|expired\|revoked\|all` 筛选 |
| `POST /api/audit/exceptions` | 新建（自动取号 `exc-NNN`；`approved_at` 默认今天） |
| `PUT /api/audit/exceptions/{id}` | 编辑（续期 / 改理由），`base_hash` 乐观锁 |
| `POST /api/audit/exceptions/{id}/revoke` | 撤销（写 revoked 块 + 原因） |

- 写入链**复用规则编辑的**：备份（`.backups/` 留 10 份）→ 原子替换（临时文件 + `os.replace`，
  Windows 占用重试）→ 校验失败回滚 → 清缓存
- **不提供物理删除**
- `GET /api/audit/device/{name}` envelope：findings 带 `exempt`；新增 `exempt_count`
- `POST /api/audit/run`：`exempt_by` / `exempt_json` / `exceptions_hash` 入库

### 前端

- **标准页新增「例外登记」标签页**：列表（规则 / 范围 / 理由 / 批准人 / 到期日 / 状态徽章）；
  默认只看 生效中 + 即将到期，可切 已过期 / 已撤销 / 全部；新增、续期、撤销对话框
- **查看器审计模式**：豁免条目灰色系 + 「已批准例外」徽章（展开看批准人/依据/到期日）；
  已过期的显示醒目「例外已过期」戳记；顶部统计加「已批准例外 N 条」独立行；
  每条 finding 卡片加「登记例外」按钮 → 预填规则与本设备 → 保存后即时刷新
- i18n zh/en 两份补齐

## 三、实施步骤（每步单独提交）

1. `_exceptions.yaml`（空登记表 + 文件头约定）+ `loader.py` 加载/校验/`exceptions_hash` + 测试
2. `engine.py` 豁免标记（匹配/优先级/过期/撤销）+ 计数 + 测试
3. v15 迁移 + `run_audit` 落库 + 迁移测试
4. API 四个端点（CRUD + 撤销）+ 测试
5. 前端：types + api service + 标准页「例外登记」标签页
6. 前端：查看器审计模式豁免呈现 + 「登记例外」入口 + i18n
7. 收尾：`.wolf` 记录（cerebrum / anatomy / memory）

## 四、验证方式

- **回归硬指标**：现有 **355 项测试全绿**；移植等价性 **207 = 207**
  （无例外时 `analyze()` 行为与现在逐字节一致）
- 单测覆盖：loader 坏数据全套（坏 scope / 缺字段 / 重复 id / 未知 rule_id / 日期不合法 /
  重复登记）、**零改动往返稳定**（ruamel 闸门，与规则文件同规格）、engine 优先级与过期/
  撤销、计数对账、API CRUD + 乐观锁 + 备份 + 撤销、迁移 v14→v15
- 端到端（浏览器）：登记一条例外 → 审计结果变化（该条进「已批准例外」组）→
  改 expires_at 到昨天 → 重新审计 → 该条回到普通统计并标「例外已过期」→ 撤销 → 恢复原状

## 五、风险与坑

1. **`analyze()` 签名不变**：例外从 `std` 取，不加新入参——测试直接调 `analyze()` 的地方很多，
   加位置参数会连带改一片。
2. **`ruleset_hash` 绝不能把例外算进去**：否则登记一条例外会让所有历史审计看起来"标准变过"。
3. **匹配细节**：已撤销条目不参与匹配；过期条目不豁免但挂标注——两处都容易写成"命中即豁免"。
4. **前端标红契约不变**：豁免条目仍按 `finding.lines` 查表着色，只是配色改灰 + 徽章。
5. **写入链复用**：`_backup` / `_atomic_dump` / 乐观锁直接复用 `api/audit.py` 既有函数，
   不另起一套（两套写入逻辑迟早漂移）。
6. **`_exceptions.yaml` 参与 ruamel 往返闸门测试**：跨行标量必须 `>-` 折叠块
   （一期已经踩过：普通标量回写会被合并成一行）。
