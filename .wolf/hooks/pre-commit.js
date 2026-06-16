// PreToolUse Bash: git commit 前检查
import { execSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

const cmd = process.env.CLAUDE_TOOL_INPUT || "";
if (!/git\s+commit/.test(cmd)) {
  process.exit(0);
}

const proj = process.env.CLAUDE_PROJECT_DIR || process.cwd();
console.log("[提交前检查] 开始...\n");

// 1. GitNexus 变更影响检测
console.log("━".repeat(40));
console.log("[GitNexus] 检测变更影响...");
try {
  execSync("npx gitnexus detect_changes", {
    cwd: proj,
    stdio: "inherit",
    timeout: 30000,
  });
} catch (e) {
  console.log(`[GitNexus] 检测完成 (退出码: ${e.status})`);
}

// 2. Python 语法检查 (已暂存的 .py 文件)
try {
  const staged = execSync(
    "git diff --cached --name-only --diff-filter=ACM",
    { cwd: proj, encoding: "utf8", timeout: 5000 }
  );
  const pyFiles = staged.split("\n").filter((f) => f.endsWith(".py"));
  if (pyFiles.length > 0) {
    console.log("━".repeat(40));
    console.log(`[Python] 语法检查 ${pyFiles.length} 个文件...`);
    let allOk = true;
    pyFiles.forEach((f) => {
      try {
        execSync(`python -m py_compile "${f}"`, {
          cwd: proj,
          stdio: "pipe",
          timeout: 10000,
        });
        console.log(`  ✓ ${f}`);
      } catch (e) {
        allOk = false;
        const err = (e.stderr || "").toString().split("\n")[0];
        console.log(`  ✗ ${f}: ${err}`);
      }
    });
    if (allOk) console.log("[Python] ✓ 全部通过");
  }
} catch {}

// 3. TypeScript 类型检查 (有前端变更时)
try {
  const staged = execSync(
    "git diff --cached --name-only --diff-filter=ACM",
    { cwd: proj, encoding: "utf8", timeout: 5000 }
  );
  const tsFiles = staged
    .split("\n")
    .filter((f) => f.match(/\.(ts|tsx)$/) && f.startsWith("frontend/"));
  if (tsFiles.length > 0) {
    console.log("━".repeat(40));
    console.log("[TypeScript] 类型检查...");
    try {
      execSync("npx tsc --noEmit --pretty", {
        cwd: path.join(proj, "frontend"),
        stdio: "inherit",
        timeout: 60000,
      });
      console.log("[TypeScript] ✓ 通过");
    } catch (e) {
      console.log(`[TypeScript] ✗ 类型错误 (退出码: ${e.status})`);
    }
  }
} catch {}

// 4. pytest (如果存在测试目录)
const testDir = path.join(proj, "tests");
if (fs.existsSync(testDir)) {
  console.log("━".repeat(40));
  console.log("[pytest] 运行测试...");
  try {
    execSync("python -m pytest --timeout=30 -q 2>nul", {
      cwd: proj,
      stdio: "inherit",
      timeout: 60000,
    });
    console.log("[pytest] ✓ 全部通过");
  } catch (e) {
    console.log(`[pytest] 测试未全部通过 (退出码: ${e.status})`);
  }
}

console.log("\n[提交前检查] 完成");
process.exit(0);
