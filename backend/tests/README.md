# 后端测试

## 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio pytest-cov

# 运行所有测试
pytest backend/tests/ -v

# 运行特定测试文件
pytest backend/tests/test_password.py -v

# 运行测试并生成覆盖率报告
pytest backend/tests/ -v --cov=. --cov-report=html

# 只运行快速测试
pytest backend/tests/ -v -m "not slow"

# 运行测试直到失败
pytest backend/tests/ -v -x
```

## 测试覆盖

### 密码加密模块
- 基本加密解密
- 相同密码产生不同加密（随机 IV）
- 特殊字符处理
- 中文密码
- 空密码
- 长密码

### 收集器服务
- 成功收集配置
- SSH 连接失败处理

## 添加新测试

1. 在 `backend/tests/` 目录创建新的测试文件
2. 文件名必须匹配 `test_*.py` 模式
3. 函数名必须匹配 `test_*` 模式
4. 使用 `@pytest.mark.slow` 标记慢速测试
