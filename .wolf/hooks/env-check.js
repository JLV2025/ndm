// SessionStart: 项目环境检查
import * as fs from "node:fs";
import * as path from "node:path";
import { execSync } from "node:child_process";

const proj = process.env.CLAUDE_PROJECT_DIR || process.cwd();

function ok(msg) { console.log(`[环境检查] ✓ ${msg}`); }
function warn(msg) { console.log(`[环境检查] ⚠ ${msg}`); }

// 1. data/ 目录
const dataDir = path.join(proj, "data");
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
  ok("data/ 已创建");
} else {
  try {
    fs.accessSync(dataDir, fs.constants.W_OK);
    ok("data/ 目录可读写");
  } catch {
    warn("data/ 不可写");
  }
}

// 2. 虚拟环境
const venvPython = path.join(proj, "venv", "Scripts", "python.exe");
if (fs.existsSync(venvPython)) {
  ok("虚拟环境: venv/");
} else {
  warn("虚拟环境不存在，运行: python -m venv venv");
}

// 3. 端口检查
try {
  const r = execSync("netstat -ano 2>nul | findstr :8002", {
    timeout: 3000,
    stdio: "pipe",
  }).toString();
  if (r.includes("LISTENING")) ok("后端端口 8002 已监听");
  else warn("端口 8002 未在监听");
} catch {
  warn("端口 8002 未在监听");
}

try {
  const r = execSync("netstat -ano 2>nul | findstr :3000", {
    timeout: 3000,
    stdio: "pipe",
  }).toString();
  if (r.includes("LISTENING")) ok("前端端口 3000 已监听");
} catch {
  // 开发服务器可能未启动，正常情况
}

// 4. 前端依赖
const nodeModules = path.join(proj, "frontend", "node_modules");
if (fs.existsSync(nodeModules)) {
  ok("前端 node_modules/ 存在");
} else {
  warn("前端依赖未安装，运行: cd frontend && npm install");
}

console.log("[环境检查] 完成");
process.exit(0);
