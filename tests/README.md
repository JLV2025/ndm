# 测试覆盖率目标

## 后端测试

### 覆盖率目标：80%+

#### 测试文件
- `backend/tests/test_password.py` - 密码加密/解密模块
- `backend/tests/test_services.py` - 服务层
- `backend/tests/test_analyzers.py` - 分析器
- `backend/tests/test_collector.py` - 收集器

#### 运行测试
```bash
# 运行所有测试
pytest backend/tests/ -v

# 生成覆盖率报告
pytest backend/tests/ --cov=. --cov-report=html

# 查看覆盖率
open backend/.coverage_html/index.html
```

## 前端测试

### 覆盖率目标：60%+

#### 测试文件
- `frontend/src/test/test_login.tsx` - 登录页面
- `frontend/src/test/test_devices.tsx` - 设备管理
- `frontend/src/test/test_api.ts` - API 服务

#### 运行测试
```bash
cd frontend
npm install  # 安装测试依赖
npm test
```

## 测试清单

### 后端测试清单
- [ ] 密码加密模块
- [ ] 设备收集服务
- [ ] 配置验证器
- [ ] 性能分析器
- [ ] 变更检测器
- [ ] 存储管理器

### 前端测试清单
- [ ] 登录页面
- [ ] 设备列表页面
- [ ] 设备详情页
- [ ] API 服务层
- [ ] 认证服务层
