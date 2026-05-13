# OpenWolf

@.wolf/OPENWOLF.md

This project uses OpenWolf for context management. Read and follow .wolf/OPENWOLF.md every session. Check .wolf/cerebrum.md before generating code. Check .wolf/anatomy.md before reading files.


# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QCNDM is a network switch configuration and log collection tool for Cisco IOS and Aruba OS switches. It SSHs into devices, collects running-config, startup-config, logs, and version info, then saves and analyzes the data locally.

## Architecture

The project uses a modular Python architecture:

**Entry point:** `cli_main.py` - Orchestrates device collection workflow

**Core modules:**

- `lib/collector.py` - Device data collection logic (extracts version/serial from `show version`, saves data)
- `collectors/base.py` - `DeviceConnection` class using Netmiko for SSH, provides `send_command`, `collect_config`, `collect_logs`, etc.
- `analyzers/`:
  - `config_validator.py` - `ConfigValidator` checks completeness (truncation), critical items (VLANs, interfaces, routing, auth), syntax
  - `performance.py` - `PerformanceAnalyzer` parses interface status (UP/DOWN counts), error stats (err-disabled, discards), bandwidth
  - `change_detector.py` - `ChangeDetector` uses `difflib` to compare configs, reports added/removed lines
- `utils/storage.py` - File organization: creates `data/YYYY-WW/{device-name}/` directories, `keep_latest_versions()` removes old weeks

**Data flow:**

1. Load `config/devices.yaml` (device list with name, IP, type, platform)
2. Interactive CLI prompts for username/password per device
3. `DeviceConnection.connect()` establishes SSH via Netmiko
4. Collect: `show running-config`, `show startup-config`, `show log`, `show interface status`, `show version`
5. Extract software version and serial number from `show version` output
6. Run validators/analyzer on collected config
7. Save raw files + JSON analysis to `data/YYYY-WW/`
8. Generate `summary.txt` with key metrics

**API layer (optional):** `api/` subdirectory provides Flask/FastAPI endpoints for programmatic access to collection and management functions.

## Configuration

- `config/devices.yaml` - Device inventory (name, IP, type, platform, location, notes, username)
- `config/settings.yaml` - Global settings (data_root, max_versions, SSH timeouts, analyzer flags)

## Common Commands

```bash
# Run collection
python cli_main.py

# Manage device list
python config/manager.py

# Add a new device to the list
python config/manager.py
# Then select option 2 to add

# Run a single test
python -m pytest tests/ -k test_name  # if pytest is configured
```

## File Structure

```
.
├── cli_main.py              # Main entry point
├── config/
│   ├── devices.yaml         # Device inventory
│   └── settings.yaml        # Global settings
├── lib/
│   └── collector.py         # Collection logic (version extraction, data saving)
├── collectors/
│   └── base.py              # SSH connection via Netmiko
├── analyzers/
│   ├── config_validator.py  # Config completeness & syntax checks
│   ├── performance.py       # Interface status & error analysis
│   └── change_detector.py   # Config diffing
└── utils/
    └── storage.py           # File I/O, weekly organization, cleanup
```

## Key Design Patterns

1. **Context manager pattern** - `DeviceConnection` uses `__enter__`/`__exit__` for automatic disconnect
2. **Strategy pattern** - Device type (cisco_ios/aruba_osswitch) determines command parsing regex
3. **Chain of responsibility** - Analysis pipeline: validator → performance analyzer → change detector
4. **Weekly archival** - Data organized by ISO week (YYYY-WW), old versions auto-cleanup

## Important Notes

- Password input is interactive (not stored in config file)
- Serial number extracted from `show version` is used as device directory name when available
- Config validation runs automatically on each collection
- Maximum 10 weekly versions retained per device

## Workflow

- 架构决策前先询问
- 做最小改动，不重构无关代码
- 每次变更后跑测试，失败先修复再继续
- 每个逻辑变更单独提交
- 两种方案之间拿不准时，两个都解释，让我来选

## Out of scope

- migrations/ → 由 ORM CLI 管理，不要手动创建
- public/assets/ → 静态文件，不要修改
- .github/workflows/ → CI/CD，未经询问不要改动

## Language Rules

* All communication, comments, and documentation must be in **Simplified Chinese**
* Code comments must be in Chinese
* Commit messages must be in Chinese
* Professional English terms/abbreviations allowed
