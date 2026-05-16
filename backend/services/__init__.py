"""服务模块"""

from .config_saver import ConfigSaver
from .collector_service import collect_device, extract_software_version, extract_serial_number

__all__ = ["ConfigSaver", "collect_device", "extract_software_version", "extract_serial_number"]
