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


def get_devices_config_path() -> str:
    """获取 devices.yaml 的绝对路径，支持环境变量覆盖"""
    config_path = os.environ.get("DEVICES_CONFIG_PATH")
    if config_path:
        return config_path
    return str(_CONFIG_DIR / "devices.yaml")
