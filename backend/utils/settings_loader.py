"""配置加载器"""

import os
import yaml
from pathlib import Path
from typing import Dict


# 配置文件路径（相对于项目根目录）
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def load_settings(config_path: str = None) -> Dict:
    """加载全局配置"""
    if config_path is None:
        config_path = str(_CONFIG_DIR / "settings.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_devices(config_path: str = None) -> Dict:
    """加载设备清单"""
    if config_path is None:
        config_path = str(_CONFIG_DIR / "devices.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
