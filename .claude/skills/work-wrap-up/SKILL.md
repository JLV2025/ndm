---
name: work-wrap-up
description: 下班交接：把今天的工作成果完整保存并推送到 GitHub，方便其他电脑继续。清理临时文件、更新 OpenWolf 学习记录（.wolf/cerebrum.md、buglog.json、memory.md）、按需更新 README、安全检查，然后提交并推送所有变更。要求快、完整——不跑测试、不构建产物，代码有错误也直接上传。当用户说「收工」「下班」「结束今天的工作」「提交保存一下」等表达结束会话、准备离开时使用。
disable-model-invocation: true
---

# 收工

下班交接：把今天的工作成果（代码 + 学习记录 + 踩坑记录）完整保存并推送到 GitHub，让其他电脑 clone/pull 后能无缝继续。**要快、要完整**——不跑测试、不构建，代码有错误也没关系，直接上传。

前台依次执行以下阶段，不通过 Workflow 后台运行。

## 执行方式

直接在本会话内按顺序调用工具，不使用 `Workflow` 或 `Agent` 工具。

---

## Phase 1：清理临时文件（快速）

按项目类型清理临时文件，让提交体积更小：

```
[ -f requirements.txt ] && find . -type d -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null
[ -f requirements.txt ] && rm -rf .pytest_cache 2>/dev/null
[ -f frontend/package.json ] && rm -rf frontend/tsconfig.tsbuildinfo 2>/dev/null
```

跳过非 git 追踪的构建产物（`dist/`、`venv/` 等）。

---

## Phase 2：更新学习记录（核心，仅当存在 `.wolf/` 目录）

1. 回顾本次会话，追加关键知识点到 `.wolf/cerebrum.md`（Key Learnings / User Preferences / Do-Not-Repeat）
2. 有 bug 修复或踩坑则追加到 `.wolf/buglog.json`（error_message / root_cause / fix / tags）
3. 追加一行到 `.wolf/memory.md`：`| HH:MM | 描述 | 文件 | 结果 | ~tokens |`

若项目没有 `.wolf/` 目录，跳过本阶段。

---

## Phase 3：更新文档（可选）

仅当本次提交引入面向用户的新功能或重大变更时，才更新 `README.md`。

---

## Phase 4：安全检查（快速）

运行 `git status --short` 检查变更文件列表；用 grep 检查敏感信息（密码/密钥）：

```
grep -rni "password\|secret\|token\|api_key\|apikey\|jwt_secret" --include="*.go" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.md" . 2>/dev/null | grep -v node_modules | grep -v ".git/" | grep -v "venv/" | grep -v "__pycache__" | grep -v "config.yaml" | grep -v "\.claude/" | grep -v ".gitnexus/" | grep -v ".playwright-mcp/" | grep -v "frontend-dist" || echo "No secrets found"
```

若 `git status` 出现真实配置、密钥、数据库等明显不该提交的文件，先向用户说明再继续。

---

## Phase 5：提交并推送（快，完整）

1. `git add -A` — 暂存所有变更（完整上传，一个不漏）
2. `git status --short` + `git diff --cached --stat` — 展示本次提交内容
3. 生成中文 commit message（`简短动词短语：详细说明`）
4. `git commit -m "..."` — 提交
5. `git push origin <current-branch>` — 推送，失败立即报错
6. `git fetch origin` 后 `git log origin/<current-branch> --oneline -3` — 验证远程已收到

---

## Phase 6：更新 GitNexus 索引（仅当项目已使用 GitNexus）

代码已推送后，刷新代码知识图，保证其他电脑 clone 后索引是最新的：

1. 检查是否已索引：`npx gitnexus status` — 显示索引时间与符号/关系数；若提示未索引或 stale，继续下一步
2. 创建或更新索引：`npx gitnexus analyze` — **首次运行即创建索引**，之后是增量刷新；commit/merge 后索引变 stale 时同样用它
3. 索引损坏时重建：`npx gitnexus clean` 删除旧索引（会清掉 `.gitnexus/` 并注销注册），再 `npx gitnexus analyze --force` 全量重建
4. 验证索引可用：读 `gitnexus://repo/{name}/context` 资源确认加载成功

若项目没有 `.gitnexus/` 目录且未注册索引（不打算启用 GitNexus），跳过本阶段。

---

## 规则

- 所有阶段在当前会话前台执行，不 fork 子进程
- **不跑测试、不构建**——用户明确要求：要快、要完整，代码有错误直接上传，不要画蛇添足
- 如果有多个仓库都有变更（如技能在 ndm 和全局两处），全部提交推送
- 如果某个阶段无内容可做，直接跳过
- commit message 必须使用简体中文
- 只有用户明确表示收工/结束时才执行，不要在其他时机自行触发
