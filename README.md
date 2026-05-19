# NDM — 网络设备配置管理系统

通过 SSH 批量收集 Cisco IOS / Aruba OS 交换机配置与日志，前端可视化查看、对比、分析。

## 功能特性

- **多厂商支持** — Cisco IOS、Cisco IOS XE、Aruba OS、Aruba OS CX
- **Web 管理面板** — React + MUI OLED Dark 主题，专为网络运维设计
- **设备管理** — 添加、编辑、删除设备，按类型 / 位置筛选
- **配置收集** — 一键收集 running-config、startup-config、日志、接口状态、版本信息
- **在线查看** — 代码高亮查看配置内容，支持版本对比（diff）
- **前面板可视化** — 交换机端口状态前面板示意图，支持堆叠设备、上行端口自动识别
- **基础分析** — 配置完整性验证、接口状态统计、变更检测
- **按周归档** — `data/设备名/YYYY-WW/` 目录结构，自动保留最近 10 个版本
- **单一端口部署** — 前端静态文件由 FastAPI 直接托管，一个命令启动

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + MUI v5 + Vite 5 |
| 后端 | Python FastAPI + Netmiko (SSH) |
| 主题 | OLED Dark (#020617 底色, #22C55E 强调色) |

## 快速开始

### 环境要求

- Python 3.9+（部分系统命令为 `python3`）
- Node.js 18+
- 可 SSH 访问的目标网络设备

### 安装

> **注意：** 所有命令在项目根目录（`ndm/`）下执行。

```bash
# 1. 创建 Python 虚拟环境（避免系统级安装冲突）
python3 -m venv venv

# 2. 激活虚拟环境
# Linux / macOS:
source venv/bin/activate
# Windows (CMD):
venv\Scripts\activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 3. 安装后端依赖
pip install -r backend/requirements.txt

# 4. 安装前端依赖
cd frontend && npm install && cd ..
```

### 开发模式

```bash
# 确保虚拟环境已激活，在项目根目录执行

# 终端 1：启动后端 (端口 8002)
python backend/main.py

# 终端 2：启动前端 (端口 3000，自动代理 /api 到后端)
cd frontend && npm run dev
```

浏览器访问 `http://localhost:3000`。

### 生产部署

```bash
# 确保虚拟环境已激活，在项目根目录执行

# 1. 构建前端
cd frontend && npm run build && cd ..

# 2. 启动（前端 + 后端同一端口）
python backend/main.py
```

浏览器访问 `http://localhost:8002`，局域网内均可使用。

Windows 下可直接双击 `start.bat`，脚本会自动构建前端（如未构建）并启动后端。

## 配置

### 设备清单 (`config/devices.yaml`)

```yaml
devices:
  - name: "BJQD1SWI01"
    ip: "10.210.255.100"
    type: "aruba_aoscx"
    platform: "aruba_6300"
    location: "北京"
    notes: "核心交换机"
```

### 全局设置 (`config/settings.yaml`)

```yaml
data_root: "./data"        # 数据存储目录
max_versions: 10            # 每设备最大保留周数
ssh_timeout: 30             # SSH 连接超时（秒）
```

## 使用流程

1. 在 Web 面板添加设备（名称、IP、类型、位置）
2. 进入设备详情页，点击「收集配置」
3. 输入设备的 SSH 用户名和密码
4. 系统自动通过 SSH 登录设备，收集配置和日志
5. 在 Viewer 页面查看、对比历史版本

## 数据目录

```
data/
└── {设备名称}/
    └── YYYY-WW/
        ├── running-config.raw
        ├── startup-config.raw
        ├── logs.raw
        ├── interface-status.raw
        ├── version.raw
        ├── validation.json
        ├── performance.json
        ├── change.json
        └── summary.txt
```

## API 文档

后端运行后访问 `http://localhost:8002/docs` 查看 Swagger 文档。

## 项目结构

```
ndm/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 入口，含前端静态托管及 SPA 回退
│   ├── api/                 # 路由：设备、收集、数据、认证、统计
│   ├── services/            # 业务逻辑：SSH 收集、设备管理
│   ├── analyzers/           # 分析：配置验证、性能、变更检测
│   ├── collectors/          # Netmiko SSH 连接层
│   └── utils/               # 存储、密码管理、配置加载
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # 页面：Dashboard, DeviceList, DeviceDetail, Viewer, Login
│       ├── services/        # API 调用 + 认证管理
│       └── components/      # 通用组件（MatrixRain 背景、FrontPanel 前面板等）
├── config/                  # YAML 配置文件
├── data/                    # 收集数据（按周归档）
└── start.bat                # Windows 一键启动脚本
```
