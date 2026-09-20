"""running/startup 配置比对测试。

这套归一化是"改了没保存"检查的地基：**一条总在误报的检查等于没有**，
所以这里把现网实测到的每一类噪声都钉成用例。

实测背景（109 对真实样本，data/{设备}/{周}/ 下的同期 running 与 startup）：
  最初版本 108/109 报差异（全是误报）→ 逐类剥离后 105 一致 / 4 差异，
  且那 4 处经设备自报时间戳交叉验证，是**真实的未保存变更**（SHAD1SWI01）。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from utils.config_diff import diff_configs, normalized_lines  # noqa: E402

RUNNING = """Building configuration...

Current configuration : 28494 bytes
!
! Last configuration change at 13:58:10 ICT Tue Jun 30 2026 by pa.jing.lv
! NVRAM config last updated at 21:36:51 ICT Thu Jun 25 2026 by pa.scott.hanson
!
version 16.9
hostname SHAD1SWI01
!
interface HundredGigE1/0/27
 description stackwise
!
end
"""

STARTUP = """Using 10492 out of 33554432 bytes, uncompressed size = 24620 bytes
!
! Last configuration change at 21:36:49 ICT Thu Jun 25 2026 by pa.scott.hanson
! NVRAM config last updated at 21:36:51 ICT Thu Jun 25 2026 by pa.scott.hanson
!
version 16.9
hostname SHAD1SWI01
!
interface HundredGigE1/0/27
 description stackwise
!
end
"""


# ---------------------------------------------------------------- 噪声必须被忽略

def test_headers_and_timestamps_are_ignored():
    """两边输出头不同（Building configuration... vs Using N out of M bytes），
    且 `! Last configuration change` 时间戳**本来就该不同** —— 都不能算差异。"""
    d = diff_configs(RUNNING, STARTUP)
    assert d["differ"] is False


def test_prompt_echo_is_ignored():
    """采集时终端回显会混进 running，如 `BJQD1SWI01#` 或 `SWI01# show running-config`。"""
    running = "SWI01# show running-config\nCurrent configuration:\nhostname X\nend\n"
    startup = "Startup configuration:\nhostname X\nend\n"
    assert diff_configs(running, startup)["differ"] is False
    running2 = "SWI01#\nSWI01#\nCurrent configuration:\nhostname X\n"
    assert diff_configs(running2, "hostname X\n")["differ"] is False


def test_certificate_block_representation_differs_and_is_ignored():
    """同一条证书两种表示：running 是 `certificate ca 01` + 数十行 hex + quit；
    startup 只有 `certificate ca 01 nvram:xxx.cer`。不忽略必然每次误报。"""
    running = ("crypto pki certificate chain TP\n"
               " certificate ca 01\n"
               "  7CA7B7E6 C1AF74F6 152E99B7 B1FCF9BB\n"
               "  D697DF7F 28\n"
               "\tquit\n"
               "!\n")
    startup = ("crypto pki certificate chain TP\n"
               " certificate ca 01 nvram:CiscoLicensi#1CA.cer\n"
               "!\n")
    assert diff_configs(running, startup)["differ"] is False


def test_hex_blob_detection_does_not_eat_real_config():
    """证书块剥离不能误伤普通配置行：非 hex 行要结束证书块。"""
    running = ("certificate self-signed 01\n"
               "  AABBCCDD AABBCCDD\n"
               "interface Gi0/1\n"
               " description FACE\n")     # 'FACE' 是 hex，但它是描述的一部分
    startup = "interface Gi0/1\n description FACE\n"
    # 证书行与 blob 被丢掉，剩下的 interface 块两边一致 → 不算差异
    assert diff_configs(running, startup)["differ"] is False


def test_ntp_clock_period_is_ignored():
    """IOS 自动维护的时钟周期值：NTP 每次校准都会改写 running，不是人工配置改动。"""
    running = "ntp clock-period 36029110\nntp server 10.1.1.1\n"
    startup = "ntp clock-period 36029218\nntp server 10.1.1.1\n"
    assert diff_configs(running, startup)["differ"] is False


def test_trailing_whitespace_and_blank_lines_ignored():
    """实测 35/36 台配置带行尾空格；空行与分隔行（`!` / `! ! !` / `---`）两边本就可能不同。"""
    running = "hostname X   \n!\n\nservice timestamps  \n! ! !\n"
    startup = "hostname X\n! ! !\nservice timestamps\n"
    assert diff_configs(running, startup)["differ"] is False


def test_line_order_still_matters():
    """归一化只剥无关行，**顺序仍然算数** —— 两行内容相同但顺序不同必须报出来。"""
    assert diff_configs("a\nb\n", "b\na\n")["differ"] is True


# ---------------------------------------------------------------- 真差异必须报出来

def test_real_unsaved_change_is_detected_with_line_numbers():
    """真机案例：SHAD1SWI01 的 SVL 链路配置在 running 里、不在 startup 里
    （设备自报时间戳也印证：配置 6/30 变更、NVRAM 6/25 保存）。"""
    running = RUNNING.replace(
        "interface HundredGigE1/0/27\n description stackwise\n",
        "interface HundredGigE1/0/27\n stackwise-virtual link 1\n description stackwise\n")
    d = diff_configs(running, STARTUP)
    assert d["differ"] is True
    assert d["total_running_only"] == 1
    assert d["only_running"][0]["text"] == " stackwise-virtual link 1"
    # 行号必须映射回 running 原文（前端标红只认行号）
    ln = d["only_running"][0]["line"]
    assert running.split("\n")[ln - 1].strip() == "stackwise-virtual link 1"
    assert d["only_startup"] == []


def test_only_in_startup_is_reported():
    """startup 有而 running 没有 → 保存过但后来被改掉/删了。"""
    running = "hostname X\n"
    startup = "hostname X\nsnmp-server community OLD\n"
    d = diff_configs(running, startup)
    assert d["differ"] is True and d["total_startup_only"] == 1
    assert d["only_startup"][0]["text"] == "snmp-server community OLD"


def test_identical_configs_take_fast_path():
    """绝大多数情况两边完全一致；快路径下 differ=False 且不带明细。"""
    d = diff_configs(RUNNING, RUNNING)
    assert d["differ"] is False and d["only_running"] == [] and d["only_startup"] == []
    assert d["running_lines"] == d["startup_lines"]


def test_truncation_caps_output():
    running = "".join(f"line-{i}\n" for i in range(100))
    startup = "hostname X\n"
    d = diff_configs(running, startup, limit=10)
    assert d["differ"] is True
    assert len(d["only_running"]) == 10 and d["truncated"] is True
    assert d["total_running_only"] == 100


def test_empty_inputs():
    assert diff_configs("", "")["differ"] is False
    assert diff_configs("hostname X\n", "")["differ"] is True


def test_normalized_lines_keep_original_line_numbers():
    text = "Building configuration...\n!\nhostname X\n!\ninterface Gi0/1\n"
    lines = normalized_lines(text)
    assert lines == [(3, "hostname X"), (5, "interface Gi0/1")]
