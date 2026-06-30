# SQLite 迁移计划

## 目标

停止文件存储，数据全部写入 SQLite。唯一例外：`running-config.raw` 保留文件 + SQLite 双轨。

## 进度

- [x] 步骤 1：停止文件写入 (collector_service.py)
- [x] 步骤 2：stats.py → SQLite
- [ ] 步骤 3：topology.py → SQLite
- [ ] 步骤 4：data.py → SQLite（部分）
- [ ] 步骤 5：role_verifier → SQLite
- [ ] 步骤 6：清理废弃函数

## 各步骤详情

### 步骤 3: topology.py → SQLite

- 新增 `_get_latest_running_config(device_name) -> (text, week)` 从 collections 表查询
- 新增 `_get_latest_neighbors(device_name) -> list[dict]` 从 neighbors 表查询
- 新增 `_scan_device_neighbors() -> dict[str, list]` 聚合所有设备最新邻居
- 替换 `/topology/{name}` 中 `_find_device_data_file()` 调用
- 替换 `/topology/location/{loc}` 中 `_scan_device_files()` 调用
- 保留端口规范化、堆叠检测、双向链路合并逻辑不变

### 步骤 4: data.py → SQLite（部分）

- `GET /{name}/weeks` → 从 collections 查 DISTINCT week
- `GET /{name}/ports/latest` → 从 port_snapshots 查询
- `GET /{name}/{week}/files` → 保持文件列表（向后兼容）
- `GET /{name}/{week}/{filename}` → 保持文件读取

### 步骤 5: role_verifier → SQLite

- `_get_switch_neighbors()` → 从 neighbors 表查询
- `devices` 属性 → 从 YAML 加载（不变），加 SQLite 补充

### 步骤 6: 清理

- 删除 `_generate_summary()` 函数
- 删除 `_update_device_field()` `_update_device_serial()`
- `file_manager.py` 标记废弃函数
- `config_saver.py` 添加废弃注释
- 更新测试 conftest.py

- [ ] 步骤 7：日志 AI 分析功能

## 步骤 7：日志 AI 分析功能

### 设计决策

| 决策 | 选择 |
|------|------|
| LLM API | OpenAI 兼容接口（支持 OpenAI / DeepSeek / Qwen 等） |
| 脱敏策略 | 轻量脱敏（替换设备 IP + 设备名，保留端口名/日志级别/时间戳） |
| 缓存匹配 | 关键词精确匹配（从消息提取关键词，和 hints.keyword 精确匹配） |

### 后端新增

**配置** — `settings.yaml` 增 `llm` 段：
```yaml
llm:
  api_key: ""       # 从环境变量覆盖
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
  timeout: 30
```

**端点 1**: `GET /api/logs/{device_name}`
- 参数: `week`（可选）、`severity`（可选过滤）、`limit`（默认 200）
- 从 `device_logs` JOIN `collections` 返回
- 返回: `[{id, timestamp, severity, facility, message}]`

**端点 2**: `POST /api/logs/analyze`
- 入参: `{log_ids: [], device_name: ""}`
- 流程:
  1. 从 DB 加载日志原文
  2. 轻量脱敏（替换设备 IP + 设备名）
  3. 提取关键词（正则匹配 FACILITY-SEVERITY-MNEMONIC 或常见模式）
  4. 关键词精确匹配 `remediation_hints.keyword`
  5. 未命中 → 构建 prompt → 调 LLM（后台异步）→ 写入 hints
  6. 返回 `{suggestion, source: "cache"|"llm", from_cache: bool}`

**端点 3**: `GET /api/logs/analysis-history`
- 返回用户历史上触发过的所有分析记录（从 hints 表查）

**新增模块**: `backend/services/log_analyzer.py`
- `sanitize_logs(logs) → sanitized_text` — 轻量脱敏
- `extract_keywords(log_message) → list[str]` — 提取关键词
- `query_cache(keywords) → suggestion | None` — 精确匹配 hints
- `call_llm(prompt) → suggestion` — 调 LLM API
- `save_to_cache(alert_type, keyword, suggestion)` — 写入 hints

### 前端新增

**新页面**: `frontend/src/pages/LogAnalyzer.tsx`
- 路由: `/log-analyzer`
- 左侧: 设备下拉选择器 + 日志表格（可多选）
- 右侧: AI 建议面板 + 历史分析记录
- 侧边栏新增 "Log Analyzer" 导航项

### 数据流

```
用户选设备 → /api/logs/{device} 加载日志表
  → 勾选相关日志行
  → 点击"AI 分析"
  → /api/logs/analyze
      ├── 脱敏 + 提取关键词
      ├── 查 remediation_hints (keyword 精确匹配)
      │     ├── 命中 → 返回缓存建议
      │     └── 未命中 → LLM API
      │           ├── 返回建议
      │           └── 写入 hints 表 (alert_type=log_analysis, keyword=xxx)
  → 前端显示建议 + 标记来源

## 第二台电脑同步

```bash
git pull origin master
python -m backend.scripts.migrate_to_sqlite
# data/ndm.db 自动重建，历史文件数据全部保留
```
