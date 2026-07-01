# SQLite 迁移计划

## 最终决策

| 决策 | 结论 |
|------|------|
| running-config | **双轨制**：文件 + SQLite 各存一份。SQLite 供查询/diff，文件供紧急恢复 |
| startup-config | **放弃**，不存文件也不入库 |
| 日志 | 文件**不存**（不再写 logs.raw），仅 SQLite 逐条存储 |
| 日志去重 | 按**上次 collected_at** 过滤，只保留区间内日志；首次收集保留最近 7 天 |
| 日志时间戳 | Aruba 保持 ISO 8601；Cisco 解析时统一补当年年份转 ISO |
| 其他 raw 文件 | 全部停写，SQLite 已有对应表 |
| 数据查询 | 所有 API 统一从 SQLite 读取 |

## 进度

- [x] 步骤 1：停止文件写入 (collector_service.py) — 除 running-config.raw 外
- [x] 步骤 2：stats.py → SQLite
- [x] 步骤 3：topology.py → SQLite
- [x] 步骤 4：data.py → SQLite
- [x] 步骤 5：role_verifier → SQLite
- [x] 步骤 6：清理废弃函数（_generate_summary 等已删除）
- [x] 步骤 7：日志时间戳规范化 + 按时间过滤去重
- [x] 步骤 8：去除 startup-config 收集 & 清理残留代码
- [x] 步骤 8.1：Cisco IOS 日志收集恢复（所有设备统一收集）
- [x] 步骤 9：日志 AI 分析功能

## 各步骤详情

### 步骤 3: topology.py → SQLite

- `_get_latest_running_config(device_name)` → `SELECT running_config FROM collections ... ORDER BY id DESC LIMIT 1`
- `_get_latest_neighbors(device_name)` → `SELECT * FROM neighbors WHERE device_id=...`
- `_scan_device_neighbors()` → 聚合 neighbors 表所有设备最新邻居
- 替换 `/topology/{name}` 中 `_find_device_data_file()` 调用
- 替换 `/topology/location/{loc}` 中 `_scan_device_files()` 调用
- **注意**：当前 topology.py 读 neighbors.json 文件，新代码已不写 neighbors.json，此端点实际已损坏

### 步骤 4: data.py → SQLite

- `GET /{name}/weeks` → `SELECT DISTINCT week FROM collections`
- `GET /{name}/ports/latest` → `SELECT * FROM port_snapshots ... ORDER BY id DESC`
- `GET /{name}/{week}/files` → 保持文件列表（向后兼容）
- `GET /{name}/{week}/{filename}` → running-config.raw 从文件读，其余从 SQLite 或返回 404

### 步骤 5: role_verifier → SQLite

- `_get_switch_neighbors()` → 查 neighbors 表
- YAML 加载保留（devices 基础信息），SQLite 补充运行时数据

### 步骤 7: 日志预处理优化

**时间戳规范化**：
- Aruba：`2026-06-24T14:35:22.000000+08:00` → 保持 ISO 8601
- Cisco 有时间戳：`*Mar  1 00:00:00.000` → 补年份转 `2026-03-01T00:00:00`
- Cisco 无时间戳：`%LINK-3-UPDOWN: ...` → 保留原样，timestamp 为空

**去重逻辑**：
```
1. 查 SQLite → 获取该设备上次 collected_at
2. parse_syslog_lines() 解析 300 条
3. 过滤：log_timestamp > last_collected_at
4. 首次收集（无 last_collected_at）→ 保留最近 7 天
```

**修改点**：
- `collector_service.py` `_save_to_sqlite()` → 加时间过滤
- `collector_service.py` `parse_syslog_lines()` → Cisco 时间戳补年份
- 可选迁移：`_migrate_v5` → 规范化已有 Cisco 时间戳

### 步骤 8: 去除 startup-config

- `collectors/base.py` `collect_startup_config()` → 删除或标记废弃
- `collector_service.py` → 不再调用 startup-config 收集
- `_save_data()` → 删除 startup-config 文件写入（如有）
- `database.py` → 无需新增 startup_config 列

### 步骤 9: 日志 AI 分析功能

**设计决策**：

| 决策 | 选择 |
|------|------|
| LLM API | OpenAI 兼容接口（支持 OpenAI / DeepSeek / Qwen 等） |
| 脱敏策略 | 轻量脱敏（替换设备 IP + 设备名，保留端口名/日志级别/时间戳） |
| 缓存匹配 | 关键词精确匹配（从消息提取关键词，和 hints.keyword 精确匹配） |

**后端新增**：

**配置** — `settings.yaml` 增 `llm` 段：
```yaml
llm:
  api_key: ""
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
  timeout: 30
```

**端点 1**: `GET /api/logs/{device_name}`
- 参数: `week`（可选）、`severity`（可选过滤）、`limit`（默认 200）
- 从 `device_logs` JOIN `collections` 返回

**端点 2**: `POST /api/logs/analyze`
- 入参: `{log_ids: [], device_name: ""}`
- 流程: 脱敏 → 提取关键词 → 精确匹配缓存 → 未命中调 LLM → 写入 hints

**端点 3**: `GET /api/logs/analysis-history`
- 返回历史分析记录（从 hints 表查）

**新增模块**: `backend/services/log_analyzer.py`
- `sanitize_logs()` / `extract_keywords()` / `query_cache()` / `call_llm()`

**前端新增**: `frontend/src/pages/LogAnalyzer.tsx`
- 路由: `/log-analyzer`

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
      │           └── 写入 hints 表

## 第二台电脑同步

```bash
git pull origin master
python -m backend.scripts.migrate_to_sqlite
```
