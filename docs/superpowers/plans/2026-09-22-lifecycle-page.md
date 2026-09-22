# 生命周期页 Implementation Plan（Plan 2 / 共 2 份）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增「生命周期」导航页——显示、编辑全部物理设备的 EoS/EoL 与维保信息，并用三色标识状态；详情页卡片接同一套状态判定。

**Architecture:** 状态判定（三色）是**后端纯函数**（可 pytest，单一来源），API 在每行上返回 `warranty_status` / `eol.status`；前端只做"状态 → 颜色"映射。数据源是 Plan 1 的物理行（member + standalone），编辑复用既有 `/api/lifecycle/*`（同一份表，无第二份数据）。**邮件/告警推送不在本期**（spec 第十三节：后续可选）。

**Tech Stack:** Python 3 / FastAPI / SQLite；React 18 + MUI + TypeScript（`npx tsc --noEmit` 验证）。

**Spec:** `docs/superpowers/specs/2026-09-22-device-identity-design.md`（第十三节）

**前置依赖：Plan 1（`2026-09-22-device-identity-model.md`）已完成**——本计划直接读 `kind='member'` 行。若必须在 Plan 1 之前实施：数据源临时改用 `reports._expand_device_members` 展开（替换点集中在 Task 2 的 `_list_physical_rows` 一个函数内）。

## Global Constraints

- 三色判定（spec 第十三节，**判定顺序即优先级**）：
  - 维保：有到期日且剩余 > 2 个月 = `ok`（绿）；有到期日且剩余 ≤ 2 个月 = `soon`（橙）；**未填写到期日 = `missing`（橙）**；已过期、或未填写且备注归一化（去首尾空格、忽略大小写）**等于** `unavailable` = `expired`（红）。
  - EoS/EoL：对「停止销售」「停止支持」两日期**分别判定、取最严重（expired > soon > ok）**——已过 = `expired`（红）；剩余 ≤ 6 个月 = `soon`（橙）；> 6 个月 = `ok`（绿）；两日期都未登记 = `none`（灰）。
  - 月份按**日历月**计算（`now + N 个月`），不是 60/180 天。
- 颜色映射（前端唯一一处）：`ok→success`（绿）/ `soon→warning`（橙）/ `missing→warning`（橙）/ `expired→error`（红）/ `none→text.disabled`（灰）；与既有 MUI 语义色板对齐，不引入新色。
- 编辑入口**两处并存**（spec 第十三节第 5 条）：详情页 `LifecycleCard` 保留编辑；新页面承担全局视角与批量导入。两处写同一 API。
- 语言：界面文案中英双份（`i18n/zh.ts` + `en.ts`）；`t(key, fallback)` 不支持占位符，模板用 JS 字符串拼接。
- **不要用 bash heredoc 写含反引号/花括号的中文内容**（会生成 0 字节怪文件，bug-151 第 8 次）；追加文件一律用 Edit/Write 工具。
- 后端测试在 `backend/` 下跑：`python -m pytest tests/ -q`；前端改完 `npx tsc --noEmit`，再 `npm run build`。
- 每个任务一个提交，提交信息中文。

## File Structure

- Create: `backend/services/lifecycle_status.py` — 三色判定纯函数（唯一实现）
- Modify: `backend/api/lifecycle.py`、`backend/storage/lifecycle_dal.py` — 新增物理清单端点 + 每行状态
- Create: `frontend/src/pages/Lifecycle.tsx` — 新页面
- Modify: `frontend/src/App.tsx`（导航/路由）、`frontend/src/services/api.ts`、`frontend/src/i18n/zh.ts` + `en.ts`、`frontend/src/types/index.ts`
- Modify: `frontend/src/components/LifecycleCard.tsx` — 接状态与颜色
- Tests: `backend/tests/test_lifecycle_status.py`、`backend/tests/test_lifecycle_api.py`（追加）

---

### Task 1: 三色判定纯函数

**Files:**
- Create: `backend/services/lifecycle_status.py`
- Test: `backend/tests/test_lifecycle_status.py`

**Interfaces:**
- Consumes: 无
- Produces（Task 2/4 依赖，签名不可改）：
  - `warranty_status(warranty_end: str, note: str, today: date | None = None) -> str` → `"ok" | "soon" | "missing" | "expired"`
  - `eol_status(end_of_sale: str, end_of_support: str, today: date | None = None) -> str` → `"ok" | "soon" | "expired" | "none"`
  - 日期格式：`YYYY-MM-DD`；空串/非法格式按"未登记"处理

