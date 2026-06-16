---
name: config-diff
description: "对比两台设备或同一设备不同版本的配置变更。用户通过 /config-diff 调用，交互式选择设备和版本后输出结构化 diff 报告。"
disable-model-invocation: true
---

# 配置变更对比

封装 `backend/analyzers/change_detector.py` 的 diff 能力，提供交互式配置对比流程。

## 触发方式

用户输入 `/config-diff` 或包含关键词"配置对比""diff""变更""变化"的请求。

## 工作流

### 1. 扫描数据目录
```bash
# data 目录结构：data/YYYY-WW/{device-name}/
# 每个设备目录下有: running-config.txt, startup-config.txt, summary.json
ls data/ | sort  # 列出所有周目录
```

### 2. 交互式选择
询问用户三个问题：
- **设备名**（选择一个或多个设备）
- **对比基准**（旧版本）：列出现有的 ISO 周，默认选上上周
- **对比目标**（新版本）：默认选本周
- **配置类型**：running-config 还是 startup-config？默认 running

### 3. 读取配置
```python
from backend.analyzers.change_detector import ChangeDetector

# 读取新旧配置
old_config = Path(f"data/{old_week}/{device}/running-config.txt").read_text(errors='replace')
new_config = Path(f"data/{new_week}/{device}/running-config.txt").read_text(errors='replace')
```

### 4. 执行对比
```python
detector = ChangeDetector(new_config, old_config)
result = detector.detect()
```

### 5. 格式化输出

以 Markdown 展示变更：

```
## 配置变更：{device} ({old_week} → {new_week})

### 摘要
| 指标 | 数量 |
|------|------|
| 新增行 | {summary.added} |
| 删除行 | {summary.removed} |
| 有变更 | {has_changes} |

### 变更详情
```diff
- 删除的行
+ 新增的行
```
```

## 约束

- 仅读取配置，不修改任何文件
- 如果设备只有一个版本，提示"需要至少两个版本才能对比"
- 对比结果超过 200 行时显示精简摘要，并提供保存完整 diff 到文件的选项
- 使用 `errors='replace'` 处理编码问题
