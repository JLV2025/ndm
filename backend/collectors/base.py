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
        self.configured_platform = device_config.get("platform", "")
        self.actual_device_type = ""
        self.type_mismatch = False

    @staticmethod
    def _resolve_device_type(device_type: str, platform: str) -> str:
        """设备类型映射到 Netmiko 驱动

        platform 不影响 Netmiko 驱动选择，仅用于命令分发。
        cisco_ios_router / cisco_ios_xe 使用 cisco_ios 驱动（CLI 兼容）。
        """
        if device_type == "cisco_ios_router":
            return "cisco_ios"
        return device_type

    def _do_connect(self, username: str, password: str, device_type: str) -> bool:
        """单次连接尝试"""
        host = self.config.get("ip")
        port = self.config.get("port", 22)
        timeout = self.config.get("timeout", 30)

        print(f"[连接] 设备={self.hostname}, IP={host}:{port}")
        print(f"[连接] 驱动={device_type}, 用户名={username}")

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
        use_timing = device_type == "aruba_aoscx"

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
            except OSError:
                # 回退到 send_command_timing（Netmiko 某些驱动不支持 send_command）
                print(f"[调试] send_command 失败，回退到 send_command_timing")
                return self.connection.send_command_timing(
                    command_string=command,
                    read_timeout=rt,
                    last_read=5.0,
                )

    def _device_type(self) -> str:
        """当前实际设备类型"""
        return self.actual_device_type or self.configured_device_type

    def _platform(self) -> str:
        """当前设备平台类型"""
        return self.configured_platform or ""

    def collect_config(self) -> Tuple[str, str]:
        # 先发送分页关闭指令，确保一次性全量输出
        dt = self._device_type()
        if dt == "aruba_aoscx":
            self.send_command("no page", read_timeout=20)
        elif dt.startswith("cisco"):
            self.send_command("terminal length 0", read_timeout=20)
        running = self.send_command("show running-config", read_timeout=40)
        return running, ""  # startup-config 已废弃，不再收集

    def collect_logs(self) -> str:
        """统一收集最新 300 条日志

        Cisco: terminal shell + show logging | tail 300
        Aruba: show logging -r -n 300
        """
        dt = self._device_type()
        if dt.startswith("cisco"):
            self.send_command("terminal shell", read_timeout=20)
            return self.send_command("show logging | tail 300", read_timeout=20)
        if dt == "aruba_aoscx":
            return self.send_command("show logging -r -n 300", read_timeout=20)
        return self.send_command("show log", read_timeout=20)

    def collect_interface_status(self) -> str:
        dt = self._device_type()
        if dt == "aruba_aoscx":
            return self.send_command("show interface brief", read_timeout=20)
        return self.send_command("show interface status", read_timeout=20)

    def collect_show_version(self) -> str:
        return self.send_command("show version", read_timeout=20)

    def collect_show_interface_utilization(self) -> str:
        """收集端口利用率

        Cisco: show interfaces | include rate|load|packets
        Aruba: no page → show interface utilization
        """
        dt = self._device_type()
        if dt == "aruba_aoscx":
            self.send_command("no page", read_timeout=20)
            return self.send_command("show interface utilization", read_timeout=20)
        if dt.startswith("cisco"):
            return self.send_command("show interfaces | include rate|load|packets", read_timeout=20)
        return self.send_command("show interface utilization", read_timeout=20)

    def collect_cdp_neighbors(self) -> str:
        """收集 CDP 邻居信息"""
        return self.send_command("show cdp nei", read_timeout=60)

    def collect_lldp_neighbors(self) -> str:
        """收集 LLDP 邻居信息"""
        return self.send_command("show lldp nei", read_timeout=60)

    def collect_system_info(self) -> str:
        """收集系统信息（Aruba CX 用于获取序列号和型号）"""
        return self.send_command("show system", read_timeout=20)

    def collect_boot_history(self) -> str:
        """收集设备启动历史（Aruba CX 用于获取运行时间）

        Aruba: show boot-history → Current Boot, up for X days X hrs ...
        Cisco: 运行时间从 show version 中提取，无需单独收集
        """
        dt = self._device_type()
        if dt == "aruba_aoscx":
            return self.send_command("show boot-history", read_timeout=20)
        return ""

    def collect_vsf_info(self) -> str:
        """收集 VSF 堆叠信息（Aruba CX VSF 成员序列号）"""
        return self.send_command("show vsf detail", read_timeout=20)

    def collect_switch_detail(self) -> str:
        """收集 Cisco 堆叠信息

        Cisco IOS XE: show switch
        Cisco IOS:    show switch detail
        路由器不适用，返回空字符串。
        """
        if self.configured_device_type == "cisco_ios_router":
            return ""
        if self._platform() == "cisco_ios_xe":
            return self.send_command("show switch", read_timeout=20)
        return self.send_command("show switch detail", read_timeout=20)

    def collect_routing_table(self) -> str:
        """收集路由表（Cisco IOS 路由器）"""
        return self.send_command("show ip route", read_timeout=45)

    def disconnect(self) -> None:
        """断开连接"""
        if self.connection is not None:
            try:
                self.connection.disconnect()
            except Exception as e:
                print(f"断开连接失败: {e}")
            self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