- [ ] **Step 1: 写失败测试**

```python
"""三色状态判定测试（spec 第十三节：绿在保 / 橙临近 / 红出保）"""
from datetime import date
from services.lifecycle_status import warranty_status, eol_status

TODAY = date(2026, 9, 22)


def test_在保_剩余超两个月():
    assert warranty_status("2027-01-01", "", TODAY) == "ok"     # 剩 3 个月+


def test_临近_两个月内():
    assert warranty_status("2026-11-21", "", TODAY) == "soon"   # 恰好 +2 月
    assert warranty_status("2026-11-30", "", TODAY) == "soon"


def test_已过期():
    assert warranty_status("2026-09-21", "", TODAY) == "expired"


def test_未登记为橙色():
    assert warranty_status("", "", TODAY) == "missing"
    assert warranty_status("", "在保", TODAY) == "missing"


def test_unavailable按出保():
    assert warranty_status("", "Unavailable", TODAY) == "expired"
    assert warranty_status("", " unavailable ", TODAY) == "expired"   # 去空格/忽略大小写
    assert warranty_status("", "unavailable info", TODAY) == "missing"  # 等于才算，包含不算


def test_eol_六个月阈值():
    assert eol_status("2027-04-01", "", TODAY) == "ok"          # 超 6 个月
    assert eol_status("2026-12-01", "", TODAY) == "soon"        # ≤ 6 个月
    assert eol_status("", "", TODAY) == "none"


def test_eol_取最严重():
    assert eol_status("2026-01-01", "2028-01-01", TODAY) == "expired"   # 停止销售已过
    assert eol_status("2026-12-01", "2028-01-01", TODAY) == "soon"      # 一个临近
    assert eol_status("2027-04-01", "", TODAY) == "ok"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_lifecycle_status.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

```python
"""生命周期三色判定 —— 唯一实现（spec 第十三节）

判定顺序即优先级（红 > 橙 > 绿）。月份按日历月计算。
"""
from datetime import date

WARRANTY_UNKNOWN_NOTE = "unavailable"   # 抄自 Cisco/HPE 保修查询页：查无结果


