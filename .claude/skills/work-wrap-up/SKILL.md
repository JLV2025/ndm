---
name: work-wrap-up
description: 执行收工任务：清理文件、更新学习记录、更新文档、检查变更并推送代码
---

# 收工

前台依次执行以下阶段，不通过 Workflow 后台运行。

## 执行方式

直接在本会话内按顺序调用工具，不使用 `Workflow` 或 `Agent` 工具。

---

## Phase 1：清理环境

用 Bash 搜索并清理临时文件：

```
# 清理 Python 缓存
find . -type d -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null

# 清理测试缓存
rm -rf .pytest_cache 2>/dev/null

# 清理 TypeScript 构建缓存（非 dist）
rm -rf frontend/tsconfig.tsbuildinfo 2>/dev/null
```

跳过非 git 追踪的构建产物（`dist/`、`venv/` 等）。

---

## Phase 2：更新学习记录

1. 回顾本次会话的改动，提取关键知识点
2. 追加到 `.wolf/cerebrum.md` 的 `## Key Learnings` 或 `## User Preferences`
3. 检查是否有 bug 修复，追加到 `.wolf/buglog.json`
4. 追加一行到 `.wolf/memory.md`：`| HH:MM | 描述 | 文件 | 结果 | ~tokens |`

---

## Phase 3：更新文档

仅当本次提交引入面向用户的新功能或重大变更时，才更新 `README.md`。内部优化、基础设施变更不需要更新。

---

## Phase 4：安全检查

运行 `git status --short` 检查变更文件列表。
使用 Bash 检查是否有敏感信息泄露：

```
grep -r "password\|secret\|token\|key" --include="*.ts" --include="*.tsx" --include="*.py" --include="*.yaml" --include="*.json" . 2>/dev/null | grep -v node_modules | grep -v ".git/" | grep -v "venv/" | grep -v "__pycache__" || echo "No secrets found"
```

---

## Phase 5：构建前端 + 提交变更

0. 如果存在 `frontend/package.json`，执行 `npm run build --prefix frontend` — 确保 `frontend/dist/` 是与源码同步的最新构建产物
1. `git add -A` — 暂存所有变更
2. `git status --short` — 再次确认
3. `git diff --cached --stat` — 查看统计
4. 生成中文 commit message，格式：`简短动词短语：详细说明`
5. `git commit -m "..."` — 提交
6. `git push origin <current-branch>` — 推送，失败立即报错
7. `git fetch origin` 后 `git log origin/<current-branch> --oneline -3` — 验证远程已收到

---

## 规则

- 所有阶段在当前会话前台执行，不 fork 子进程
- 如果某个阶段无内容可做（无临时文件、无新知识等），直接跳过
- 如果有未提交的变更，必须先确认再推送
- commit message 必须使用简体中文
