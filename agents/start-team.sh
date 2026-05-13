#!/bin/bash
# 子代理团队启动脚本
# 启动所有开发代理和测试代理

echo "========================================"
echo "  启动开发团队代理"
echo "========================================"
echo ""

# 当前项目路径
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 启动集成管理器（协调所有代理）
echo "启动 integration-manager (集成管理器)..."
echo "职责：协调所有开发代理，分配任务，跟踪进度"
echo ""

# 启动前端开发代理
echo "启动 frontend-dev (前端开发代理)..."
echo "职责：编写 React/Next.js 前端代码，实现 UI 组件和页面"
echo ""

# 启动后端开发代理
echo "启动 backend-dev (后端开发代理)..."
echo "职责：编写 Python 后端代码，API 端点和数据库操作"
echo ""

# 启动安全审查代理
echo "启动 security-reviewer (安全审查代理)..."
echo "职责：审查代码安全漏洞，确保最佳实践"
echo ""

# 启动 QA 测试代理
echo "启动 qa-tester (QA 测试代理)..."
echo "职责：编写和运行测试，验证功能"
echo ""

# 启动构建错误解决代理
echo "启动 build-error-resolver (构建错误解决代理)..."
echo "职责：修复构建和类型错误"
echo ""

# 启动代码审查代理
echo "启动 code-reviewer (代码审查代理)..."
echo "职责：审查代码质量，检查 bug 和问题"
echo ""

# 启动架构设计代理
echo "启动 code-architect (架构设计代理)..."
echo "职责：设计功能架构，规划文件结构"
echo ""

# 启动规划代理
echo "启动 planner (规划代理)..."
echo "职责：创建实施计划，分解复杂功能"
echo ""

echo "========================================"
echo "  团队已启动"
echo "========================================"
echo ""
echo "可用命令："
echo "  /agent integration-manager   - 启动集成管理器"
echo "  /agent frontend-dev          - 启动前端开发代理"
echo "  /agent backend-dev           - 启动后端开发代理"
echo "  /agent security-reviewer     - 启动安全审查代理"
echo "  /agent qa-tester             - 启动 QA 测试代理"
echo "  /agent build-error-resolver  - 启动构建错误解决代理"
echo "  /agent code-reviewer         - 启动代码审查代理"
echo "  /agent code-architect        - 启动架构设计代理"
echo "  /agent planner               - 启动规划代理"
echo ""
echo "提示：使用 /agent 命令启动特定代理"
echo "      集成管理器将自动协调所有任务"
echo ""
