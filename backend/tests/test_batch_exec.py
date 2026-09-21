"""批量命令执行测试 —— 黑名单三态 + 单台执行器（mock netmiko）。

黑名单是**安全边界**，测三件事：
  1. 拦截：重启 / 擦除 / 删文件 / 引导类命令（含前缀变体与大小写）
  2. 警告：可能锁死登录或断链路的（不拦，交给操作者判断）
  3. 放行：`show boot` 这类只读命令**不能**被误伤；`no shutdown` 不是"关闭端口"
执行器用假 DeviceConnection（记录了调用），验证提权 / 保存 / 异常 / 兜底拦截四条路径。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services import batch_exec  # noqa: E402


# ---------------------------------------------------------------- 黑名单：拦截

@pytest.mark.parametrize("cmd", [
    "reload",
    "reload in 5",
    "erase startup-config",
    "erase all zeroize",
    "no boot system flash:/old.bin",       # boot 前缀变体也要拦
    "boot system flash:/new.bin",
    "write erase",
    "delete flash:/backup.cfg",
    "format flash:",
    "factory-reset",
    "factory_reset",
    "config-register 0x2102",
    "tftpdnld",
    "usb",
    "clear config",
    "clear startup-config",
    "squeeze flash:",
])
def test_危险命令一律拦截(cmd):
    v = batch_exec.check_commands([cmd])
    assert [b["cmd"] for b in v["blocked"]] == [cmd] and v["warnings"] == []


def test_黑名单不锚定行首且不区分大小写():
    """命令可能带缩进 / 多个空格 / 大写（与 redact 的教训同源：行首锚定会漏判）。"""
    v = batch_exec.check_commands(["  RELOAD", "no  reload in 5", "  erase  startup-config"])
    assert len(v["blocked"]) == 3


def test_只读命令放行_show_boot不被误伤():
    """`show boot`（看引导配置）是只读命令 —— 拦了它就成了笑话。"""
    v = batch_exec.check_commands(
        ["show boot", "show running-config", "display version", "do show boot",
         "show reload", "show erase-config-log"])
    assert v["blocked"] == [] and v["warnings"] == []


# ---------------------------------------------------------------- 黑名单：警告

@pytest.mark.parametrize("cmd", [
    "no username oldadmin",
    "username admin privilege 15",
    "no aaa authentication login default",
    "no enable secret",
    "no ip route 0.0.0.0 0.0.0.0 10.1.1.1",
    "no ip default-gateway",
    "no vlan 16",
    "no interface vlan 100",
    "shutdown",
    "interface 1/1/1 shutdown",
    "no spanning-tree",
])
def test_锁死风险给警告不拦截(cmd):
    v = batch_exec.check_commands([cmd])
    assert v["blocked"] == [] and [w["cmd"] for w in v["warnings"]] == [cmd]


def test_no_shutdown不是关闭端口():
    """`no shutdown` 是**开启**端口 —— 常见且安全，不能警告。"""
    v = batch_exec.check_commands(["no shutdown", "no  shutdown"])
    assert v["blocked"] == [] and v["warnings"] == []


# ---------------------------------------------------------------- 黑名单：放行

def test_正常配置命令放行():
    v = batch_exec.check_commands([
        "ntp server 10.1.1.1",
        "no ntp server 10.8.26.10",       # 修外部 NTP 的典型修复命令
        "vlan 16", "interface 1/1/1", "spanning-tree bpdu-guard",
        "logging host 10.1.1.2", "snmp-server host 10.1.1.3 version 3",
    ])
    assert v["blocked"] == [] and v["warnings"] == []


def test_重复行只报一次():
    v = batch_exec.check_commands(["reload", "reload", " reload "])
    assert len(v["blocked"]) == 1


def test_注释与空行跳过():
    v = batch_exec.check_commands(["", "   ", "! 这是注释", "reload"])
    assert len(v["blocked"]) == 1 and v["blocked"][0]["cmd"] == "reload"


def test_split_commands():
    assert batch_exec.split_commands("ntp server 1.1.1.1\n\n! 注释\n  vlan 16  \n") == \
        ["ntp server 1.1.1.1", "vlan 16"]


# ---------------------------------------------------------------- 执行器（mock）

def make_conn_cls(*, connect_ok=True, enable_mode=True, enable_raises=False,
                  outputs=None, fail_on=None):
    """构造可配置的假 DeviceConnection（netmiko 层由同一对象兼任）。"""
    outputs = outputs or {}

    class Fake:
        calls: list = []
        _last_error = ""

        def __init__(self, config):
            self.config = config
            self.connection = self          # check_enable_mode / send_config_set 走这里
            self.secret = ""

        def connect(self, u, p):
            self.__class__.calls.append(("connect", self.config["name"]))
            self.creds = (u, p)
            return connect_ok

        def check_enable_mode(self):
            return enable_mode

        def enable(self):
            self.__class__.calls.append(("enable",))
            if enable_raises:
                raise RuntimeError("enable rejected")

        def send_config_set(self, cmds, read_timeout=None):
            self.__class__.calls.append(("config_set", list(cmds)))
            return "config applied"

        def send_command(self, cmd, read_timeout=None):
            self.__class__.calls.append(("cmd", cmd))
            if fail_on and cmd == fail_on:
                raise OSError("connection reset")
            return outputs.get(cmd, f"output of {cmd}")

        def disconnect(self):
            self.__class__.calls.append(("disconnect",))

    return Fake


DEV = SimpleNamespace(name="BJQD1SWI01", ip="10.0.0.1", type="aruba_aoscx",
                      platform="aruba_aoscx")


def test_show模式逐条执行并分段输出(monkeypatch):
    Fake = make_conn_cls(outputs={"show ntp status": "NTP synchronized"})
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw", ["show ntp status", "show clock"])

    assert res["status"] == "success" and res["error"] == ""
    assert "show ntp status\nNTP synchronized" in res["output"]
    assert "show clock\noutput of show clock" in res["output"]
    assert ("connect", "BJQD1SWI01") in Fake.calls
    assert Fake.calls[-1] == ("disconnect",)      # 一定断开


def test_config模式_不在特权模式时同密码提权(monkeypatch):
    Fake = make_conn_cls(enable_mode=False)
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw",
                                       ["ntp server 10.1.1.1"], mode="config")

    assert res["status"] == "success"
    assert ("enable",) in Fake.calls and ("config_set", ["ntp server 10.1.1.1"]) in Fake.calls


def test_config模式_提权失败给可读错误(monkeypatch):
    Fake = make_conn_cls(enable_mode=False, enable_raises=True)
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw", ["vlan 16"], mode="config")

    assert res["status"] == "failed" and "特权模式" in res["error"]
    assert ("config_set", ["vlan 16"]) not in Fake.calls    # 没提权成功就不该下发


def test_config模式_保存配置(monkeypatch):
    Fake = make_conn_cls()
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw",
                                       ["vlan 16"], mode="config", save=True)
    assert res["status"] == "success"
    assert ("cmd", "write memory") in Fake.calls
    assert "[save] write memory" in res["output"]


def test_保存失败时如实标注且保留下发结果(monkeypatch):
    Fake = make_conn_cls(fail_on="write memory")
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw",
                                       ["vlan 16"], mode="config", save=True)
    assert res["status"] == "success"                  # 配置已下发
    assert "保存失败" in res["output"]                  # 但要显眼警告


def test_连接失败(monkeypatch):
    Fake = make_conn_cls(connect_ok=False)
    Fake._last_error = "SSH 认证失败：用户名或密码错误"
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "bad", ["show clock"])
    assert res["status"] == "failed" and "认证失败" in res["error"]


def test_执行中异常返回部分输出(monkeypatch):
    """第 2 条命令挂掉 —— 第 1 条的结果仍要带回来（失败排查就靠它）。"""
    Fake = make_conn_cls(outputs={"show clock": "12:00:00"}, fail_on="show ntp status")
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw", ["show clock", "show ntp status"])
    assert res["status"] == "failed"
    assert "show clock\n12:00:00" in res["output"]
    assert "OSError" in res["error"]


def test_服务端兜底拦截_不建连接(monkeypatch):
    """即使前端预检被绕过，服务端也必须拒绝 —— 且根本不尝试连接设备。"""
    Fake = make_conn_cls()
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)

    res = batch_exec.execute_on_device(DEV, "admin", "pw", ["reload"])
    assert res["status"] == "blocked" and "拦截" in res["error"]
    assert Fake.calls == []


def test_空命令拒绝(monkeypatch):
    Fake = make_conn_cls()
    monkeypatch.setattr("collectors.base.DeviceConnection", Fake)
    res = batch_exec.execute_on_device(DEV, "admin", "pw", ["", "  "])
    assert res["status"] == "failed" and Fake.calls == []
