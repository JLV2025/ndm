# 设备生命周期（EoL + 保修期）（二期）—— 设计与实施计划

> 上游：`docs/superpowers/plans/2026-09-18-compliance-audit.md`（配置审计总计划，定案 2：EoL 归「风险提示」）
> 前置：例外机制、趋势页（均已落地）
> 本文件 = 设计稿 + 实施计划（本项目惯例，二者合一）。

## 一、背景与已核实的可行性（2026-09-20 调研）

| 厂商 | EoL | 保修期 |
|---|---|---|
| **Cisco** | ✅ 官方 **EoX API**：`EOXByProductID`（每次 ≤20 个型号）/**`EOXBySerialNumber`**/`EOXByDates`；返回 EoS 日期、`LastDateOfSupport`、公告号与链接、迁移建议。OAuth2 凭据来自 `apiconsole.cisco.com`（用户正在办理） | ⚠️ `SN2INFO` API（`/product/v1.0/coverage/summary/serial_numbers/...` 返回 `warranty_end_date`/`is_covered`）**仅对 SNTC 客户/PSS 合作伙伴开放** → 本期不做自动，走手工 |
| **Aruba / HPE** | ❌ 无公开 API（只发公告） → 离线登记 | ❌ 只有网页表单（逐台人工查） → 手工登记 |

### 用户定案（2026-09-20）

1. **双轨**：Cisco 走 EoX API（凭据到位前手工兜底）；Aruba 手工登记（允许页面编辑）。
2. **保修期按手工编辑设计**（Cisco 无 SNTC 权限、Aruba 无 API；自动查是加分项不是前提）。
3. **有 EoL / 保修信息的进审计，算「风险」；没有信息的设备显示「待查」TBD，算建议**（不放任静默通过）。
4. **「待查」必须聚合**：N 台未登记 → **一条**网络级条目（否则 20 条"待查"会淹掉真问题）。
5. **陈旧数据回退**：超过 365 天未复核（`verified_at`）的重新算「待查」——两年前抄的日期不能一直冒充"已确认"。

## 二、设计

### 数据模型（v16 迁移，**进 DB 不进 YAML**）

> 与例外机制相反的理由：例外是**决策记录**（谁批的、到期复核）→ YAML + git 追溯；
> EoL/保修是**设备事实数据**，随 API 刷新而变、条数多（≈50 个序列号）、且需要"手工值不被自动刷新覆盖"的语义 → 进库 + 页面编辑。

```sql
-- 型号级 EoL 缓存：一次查到，同型号所有设备共享
CREATE TABLE eol_models (
    model          TEXT PRIMARY KEY,   -- 型号（Cisco PID 或 Aruba 型号号，如 C9500-48Y4C / JL659A）
    description    TEXT,               -- 产品描述
    end_of_sale    TEXT,               -- YYYY-MM-DD
    end_of_support TEXT,               -- LastDateOfSupport
    announcement   TEXT,               -- 公告日期
    bulletin       TEXT,               -- 公告编号
    bulletin_url   TEXT,
    source         TEXT,               -- api（Cisco EoX）| manual
    fetched_at     TEXT,
    updated_by     TEXT,
    note           TEXT
);

-- 设备/序列号级生命周期：保修期为主。堆叠设备逐成员一行（NDM 已采到成员序列号）
CREATE TABLE device_lifecycle (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name  TEXT NOT NULL,        -- 冗余设备名：设备改名/删除后仍可追溯（同 audit_findings 做法）
    serial       TEXT NOT NULL DEFAULT '',
    model        TEXT,                 -- 冗余当时型号
    warranty_end TEXT,                 -- YYYY-MM-DD
    note         TEXT,                 -- 例：Smart Net 到期日 / 仅硬件换修
    source       TEXT,                 -- manual | api
    verified_at  TEXT,                 -- 何时核实的（陈旧判定用）
    verified_by  TEXT,
    updated_at   TEXT,
    UNIQUE(device_name, serial)
);
```

### 审计接线（三条规则 + 一个新的通用机制）

1. **判定器读"资产上下文"**：`source.load_lifecycle(db, device_name)` 装好（含该设备各序列号的保修期、型号 EoL、已知序列号清单），
   经 `analyze(..., lifecycle=...)` 挂到 `dev.lifecycle` —— 与 `port_context` 同一模式。
2. **三条规则**（`config/audit/org-convention.yaml`，severity=convention）：
   | 规则 | 条件 | 档位 |
   |---|---|---|
   | `ops_eol_announced` | 型号已公布停止销售/停止支持 | 风险提示 |
   | `ops_warranty_expired` | 任一序列号保修已过期，或 `params.warn_days`（默认 90）内到期 | 风险提示 |
   | `ops_lifecycle_unknown` | 型号 EoL 与全部序列号保修**都没登记**，或有记录但 `verified_at` 距今 > `params.stale_days`（默认 365） | 需人工判断（**collective**） |
3. **「集体性折叠」`engine.collapse_collective()`（新通用机制，全量审计时用）**：
   规则标 `collective: true` 时，若命中设备数 ≥ 阈值（`params.collective_threshold`，默认 3），
   把逐台条目折叠成**一条**网络级条目（标题含台数、detail 列出设备名），
   `device_name` 记为 `全网`。单台审计不折叠（一台就是一台的事）。
   —— 这同时补上了一期承诺但未实现的「集体性漏配单独成类」缺口。
