"""
基础网络连接模块
使用 Netmiko 进行 SSH 连接，支持会话保持（一次认证，多次命令）
支持设备类型自动探测
"""

import netmiko
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from netmiko import ConnectHandler
from typing import Dict, Optional, Tuple, List


class DeviceConnection:
    """网络设备连接管理器"""

    def __init__(self, device_config: Dict):
        """
        初始化连接

        Args:
            device_config: 设备配置字典，包含：
                - name: 设备名称
                - ip: 设备 IP
                - type: 设备类型 (cisco_ios, aruba_osswitch, aruba_aoscx)
                - port: SSH 端口（可选，默认 22）
                - timeout: 超时设置（可选）
        """
        self.config = device_config
        self.connection: Optional[ConnectHandler] = None
        self.hostname = device_config.get("name", "unknown")
        self._last_error = ""
        # 设备类型自动探测结果
        self.configured_device_type = device_config.get("type", "cisco_ios")
        self.actual_device_type = ""
        self.type_mismatch = False

    @staticmethod
    def _resolve_device_type(device_type: str, platform: str) -> str:
        """根据 platform 字段修正设备类型（Aruba CX 系列需使用 aruba_aoscx 驱动）"""
        if device_type == "aruba_osswitch" and platform:
            if any(x in platform.lower() for x in ["6300", "6400", "8", "cx", "aoscx"]):
                return "aruba_aoscx"
        return device_type

    @staticmethod
    def _get_alternative_types(device_type: str) -> List[str]:
        """返回应尝试的替代设备类型列表"""
        if device_type == "aruba_osswitch":
            return ["aruba_aoscx"]
        elif device_type == "aruba_aoscx":
            return ["aruba_osswitch"]
        elif device_type == "cisco_ios":
            return ["cisco_xe"]
        elif device_type == "cisco_xe":
            return ["cisco_ios"]
        else:
            return []

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

            # 退出 enable 模式。Aruba/ProCurve 设备不支持，静默忽略
            try:
                if self.connection.check_enable_mode():
                    self.connection.exit_enable_mode()
            except Exception:
                pass

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

    def connect(self, username: str, password: str, auto_detect: bool = True) -> bool:
        """
        建立 SSH 连接，支持设备类型自动探测

        Args:
            username: 登录用户名
            password: 登录密码
            auto_detect: 是否在失败时自动探测设备类型

        Returns:
            bool: 连接是否成功
        """
        platform = self.config.get("platform", "")
        device_type = self._resolve_device_type(self.configured_device_type, platform)

        # 1. 先尝试配置的设备类型（经过 platform 修正）
        if self._do_connect(username, password, device_type):
            self.actual_device_type = device_type
            self.type_mismatch = (device_type != self.configured_device_type)
            return True

        # 2. 认证失败不重试（凭据错误，换类型也没用）
        if not auto_detect or "认证" in self._last_error:
            return False

        # 3. 自动探测：尝试替代设备类型
        alternatives = self._get_alternative_types(device_type)
        for alt_type in alternatives:
            print(f"[自动探测] {device_type} 失败，尝试 {alt_type} ...")
            self.disconnect()
            if self._do_connect(username, password, alt_type):
                self.actual_device_type = alt_type
                self.type_mismatch = True
                print(f"[自动探测] 成功! 实际类型={alt_type}，配置类型={self.configured_device_type}")
                return True

        return False

    def send_command(self, command: str, read_timeout: float = None) -> str:
        """
        发送命令并返回输出

        Args:
            command: 要执行的命令
            read_timeout: 读取超时（可选）

        Returns:
            str: 命令输出
        """
        if self.connection is None:
            raise RuntimeError("未建立连接")

        rt = read_timeout if read_timeout is not None else 10.0
        return self.connection.send_command(
            command,
            read_timeout=rt
        )

    def collect_config(self) -> Tuple[str, str]:
        """
        收集配置信息

        Returns:
            Tuple[str, str]: (running_config, startup_config)
        """
        running = self.send_command("show running-config")
        startup = self.send_command("show startup-config")
        return running, startup

    def collect_logs(self) -> str:
        """收集日志"""
        return self.send_command("show log")

    def collect_interface_status(self) -> str:
        """收集接口状态"""
        return self.send_command("show interface status")

    def collect_show_version(self) -> str:
        """收集版本信息"""
        return self.send_command("show version")

    def collect_show_interface_utilization(self) -> str:
        """
        收集接口利用率信息
        Aruba: show interface utilization
        Cisco: show interface summary (包含利用率)
        """
        return self.send_command("show interface utilization")

    def disconnect(self) -> None:
        """断开连接"""
        if self.connection is not None:
            try:
                self.connection.disconnect()
            except Exception:
                pass
            self.connection = None

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False
