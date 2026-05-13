# 网络交换机配置收集系统 - 实施计划

## 上下文

这是一个全栈项目，用于通过 SSH 从 Cisco 和 Aruba 网络交换机收集配置文件（running-config 和 startup-config），保存到本地并进行分析存档。前端提供 Web 界面进行设备选择、密码输入、配置收集和数据查看。

## 技术选型确认

| 组件     | 技术栈                |
| ------ | ------------------ |
| 前端     | React + TypeScript |
| 后端     | FastAPI (Python)   |
| SSH 连接 | Netmiko            |
| 部署     | Docker 容器          |
| 数据存储   | 本地文件系统（按周归档）       |

## 核心功能需求

### 1. 认证与会话管理

- 用户打开网页 -> 输入用户名和密码（用于 SSH 登录设备）
- 密码加密存储在浏览器前端（localStorage + session 标识）
- 登录失败 -> 返回登录页重新输入
- 关闭网页 -> 会话结束，密码自动删除

### 2. 设备管理

- 设备列表展示（从 config/devices.yaml 读取）
- 设备详情页面：显示 IP、类型、位置、备注
- 批量操作：单选/多选/全选设备
- 端口流量 Top1 分析

### 3. 配置收集流程

1. 选择设备（单/多/全选）
2. 确认/输入用户名密码
3. 逐个设备 SSH 连接
4. 收集：running-config, startup-config, logs, interface status, show version
5. 提取软件版本和序列号
6. 运行分析（配置验证、性能分析、变更检测）
7. 保存到 data/YYYY-WW/{device-name}/

### 4. 数据分析

- **基础分析**: 行数统计、接口数量、版本信息
- **配置验证**: 检查截断、关键配置项（VLAN、接口、路由、认证）
- **性能分析**: 接口状态 (UP/DOWN)、错误统计 (err-disabled, discards)
- **变更检测**: 对比历史版本，高亮新增/删除配置
- **端口流量 Top10**: 
  - Aruba: `show interface utilization`
  - Cisco: `show interface summary`

### 5. 数据展示

- **网页查看器**: 查看原始配置和 JSON 分析结果
- **对比功能**: 时间维度的配置变更对比
- **仪表盘**: 设备列表、版本统计、异常告警
- **数据下载**: 打包导出 data 目录

### 6. 数据归档

- 按周组织：`data/YYYY-WW/{device-name}/`
- 按设备独立保留版本（不跨设备清理）
- 保留策略：最近 N 个周版本（config/settings.yaml 配置）

## 文件结构

```
ndm/
├── frontend/                    # React + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── Login.tsx           # 登录页面
│   │   │   ├── DeviceList.tsx      # 设备列表
│   │   │   ├── DeviceDetail.tsx    # 设备详情
│   │   │   ├── Collector.tsx       # 收集流程
│   │   │   ├── Viewer.tsx          # 配置查看器
│   │   │   ├── Dashboard.tsx       # 仪表盘
│   │   │   └── ChangeCompare.tsx   # 变更对比
│   │   ├── services/
│   │   │   ├── api.ts              # API 调用
│   │   │   └── auth.ts             # 认证管理
│   │   ├── hooks/
│   │   │   └── useSession.ts       # 会话管理
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                     # FastAPI
│   ├── main.py                   # API 入口
│   ├── collectors/
│   │   ├── base.py               # DeviceConnection (Netmiko)
│   │   ├── cisco.py              # Cisco 特定收集
│   │   └── aruba.py              # Aruba 特定收集
│   ├── analyzers/
│   │   ├── config_validator.py   # 配置验证
│   │   ├── performance.py        # 性能分析
│   │   └── change_detector.py    # 变更检测
│   ├── storage/
│   │   └── file_manager.py       # 文件系统管理
│   ├── models/
│   │   └── devices.py            # 设备模型
│   ├── utils/
│   │   └── password.py           # 密码加密/解密
│   └── config/
│       ├── devices.yaml
│       └── settings.yaml
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
│
├── config/
│   └── devices.yaml
│
└── README.md
```

## 关键文件清单

1. `backend/collectors/base.py` - Netmiko SSH 连接
2. `backend/analyzers/config_validator.py` - 配置完整性检查
3. `backend/analyzers/performance.py` - 接口状态和错误统计
4. `backend/analyzers/change_detector.py` - 配置变更检测
5. `backend/utils/password.py` - 密码加密（AES）
6. `frontend/services/auth.ts` - 前端会话管理
7. `docker-compose.yml` - 容器化部署

## 验证清单

- [ ] 后端 API 文档生成（Swagger UI）
- [ ] 前端登录流程测试
- [ ] SSH 连接测试（真实设备）
- [ ] 数据保存和读取测试
- [ ] 配置分析功能验证
- [ ] Docker 容器启动测试
- [ ] 端到端流程测试

## 依赖清单

```txt
# Backend
netmiko>=4.4.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
aiofiles>=23.0.0
cryptography>=41.0.0
pyyaml>=6.0.0

# Frontend
react@18.x
typescript@5.x
vite@5.x
axios>=1.6.0
```

## 下一步行动

1. 确认所有需求无误
2. 创建项目目录结构
3. 实现后端核心模块（collector, analyzer）
4. 实现前端基础框架（登录、设备列表）
5. 配置 Docker 镜像
6. 编写单元测试
7. 端到端集成测试

---

**状态**: 计划待批准
