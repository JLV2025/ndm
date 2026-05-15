"""
基础网络连接模块
使用 Netmiko 进行 SSH 连接
"""

import netmiko
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from netmiko import ConnectHandler
from typing import Dict, Optional, Tuple, List


class DeviceConnection:
    """网络设备连接管理器"""

    def __init__(self, device_config: Dict):
        self.config = device_config
        self.connection: Optional[ConnectHandler] = None
        self.hostname = device_config.get("name", "unknown")
        self._last_error = ""
        self.configured_device_type = device_config.get("type", "cisco_ios")
        self.actual_device_type = ""
        self.type_mismatch = False

    @staticmethod
    def _resolve_device_type(device_type: str, platform: str) -> str:
        """根据 platform 字段修正设备类型（Aruba CX 系列需使用 aruba_aoscx 驱动）"""
        if device_type == "aruba_osswitch" and platform:
            if any(x in platform.lower() for x in ["6300", "6400", "8320", "8xxx", "cx", "aoscx"]):
                return "aruba_aoscx"
        return device_type

    def _do_connect(self, username: str, password: str, device_type: str) -> bool:
        """单次连接尝试"""
        host = self.config.get("ip")
        port = self.config.get("port", 22)
        timeout = self.config.get("timeout", 30)

        print(f"[连接] 设备={self.hostname}, IP={host}:{port}")
        print(f"[连接] 驱动={device_type}, 用户名={username}, 密码={'*' * len(password) if password else '(空)'}")

        try:
            self.connection = ConnectHandler(
                device_type=device_type,
                host=host,
                port=port,
                username=username,
                password=password,
                conn_timeout=timeout,
                auth_timeout=timeout,
                banner_timeout=timeout,
            )

            # 调试：打印连接后的实际状态
            prompt = self.connection.find_prompt()
            print(f"[调试] 提示符: {repr(prompt)}")
            print(f"[调试] base_prompt: {repr(self.connection.base_prompt)}")
            print(f"[调试] enable模式: {self.connection.check_enable_mode()}")

            return True

        except NetmikoAuthenticationException as e:
            print(f"SSH 认证失败：{e}")
            self.disconnect()
            self._last_error = f"SSH 认证失败：用户名或密码错误 ({str(e)[:100]})"
            return False
        except NetmikoTimeoutException as e:
            print(f"SSH 连接超时：{e}")
            self.disconnect()
            self._last_error = f"SSH 连接超时：设备不可达或端口不通 ({str(e)[:100]})"
            return False
        except Exception as e:
            print(f"SSH 连接异常：{e}")
            self.disconnect()
            self._last_error = f"SSH 连接异常：{str(e)[:200]}"
            return False

    def connect(self, username: str, password: str) -> bool:
        """建立 SSH 连接"""
        platform = self.config.get("platform", "")
        device_type = self._resolve_device_type(self.configured_device_type, platform)

        if self._do_connect(username, password, device_type):
            self.actual_device_type = device_type
            self.type_mismatch = (device_type != self.configured_device_type)
            return True
        return False

    def send_command(self, command: str, read_timeout: float = None) -> str:
        """发送命令并返回输出"""
        if self.connection is None:
            raise RuntimeError("未建立连接")

        rt = read_timeout if read_timeout is not None else 120.0

        device_type = self.actual_device_type or self.configured_device_type
        use_timing = device_type in ("aruba_aoscx", "aruba_osswitch")

        if use_timing:
            print(f"[调试] send_command_timing ({device_type}): {command}")
            return self.connection.send_command_timing(
                command_string=command,
                read_timeout=rt,
                last_read=5.0,
            )
        else:
            print(f"[调试] send_command ({device_type}): {command}")
            try:
                return self.connection.send_command(
                    command,
                    read_timeout=rt,
                )
            except Exception:
                # 回退到 send_command_timing
                print(f"[调试] send_command 失败，回退到 send_command_timing")
                return self.connection.send_command_timing(
                    command_string=command,
                    read_timeout=rt,
                    last_read=5.0,
                )

    def _device_type(self) -> str:
        """当前实际设备类型"""
        return self.actual_device_type or self.configured_device_type

    def collect_config(self) -> Tuple[str, str]:
        running = self.send_command("show running-config")
        startup = self.send_command("show startup-config")
        return running, startup

    def collect_logs(self) -> str:
        dt = self._device_type()
        if dt == "cisco_ios":
            return self.send_command("show logging", read_timeout=30)
        elif dt == "aruba_aoscx":
            return self.send_command("show logging -r -n 100", read_timeout=30)
        else:
            return self.send_command("show log", read_timeout=30)

    def collect_interface_status(self) -> str:
        dt = self._device_type()
        if dt == "aruba_aoscx":
            return self.send_command("show interface brief", read_timeout=30)
        else:
            return self.send_command("show interface status", read_timeout=30)

    def collect_show_version(self) -> str:
        return self.send_command("show version", read_timeout=30)

    def collect_show_interface_utilization(self) -> str:
        dt = self._device_type()
        if dt == "cisco_ios":
            return self.send_command("show interfaces | include rate|load|packets", read_timeout=30)
        else:
            return self.send_command("show interface utilization", read_timeout=30)

    def collect_system_info(self) -> str:
        """收集系统信息（Aruba CX 用于获取序列号和型号）"""
        return self.send_command("show system", read_timeout=15)

    def collect_vsf_info(self) -> str:
        """收集 VSF 堆叠信息（Aruba CX VSF 成员序列号）"""
        return self.send_command("show vsf detail", read_timeout=15)

    def disconnect(self) -> None:
        """断开连接"""
        if self.connection is not None:
            try:
                self.connection.disconnect()
            except Exception:
                pass
            self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
