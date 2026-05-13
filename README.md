# 网络交换机配置收集系统

通过 SSH 登录 Cisco 和 Aruba 交换机，收集配置和日志，保存到本地并进行分析。

## 功能特性

- **SSH 连接** - 支持 Cisco IOS 和 Aruba OS 交换机
- **交互式密码输入** - 用户登录网页后，密码加密存储在浏览器中
- **软件版本自动提取** - 从 `show version` 输出自动提取版本号
- **完整收集** - running-config、startup-config、设备日志、版本信息、接口利用率
- **混合格式** - 原始文本 + JSON 结构化数据
- **按周归档** - 自动按 YYYY-WW 组织，按设备独立保留最近 10 个版本
- **基础分析** - 配置验证、性能分析、变更检测、端口流量 Top1

## 技术栈

- **前端**: React + TypeScript + Material-UI
- **后端**: FastAPI (Python) + Netmiko
- **部署**: Docker 容器

## 安装

### 开发环境

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 运行

```bash
# 后端
cd backend
python main.py

# 前端
cd frontend
npm run dev
```

## 配置

### 设备清单 (`config/devices.yaml`)

```yaml
devices:
  - name: "BJQD1SWI01"
    ip: "10.210.255.1"
    type: "aruba_osswitch"
    platform: "aruba_6300"
    location: "BJQ"
    notes: "北京 - 核心交换机 1"
```

### 全局配置 (`config/settings.yaml`)

```yaml
data_root: "./data"
max_versions: 10
analysis:
  enable_config_validation: true
  enable_performance_analysis: true
  enable_change_detection: true
```

## 运行收集

1. 编辑设备清单 `config/devices.yaml`
2. 启动后端：`cd backend && python main.py`
3. 启动前端：`cd frontend && npm run dev`
4. 访问 http://localhost:3000
5. 输入用户名和密码（用于 SSH 登录设备）
6. 选择设备并收集配置

## 数据目录结构

```
data/
└── {device-name}/
    └── YYYY-WW/
        ├── running-config.raw      # 原始运行配置
        ├── startup-config.raw      # 原始启动配置
        ├── logs.raw                # 原始日志
        ├── interface-status.raw    # 接口状态
        ├── interface-utilization.raw # 接口利用率
        ├── version.raw             # 版本信息
        ├── validation.json         # 配置验证结果
        ├── performance.json        # 性能分析结果
        ├── change.json             # 变更检测结果
        └── summary.txt             # 易读摘要报告
```

## 分析功能

### 配置验证
- 检查配置完整性（是否有截断）
- 检查关键配置项（VLAN、接口、路由、认证）
- 检测语法错误

### 性能分析
- 接口状态摘要（up/down 统计）
- 错误计数统计（err-disabled、discards、dropped）
- 带宽信息提取

### 变更检测
- 对比本周 vs 上周配置
- 高亮显示新增/删除的配置行
- 生成变更报告

### 端口流量 Top1
- Aruba: `show interface utilization`
- Cisco: `show interface summary`

## Docker 部署

```bash
docker-compose up -d
```

访问 http://localhost:8000

## API 文档

后端启动后访问 http://localhost:8000/docs 查看 Swagger 文档。
