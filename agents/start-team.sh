#!/bin/bash
# Start sub-agent development team
# Launch all dev and test agents

echo "========================================"
echo "  Start Development Team Agents"
echo "========================================"
echo ""

# Current project path
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start integration manager (coordinates all agents)
echo "Starting integration-manager..."
echo "  Role: Coordinate all dev agents, assign tasks, track progress"
echo ""

# Start frontend dev agent
echo "Starting frontend-dev..."
echo "  Role: Write React/Next.js frontend code, implement UI components & pages"
echo ""

# Start backend dev agent
echo "Starting backend-dev..."
echo "  Role: Write Python backend code, API endpoints & DB operations"
echo ""

# Start security reviewer agent
echo "Starting security-reviewer..."
echo "  Role: Review code for security vulnerabilities, enforce best practices"
echo ""

# Start QA test agent
echo "Starting qa-tester..."
echo "  Role: Write and run tests, verify functionality"
echo ""

# Start build error resolver agent
echo "Starting build-error-resolver..."
echo "  Role: Fix build and type errors"
echo ""

# Start code reviewer agent
echo "Starting code-reviewer..."
echo "  Role: Review code quality, check for bugs & issues"
echo ""

# Start code architect agent
echo "Starting code-architect..."
echo "  Role: Design feature architecture, plan file structure"
echo ""

# Start planner agent
echo "Starting planner..."
echo "  Role: Create implementation plans, decompose complex features"
echo ""

echo "========================================"
echo "  Team Ready"
echo "========================================"
echo ""
echo "Available commands:"
echo "  /agent integration-manager   - Start integration manager"
echo "  /agent frontend-dev          - Start frontend dev agent"
echo "  /agent backend-dev           - Start backend dev agent"
echo "  /agent security-reviewer     - Start security reviewer agent"
echo "  /agent qa-tester             - Start QA test agent"
echo "  /agent build-error-resolver  - Start build error resolver"
echo "  /agent code-reviewer         - Start code reviewer agent"
echo "  /agent code-architect        - Start code architect agent"
echo "  /agent planner               - Start planner agent"
echo ""
echo "Tip: Use /agent command to launch a specific agent"
echo "     The integration manager auto-coordinates all tasks"
echo ""
