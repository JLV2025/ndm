# 子代理团队

开发团队已创建，包含以下代理：

## 开发代理

| 代理 | 职责 |
|------|------|
| `frontend-dev` | 前端开发 - 编写 React/Next.js 代码，实现 UI 组件和页面 |
| `backend-dev` | 后端开发 - 编写 Python 后端代码，API 端点和数据库操作 |

## 审查代理

| 代理 | 职责 |
|------|------|
| `security-reviewer` | 安全审查 - 审查代码漏洞，确保安全最佳实践 |
| `code-reviewer` | 代码审查 - 审查代码质量，检查 bug 和问题 |

## 测试代理

| 代理 | 职责 |
|------|------|
| `qa-tester` | QA 测试 - 编写和运行测试，验证功能 |

## 辅助代理

| 代理 | 职责 |
|------|------|
| `build-error-resolver` | 构建错误解决 - 修复构建和类型错误 |
| `code-architect` | 架构设计 - 设计功能架构，规划文件结构 |
| `planner` | 规划 - 创建实施计划，分解复杂功能 |

## 集成管理器

| 代理 | 职责 |
|------|------|
| `integration-manager` | 集成管理 - 协调所有开发代理，分配任务，跟踪进度 |

## 启动方式

### 方式 1：命令行启动单个代理

```bash
# 启动集成管理器
Agent({
  description: "集成管理器启动",
  prompt: "启动集成管理器并协调所有子代理",
  subagent_type: "general-purpose"
})
```

### 方式 2：使用启动脚本

```bash
chmod +x agents/start-team.sh
./agents/start-team.sh
```

### 方式 3：使用 Slash Command

```
/agent integration-manager
/agent frontend-dev
/agent backend-dev
/agent security-reviewer
/agent qa-tester
/agent build-error-resolver
/agent code-reviewer
/agent code-architect
/agent planner
```

## 工作流程

1. **需求分析** → 用户提出需求
2. **规划** → `planner` 创建实施计划
3. **架构设计** → `code-architect` 设计架构
4. **开发** → `frontend-dev` / `backend-dev` 编写代码
5. **代码审查** → `code-reviewer` 审查代码
6. **安全审查** → `security-reviewer` 审查安全
7. **测试** → `qa-tester` 编写和运行测试
8. **构建验证** → `build-error-resolver` 确保构建通过
9. **集成** → `integration-manager` 协调所有步骤

## 快速命令

### 启动完整团队

```bash
Agent({
  description: "启动完整开发团队",
  prompt: "启动所有开发代理和测试代理，准备开始工作"
})
```

### 启动前端开发

```bash
Agent({
  description: "启动前端开发代理",
  prompt: "准备开发前端功能"
})
```

### 启动后端开发

```bash
Agent({
  description: "启动后端开发代理",
  prompt: "准备开发后端功能"
})
```

### 启动安全审查

```bash
Agent({
  description: "启动安全审查代理",
  prompt: "审查代码安全漏洞"
})
```

## 代理职责详解

### integration-manager (集成管理器)
- 总体协调所有代理
- 分配任务给合适的代理
- 跟踪任务进度
- 解决代理间的冲突
- 确保代码质量门禁

### frontend-dev (前端开发)
- 编写 React/Next.js 组件
- 实现 UI 页面和布局
- 处理前端状态管理
- API 调用和数据获取
- 响应式设计

### backend-dev (后端开发)
- 编写 Python 后端代码
- 创建 API 端点
- 数据库操作和查询
- 业务逻辑实现
- 认证和授权

### security-reviewer (安全审查)
- 审查代码安全漏洞
- 检查认证授权
- 验证输入验证和输出编码
- 确保安全最佳实践
- 检查敏感数据处理

### qa-tester (QA 测试)
- 编写单元测试
- 编写集成测试
- 编写 E2E 测试
- 运行测试套件
- 验证功能完整性

### code-reviewer (代码审查)
- 审查代码质量
- 检查 bug 和潜在问题
- 确保代码标准
- 检查性能问题
- 提供改进建议

### build-error-resolver (构建错误解决)
- 修复构建错误
- 解决类型错误
- 修复编译问题
- 确保代码可构建
- 最小化改动

### planner (规划)
- 创建实施计划
- 分解复杂功能
- 识别依赖关系
- 规划实施顺序
- 识别潜在风险

### code-architect (架构设计)
- 设计功能架构
- 规划文件结构
- 定义接口和数据流
- 考虑扩展性
- 遵循现有模式

## 注意事项

- **明天上线**：优先完成核心功能，快速迭代
- **质量门禁**：所有代码必须通过审查和测试
- **最小改动**：每次只做必要的改动
- **并行开发**：使用 `dispatching-parallel-agents` 并行处理独立任务