4. 运行器 `run_full_audit` 改为：先收集全部 findings → 折叠 → 再落库（计数同步调整）。

### API（新增 `backend/api/lifecycle.py`）

| 端点 | 说明 |
|---|---|
| `GET /api/lifecycle/device/{name}` | 该设备：已知序列号（来自最近采集，逗号串拆分）+ 各自保修记录 + 型号 EoL + 刷新可用性 |
| `PUT /api/lifecycle/device/{name}` | 手工登记/修改（逐序列号）：`warranty_end` / `note` / `verified_by`；`source=manual`，自动写 `verified_at` |
| `POST /api/lifecycle/import` | **批量粘贴导入**：文本行 `序列号,到期日[,备注]`（逗号/制表/空格分隔）；按序列号自动匹配设备（大小写不敏感、去空格）；返回匹配/未匹配清单 |
| `PUT /api/lifecycle/model/{model}` | 手工登记型号 EoL（Aruba 与凭据到位前的 Cisco 都用它） |
| `POST /api/lifecycle/refresh` | Cisco EoX 刷新全部型号（读环境变量凭据；**未配置凭据时返回可读原因而不是报错**） |
| `GET /api/lifecycle/overview` | 全部设备的生命周期概况（供页面筛选"待查"清单） |

### Cisco EoX 客户端（`backend/services/eox_client.py`）

- OAuth2 client_credentials → `https://id.cisco.com/oauth2/default/v1/token`（token URL 与 API base 可配）；
  `GET https://apix.cisco.com/supporttools/eox/rest/5/EOXByProductID/1/{pids}?responseencoding=json`；型号按 20 个一组切分。
- 凭据走环境变量 `CISCO_API_CLIENT_ID` / `CISCO_API_CLIENT_SECRET`（与项目既有 LLM key 同模式，**绝不落盘**）。
- 解析字段：`EOLProductID` / `ProductIDDescription` / `EndOfSaleDate.value` / `LastDateOfSupport.value` /
  `EOXExternalAnnouncementDate.value` / `ProductBulletinNumber` / `LinkToProductBulletinURL`。
- **诚实标注**：凭据到位前无法做实盘验证；单元测试用官方文档的响应样例（mock HTTP），拿到凭据当天即可实跑。

### 前端

- **设备详情页新增「生命周期」卡片**：型号 EoL 行（状态/日期/来源/编辑）+ 逐序列号保修表（内联编辑保存）+
  「刷新 EoL（Cisco）」按钮（未配凭据时提示）+ 「批量导入」对话框（粘贴 → 反馈匹配结果）。
- i18n zh/en；类型与服务进 `types/index.ts` / `services/api.ts`。
- 聚合条目在审计报告/趋势页的呈现：设备列显示 `全网`，detail 列出设备名。

## 三、实施步骤（每步单独提交）

1. 本计划文档
2. v16 迁移 + `backend/storage/lifecycle_dal.py`（upsert/get/import 匹配）+ 测试
3. 审计接线：`source.load_lifecycle` + `analyze(lifecycle=)` + 三条判定器 + `collapse_collective` + 规则 YAML + 测试
4. `backend/api/lifecycle.py` 六个端点 + 测试
5. Cisco EoX 客户端（mock 测试 + 未配凭据的可读路径）+ 测试
6. 前端：设备详情卡片 + 批量导入 + i18n + 构建
7. 浏览器端到端 + `.wolf` 记录

## 四、验证方式

- 单测：迁移 v15→v16；dal 的 upsert/匹配（大小写/空格/堆叠成员）；判定器三条（有日期/无信息/陈旧）；
  **折叠阈值**（≥3 台折叠成一条、<3 台不折叠、单台审计不折叠）；端点（含未配凭据的 refresh）；EoX 解析（mock）。
- 回归：401 项全绿；等价性 486=486（未登记生命周期时，审计结果与现在一致——新规则在**无数据**时会命中
  「待查」，所以等价性基线会变：需要重新锁定基线并说明变化原因）。
  ⚠️ 这条要如实记录：新增规则必然改变命中数，这是**预期变更**而非回归。
- 端到端：设备详情页登记一条保修期 → 审计报告出现对应风险条目；导入多个序列号 → 待查条目从聚合列表里消失。

## 五、风险与坑

1. **等价性基线会变**：新规则上线后全量命中数不再是 486。做法：先在**规则全部启用**下重新锁定基线，
   并单独验证「把三条新规则停用后仍为 486」——保证既有判定零变化。
2. **折叠会改变落库形态**：`audit_findings.device_name='全网'` 是合成值；按设备筛选时它自成一类（可接受，已在 UI 说明）。
3. **序列号匹配**要处理：大小写、空格、堆叠成员串拆分、重复序列号（同序列号多设备 → 全部更新并提示）。
4. **Cisco EoX 的 PID 与设备型号可能不同**（EoX 返回 orderable PID）：先用 `devices.model` 查，未命中再尝试通配；查不到不等于 EoL。
5. **不做后台定时刷新**：刷新是显式动作（按钮 / 将来可挂采集后），避免对外部服务的常驻依赖。
6. **保修与合同是两回事**：`warranty_end` 是保修（hardware warranty），不是 Smart Net 合同到期——`note` 字段要写清楚口径。
