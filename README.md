# NDM — 网络设备配置管理系统

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.8.3-2DD46E" alt="Version 2.8.3">
  <img src="https://img.shields.io/badge/Python-3.9%2B-2DD46E" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/React-18-2DD46E" alt="React 18">
  <img src="https://img.shields.io/badge/Backend-FastAPI-2DD46E" alt="FastAPI">
  <img src="https://img.shields.io/badge/Storage-SQLite-2DD46E" alt="SQLite">
  <img src="https://img.shields.io/badge/SSH-Netmiko-2DD46E" alt="Netmiko">
  <img src="https://img.shields.io/badge/i18n-%E4%B8%AD%E6%96%87%20%2F%20English-2DD46E" alt="中 / English">
  <img src="https://img.shields.io/github/last-commit/JLV2025/ndm?color=2DD46E" alt="Last Commit">
</p>

通过 SSH 批量收集 Cisco IOS / Aruba OS 交换机与路由器配置和日志，SQLite 存储，Web 前端可视化查看、对比、分析，支持 AI 日志诊断。

## 功能特性

- **多厂商支持** — Cisco IOS、Cisco IOS XE、Cisco IOS Router、Aruba OS、Aruba OS CX
- **Web 管理面板** — React + MUI OLED Dark 主题，专为网络运维设计
- **设备管理** — 添加、编辑、删除、批量导入（CSV）设备，按类型 / 位置筛选
- **配置收集** — 一键收集 running-config、日志、接口状态、路由表、版本信息
- **AI 日志分析** — 用户自配 LLM API Key，自动提取错误助记符 + 优先级链降级（DeepSeek / Qwen），本地缓存常见错误，脱敏保护网络安全
- **在线查看** — 代码高亮查看配置内容，支持版本对比（diff）
- **告警与报告** — 端口 DOWN / 配置变更 / 版本不一致等异常检测，自动生成修复建议
- **Dashboard 图表** — Recharts 可视化：设备类型环形图、端口状态柱状图、流量 Top 10 排行、配置变更趋势折线图 + 热力图
- **前端面板可视化** — 交换机端口状态前面板 + 路由器接口层级树，支持堆叠设备、子接口缩进，10Gb 端口红色数字标识
- **设备端口连接图** — CDP/LLDP + ConfigParser 双数据源合并，React Flow 管道走线拓扑画布，四层自动布局（WAN→核心→接入→端点），堆叠展开 + 奇偶端口上下 Handle + 端点聚合计数，管道圆弧转角 + 自动居中适配；LAG/Port-Channel 逻辑端口聚合（物理成员隐藏），端口 DOWN 红色 ✕ 警告（有邻居条目但物理断开的端口）
- **多设备网络拓扑图** — CDP + LLDP 邻居自动发现 + ConfigParser 端口描述补充，三层分层布局（WAN → 核心 → 接入），智能连线最短路由，PNG/Visio 导出；端口 DOWN 红色 ✕ 警告，链路保留不删除（设备可能离线/故障）
- **基础分析** — 配置完整性验证、接口状态统计、利用率分析、变更检测
- **SQLite 全量存储** — running-config 双轨（文件 + 库），其余数据全量入 SQLite，日志按时间戳自动去重
- **双语文案** — 中 / 英文界面一键切换
- **单一端口部署** — 前端静态文件由 FastAPI 直接托管，一个命令启动

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + MUI v5 + Recharts + React Flow (@xyflow/react) + Vite 7 |
| 后端 | Python FastAPI + Netmiko (SSH) + SQLite |
| AI | OpenAI 兼容接口（DeepSeek / Qwen 等），优先级链降级，本地缓存 |
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

# LLM 配置（可选，用于日志 AI 分析）
llm:
  timeout: 30
  providers:
    - name: "DeepSeek"
      base_url: "https://api.deepseek.com/v1"
      api_key: ""           # 空则从前端设置页填写
      model: "deepseek-chat"
    - name: "Qwen"
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key: ""
      model: "qwen-turbo"
```

## 使用流程

1. 在 Web 面板添加设备（名称、IP、类型、位置）
2. 进入设备详情页，点击「收集配置」
3. 输入设备的 SSH 用户名和密码
4. 系统自动通过 SSH 登录设备，收集配置和日志
5. 在 Viewer 页面查看、对比历史版本

## 数据存储

所有采集数据统一存入 SQLite（`data/ndm.db`），仅 running-config 保留文件副本供紧急恢复。

```
data/
├── ndm.db                   # SQLite 数据库（所有数据主存储）
├── YYYY-WW/                 # 周归档目录
│   └── {设备名称}/
│       └── running-config.raw   # 双轨保留（唯一文件）
└── 设备名/                   # 旧版数据目录（向后兼容）
    └── YYYY-WW/
```

## 日志 AI 分析

1. 侧边栏进入「日志分析」→ 选择设备 → 勾选日志条目 → 点击「AI 分析」
2. 首次使用需在设置页面（⚙ 图标）配置 LLM API Key
3. 支持多个 LLM Provider 优先级链：按顺序尝试，第一个失败自动降级
4. 分析结果自动缓存到本地知识库，同类型错误下次秒级命中
5. 发送前自动脱敏（设备名 / IP 替换为占位符），回复后再还原

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
