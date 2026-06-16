export const meta = {
  name: 'work-wrap-up',
  description: '执行收工任务：清理文件、更新学习记录、更新文档、检查变更并推送代码',
  phases: [
    { title: '清理环境', detail: '清理临时文件和垃圾文件' },
    { title: '更新学习记录', detail: '更新 cerebrum.md 和 buglog.json' },
    { title: '更新文档', detail: '同步 README.md' },
    { title: '安全检查', detail: '运行 GitNexus 变更检测' },
    { title: '发布项目', detail: '提交并推送到 GitHub' },
  ],
}

// 1. 清理临时文件
phase('清理环境')
log('检查临时文件和垃圾文件...')
const tempPatterns = ['./frontend/dist', './backend/__pycache__', './.pytest_cache']
for (const p of tempPatterns) {
  log(`  跳过: ${p} (构建产物，非 git 追踪，无需清理)`)
}

// 2. 更新学习记录和 buglog
phase('更新学习记录')
const cerebrumPath = '.wolf/cerebrum.md'
const cerebrumResult = await agent(
  `读取 ${cerebrumPath} 和 .wolf/buglog.json。
   分析本次对话中：
   1. 用户纠正过什么？发现了什么新坑？有什么最佳实践？
   2. 是否修复过 bug？

   请返回：
   - do_not_repeat: 需要新增的 Do-Not-Repeat 条目（中文，每条带日期）
   - preferences: 用户表达的新偏好
   - learnings: 新发现的项目约定或模式
   - bugs: 需要记录的 bug（含 error_message, root_cause, fix, tags）`,
  {
    label: '提取知识点',
    phase: '更新学习记录',
    schema: {
      type: 'object',
      properties: {
        do_not_repeat: { type: 'array', items: { type: 'string' } },
        preferences: { type: 'array', items: { type: 'string' } },
        learnings: { type: 'array', items: { type: 'string' } },
        bugs: { type: 'array', items: { type: 'object', properties: {
          error_message: { type: 'string' }, root_cause: { type: 'string' },
          fix: { type: 'string' }, tags: { type: 'array', items: { type: 'string' } }
        }}}
      }
    }
  }
)

if (cerebrumResult) {
  const { do_not_repeat, preferences, learnings, bugs } = cerebrumResult
  if (do_not_repeat?.length) log(`新增 Do-Not-Repeat: ${do_not_repeat.length} 条`)
  if (preferences?.length) log(`新增偏好: ${preferences.length} 条`)
  if (learnings?.length) log(`新增学习: ${learnings.length} 条`)
  if (bugs?.length) log(`新增 bug 记录: ${bugs.length} 条`)
  if (!do_not_repeat?.length && !preferences?.length && !learnings?.length && !bugs?.length) {
    log('无新知识点需要记录')
  }
}

// 3. 更新 README
phase('更新文档')
const readmeCheck = await agent(
  `检查本次会话的改动 (git diff --stat HEAD~1 或 git diff --stat HEAD)，判断 README.md 是否需要更新。
   如果需要更新，返回需要修改的具体内容。如果不需要，返回 null。`,
  { label: 'README 审计', phase: '更新文档' }
)
if (readmeCheck) {
  log(`README 需更新: ${readmeCheck}`)
} else {
  log('README 无需更新')
}

// 4. GitNexus 变更检测
phase('安全检查')
const gitnexusOk = await agent(
  `运行 git status --short 查看变更文件列表。
   如果有 .tsx/.ts/.py 文件变更，列出它们并说明可能影响的功能模块。
   如果没有代码文件变更，直接报告"无代码变更"。`,
  { label: '变更分析', phase: '安全检查' }
)
log(`变更分析: ${gitnexusOk}`)

// 5. 提交并推送（关键修复：不用 isolation:worktree，用 git add -A）
phase('发布项目')
const pushResult = await agent(
  `执行以下命令，每步检查结果：

   1. git status --short （确认有变更）
   2. 如果 git status --short 有输出：
      - 根据 git diff --stat 生成一个中文 commit message（描述实际改动，不超过 50 字）
      - git add -A
      - git commit -m "刚才生成的中文message"
      - git push origin master
      - 报告 commit SHA 和推送结果
   3. 如果 git status --short 无输出，报告"无变更，跳过推送"`,
  { label: 'Git 推送', phase: '发布项目' }
)
log(`推送结果: ${pushResult}`)
