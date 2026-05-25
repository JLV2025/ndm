# NDM — Network Device Manager

SSH-based configuration and log collection for Cisco IOS and Aruba OS switches and routers, with a web dashboard for viewing, diffing, and analysis.

## Features

- **Multi-vendor** — Cisco IOS, Cisco IOS XE, Cisco IOS Router, Aruba OS, Aruba OS CX
- **Web Dashboard** — React + MUI OLED Dark theme, purpose-built for network operations
- **Device Management** — Add, edit, delete devices; filter by type and location
- **Config Collection** — One-click retrieval of running-config, startup-config, logs, interface status, routing table, and version info
- **Online Viewer** — Syntax-highlighted config viewer with version diff comparison
- **Front Panel Visualization** — Switch port status panel + router interface hierarchy tree, with stack support and sub-interface indentation
- **Basic Analysis** — Config completeness validation, interface status summary, utilization analysis, change detection
- **Weekly Archival** — `data/{device}/YYYY-WW/` directory structure, retains last 10 weeks
- **Bilingual UI** — English / Chinese one-click toggle
- **Single-Port Deployment** — Frontend static files served directly by FastAPI

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + MUI v5 + Vite 5 |
| Backend | Python FastAPI + Netmiko (SSH) |
| Theme | OLED Dark (#020617 background, #22C55E accent) |
| i18n | React Context i18n (zh / en) |

## Quick Start

### Prerequisites

- Python 3.9+ (`python3` on some systems)
- Node.js 18+
- Network devices accessible via SSH

### Install

> **Note:** Run all commands from the project root directory (`ndm/`).

```bash
# 1. Create a Python virtual environment (avoids system-wide conflicts)
python3 -m venv venv

# 2. Activate the virtual environment
# Linux / macOS:
source venv/bin/activate
# Windows (CMD):
venv\Scripts\activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 3. Install backend dependencies
pip install -r backend/requirements.txt

# 4. Install frontend dependencies
cd frontend && npm install && cd ..
```

### Development

```bash
# Make sure the virtual environment is activated, run from project root

# Terminal 1: Start backend (port 8002)
python backend/main.py

# Terminal 2: Start frontend (port 3000, proxies /api to backend)
cd frontend && npm run dev
```

Open `http://localhost:3000` in browser.

### Production Deployment

```bash
# Make sure the virtual environment is activated, run from project root

# 1. Build frontend
cd frontend && npm run build && cd ..

# 2. Start (frontend + backend on single port)
python backend/main.py
```

Open `http://localhost:8002` — all clients on the LAN can access it.

On Windows, double-click `start.bat` to launch. It auto-builds the frontend if not yet built.

### Uninstall

The project is fully self-contained — no registry entries, no system services, no scheduled tasks. To uninstall completely, delete the project folder:

```bash
# Windows (Explorer): right-click delete ndm/ folder
# Windows (CMD):
rmdir /s /q ndm
# Linux / macOS:
rm -rf ndm/
```

> If Python or Node.js was installed specifically for this project, uninstall them separately via system settings.

## Configuration

### Device Inventory (`config/devices.yaml`)

```yaml
devices:
  # Cisco IOS switch example
  - name: "BJQD1SWI01"
    ip: "10.210.255.100"
    type: "cisco_ios"
    platform: "cisco_ios"
    location: "Beijing"
    notes: "Core switch"

  # Aruba CX switch example
  - name: "BJQD1SWI02"
    ip: "10.210.255.101"
    type: "aruba_aoscx"
    platform: "aruba_6300"
    location: "Beijing"
    notes: "Aggregation switch"

  # Cisco IOS router example
  - name: "BJQD1RTW01"
    ip: "10.0.0.1"
    type: "cisco_ios_router"
    platform: "cisco_ios_router"
    location: "Beijing"
    notes: "WAN Router"
```

### Device Types

| type | Description | Suitable For |
|------|-------------|--------------|
| `cisco_ios` | Cisco IOS switch | Catalyst 2960/3560/3750 etc. |
| `cisco_ios_xe` | Cisco IOS XE | Catalyst 9200/9300/9500 etc. |
| `cisco_ios_router` | Cisco IOS router | ISR 1900/2900/4300, ASR etc. |
| `aruba_aoscx` | Aruba CX | CX 6100/6200/6300/6400 etc. |

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
4. System SSHs into the device and collects configs, logs, and routing table
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
        ├── interface-utilization.raw
        ├── version.raw
        ├── routing-table.raw       # Routers only
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
│   ├── api/                 # Routers: devices, collection, data, auth, stats
│   ├── services/            # Business logic: SSH collection, device management
│   ├── analyzers/           # Analysis: config validation, performance, change detection
│   ├── collectors/          # Netmiko SSH connection layer
│   └── utils/               # Storage, password management, config loading
├── frontend/                # React frontend
│   └── src/
│       ├── pages/           # Pages: Dashboard, DeviceList, DeviceDetail, Viewer, Login
│       ├── services/        # API calls + auth management
│       ├── components/      # Shared components (MatrixRain bg, FrontPanel etc.)
│       └── i18n/            # i18n translations (zh / en)
├── config/                  # YAML configuration files
├── data/                    # Collected data (weekly archival)
├── start.bat                # Windows one-click launcher
└── README.md
```

## License

This project is for internal network operations use only.
