// PostToolUse Write|Edit|MultiEdit: 语法检查
import { execSync } from "node:child_process";
import * as path from "node:path";

const proj = process.env.CLAUDE_PROJECT_DIR || process.cwd();

let input;
try {
  input = JSON.parse(process.env.CLAUDE_TOOL_INPUT || "{}");
} catch {
  process.exit(0);
}

const fp = input.file_path || "";
if (!fp) process.exit(0);

const ext = path.extname(fp).toLowerCase();

// Python 语法检查 (快速)
if (ext === ".py") {
  const relPath = path.relative(proj, path.isAbsolute(fp) ? fp : path.join(proj, fp));
  console.log(`[语法检查] Python: ${relPath}`);
  try {
    const absPath = path.isAbsolute(fp) ? fp : path.join(proj, fp);
    execSync(`python -m py_compile "${absPath}"`, {
      cwd: proj,
      stdio: "pipe",
      timeout: 10000,
    });
    console.log("[语法检查] ✓ 通过");
  } catch (e) {
    const err = (e.stderr || e.stdout || "").toString();
    const lines = err.split("\n").slice(0, 5).join("\n");
    console.log(`[语法检查] ✗ 失败:\n${lines}`);
    if (err.split("\n").length > 5) console.log("... (截断)");
  }
}

process.exit(0);
