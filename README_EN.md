# NDM — Network Device Manager

SSH-based configuration and log collection for Cisco IOS and Aruba OS switches, with a web dashboard for viewing, diffing, and analysis.

## Features

- **Multi-vendor** — Cisco IOS, Cisco IOS XE, Aruba OS, Aruba OS CX
- **Web Dashboard** — React + MUI OLED Dark theme, purpose-built for network operations
- **Device Management** — Add, edit, delete devices; filter by type and location
- **Config Collection** — One-click retrieval of running-config, startup-config, logs, interface status, and version info
- **Online Viewer** — Syntax-highlighted config viewer with version diff comparison
- **Basic Analysis** — Config completeness validation, interface status summary, change detection
- **Weekly Archival** — `data/{device}/YYYY-WW/` directory structure, retains last 10 weeks
- **Single-Port Deployment** — Frontend static files served directly by FastAPI

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + MUI v5 + Vite 5 |
| Backend | Python FastAPI + Netmiko (SSH) |
| Theme | OLED Dark (#020617 background, #22C55E accent) |

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Network devices accessible via SSH

### Install

```bash
# Backend dependencies
cd backend
pip install -r requirements.txt

# Frontend dependencies
cd ../frontend
npm install
```

### Development

```bash
# Terminal 1: Start backend (port 8002)
cd backend
python main.py

# Terminal 2: Start frontend (port 3000, proxies /api to backend)
cd frontend
npm run dev
```

Open `http://localhost:3000` in browser.

### Production Deployment

```bash
# 1. Build frontend
cd frontend && npm run build

# 2. Start (frontend + backend on single port)
cd .. && python backend/main.py
```

Open `http://<server-ip>:8002` — all clients on the network can access it.

On Windows Server, double-click `start.bat` to launch.

## Configuration

### Device Inventory (`config/devices.yaml`)

```yaml
devices:
  - name: "BJQD1SWI01"
    ip: "10.210.255.100"
    type: "aruba_aoscx"
    platform: "aruba_6300"
    location: "Beijing"
    notes: "Core switch"
```

### Global Settings (`config/settings.yaml`)

```yaml
data_root: "./data"        # Data storage directory
max_versions: 10            # Max weekly versions retained per device
ssh_timeout: 30             # SSH connection timeout (seconds)
```

## Workflow

1. Add devices via the web panel (name, IP, type, location)
2. Open device detail page, click "Collect Configuration"
3. Enter the device's SSH username and password
4. System SSHs into the device and collects configs and logs
5. View and compare historical versions in the Viewer page

## Data Directory

```
data/
└── {device-name}/
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

## API Documentation

Once the backend is running, visit `http://localhost:8002/docs` for the Swagger UI.

## Project Structure

```
ndm/
├── backend/                 # FastAPI backend
│   ├── main.py              # Entry point, includes frontend hosting & SPA fallback
│   ├── api/                 # Routers: devices, collection, data, auth
│   ├── services/            # Business logic: SSH collection, device management
│   ├── analyzers/           # Analysis: config validation, performance, change detection
│   ├── collectors/          # Netmiko SSH connection layer
│   └── utils/               # Storage, password management, config loading
├── frontend/                # React frontend
│   └── src/
│       ├── pages/           # Pages: Dashboard, DeviceList, DeviceDetail, Viewer, Login
│       ├── services/        # API calls + auth management
│       └── components/      # Shared components
├── config/                  # YAML configuration files
├── data/                    # Collected data (weekly archival)
└── start.bat                # Windows one-click launcher
```
