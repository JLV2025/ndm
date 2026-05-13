"""
测试配置和共享 fixture
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Mock 外部依赖
@pytest.fixture
def mock_netmiko_connection():
    """创建 Mock 的 Netmiko 连接"""
    connection = MagicMock()
    connection.remote_conn_closed = MagicMock(return_value=False)
    connection.send_command_expect = MagicMock(return_value=("Cisco IOS Software, Catalyst 3640 (revision 0x8102)\n\nCisco 3640 (rom) system image file is \"flash:c2900-adventerprisek9-mz.15.0.4.S.\"\n\nSystem uptime: 0:00:10\nSystem reload reason: Power-on\n\nCisco IOS Software, Catalyst 3640 Software (C3640-JS9M-M), Version 15.0(4)S\nCopyright (c) 1986-2018 by Cisco Systems, Inc.\n\nCompiled Mon 01-Apr-2019 14:52 by aa_preprod\n\nROM: Bootstrap program is Cisco IOS, Version 12.4(24r)X\n\nHardware:        Cisco 3640\n                Processor board ID FTX1513W16V\n                Motherboard serial number FXS1409W16V\n                CPU identifier    882584\n                Motherboard serial number FXS1409W16V\n\n        Configuration register is 0x2102"))
    connection.send_command.return_value = "Cisco IOS Software"
    connection.collect_config = MagicMock(return_value=("sample running config\nip address 10.0.0.1", "sample startup config\n"))
    connection.collect_logs = MagicMock(return_value="")
    connection.collect_interface_status = MagicMock(return_value="")
    connection.collect_show_version = MagicMock(return_value=connection.send_command_expect.return_value)
    connection.collect_show_interface_utilization = MagicMock(return_value="")
    connection.connect = MagicMock(side_effect=lambda user, pwd: True)
    return connection


@pytest.fixture
def mock_file_system(tmp_path):
    """创建 Mock 的文件系统操作"""
    with patch('builtins.open', new_callable=MagicMock) as mock_open:
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_file
        yield mock_open


@pytest.fixture
def test_password_manager():
    """创建密码管理器的测试实例 - 使用固定 key 以便测试可重复"""
    from utils.password import PasswordManager
    import os
    # 使用固定 key 以便测试可重复，而不是随机生成
    return PasswordManager(key=b'0123456789abcdef0123456789abcdef')


@pytest.fixture
def mock_device():
    """创建 Mock 设备对象"""
    from unittest.mock import MagicMock
    device = MagicMock()
    device.name = "test_device"
    device.ip = "10.210.255.1"
    device.type = "cisco_ios"
    device.platform = "cisco_3640"
    return device


@pytest.fixture
def mock_global_settings():
    """创建 Mock 全局设置"""
    from unittest.mock import MagicMock
    settings = MagicMock()
    settings.data_root = "./data"
    settings.max_versions_per_device = 10
    settings.ssh_timeout = 30
    settings.ssh_connect_timeout = 10
    settings.analysis = {
        "enable_config_validation": True,
        "enable_performance_analysis": True,
        "enable_change_detection": True,
    }
    return settings


@pytest.fixture
def mock_storage(tmp_path):
    """创建 Mock 的 storage 模块"""
    with patch('storage.file_manager.get_week_dir', return_value=str(tmp_path / "2026-W20")):
        with patch('storage.file_manager.create_device_dir') as mock_create:
            with patch('storage.file_manager.keep_latest_versions_per_device'):
                with patch('services.collector_service._update_device_serial'):
                    yield mock_create


@pytest.fixture
def test_client():
    """创建测试客户端 fixture"""
    from _main import app
    client = TestClient(app, raise_server_exceptions=False, follow_redirects=True)
    yield client
