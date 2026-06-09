# NDM — 网络设备配置管理系统

通过 SSH 批量收集 Cisco IOS / Aruba OS 交换机与路由器配置和日志，Web 前端可视化查看、对比、分析。

## 功能特性

- **多厂商支持** — Cisco IOS、Cisco IOS XE、Cisco IOS Router、Aruba OS、Aruba OS CX
- **Web 管理面板** — React + MUI OLED Dark 主题，专为网络运维设计
- **设备管理** — 添加、编辑、删除设备，按类型 / 位置筛选
- **配置收集** — 一键收集 running-config、startup-config、日志、接口状态、路由表、版本信息
- **在线查看** — 代码高亮查看配置内容，支持版本对比（diff）
- **Dashboard 图表** — Recharts 可视化：设备类型环形图、端口状态柱状图、流量 Top 10 排行、配置变更趋势折线图 + 热力图
- **前端面板可视化** — 交换机端口状态前面板 + 路由器接口层级树，支持堆叠设备、子接口缩进，10Gb 端口红色数字标识
- **设备端口连接图** — 从 running-config description 正则提取邻居设备，React Flow 拓扑画布，前面板矩形节点 + 奇偶端口上下分行 + 端点聚合，方向键盘微调 + 高亮连线
- **多设备网络拓扑图** — CDP + LLDP 邻居自动发现 + ConfigParser 端口描述补充，三层分层布局（WAN → 核心 → 接入），智能连线最短路由，PNG/Visio 导出
- **基础分析** — 配置完整性验证、接口状态统计、利用率分析、变更检测
- **按周归档** — `data/设备名/YYYY-WW/` 目录结构，自动保留最近 10 个版本
- **双语文案** — 中 / 英文界面一键切换
- **单一端口部署** — 前端静态文件由 FastAPI 直接托管，一个命令启动

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + MUI v5 + Recharts + React Flow (@xyflow/react) + Vite 8 |
| 后端 | Python FastAPI + Netmiko (SSH) |
| 主题 | OLED Dark (#020617 底色, #2DD46E 强调色)，IBM Plex Sans + JetBrains Mono 字体 |
| 多语言 | React Context i18n (zh / en) |

## 快速开始

### 环境要求

- Python 3.9+（部分系统命令为 `python3`）
- Node.js 18+
- 可 SSH 访问的目标网络设备

### 安装

> **注意：** 所有命令在项目根目录下执行。GitHub 克隆后文件夹名为 `ndm-master`，建议重命名为 `ndm`（或直接进入该目录操作）。

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

### 卸载

项目完全自包含，不写入注册表、不安装系统服务、不创建计划任务。完整卸载只需删除项目文件夹：

```bash
# 删除整个项目目录即可
# Windows (资源管理器): 右键删除 ndm/ 文件夹
# Windows (CMD):
rmdir /s /q ndm
# Linux / macOS:
rm -rf ndm/
```

> 如果专门为此项目安装了 Python 或 Node.js，可在系统"应用和功能"中单独卸载。

## 配置

### 设备清单 (`config/devices.yaml`)

```yaml
devices:
  # Cisco IOS 交换机示例
  - name: "BJQD1SWI01"
    ip: "10.210.255.100"
    type: "cisco_ios"
    platform: "cisco_ios"
    location: "北京"
    notes: "核心交换机"

  # Aruba CX 交换机示例
  - name: "BJQD1SWI02"
    ip: "10.210.255.101"
    type: "aruba_aoscx"
    platform: "aruba_6300"
    location: "北京"
    notes: "汇聚交换机"

  # Cisco IOS 路由器示例
  - name: "BJQD1RTW01"
    ip: "10.0.0.1"
    type: "cisco_ios_router"
    platform: "cisco_ios_router"
    location: "北京"
    notes: "WAN 路由器"
```

### 设备类型说明

| type | 说明 | 适用设备 |
|------|------|----------|
| `cisco_ios` | Cisco IOS 交换机 | Catalyst 2960/3560/3750 等 |
| `cisco_ios_xe` | Cisco IOS XE | Catalyst 9200/9300/9500 等 |
| `cisco_ios_router` | Cisco IOS 路由器 | ISR 1900/2900/4300、ASR 等 |
| `aruba_aoscx` | Aruba CX | CX 6100/6200/6300/6400 等 |

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
        ├── interface-utilization.raw
        ├── version.raw
        ├── routing-table.raw       # 仅路由器
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
│   ├── analyzers/           # 分析：配置验证、性能、变更检测、端口解析
│   ├── collectors/          # Netmiko SSH 连接层
│   └── utils/               # 存储、密码管理、配置加载
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # 页面：Dashboard, DeviceList, DeviceDetail, Viewer, Login, Topology
│       ├── services/        # API 调用 + 认证管理
│       ├── components/      # 通用组件（MatrixRain 背景、FrontPanel 前面板、TopologyCanvas 等）
│       └── i18n/            # 多语言文案（zh / en）
├── config/                  # YAML 配置文件
├── data/                    # 收集数据（按周归档）
├── start.bat                # Windows 一键启动脚本
└── README.md
```

## 许可证

本项目仅供内部网络运维使用。
