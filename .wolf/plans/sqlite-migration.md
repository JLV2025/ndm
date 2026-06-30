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

## 第二台电脑同步

```bash
git pull origin master
python -m backend.scripts.migrate_to_sqlite
# data/ndm.db 自动重建，历史文件数据全部保留
```