def _parse(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _add_months(today: date, months: int) -> date:
    m = today.month - 1 + months
    return date(today.year + m // 12, m % 12 + 1, today.day)


def _trend(end: date, today: date, soon_months: int) -> str:
    if end < today:
        return "expired"
    return "soon" if end <= _add_months(today, soon_months) else "ok"


def warranty_status(warranty_end: str, note: str, today: date | None = None) -> str:
    today = today or date.today()
    end = _parse(warranty_end)
    if end:
        return _trend(end, today, 2)
    if (note or "").strip().lower() == WARRANTY_UNKNOWN_NOTE:
        return "expired"
    return "missing"


def eol_status(end_of_sale: str, end_of_support: str, today: date | None = None) -> str:
    today = today or date.today()
    ranks = {"expired": 3, "soon": 2, "ok": 1, "none": 0}
    results = []
    for raw in (end_of_sale, end_of_support):
        end = _parse(raw)
        results.append(_trend(end, today, 6) if end else "none")
    return max(results, key=lambda s: ranks[s])
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_lifecycle_status.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/services/lifecycle_status.py backend/tests/test_lifecycle_status.py
git commit -m "生命周期三色判定：绿在保/橙临近(维保2月·EoL 6月)/红出保，Unavailable 按出保"
```

---

### Task 2: 生命周期 API —— 物理设备清单 + 每行状态

**Files:**
- Modify: `backend/api/lifecycle.py`（新增端点；`get_device_lifecycle` 响应加 status）
- Modify: `backend/storage/lifecycle_dal.py`（`list_physical_rows` 装配查询）
- Test: `backend/tests/test_lifecycle_api.py`（追加）

**Interfaces:**
- Consumes: `lifecycle_status.warranty_status/eol_status`（Task 1）、`device_dal.list_physical()`（Plan 1 Task 6）
- Produces:
  - `GET /api/lifecycle/physical` → `{"devices": [PhysicalLifecycleRow, ...]}`
    ```
    PhysicalLifecycleRow = {
      "name": "SZXD1SWI01-1",       # 物理名（存储名）
      "display_name": "SZXD1SWI01-1",# 展示名（1 成员堆叠 → 基础名，走 device_identity.display_name）
      "device": "SZXD1SWI01",        # 所属堆叠/单机（编辑时 PUT 的目标）
      "kind": "member", "serial": "FCW2129B3TR", "model": "C9500-24Y4C", "location": "SZX",
      "warranty_end": "2027-03-01", "note": "", "warranty_status": "ok",
      "eol": {"end_of_sale": "2028-01-01", "end_of_support": "2029-01-01", "status": "ok"},
      "source": "manual", "verified_at": "2026-09-01"
    }
    ```
  - `GET /api/lifecycle/device/{name}`：`serials` 每项增加 `warranty_status`

- [ ] **Step 1: 写失败测试**（临时库造 1 堆叠（2 成员）+ 1 单机，写保修与 EoL 行，断言两份响应的状态字段；`Unavailable` 行 = expired；无日期行 = missing；EoS 已过 = eol.status expired）
- [ ] **Step 2: 跑测试确认失败** — Run: `cd backend && python -m pytest tests/test_lifecycle_api.py -q`
- [ ] **Step 3: 实现**：`lifecycle_dal.list_physical_rows(conn)` 一次查询物理行 + LEFT JOIN 最新采集（拿 serial/model）+ `device_lifecycle`（保修）+ `eol_models`（按 model，逗号串拆分去重）；`api/lifecycle.py` 装配状态字段。**筛选/排序放前端**（49 行量级，符合项目既有偏好）。
- [ ] **Step 4: 跑测试确认通过** — `cd backend && python -m pytest tests/test_lifecycle_api.py tests/test_lifecycle_dal.py -q`
- [ ] **Step 5: 提交**

```bash
git add backend/api/lifecycle.py backend/storage/lifecycle_dal.py backend/tests/test_lifecycle_api.py
git commit -m "生命周期 API：物理设备清单端点 + 每行三色状态"
```

---

### Task 3: 生命周期页 + 导航 + i18n

**Files:**
- Create: `frontend/src/pages/Lifecycle.tsx`
- Modify: `frontend/src/App.tsx`（导航入口 + 路由）、`frontend/src/services/api.ts`、`frontend/src/i18n/zh.ts`、`frontend/src/i18n/en.ts`、`frontend/src/types/index.ts`

**Interfaces:**
- Consumes: `GET /api/lifecycle/physical`（Task 2）；既有 `PUT /api/lifecycle/device/{name}`、`PUT /api/lifecycle/model/{model}`、`POST /api/lifecycle/import`、`POST /api/lifecycle/refresh`
- Produces: 页面路由 `/lifecycle`；颜色映射常量 `STATUS_COLOR`（页面与卡片共用，放 `frontend/src/shared/constants.ts` 追加）

- [ ] **Step 1: 颜色映射 + 类型**

`frontend/src/shared/constants.ts` 追加：

```ts
export const STATUS_COLOR: Record<string, 'success.main' | 'warning.main' | 'error.main' | 'text.disabled'> = {
  ok: 'success.main', soon: 'warning.main', missing: 'warning.main',
  expired: 'error.main', none: 'text.disabled',
}
```

`types/index.ts` 追加 `PhysicalLifecycleRow`（字段同 Task 2 的接口定义）。

- [ ] **Step 2: 页面骨架**（表格 + 筛选 + 排序）

`Lifecycle.tsx`：MUI 表格，列 = 物理名（`display_name`）/序列号/位置/型号/停止销售/停止支持/维保到期/状态/来源/最后核验。状态列 = 圆点 + 文案，颜色取 `STATUS_COLOR[row.warranty_status]`（EoS/EoL 两列各自取 `row.eol.status`）。顶部筛选 chip 组：全部 / 在保 / 临近 / 出保 / 未登记（`expired`+`missing` 同色但独立筛），位置与型号下拉。排序复用 Reports 页的表头点击模式（`sortField/sortDir` state）。

- [ ] **Step 3: 编辑 + 批量导入**（复用 LifecycleCard 的既有交互模式）

- 行内编辑：维保日期（日期输入）+ 备注 → 保存时对 `row.device` 调 `PUT /api/lifecycle/device/{device}`（只提交该序列号的行，`rows=[{serial, warranty_end, note}]`）；
- 型号 EoL 登记：型号单元格点击打开对话框（字段同 `ModelEolUpdate`）→ `PUT /api/lifecycle/model/{model}`；
- 批量导入：复用 `POST /api/lifecycle/import`（textarea 粘贴，返回 matched/unmatched/ambiguous 原样展示）；
- EoX 刷新按钮：`POST /api/lifecycle/refresh`，未配凭据时展示 400 的可读原因（既有行为）。

- [ ] **Step 4: 导航 + i18n + API client**

`App.tsx` 在导航栏加「生命周期」入口（与「配置审计」等平级）；`api.ts` 加 `lifecycleApi.listPhysical()`；`zh.ts`/`en.ts` 补 key（`lifecycle.page.*`、`lifecycle.status.ok/soon/missing/expired/none`）。**i18n 注意：`t()` 不支持 `{}` 占位符，模板用拼接。**

- [ ] **Step 5: 验证 + 提交**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 无新增类型错误（存量错误：LocationFilter/DirectionPad/LocationTopologyCanvas，与本改动无关）

```bash
git add frontend/src frontend/dist
git commit -m "生命周期页：物理设备清单 + 三色状态 + 编辑/批量导入 + 导航入口"
```

---

### Task 4: 详情页卡片接同一套状态与颜色

**Files:**
- Modify: `frontend/src/components/LifecycleCard.tsx`
- Test: 手动验证（该卡片无自动化测试；状态逻辑已在 Task 1 覆盖）

**Interfaces:**
- Consumes: `GET /api/lifecycle/device/{name}` 的 `serials[].warranty_status`（Task 2）、`STATUS_COLOR`（Task 3）
- Produces: 卡片维保行显示圆点+颜色；型号 EoL 行显示 `eol_status` 颜色

- [ ] **Step 1: 接状态**：维保行左侧加状态圆点（颜色取 `STATUS_COLOR[s.warranty_status]`），未登记显示"未登记"文案（橙色）；EoL 区块用 `eol_status` 上色。
- [ ] **Step 2: 验证**：`cd frontend && npx tsc --noEmit`；用生产库起服务手动核对三台样本（一台在保、一台 `Unavailable`、一台未登记），确认与生命周期页颜色一致。
- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/LifecycleCard.tsx frontend/dist
git commit -m "详情页生命周期卡片：维保行三色状态，与生命周期页同源"
```

---

### Task 5: 验收与收尾

**Files:**
- Modify: `.wolf/anatomy.md`（新文件条目）、`.wolf/cerebrum.md`（定案记录）

- [ ] **Step 1: 全量验证**

Run: `cd backend && python -m pytest tests/ -q`；`cd frontend && npx tsc --noEmit && npm run build`
Expected: 全绿

- [ ] **Step 2: 验收清单**（对照 spec 第十三节）
  1. 生命周期页可显示全部物理设备（成员 + 单机），列含 EoS/EoL/维保/状态/来源；
  2. 三色正确：在保绿、临近橙（维保 2 月 / EoL 6 月）、未登记橙、出保红、`Unavailable` 红、EoS/EoL 全未登记灰；
  3. 编辑可用：行内改维保、型号 EoL 登记、批量粘贴导入（含 matched/unmatched 回显）；
  4. 详情页卡片颜色与页面一致（同一后端判定）；
  5. 邮件/推送确实未做（本期范围外，已记录）。

- [ ] **Step 3: 狼记 + 提交**

```bash
git add -A
git commit -m "生命周期页收尾：验收清单通过，狼记更新"
```

---

## Self-Review 记录（计划自检）

- **Spec 覆盖**：第十三节 1（入口页）→ T3；2（三色 + Unavailable 口径 + 两处共用 helper）→ T1/T2/T4；3（与审计分工）→ 不改审计，仅验证其独立性（T5 验收 4 不涉审计）；4（物理行）→ 依赖 Plan 1；5（现有入口保留）→ T4 保留并升级卡片。
- **判定层选择说明**：spec 只要求"两处共用同一判定"，本计划把判定放在**后端纯函数**（可 pytest），而非前端——单一来源更硬、且天然覆盖未来第三个消费方；如实施时坚持放前端，须同时补前端测试框架（超范围，不推荐）。
- **类型一致性**：`warranty_status` 返回值集合 `ok/soon/missing/expired` 与 `STATUS_COLOR` 键一致；`eol_status` 的 `none` 对应灰色键 `none`。
