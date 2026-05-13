"""
服务层测试
"""
import pytest
from unittest.mock import MagicMock, patch


class TestCollectorService:
    """收集器服务测试"""

    @pytest.fixture
    def mock_device(self):
        """创建 Mock 设备对象 - 使用 MagicMock 以支持属性访问"""
        from unittest.mock import MagicMock
        device = MagicMock()
        device.name = "test_device"
        device.ip = "192.168.1.1"
        device.type = "cisco_ios"
        device.platform = "cisco_ios"
        device.location = "test"
        return device

    @pytest.fixture
    def mock_global_settings(self):
        """创建 Mock 全局设置 - 使用 dict 以支持 settings.get()"""
        return {
            "data_root": "./data",
            "max_versions": 10,
            "ssh_timeout": {"connect": 10, "read": 30, "write": 30},
            "analysis": {
                "enable_config_validation": True,
                "enable_performance_analysis": True,
                "enable_change_detection": True,
            },
        }

    def test_collect_device_success(self, mock_device, mock_global_settings, mock_netmiko_connection):
        """测试成功收集设备配置"""
        mock_get_week = lambda *args: "2026-W20"

        mock_connection_instance = MagicMock()
        mock_connection_instance.connect.return_value = True
        mock_connection_instance.collect_config.return_value = ("running-config", "startup-config")
        mock_connection_instance.collect_logs.return_value = ""
        mock_connection_instance.collect_interface_status.return_value = ""
        mock_connection_instance.collect_show_version.return_value = "Cisco IOS Software, Catalyst 3640 (revision 0x8102)\n\nCisco 3640 (rom) system image file is \"flash:c2900-adventerprisek9-mz.15.0.4.S.\"\n\nSystem uptime: 0:00:10\nSystem reload reason: Power-on\n\nCisco IOS Software, Catalyst 3640 Software (C3640-JS9M-M), Version 15.0(4)S\n\nSerial Number: ABC123DEF"
        mock_connection_instance.collect_show_interface_utilization.return_value = ""

        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.read = MagicMock(return_value="sample old config\n")
            mock_open.return_value = mock_file
            mock_open.return_value.__enter__.return_value.read = MagicMock(return_value="sample old config\n")

            with patch('storage.file_manager.get_week_dir', return_value='2026-W20'):
                with patch('storage.file_manager.create_device_dir'):
                    with patch('storage.file_manager.keep_latest_versions_per_device'):
                        with patch('services.collector_service._update_device_serial'):
                            with patch('services.collector_service._get_device_connection') as mock_get_conn:
                                mock_get_conn.return_value = MagicMock(return_value=mock_connection_instance)

                                from services.collector_service import collect_device

                                try:
                                    result = collect_device(mock_device, "admin", "password123", mock_global_settings)
                                except Exception as e:
                                    import traceback
                                    print(f"DEBUG: Exception: {e}")
                                    traceback.print_exc()
                                    raise

                                assert result["status"] == "success"
                                assert "running_lines" in result

    def test_collect_device_ssh_failure(self, mock_device, mock_global_settings):
        """测试 SSH 连接失败"""
        mock_failed_conn = MagicMock()
        mock_failed_conn.connect = MagicMock(return_value=False)
        mock_failed_conn._last_error = "SSH 认证失败：用户名或密码错误"

        with patch('storage.file_manager.get_week_dir', return_value="2026-W20"):
            with patch('storage.file_manager.create_device_dir'):
                with patch('storage.file_manager.keep_latest_versions_per_device'):
                    with patch('services.collector_service._update_device_serial'):
                        with patch('services.collector_service._get_device_connection') as mock_get_conn:
                            mock_get_conn.return_value = MagicMock(return_value=mock_failed_conn)

                            from services.collector_service import collect_device

                            result = collect_device(mock_device, "admin", "password123", mock_global_settings)
                            assert result["status"] == "failed"
                            assert "SSH" in result.get("error", "")
