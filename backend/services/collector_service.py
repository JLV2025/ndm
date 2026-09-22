"""配置收集服务"""

import os
import json
import re
import sys
import traceback
import threading
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def _get_device_connection():
    """延迟导入 DeviceConnection 以支持 mocking"""
    from collectors.base import DeviceConnection
    return DeviceConnection
from analyzers.config_validator import ConfigValidator
from analyzers.performance import PerformanceAnalyzer
from analyzers.change_detector import ChangeDetector
from analyzers.stp_parser import parse_spanning_tree
from utils.settings_loader import load_settings
from utils.password import password_manager
from utils.port_names import normalize_port_name, norm_lag_name, member_no_from_port
from utils.device_identity import kind_from_config, member_suffixes, physical_name
from analyzers.hardware_change import compute_fingerprint, diff_fingerprints, record_event
from storage.file_manager import get_week_dir, run_retention
from storage.database import get_connection as get_db
from models.devices import Device


# 全局收集进度追踪
_progress_lock = threading.Lock()
_collection_progress: Dict[str, Dict] = {}


def get_collection_progress(device_name: str) -> Dict | None:
    """获取设备收集进度（线程安全）"""
    with _progress_lock:
        return _collection_progress.get(device_name)


def _set_progress(device_name: str, step: str, error: str = "", progress: float = 0,
                  cmd_done: int = 0, total_cmds: int = 0):
    """设置设备收集进度（线程安全）

    Args:
        device_name: 设备名
        step: 当前步骤标识 (connecting / collecting / analyzing / saving / complete / failed)
        error: 错误信息
        progress: 当前步骤进度百分比 (0~100)
        cmd_done: 已完成的命令数
        total_cmds: 总命令数
    """
    with _progress_lock:
        _collection_progress[device_name] = {
            "step": step,
            "started_at": datetime.now().isoformat(),
            "error": error,
            "progress": progress,
            "cmd_done": cmd_done,
            "total_cmds": total_cmds,
        }


def _clear_progress(device_name: str):
    """清除设备收集进度"""
    with _progress_lock:
        _collection_progress.pop(device_name, None)


def _is_aruba_device(device_type: str) -> bool:
    """判断是否为 Aruba 设备（兼容多种类型名）"""
    return device_type == "aruba_aoscx"


def _is_router_device(device_type: str) -> bool:
    """判断是否为 Cisco IOS 路由器"""
    return device_type == "cisco_ios_router"


def _is_svl_device(device_model: str) -> bool:
    """是否为 C9500 StackWise Virtual（特例平台）

    老 C9500 的命令与其它 Cisco 平台都不一样：show version 没有成员表、成员段
    也没有 Switch Uptime，成员运行时间只能用 onboard logging 单独采（见
    base.py:collect_svl_uptime）。按**型号**判断 —— platform 是 cisco_ios_xe，
    与 C9200L 等共用，区分不开。
    """
    return "C9500" in (device_model or "").upper()


def _strip_ansi(text: str) -> str:
    """去除 ANSI 转义码和终端控制字符"""
    # ANSI escape sequences: ESC[...m, ESC[...K, etc.
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # 其他控制字符 (保留 \r\n)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text


def _extract_shutdown_ports(config_text: str, norm_fn) -> set:
    """从 running-config 中提取所有 admin down (shutdown) 端口的规范化名称"""
    shutdown: set = set()
    current_iface: str | None = None
    is_shutdown: bool = False
    for line in config_text.splitlines():
        if_match = re.match(r'^interface\s+(\S+)', line)
        if if_match:
            if current_iface and is_shutdown:
                shutdown.add(norm_fn(current_iface))
            current_iface = if_match.group(1)
            is_shutdown = False
        elif re.match(r'^\s*shutdown\s*$', line):
            is_shutdown = True
        elif re.match(r'^\s*no\s+shutdown\s*$', line):
            is_shutdown = False
    if current_iface and is_shutdown:
        shutdown.add(norm_fn(current_iface))
    return shutdown


def extract_software_version(version_output: str, device_type: str) -> str:
    """从 show version 输出中提取软件版本号"""
    version_output = _strip_ansi(version_output)
    lines = version_output.splitlines()

    if device_type in ("cisco_ios", "cisco_ios_router"):
        for line in lines:
            # 支持: 15.7(3)M5, 17.9.4a, 15.2(4), 16.09.03 等格式
            match = re.search(r'Version\s+(\d+\.\d+(?:\.\d+)?(?:\(\d+\))?[A-Za-z]?\d*)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    elif _is_aruba_device(device_type):
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            # Version      : FL.10.10.1070  (ArubaOS-CX)
            match = re.search(r'Version\s*:\s*([A-Z]+\.\d+\.\d+\.\d+)', line_clean, re.IGNORECASE)
            if match:
                print(f"[版本匹配] 模式1 (Version:): {match.group(1)}")
                return match.group(1)
            # ArubaOS-CX FL.10.10.1070 或 ML.10.13.1040
            match = re.search(r'ArubaOS-CX\s+(?:[A-Z]+\.)?(\d+\.\d+\.\d+)', line_clean)
            if match:
                print(f"[版本匹配] 模式2 (ArubaOS-CX): {match.group(1)}")
                return match.group(1)
            # ArubaOSv9, 10.10.1070.0001
            match = re.search(r'ArubaOSv\d+,\s*(\d+\.\d+\.\d+\.\d+)', line_clean)
            if match:
                print(f"[版本匹配] 模式3 (ArubaOSv): {match.group(1)}")
                return match.group(1)
            # Firmware Version 10.10.1070
            match = re.search(r'Firmware Version\s+(\d+\.\d+\.\d+\.?\d*)', line_clean, re.IGNORECASE)
            if match:
                print(f"[版本匹配] 模式4 (Firmware Version): {match.group(1)}")
                return match.group(1)

    print(f"[版本提取失败] 设备类型={device_type}, 内容前500字符: {repr(version_output[:500])}")
    return "未知"


def extract_serial_number(version_output: str, device_type: str, system_output: str = "", vsf_output: str = "", platform: str = "") -> str:
    """从 show version、show system、show vsf 输出中提取设备序列号（VSF/Stack 返回逗号拼接）"""
    version_output = _strip_ansi(version_output)
    lines = version_output.splitlines()
    serials = []

    if device_type in ("cisco_ios", "cisco_ios_router"):
        if platform == "cisco_ios_xe":
            # Cisco IOS XE：序列号来自 Motherboard Serial Number（每个堆叠成员一个）
            for line in lines:
                match = re.search(r'Motherboard\s+[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
        # 回退：System Serial Number（非 XE 或 XE 无 Motherboard SN 时）
        if not serials:
            for line in lines:
                match = re.search(r'System\s+[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
        # 回退：Processor board ID（独立交换机/路由器）
        if not serials:
            for line in lines:
                match = re.search(r'Processor\s+board\s+ID[:\s]+([A-Za-z0-9]+)', line, re.IGNORECASE)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
    elif _is_aruba_device(device_type):
        # 1. 从 show vsf detail 提取成员序列号（VSF 堆叠）
        if vsf_output:
            vsf_output = _strip_ansi(vsf_output)
            for line in vsf_output.splitlines():
                match = re.search(r'[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
                    print(f"[序列号匹配] show vsf detail: {match.group(1)}")
        # 2. 从 show version 提取
        if not serials:
            for line in lines:
                match = re.search(r'[Ss]erial\s*[Nn]umber[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
        # 3. 从 show system 提取
        if not serials and system_output:
            system_output = _strip_ansi(system_output)
            for line in system_output.splitlines():
                match = re.search(r'(?:Chassis\s*)?[Ss]erial\s*[Nn](?:br|umber)?[:\s]+([A-Za-z0-9]+)', line)
                if match and match.group(1) not in serials:
                    serials.append(match.group(1))
                    print(f"[序列号匹配] show system: {match.group(1)}")

    result = ", ".join(serials) if serials else "未知"
    if result == "未知":
        print(f"[序列号提取失败] 设备类型={device_type}, 版本输出前300字符: {repr(version_output[:300])}")
        if system_output:
            print(f"[序列号提取失败] 系统输出前300字符: {repr(system_output[:300])}")
    return result


def extract_member_ids(vsf_output: str = "", version_output: str = "") -> str:
    """堆叠成员号（逗号拼接，与序列号同序 1:1）

    ① Aruba：show vsf detail 的 `Member ID : N` 行（例: "Member ID : 1" → "1"）；
    ② Cisco：show version 成员表第 1 列（`* 1 52 WS-C2960X...`）——与成员版本同表，
       此前只取了第 4 组（版本），Switch 号被丢弃。不加此源，Cisco 堆叠只能靠
       顺序号兜底：跳号场景（成员 2 拆走后成员 3 被标成 -2）会身份漂移，
       成员行"改名"，历史与保修断链。
    注意: 不去重 — 与序列号按行序一一对应，重复序列号（罕见）时去重会错位。
    空输出（非堆叠 / 提取失败）返回 ""，由调用方决定是否使用。
    """
    members: list[str] = []
    # ① Aruba VSF
    if vsf_output:
        for line in _strip_ansi(vsf_output).splitlines():
            match = re.search(r'^\s*Member\s+ID\s*:\s*(\d+)', line, re.IGNORECASE)
            if match:
                members.append(match.group(1))
    if members:
        return ", ".join(members)
    # ② Cisco 成员表（复用版本解析的同一表头/行正则，第 1 组即 Switch 号）
    if version_output:
        text = _strip_ansi(version_output)
        header = _CISCO_MEMBER_TABLE_HEADER.search(text)
        if header:
            for line in text[header.end():].splitlines():
                match = _CISCO_MEMBER_TABLE_ROW.match(line)
                if match:
                    members.append(match.group(1))
                elif members:
                    break  # 表数据结束后的第一个不匹配行即表尾
    return ", ".join(members)


# Cisco classic IOS 堆叠的成员表（真机样本：SZXD1SWI01 / PVGD1SWI05 —— 2960X 堆叠）
#   Switch Ports Model                     SW Version            SW Image
#   ------ ----- -----                     ----------            ----------
#   *    1 52    WS-C2960X-48FPD-L         15.2(4)E8             C2960X-UNIVERSALK9-M
_CISCO_MEMBER_TABLE_HEADER = re.compile(
    r'^Switch\s+Ports\s+Model\b.*\bSW\s+Version\b', re.MULTILINE | re.IGNORECASE)
_CISCO_MEMBER_TABLE_ROW = re.compile(
    r'^\s*(?:\*\s*)?(\d+)\s+(\d+)\s+(\S+)\s+(\S+)(?:\s+\S+)?\s*$')


def extract_member_versions(version_output: str = "") -> str:
    """提取堆叠各成员的软件版本（逗号拼接，与序列号同序）；单机 / 无成员表返回 ""

    数据源是 Cisco ``show version`` 的成员表 —— 这是**唯一**逐成员给出软件版本的地方
    （classic IOS 堆叠，如 2960X）。IOS-XE 堆叠（C9500/3850）与 Aruba VSF 的该命令
    没有成员版本表：整堆叠共享一个镜像、成员版本恒等，由报告侧用整机版本填充。

    成员版本不一致只可能出现在 classic IOS 堆叠的升级窗口内（一个成员已重启进新镜像、
    另一个还在跑旧版本）—— 这正是值得报警的场景。
    """
    if not version_output:
        return ""
    text = _strip_ansi(version_output)
    header = _CISCO_MEMBER_TABLE_HEADER.search(text)
    if not header:
        return ""
    versions: list[str] = []
    for line in text[header.end():].splitlines():
        match = _CISCO_MEMBER_TABLE_ROW.match(line)
        if match:
            versions.append(match.group(4))
        elif versions:
            break  # 表数据结束后的第一个不匹配行即表尾
    return ", ".join(versions)


def _member_count(serial_number: str) -> int:
    """序列号（逗号拼接）→ 物理成员台数（用于把设备级字段复制到各成员行）"""
    return len([s for s in (serial_number or "").split(",") if s.strip()])


def _cisco_boot_version(text: str) -> str:
    """从 Cisco ``show version`` 提取引导（ROM/BOOTLDR）版本号

    真机样本（2960X）：
        ROM: Bootstrap program is C2960X boot loader          ← 无版本号，跳过
        BOOTLDR: C2960X Boot Loader (C2960X-HBOOT-M) Version 15.2(4r)E3, RELEASE SOFTWARE (fc4)
    老 IOS 的 ROM 行带版本：``ROM: System Bootstrap, Version 12.2(44)SE6, ...``
    BOOTLDR 行优先（更完整），没有时再看 ROM 行。
    """
    lines = _strip_ansi(text).splitlines()
    for prefix in ("BOOTLDR", "ROM"):
        for line in lines:
            if not line.strip().upper().startswith(prefix):
                continue
            match = re.search(r'\bVersion\s+(\S+?)(?:[,\s]|$)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    return ""


def extract_member_rom_versions(vsf_output: str = "", version_output: str = "",
                                member_count: int = 0) -> str:
    """提取各成员的 ROM（引导）版本（逗号拼接，与成员 ID / 序列号同序）

    - Aruba（``show vsf detail``）：成员段的 ``ROM Version : FL.01.11.0001``，逐成员给出。
      AOS-CX 的**软件**版本是整堆叠一个（堆叠级 Software Version），成员级唯一
      逐成员给出的版本就是 ROM Version —— 升级引导时逐个成员更新，可能出现不一致。
    - Cisco（``show version``）：``BOOTLDR: ... Version 15.2(4r)E3``。真机只上报
      主交换机的引导版本（成员段不含该字段）→ **按成员数复制**，保持
      「与序列号同序对齐」的列约定（整堆叠共享同一镜像，引导版本随镜像走）。
    """
    if vsf_output:
        roms: list[str] = []
        for line in _strip_ansi(vsf_output).splitlines():
            match = re.search(r'^\s*ROM\s+Version\s*:\s*(\S+)', line, re.IGNORECASE)
            if match:
                roms.append(match.group(1))
        if roms:
            return ", ".join(roms)

    if version_output:
        boot = _cisco_boot_version(version_output)
        if boot:
            return ", ".join([boot] * max(member_count, 1))
    return ""


def extract_member_uptimes(version_output: str = "", vsf_output: str = "",
                           svl_output: str = "") -> str:
    """提取堆叠各成员的运行时间（秒，逗号拼接，与序列号同序）；无成员段返回 ""

    - Cisco（show version）：设备级 ``<主机名> uptime is ...`` 是 1 号成员（主交换机，
      实测 SZXD1SWI01 主交换机与成员段数值一致），其余成员在各成员段的
      ``Switch Uptime : ...``
    - Aruba（show vsf detail）：各成员段的 ``Uptime : ...``
    - C9500 StackWise Virtual（onboard logging，特例）：两段 ``Current uptime``，
      顺序 = active、standby（与 show version 的序列号顺序一致：1 号 = active）

    成员级运行时间能看出设备级 uptime 看不出的信号：堆叠里**单台成员**重启。
    """
    # C9500 SVL 特例优先：show version 里既没有成员表也没有 Switch Uptime，
    # 只有 onboard logging 的 UPTIME SUMMARY 逐成员给运行时间。
    # 只有拿到 2 段才算数（单机 C9500 的 standby 段会失败）——
    # 1 段时走常规逻辑返回空，由报告侧回退设备级运行时间，避免把 active 的值错标成别人。
    if svl_output:
        svl_values: list[int] = []
        for match in re.finditer(r'Current uptime\s*:\s*([^\n\r]+)', _strip_ansi(svl_output), re.IGNORECASE):
            value = _parse_uptime_phrase(match.group(1))
            if value is not None:
                svl_values.append(value)
        if len(svl_values) >= 2:
            return ", ".join(str(v) for v in svl_values[:2])

    seconds_list: list[int] = []

    if version_output:
        text = _strip_ansi(version_output)
        main = re.search(r'uptime is\s+([^\n\r]+)', text, re.IGNORECASE)
        if main:
            value = _parse_uptime_phrase(main.group(1))
            if value is not None:
                seconds_list.append(value)
        for m in re.finditer(r'Switch\s+Uptime\s*:\s*([^\n\r]+)', text, re.IGNORECASE):
            value = _parse_uptime_phrase(m.group(1))
            if value is not None:
                seconds_list.append(value)

    if vsf_output:
        text = _strip_ansi(vsf_output)
        for m in re.finditer(r'^\s*Uptime\s*:\s*([^\n\r]+)', text, re.MULTILINE | re.IGNORECASE):
            value = _parse_uptime_phrase(m.group(1))
            if value is not None:
                seconds_list.append(value)

    # 只有单个成员值（非堆叠）时不返回 —— 单机运行时间由设备级字段负责，避免重复
    if len(seconds_list) < 2:
        return ""
    return ", ".join(str(s) for s in seconds_list)


def extract_model(system_output: str, version_output: str, device_type: str, vsf_output: str = "") -> str:
    """从 show system / show version / show vsf detail 输出中提取设备型号

    - Aruba VSF 堆叠: vsf.raw 中每个成员一节, Type 行 = SKU, Model 行 = 系列名
      例: "Type : JL725A" + "Model : Aruba 6200F 24G ..." → "JL725A 6200F"（逗号拼接, 与序列号 1:1 对应）
    - Aruba 单机: system.raw → Product Name 行，取前 2 个 token (SKU + 系列名)
      例: "JL659A 6300M 48SR5 CL6 PoE 4SFP56 Swch" → "JL659A 6300M"
    - Cisco: version.raw → Model number 行 (堆叠设备多 member 逗号拼接)
      例: "WS-C2960X-48FPD-L" 或 "WS-C2960X-48FPD-L, WS-C2960X-48FPD-L"
    """
    version_output = _strip_ansi(version_output)

    if _is_aruba_device(device_type):
        # 1. VSF 堆叠: 从 vsf.raw 提取每个成员的 SKU + 系列名（与序列号提取同源, 顺序一致）
        if vsf_output:
            vsf_output = _strip_ansi(vsf_output)
            skus: list[str] = []
            series: list[str] = []
            for line in vsf_output.splitlines():
                # SKU 模式: JL 前缀(JL\d{3,4}[A-Z]) + R 前缀(6300M/6400 新款, 如 R8S89A)
                m = re.search(r'^\s*Type\s*:\s*(JL\d{3,4}[A-Z]|R\d[A-Z0-9]{3,5}[A-Z]?)', line, re.IGNORECASE)
                if m:
                    skus.append(m.group(1))
                    continue
                m = re.search(r'^\s*Model\s*:\s*Aruba\s+(\S+)', line, re.IGNORECASE)
                if m:
                    series.append(m.group(1))
            if skus:
                # 位置配对依赖 AOS-CX 输出约定: 每成员节内 Type 行先于 Model 行且成对出现
                # 系列名齐全则拼 "SKU 系列名", 否则退化为纯 SKU（防错位）
                if len(series) == len(skus):
                    return ", ".join(f"{s} {t}" for s, t in zip(skus, series))
                return ", ".join(skus)
        # 2. 单机回退: 从 system.raw 提取 Product Name
        if system_output:
            system_output = _strip_ansi(system_output)
            for line in system_output.splitlines():
                m = re.search(r'Product\s+Name\s*:\s*(.+)', line, re.IGNORECASE)
                if m:
                    tokens = m.group(1).strip().split()
                    if len(tokens) >= 2:
                        return f"{tokens[0]} {tokens[1]}"
                    return tokens[0] if tokens else "未知"
        # 回退: 从 version.raw 搜索 JL 型号模式
        for line in version_output.splitlines():
            m = re.search(r'(JL\d{3}[AB]\s+\d{4}M)', line)
            if m:
                return m.group(1)
        return "未知"

    elif device_type in ("cisco_ios", "cisco_ios_router"):
        models = []
        for line in version_output.splitlines():
            # "Model number                    : WS-C2960X-48FPD-L"
            # 不去重 — 每个堆叠成员各记一条，与序列号保持 1:1 对应
            m = re.search(r'Model\s+number\s*:\s*(\S+)', line, re.IGNORECASE)
            if m:
                models.append(m.group(1).strip())

        # 回退：路由器 show version 无 Model number 行，型号在处理器行
        # "cisco ISR4331/K9 (1RU) processor with ..." → 提取 ISR4331/K9
        if not models:
            for line in version_output.splitlines():
                m = re.search(r'cisco\s+(\S+)\s*\(', line, re.IGNORECASE)
                if m:
                    models.append(m.group(1).strip())
                    break  # 路由器非堆叠，取第一个即可

        return ", ".join(models) if models else "未知"

    return "未知"


def extract_uptime_seconds(version_output: str = "", boot_history: str = "", device_type: str = "") -> int | None:
    """从 show version (Cisco) 或 show boot-history (Aruba) 提取设备运行时间（秒）

    Cisco: SHAD1SWI01 uptime is 1 year, 29 weeks, 2 days, 5 hours, 48 minutes
    Aruba: Current Boot, up for 545 days 19 hrs 43 mins 22 secs
    """
    if device_type == "aruba_aoscx" and boot_history:
        return _parse_aruba_uptime(boot_history)
    if device_type.startswith("cisco") and version_output:
        return _parse_cisco_uptime(version_output)
    return None


def _parse_cisco_uptime(version_output: str) -> int | None:
    """解析 Cisco show version 中的运行时间

    真机格式的**行首是主机名**，不是 "System"（IOS / IOS-XE 一致，实测样本）：
        SHAD1SWI01 uptime is 1 year, 29 weeks, 2 days, 5 hours, 48 minutes
        KR5D1SWI01 uptime is 6 years, 27 weeks, 12 hours, 41 minutes

    下一行还有 "Uptime for this control processor is ..."，它不含 "uptime is"
    子串（中间隔着 for this control processor），不会抢到第一个匹配。
    """
    output = _strip_ansi(version_output)
    m = re.search(r'uptime is\s+([^\n\r]+)', output, re.IGNORECASE)
    return _parse_uptime_phrase(m.group(1)) if m else None


def _parse_aruba_uptime(boot_history: str) -> int | None:
    """解析 Aruba show boot-history 中的 Current Boot 运行时间

    AOS-CX **会省略数值为 0 的单位**，四段中任意一段都可能缺席（实测样本）：
        Current Boot, up for 350 days 34 mins 32 secs     ← 无 hrs
        Current Boot, up for 180 days 4 hrs 56 secs       ← 无 mins
        Current Boot, up for 124 days 5 hrs 19 mins       ← 无 secs
    """
    output = _strip_ansi(boot_history)
    m = re.search(r'Current Boot, up for\s+([^\n\r]+)', output, re.IGNORECASE)
    return _parse_uptime_phrase(m.group(1)) if m else None


# 运行时长短语的单位 → 秒。Cisco 与 Aruba 的写法都覆盖：
#   Cisco：1 year, 29 weeks, 2 days, 5 hours, 48 minutes
#   Aruba：105 days 20 hrs 37 mins 1 secs / 21 hours under a minute（不足一分钟不计数）
_UPTIME_UNIT_SECONDS = {
    "year": 365 * 86400, "week": 7 * 86400, "day": 86400,
    "hour": 3600, "hr": 3600, "minute": 60, "min": 60, "sec": 1,
}
_UPTIME_PHRASE_RE = re.compile(r'(\d+)\s+(year|week|day|hour|hr|minute|min|sec)', re.IGNORECASE)


def _parse_uptime_phrase(text: str) -> int | None:
    """解析时长短语（任一段可省，单复数不限）；一段数值都没有 → None"""
    total = 0
    found = False
    for m in _UPTIME_PHRASE_RE.finditer(text):
        total += int(m.group(1)) * _UPTIME_UNIT_SECONDS[m.group(2).lower()]
        found = True
    return total if found else None


def parse_syslog_lines(log_output: str, device_type: str,
                       collection_dt: str = "") -> list:
    """将原始日志输出解析为结构化列表

    Cisco Syslog 格式: *Mar  1 00:00:00.000: %FACILITY-SEVERITY-MNEMONIC: message
    Cisco 无时间戳格式: %FACILITY-SEVERITY-MNEMONIC: message
    Aruba 格式: YYYY-MM-DDTHH:MM:SS.XXXXXX+XX:XX {facility} {severity} {mnemonic} message

    collection_dt: ISO 格式的收集时间，用于 Cisco 时间戳补年份

    返回: [{"timestamp": "...", "normalized_ts": "YYYY-MM-DDTHH:MM:SS" or "",
             "severity": "...", "facility": "...", "message": "..."}]
    """
    from datetime import datetime

    if not log_output or log_output.startswith('% 收集失败'):
        return []

    # 从 collection_dt 中提取年份（用于 Cisco 时间戳规范化）
    collection_year = "2026"
    try:
        if collection_dt:
            collection_year = str(datetime.fromisoformat(collection_dt).year)
    except (ValueError, TypeError):
        pass

    entries = []
    output = _strip_ansi(log_output)

    # Aruba CX show logging -r 格式:
    #   YYYY-MM-DDTHH:MM:SS.mmmmmm+ZZ:ZZ  HOSTNAME  PROCESS[PID]:  MESSAGE
    #   消息体内的 LOG_INFO/LOG_ERR/... 是真正的严重级别，进程名作为 facility
    if device_type == "aruba_aoscx":
        _ARUBA_LOG_RE = re.compile(
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})\s+'
            r'\S+\s+'                       # hostname（跳过）
            r'([^\[\s]+)\[\d+\]:\s*'        # process（用作 facility）
            r'(.*)',                        # message
        )
        _ARUBA_SEV_RE = re.compile(
            r'LOG_(EMERG|ALERT|CRIT|ERR|WARNING|NOTICE|INFO|DEBUG)'
        )
        _ARUBA_SEV_MAP = {
            'LOG_EMERG': '0', 'LOG_ALERT': '1', 'LOG_CRIT': '2',
            'LOG_ERR': '3', 'LOG_WARNING': '4', 'LOG_NOTICE': '5',
            'LOG_INFO': '6', 'LOG_DEBUG': '7',
        }

        for line in output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # 跳过表头/分隔线
            if (stripped.startswith('---')
                    or stripped.startswith('Event logs')
                    or stripped.startswith('show logging')):
                continue

            m = _ARUBA_LOG_RE.match(stripped)
            if m:
                raw_ts = m.group(1)
                norm_ts = raw_ts[:19]  # "2026-06-24T14:35:22"
                facility = m.group(2)  # 进程名 (如 log-proxyd)
                message = m.group(3)

                # 从消息体提取严重级别
                sev_match = _ARUBA_SEV_RE.search(message)
                severity = _ARUBA_SEV_MAP.get(
                    sev_match.group(0), ''
                ) if sev_match else ''

                entries.append({
                    "timestamp": raw_ts,
                    "normalized_ts": norm_ts,
                    "facility": facility,
                    "severity": severity,
                    "message": message,
                })
                continue

            # 无法解析的 Aruba 行仍保留（方便排查）
            entries.append({"timestamp": "", "normalized_ts": "", "severity": "",
                            "facility": "", "message": stripped})
        return entries

    # Cisco 月份映射
    _CISCO_MONTHS = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12',
    }

    def _normalize_cisco_ts(ts: str, year: str) -> str:
        """将 Cisco 时间戳转为 ISO: '*Mar  1 00:00:00' → '2026-03-01T00:00:00'"""
        m = re.match(r'\*?(\w{3})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})', ts)
        if m:
            month = _CISCO_MONTHS.get(m.group(1), '01')
            day = m.group(2).zfill(2)
            return f"{year}-{month}-{day}T{m.group(3)}"
        return ""

    # Cisco 格式: %FACILITY-SEVERITY-MNEMONIC: message
    cisco_ts_re = re.compile(
        r'^(?:\*)?(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\s+\w+)?):\s*'
        r'%(\w+)-(\d)-(\w+):\s*(.*)'
    )
    cisco_no_ts_re = re.compile(
        r'^%(\w+)-(\d)-(\w+):\s*(.*)'
    )

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Syslog logging:") or stripped.startswith("Buffer logging:"):
            continue
        if stripped.startswith("Trap logging:") or stripped.startswith("Log Buffer"):
            continue

        m = cisco_ts_re.match(stripped)
        if m:
            raw_ts = m.group(1)
            entries.append({
                "timestamp": raw_ts,
                "normalized_ts": _normalize_cisco_ts(raw_ts, collection_year),
                "facility": m.group(2),
                "severity": m.group(3),
                "message": m.group(5) or "",
            })
            continue

        m2 = cisco_no_ts_re.match(stripped)
        if m2:
            entries.append({
                "timestamp": "",
                "normalized_ts": "",  # 无法规范化
                "facility": m2.group(1),
                "severity": m2.group(2),
                "message": m2.group(4) or "",
            })
            continue

    return entries


def collect_device(
    device: Device,
    username: str,
    password: str,
    settings: Dict,
) -> Dict:
    """Collect device configuration data"""

    device_name = device.name
    device_ip = device.ip
    device_type = device.type
    device_platform = getattr(device, 'platform', '') or ''
    # 型号提示（来自上次采集入库的 devices.model）：只在命令总数预计算与
    # C9500 SVL 特例分支里用 —— 采集当下要等 show version 才知道型号，赶不上进度条。
    device_model_hint = getattr(device, 'model', '') or ''
    data_root = settings.get("data_root", "./data")

    # ---- 预计算命令总数（含 Ping），用于进度条百分比 ----
    # 基础命令（所有设备）：running-config, logs, interface status, version, utilization,
    #                       interface counters, cdp, lldp
    total_cmds = 1 + 6 + 2  # ping + 6 base + 2 (cdp + lldp)
    if _is_aruba_device(device_type):
        total_cmds += 3  # system, vsf, boot-history
    elif device_type == "cisco_ios" and not _is_router_device(device_type):
        total_cmds += 1  # switch detail
    if _is_router_device(device_type):
        total_cmds += 2  # routing table + interface description（端口清单）
    if device_type == "aruba_aoscx" or "cisco" in (device_type or ""):
        total_cmds += 1  # LAG 成员关系 (lacp aggregates / etherchannel summary)
    if not _is_router_device(device_type):
        total_cmds += 1  # spanning-tree（仅交换机；路由器不跑 STP）
    if _is_svl_device(device_model_hint):
        total_cmds += 1  # C9500 SVL 成员运行时间（onboard logging，两条命令算一步）
    cmd_done = 0

    def _advance(label: str = ""):
        """完成一条命令后推进进度条"""
        nonlocal cmd_done
        cmd_done += 1
        pct = cmd_done / total_cmds * 100
        _set_progress(device_name, "collecting", progress=pct, cmd_done=cmd_done, total_cmds=total_cmds)
        if label:
            print(f"[收集进度] {label}: {cmd_done}/{total_cmds} ({pct:.0f}%)")

    # Step 1: Ping 可达性检测（含 TCP/22 回退）
    _set_progress(device_name, "ping", progress=0, cmd_done=0, total_cmds=total_cmds)
    import subprocess as _sp
    import platform as _pf
    import socket as _sock
    sys_name = _pf.system().lower()
    ping_cmd = ["ping", "-n", "1", "-w", "2000", device_ip] if sys_name == "windows" \
        else ["ping", "-c", "1", "-W", "2", device_ip]
    try:
        ping_result = _sp.run(ping_cmd, capture_output=True, text=True, timeout=5)
    except _sp.TimeoutExpired:
        _set_progress(device_name, "failed", f"Ping 超时（{device_ip}）", cmd_done=0, total_cmds=total_cmds)
        return {"name": device_name, "ip": device_ip, "status": "failed", "error": f"Ping 超时（{device_ip}）"}
    except Exception as e:
        _set_progress(device_name, "failed", f"Ping 异常: {e}", cmd_done=0, total_cmds=total_cmds)
        return {"name": device_name, "ip": device_ip, "status": "failed", "error": str(e)}

    if ping_result.returncode != 0:
        # ICMP 被拦截时，尝试 TCP 22 端口回退
        try:
            sock = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            sock.settimeout(3)
            tcp_result = sock.connect_ex((device_ip, 22))
            sock.close()
            if tcp_result != 0:
                _set_progress(device_name, "failed", f"设备不可达（Ping {device_ip} 失败）", cmd_done=0, total_cmds=total_cmds)
                return {
                    "name": device_name, "ip": device_ip,
                    "status": "failed", "error": f"设备不可达（Ping {device_ip} 失败）"
                }
        except (_sock.timeout, ConnectionRefusedError, OSError):
            _set_progress(device_name, "failed", f"设备不可达（Ping {device_ip} 失败）", cmd_done=0, total_cmds=total_cmds)
            return {
                "name": device_name, "ip": device_ip,
                "status": "failed", "error": f"设备不可达（Ping {device_ip} 失败）"
            }
    _advance("ping")

    # 保持 ping 步骤的进度，不重置为 0
    current_pct = cmd_done / total_cmds * 100
    _set_progress(device_name, "connecting", progress=current_pct, cmd_done=cmd_done, total_cmds=total_cmds)

    conn = _get_device_connection()({
        "name": device_name,
        "ip": device_ip,
        "type": device_type,
        "platform": device_platform,
        "port": 22,
        "timeout": 120
    })

    if not conn.connect(username, password):
        error_msg = getattr(conn, '_last_error', '') or 'SSH 连接失败'
        print(f"[收集失败] 连接失败: {error_msg}")
        _set_progress(device_name, "failed", error_msg, cmd_done=cmd_done, total_cmds=total_cmds)
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "failed",
            "error": error_msg
        }

    print(f"[收集进度] SSH 连接成功，开始收集数据...")

    # 使用实际探测到的设备类型（可能与配置不同）
    effective_type = conn.actual_device_type or device_type
    type_mismatch = conn.type_mismatch

    # 如果实际设备类型与预计算时不同，重新调整 total_cmds
    # （mismatch 极少发生，这里做防御性处理）
    if effective_type != device_type:
        # 判定一律用 device_type（配置的设备类别）——实际采集分支用的也是它。
        # effective_type 只是 Netmiko 驱动名，cisco_ios_router 会被映射成 cisco_ios，
        # 拿它判断 _is_router_device 会漏掉路由器的专属命令。
        total_cmds = 1 + 6 + 2  # 重新计算：ping + 6 base + 2
        if _is_aruba_device(device_type):
            total_cmds += 3
        elif device_type == "cisco_ios" and not _is_router_device(device_type):
            total_cmds += 1
        if _is_router_device(device_type):
            total_cmds += 2
        if device_type == "aruba_aoscx" or "cisco" in (device_type or ""):
            total_cmds += 1  # LAG 成员关系
        if not _is_router_device(device_type):
            total_cmds += 1  # spanning-tree（仅交换机）
        if _is_svl_device(device_model_hint):
            total_cmds += 1  # C9500 SVL 成员运行时间

    def _safe_collect(collect_func, label: str) -> str:
        """安全执行单条命令收集，失败时返回错误信息但不抛异常"""
        try:
            result = collect_func()
            return result
        except Exception as e:
            print(f"[收集异常] {label}: {e}")
            return f"% 收集失败: {str(e)}"

    try:
        # 收集原始数据
        print(f"[收集进度] 获取 running-config...")
        try:
            running_config, startup_config = conn.collect_config()
        except Exception as e:
            print(f"[收集异常] config: {e}")
            running_config = f"% 收集失败: {str(e)}"
            startup_config = ""
        _advance(f"running-config: {len(running_config) if running_config else 0} 行")

        # 日志
        print(f"[收集进度] 获取 logs...")
        logs = _safe_collect(conn.collect_logs, "logs")
        _advance(f"logs: {len(logs)} 行")

        # 接口状态
        print(f"[收集进度] 获取 interface status...")
        interface_status = _safe_collect(conn.collect_interface_status, "interface status")
        _advance("interface status")

        # 版本
        print(f"[收集进度] 获取 version...")
        version_info = _safe_collect(conn.collect_show_version, "version")
        _advance("version")

        # 利用率
        print(f"[收集进度] 获取 interface utilization...")
        interface_utilization = _safe_collect(conn.collect_show_interface_utilization, "interface utilization")
        _advance("interface utilization")

        # 端口累计计数器（区间流量的原始读数，只存原值不预计算）
        print(f"[收集进度] 获取 interface counters...")
        interface_counters = _safe_collect(conn.collect_interface_counters, "interface counters")
        _advance("interface counters")

        # 路由器端口清单（路由器上 show interface status 返回空，改由 description 提供）
        interface_description = ""
        if _is_router_device(device_type):
            print(f"[收集进度] 获取 interface description...")
            interface_description = _safe_collect(conn.collect_interface_description, "interface description")
            _advance("interface description")

        # Aruba CX show version 不含序列号，需要 show system + show vsf
        system_info = ""
        vsf_info = ""
        switch_info = ""
        boot_history = ""
        if _is_aruba_device(effective_type):
            print(f"[收集进度] 获取 system info (序列号)...")
            system_info = _safe_collect(conn.collect_system_info, "show system")
            _advance("show system")

            print(f"[收集进度] 获取 vsf info (堆叠成员)...")
            vsf_info = _safe_collect(conn.collect_vsf_info, "show vsf")
            _advance("show vsf")

            print(f"[收集进度] 获取 boot-history (运行时间)...")
            boot_history = _safe_collect(conn.collect_boot_history, "show boot-history")
            _advance("show boot-history")
        elif effective_type == "cisco_ios" and not _is_router_device(device_type):
            print(f"[收集进度] 获取 switch detail (堆叠信息)...")
            switch_info = _safe_collect(conn.collect_switch_detail, "show switch detail")
            _advance("show switch detail")

        # C9500 StackWise Virtual 特例：成员运行时间只能从 onboard logging 取
        # （show version 没有成员段，取不到 Switch Uptime）
        svl_uptime_raw = ""
        if _is_svl_device(device_model_hint):
            print(f"[收集进度] 获取 SVL 成员运行时间 (C9500 特例)...")
            svl_uptime_raw = _safe_collect(conn.collect_svl_uptime, "svl uptime")
            _advance("svl uptime")

        # 路由器专属：收集路由表
        route_info = ""
        if _is_router_device(device_type):
            print(f"[收集进度] 获取 routing table...")
            route_info = _safe_collect(conn.collect_routing_table, "show ip route")
            _advance("show ip route")

        # 收集 CDP / LLDP 邻居信息 (所有设备类型)
        print(f"[收集进度] 获取 CDP neighbors...")
        cdp_neighbors_raw = _safe_collect(conn.collect_cdp_neighbors, "show cdp nei")
        _advance("show cdp nei")

        print(f"[收集进度] 获取 LLDP neighbors...")
        lldp_neighbors_raw = _safe_collect(conn.collect_lldp_neighbors, "show lldp neighbors")
        _advance("show lldp neighbors")

        # 收集 LAG / 链路聚合信息
        lag_membership_raw = ""
        lacp_raw = ""
        if effective_type == "aruba_aoscx":
            print(f"[收集进度] 获取 LACP aggregates...")
            lacp_raw = _safe_collect(conn.collect_lacp_aggregates, "show lacp aggregates")
            _advance("show lacp aggregates")
        elif "cisco" in effective_type:
            print(f"[收集进度] 获取 EtherChannel summary...")
            lacp_raw = _safe_collect(conn.collect_etherchannel_summary, "show etherchannel summary")
            _advance("show etherchannel summary")

        # 生成树（仅交换机；路由器不跑 STP）
        spanning_tree_raw = ""
        if not _is_router_device(device_type):
            print(f"[收集进度] 获取 spanning-tree...")
            spanning_tree_raw = _safe_collect(conn.collect_spanning_tree, "show spanning-tree")
            _advance("show spanning-tree")

        # 提取版本号和序列号（使用实际设备类型，传入 system + vsf 信息）
        software_version = extract_software_version(version_info, effective_type)
        serial_number = extract_serial_number(version_info, effective_type, system_info, vsf_info, platform=device_platform)

        # 提取设备型号（Aruba 从 vsf.raw/system.raw, Cisco 从 version.raw）
        device_model = extract_model(system_info, version_info, effective_type, vsf_info)

        # 回退保护: VSF 成员型号提取失败时按序列号数量补齐（历史逻辑）
        # Cisco 堆叠 show version 有多条 Model number，无需此处理
        if serial_number and serial_number != "未知" and device_model and device_model != "未知":
            serial_cnt = len([s for s in serial_number.split(",") if s.strip()])
            model_cnt = len([m for m in device_model.split(",") if m.strip()])
            if serial_cnt > 1 and model_cnt == 1:
                device_model = ", ".join([device_model] * serial_cnt)

        # 提取设备运行时间（秒）
        system_uptime_seconds = extract_uptime_seconds(version_info, boot_history, effective_type)

        # 解析生成树（仅交换机；解析失败不影响采集主流程）
        stp_rows: list = []
        if spanning_tree_raw and not spanning_tree_raw.startswith("% 收集失败"):
            try:
                stp_rows = _build_stp_rows(parse_spanning_tree(spanning_tree_raw, device_name))
            except Exception as e:
                print(f"[分析异常] STP 解析: {e}")

        # 从 SQLite 查找上一次采集的 running-config（基线对比）
        old_running_config = None
        try:
            db = get_db()
            row = db.execute(
                "SELECT running_config FROM collections WHERE device_id = "
                "(SELECT id FROM devices WHERE name=?) AND phase='1' "
                "ORDER BY id DESC LIMIT 1 OFFSET 1",
                (device_name,)
            ).fetchone()
            if row and row["running_config"]:
                old_running_config = row["running_config"]
        except Exception:
            pass

        # 运行分析
        # 保持当前命令完成进度，不重置为 0
        analyzing_pct = cmd_done / total_cmds * 100
        _set_progress(device_name, "analyzing", progress=analyzing_pct, cmd_done=cmd_done, total_cmds=total_cmds)
        if settings.get("analysis", {}).get("enable_config_validation", True):
            validator = ConfigValidator(running_config)
            validation_results = json.dumps(validator.validate(), indent=2, ensure_ascii=False)
        else:
            validation_results = "{}"

        if settings.get("analysis", {}).get("enable_performance_analysis", True):
            try:
                # 上行口推导（写入 port_snapshots.is_uplink，供流量排行与设备面板使用）
                uplink_ports = _derive_uplink_ports_for(
                    device_name, device_type, running_config,
                    cdp_neighbors_raw, lldp_neighbors_raw, stp_rows, lacp_raw,
                    device.uplink_ports)

                perf_analyzer = PerformanceAnalyzer(
                    interface_status, running_config, device_type,
                    interface_utilization, uplink_ports=uplink_ports,
                    counters_raw=interface_counters,
                    description_raw=interface_description,
                    model=device_model,
                )
                performance_results = json.dumps(perf_analyzer.analyze(), indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[分析异常] PerformanceAnalyzer: {e}")
                traceback.print_exc()
                performance_results = "{}"
        else:
            performance_results = "{}"

        if settings.get("analysis", {}).get("enable_change_detection", True) and old_running_config:
            detector = ChangeDetector(running_config, old_running_config)
            change_results = json.dumps(detector.detect(), indent=2, ensure_ascii=False)
        else:
            change_results = "{}"

        # 保存数据
        saving_pct = cmd_done / total_cmds * 100
        _set_progress(device_name, "saving", progress=saving_pct, cmd_done=cmd_done, total_cmds=total_cmds)
        week = get_week_dir(data_root)
        # 传 device_type（配置的设备类别）而非 effective_type（Netmiko 驱动名）——
        # effective_type 会把 cisco_ios_router 降级成 cisco_ios，写回 devices.type 后
        # 路由器身份就永久丢了（_is_router_device 恒为 False，show ip route 不再采集）。
        _save_data(
            device_name, device_ip, device_type,
            week, data_root, settings,
            running_config, startup_config, logs,
            interface_status, version_info, interface_utilization, system_info, vsf_info, switch_info, route_info,
            validation_results, performance_results, change_results,
            software_version, serial_number, device_model,
            cdp_neighbors_raw, lldp_neighbors_raw,
            boot_history=boot_history,
            system_uptime_seconds=system_uptime_seconds,
            platform=device_platform,
            lacp_raw=lacp_raw,
            stp_rows=stp_rows,
            svl_uptime_raw=svl_uptime_raw,
        )

        # 分层保留：配置文本按周保留（更早的按月归档）、DB 配置全文与日志各留最近 2 次。
        # 只有确实存在超过保留周数的周目录时才动手（plan 是列目录级别，代价可忽略）。
        # 保留策略失败绝不能影响采集结果，故整体兜住。
        try:
            retention = run_retention(data_root, conn=get_db())
            if retention["archived"] or retention["deleted"] or retention["config_cleared"] \
                    or retention["stp_deleted"]:
                print(f"[保留策略] 归档 {retention['archived']} 个周目录、"
                      f"删除 {retention['deleted']} 个、"
                      f"配置全文置空 {retention['config_cleared']} 条、"
                      f"日志删除 {retention['logs_deleted']} 条、"
                      f"STP 快照删除 {retention['stp_deleted']} 条")
        except Exception as e:
            print(f"[保留策略] 跳过：{e}")

        _set_progress(device_name, "complete", progress=100, cmd_done=total_cmds, total_cmds=total_cmds)
        # 延迟清除，给前端轮询窗口读取 "complete" 状态
        import time
        time.sleep(0.5)
        _clear_progress(device_name)
        # 采集成功 → 安排"采集后自动审计"（去抖：整批只跑一轮；任何失败都不影响采集）
        try:
            from services.audit_scheduler import schedule_post_collect_audit
            schedule_post_collect_audit()
        except Exception as e:              # noqa: BLE001 —— 审计不能拖累采集
            print(f"[审计] 安排采集后自动审计失败（不影响采集）：{e}")
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "success",
            "device_type": effective_type,
            "type_mismatch": type_mismatch,
            "configured_type": device_type if type_mismatch else None,
            "running_lines": len(running_config.splitlines()),
            "software_version": software_version,
            "serial_number": serial_number,
            "model": device_model
        }

    except Exception as e:
        print(f"[收集异常] {e}")
        traceback.print_exc()
        _set_progress(device_name, "failed", str(e), cmd_done=cmd_done, total_cmds=total_cmds)
        return {
            "name": device_name,
            "ip": device_ip,
            "status": "failed",
            "error": str(e)
        }
    finally:
        conn.disconnect()


def _parse_lag_members(lacp_raw: str) -> dict:
    """解析 LAG 成员关系：``{"lag 49": ["1/1/49", "1/1/50"], "po 1": [...]}``。

    Aruba `show lacp aggregates` / Cisco `show etherchannel summary` 两种输出；
    键名统一归一（lag14 → 'lag 14'，Port-channel3 → 'po 3'），与 utils.port_names.norm_lag_name 同口径。
    采集侧两处使用（上行口推导 / 落库），故抽成模块级函数。
    """
    if not (lacp_raw and lacp_raw.strip()):
        return {}
    try:
        from analyzers.neighbor_parser import parse_lacp_aruba, parse_etherchannel_cisco
        raw_map: dict = {}
        if "Aggregate name" in lacp_raw:
            raw_map = parse_lacp_aruba(lacp_raw)
        elif "Port-channel" in lacp_raw or "Group" in lacp_raw:
            raw_map = parse_etherchannel_cisco(lacp_raw)
        if not raw_map:
            return {}
        import re as _re
        out: dict = {}
        for k, v in raw_map.items():
            m = _re.match(r'^(lag|po|port-channel)\s*(\d+)$', k, _re.IGNORECASE)
            key = (f'{m.group(1).lower().replace("port-channel", "po")} {m.group(2)}'
                   if m else k)
            out[key] = v
        return out
    except Exception as e:                      # noqa: BLE001 —— 解析失败不影响采集
        print(f"[LAG] 解析失败: {e}")
        return {}


def _derive_uplink_ports_for(device_name: str, device_type: str, running_config: str,
                             cdp_raw: str, lldp_raw: str, stp_rows: list | None,
                             lacp_raw: str, manual) -> list[str]:
    """采集侧上行口推导 —— 返回上行口清单；任何失败都退回手工清单。

    抽成函数的理由：这段曾被 try/except **静默吞掉一个字段名错误**（退回手工清单、
    表面无异常），抽出来配真机形态的测试才钉得住。
    """
    manual_list = list(manual or [])
    try:
        from analyzers.compliance.port_roles import derive_uplink_ports
        from analyzers.neighbor_parser import parse_cdp, parse_lldp, merge_neighbors
        from analyzers.config_parser import ConfigParser
        cdp = parse_cdp(cdp_raw, device_type) if cdp_raw else []
        lldp = parse_lldp(lldp_raw, device_type) if lldp_raw else []
        ntypes = {e.local_port: e.neighbor_type
                  for e in merge_neighbors(cdp, lldp) if e.local_port}
        descs = {e.name: e.description
                 for e in ConfigParser(device_type).parse(running_config or "")}
        root = {r["port_name"] for r in (stp_rows or [])
                if (r.get("role") or "").lower() == "root" and r.get("port_name")}
        derived = derive_uplink_ports(
            stp_root_ports=root, neighbor_types=ntypes, descriptions=descs,
            manual=manual_list, lag_members=_parse_lag_members(lacp_raw))
        if derived:
            print(f"[上行口] {device_name}: " +
                  "；".join(f"{p}（{why}）" for p, why in sorted(derived.items())))
        return sorted(derived.keys())
    except Exception as e:                      # noqa: BLE001 —— 标识性数据，不影响采集
        print(f"[上行口] 推导失败，退回手工清单：{e}")
        return manual_list


def _build_stp_rows(result) -> list:
    """STP 解析结果 → 落库行（一行 = 设备 × VLAN × 端口）

    只保留参与生成树的端口（forwarding/blocking/loop-inc 等）：Down/Disabled
    端口不携带树信息，全量入库会让行数翻数倍（实测一台 Aruba 43 个端口里 26 个是 Down）。
    """
    rows = []
    for vlan in sorted(result.vlans.values(), key=lambda v: v.vlan):
        for port in vlan.ports:
            if port.state == "down" or port.role == "disabled":
                continue
            rows.append({
                "vlan": vlan.vlan,
                "port_name": port.name,
                "role": port.role,
                "state": port.state,
                "cost": port.cost,
                "port_priority": port.port_priority,
                "is_root": vlan.is_root,
                "root_priority": vlan.root_priority,
                "root_mac": vlan.root_mac,
                "bridge_priority": vlan.bridge_priority,
                "bridge_mac": vlan.bridge_mac,
                "mode": result.mode,
            })
    return rows


def _maintain_member_rows(
    db, device_id: int, device_name: str, serials: list[str], suffixes: list[str],
    model_list: list[str], version_list: list[str], software_version: str,
    collected_at: str,
) -> None:
    """成功采集后维护堆叠的成员行（spec 第五节）。

    - upsert by name（name 物化派生 = {堆叠名}-{后缀}，与序列号同序 1:1）
    - 消失成员：**保留行、不更新 last_synced**（离线由 30 天规则判定，不自动删）
    - 成员行不存 ip；type/platform/location 从位置行继承
    """
    for i, sn in enumerate(serials):
        suffix = suffixes[i]
        member_no = int(suffix) if suffix.isdigit() else i + 1
        name = physical_name(device_name, suffix)
        m_model = model_list[i] if i < len(model_list) else (model_list[-1] if model_list else "")
        m_version = version_list[i] if len(version_list) == len(serials) else software_version
        db.execute(
            """INSERT INTO devices (name, ip, type, platform, kind, stack_name, member_no,
                                    serial_number, model, version, location, last_synced)
               SELECT ?, '', d.type, d.platform, 'member', ?, ?, ?, ?, ?, d.location, ?
               FROM devices d WHERE d.id = ?
               ON CONFLICT(name) DO UPDATE SET
                   serial_number=excluded.serial_number,
                   model=excluded.model,
                   version=excluded.version,
                   location=excluded.location,
                   last_synced=excluded.last_synced""",
            (name, device_name, member_no, sn, m_model,
             m_version if m_version != "未知" else "", collected_at, device_id))


def _save_to_sqlite(
    device_name: str, device_ip: str, device_type: str, device_platform: str,
    week: str, collected_at: str,
    running_config: str, logs_raw: str,
    performance_results: str, validation_results: str, change_results: str,
    software_version: str, serial_number: str, device_model: str,
    system_uptime_seconds: int | None,
    port_details: list, port_errors: list,
    neighbors_data: list, boot_history: str,
    lag_membership_json: str = "{}",
    member_ids: str = "",
    member_versions: str = "",
    member_rom_versions: str = "",
    member_uptimes: str = "",
    stp_data: list | None = None,
    startup_config: str = "",
) -> dict:
    """将采集数据写入 SQLite 数据库

    返回写入统计信息。
    此函数与文件写入并行执行，互不影响。

    startup_config 放在**末尾且带默认值**：它是后加的，这样既有的位置传参
    （含测试）不受影响。
    """
    try:
        db = get_db()
    except RuntimeError:
        print("[SQLite] 数据库未初始化，跳过 SQLite 写入")
        return {"status": "skipped"}

    try:
        # 显式事务包裹：确保 8 步写入原子化，避免孤儿记录
        db.execute("BEGIN IMMEDIATE")

        # 0. 上次硬件指纹（必须在 upsert 覆盖之前读；首次采集 → None → 不产生事件）
        prev_row = db.execute(
            "SELECT platform, model, serial_number, kind, member_ids FROM devices WHERE name=?",
            (device_name,)).fetchone()
        prev_fp = (compute_fingerprint(prev_row["platform"], prev_row["model"],
                                       prev_row["serial_number"], prev_row["kind"],
                                       prev_row["member_ids"])
                   if prev_row else None)

        # 1. 确保 device 记录存在
        db.execute("""
            INSERT INTO devices (name, ip, type, platform, serial_number, member_ids, model, version,
                                 member_versions, member_rom_versions, member_uptimes, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                ip=excluded.ip, type=excluded.type, platform=excluded.platform,
                serial_number=CASE WHEN excluded.serial_number != '' AND excluded.serial_number != '未知'
                                   THEN excluded.serial_number ELSE devices.serial_number END,
                member_ids=CASE WHEN excluded.member_ids != ''
                                THEN excluded.member_ids ELSE devices.member_ids END,
                model=CASE WHEN excluded.model != '' AND excluded.model != '未知'
                           THEN excluded.model ELSE devices.model END,
                version=CASE WHEN excluded.version != '' AND excluded.version != '未知'
                              THEN excluded.version ELSE devices.version END,
                member_versions=CASE WHEN excluded.member_versions != ''
                                     THEN excluded.member_versions ELSE devices.member_versions END,
                member_rom_versions=CASE WHEN excluded.member_rom_versions != ''
                                         THEN excluded.member_rom_versions ELSE devices.member_rom_versions END,
                member_uptimes=CASE WHEN excluded.member_uptimes != ''
                                    THEN excluded.member_uptimes ELSE devices.member_uptimes END,
                last_synced=excluded.last_synced
        """, (
            device_name, device_ip, device_type, device_platform,
            serial_number if serial_number != "未知" else "",
            member_ids,
            device_model if device_model != "未知" else "",
            software_version if software_version != "未知" else "",
            member_versions, member_rom_versions, member_uptimes,
            collected_at,
        ))
        device_row = db.execute("SELECT id FROM devices WHERE name=?", (device_name,)).fetchone()
        device_id = device_row["id"]

        # 1.1 物理设备档案 upsert（序列号主键，自动建档，永不删除）
        # 以**序列号**为基准逐成员展开：member_ids 只有 Aruba VSF 有（Cisco 堆叠为空），
        # 不能拿它当 zip 的基准 —— 否则 Cisco 堆叠成员一条都进不了档案（曾经如此）。
        serials = [s.strip() for s in serial_number.split(",") if s.strip()]
        model_list = [m.strip() for m in device_model.split(",") if m.strip()]
        version_list = [v.strip() for v in member_versions.split(",") if v.strip()]
        # 成员后缀（真实号优先、顺序号兜底）——与仪表盘/报告/拓扑同一实现（device_identity）
        suffixes = member_suffixes(len(serials), member_ids)
        movements: list[dict] = []
        for idx, serial_part in enumerate(serials):
            member_no = suffixes[idx]
            # 调拨检测：该序列号上一轮在别的设备名下（device_members 以 SN 为主键，天然给出上家）
            prev_owner = db.execute(
                "SELECT last_device FROM device_members WHERE serial_number=?",
                (serial_part,)).fetchone()
            if prev_owner and prev_owner["last_device"] and prev_owner["last_device"] != device_name:
                movements.append({"serial": serial_part, "from_device": prev_owner["last_device"]})
            model_part = model_list[idx] if idx < len(model_list) else (model_list[-1] if model_list else "")
            # 成员自己的版本优先；无成员级版本（IOS-XE 堆叠 / Aruba VSF）退回整机版本
            version_part = version_list[idx] if len(version_list) == len(serials) else software_version
            db.execute("""
                INSERT INTO device_members (serial_number, model, version, last_device, last_member, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(serial_number) DO UPDATE SET
                    model=CASE WHEN excluded.model != '' THEN excluded.model ELSE device_members.model END,
                    version=excluded.version,
                    last_device=excluded.last_device,
                    last_member=excluded.last_member,
                    last_seen=excluded.last_seen
            """, (
                serial_part,
                model_part,
                version_part if version_part != "未知" else "",
                device_name,
                member_no,
                collected_at,
            ))

        # 1.2 设备身份维护（spec 第五节）：kind 按配置判定 + 堆叠成员行成行
        # 失败保护：本次 serial 为空/"未知" → 不碰身份（沿用"空/未知不覆盖"原则）
        if serial_number and serial_number != "未知":
            kind = kind_from_config(running_config or "", len(serials))
            db.execute("UPDATE devices SET kind=? WHERE id=?", (kind, device_id))
            # 判据是 kind 而不是成员数：拆到只剩一台的 VSF（配置里 vsf member 还在）
            # 仍是 stack，剩下那台的成员行必须继续更新（场景 3）
            if kind == "stack":
                _maintain_member_rows(db, device_id, device_name, serials, suffixes,
                                      model_list, version_list, software_version, collected_at)

            # 1.3 硬件变更检测（spec 第六节）：指纹 diff + 事件（调拨随事件记录）
            cur_fp = compute_fingerprint(device_platform, device_model, serial_number,
                                         kind, member_ids)
            ev = diff_fingerprints(prev_fp, cur_fp)
            if ev:
                record_event(db, device_id, ev, collected_at, movements=movements)

        # 2. 写入采集会话
        running_lines = len(running_config.splitlines()) if running_config and not running_config.startswith('%') else 0
        db.execute("""
            INSERT INTO collections (device_id, week, phase, collected_at,
                software_version, serial_number, model, system_uptime_seconds,
                running_config, running_config_lines, boot_history_raw, lag_membership,
                startup_config)
            VALUES (?, ?, '1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, week, collected_at,
            software_version, serial_number, device_model,
            system_uptime_seconds,
            running_config, running_lines,
            boot_history,
            lag_membership_json,
            startup_config or None,
        ))
        collection_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 3. 写入端口快照
        if port_details:
            def _safe_str(val) -> str:
                """安全转字符串：None→''，保留数值 0"""
                return str(val) if val is not None else ""

            rows = []
            for p in port_details:
                port_name = p.get("name", "")
                rows.append((
                    collection_id, device_id, port_name,
                    p.get("status", ""), 1 if p.get("status_up") else 0,
                    _safe_str(p.get("speed")), _safe_str(p.get("mode")),
                    _safe_str(p.get("type")), _safe_str(p.get("description")),
                    _safe_str(p.get("native_vlan")),
                    1 if p.get("is_uplink") else 0,
                    float(p.get("rx_mbps") or 0), float(p.get("tx_mbps") or 0),
                    float(p.get("rx_util_pct") or 0), float(p.get("tx_util_pct") or 0),
                    int(p.get("rx_pps") or 0), int(p.get("tx_pps") or 0),
                    int(p.get("rxload") or 0), int(p.get("txload") or 0),
                    # 累计计数器原始读数：**不要过 _safe_str**（它会把 None 变成 ""），
                    # None 必须原样入库为 NULL —— 与「读到 0」区分
                    p.get("in_octets"), p.get("out_octets"),
                    # 端口→成员号（2026-09-22 身份模型）：逻辑口（Po/Hu/lag）为 NULL
                    member_no_from_port(port_name, device_platform),
                ))
            db.executemany("""
                INSERT INTO port_snapshots
                    (collection_id, device_id, port_name, status, status_up,
                     speed, mode, port_type, description, native_vlan, is_uplink,
                     rx_mbps, tx_mbps, rx_util_pct, tx_util_pct, rx_pps, tx_pps, rxload, txload,
                     in_octets, out_octets, member_no)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

        # 4. 写入端口错误
        if port_errors:
            err_rows = []
            for err_type, ports in port_errors.items():
                for pn in ports:
                    err_rows.append((collection_id, device_id, pn, err_type, 1))
            db.executemany(
                "INSERT INTO port_errors (collection_id, device_id, port_name, error_type, count) VALUES (?, ?, ?, ?, ?)",
                err_rows,
            )

        # 5. 写入邻居关系（全量保留，用 is_logical 标记逻辑/物理端口）
        if neighbors_data:
            import re as _re
            neigh_rows = []
            for n in neighbors_data:
                lp = n.get("local_port", "")
                nb_name = n.get("neighbor_name", "")
                # 过滤自环
                if nb_name == device_name:
                    continue
                # 判断是否为逻辑端口（LAG / Port-Channel）
                is_logical = 1 if _re.match(r'^(lag|port-channel|po)\s*\d', lp, _re.IGNORECASE) else 0
                neigh_rows.append((
                    collection_id, device_id,
                    n.get("local_port", ""), n.get("neighbor_name", ""),
                    n.get("neighbor_type", ""), n.get("neighbor_platform", ""),
                    n.get("neighbor_desc", ""), n.get("source", "cdp"),
                    n.get("neighbor_port", ""),
                    is_logical,
                ))
            db.executemany(
                "INSERT INTO neighbors (collection_id, device_id, local_port, neighbor_name, neighbor_type, neighbor_platform, neighbor_desc, source, neighbor_port, is_logical) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                neigh_rows,
            )

        # 5.1 写入生成树快照（仅交换机；一行 = VLAN × 端口）
        if stp_data:
            stp_insert_rows = [(
                collection_id, device_id,
                r.get("vlan"), r.get("port_name", ""),
                r.get("role", ""), r.get("state", ""),
                r.get("cost"), r.get("port_priority"),
                1 if r.get("is_root") else 0,
                r.get("root_priority"), r.get("root_mac", ""),
                r.get("bridge_priority"), r.get("bridge_mac", ""),
                r.get("mode", ""),
            ) for r in stp_data]
            db.executemany("""
                INSERT INTO stp_snapshots
                    (collection_id, device_id, vlan, port_name, role, state,
                     cost, port_priority, is_root, root_priority, root_mac,
                     bridge_priority, bridge_mac, mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, stp_insert_rows)

        # 6. 写入配置变更
        if change_results and change_results != "{}":
            try:
                change = json.loads(change_results)
                has_changes = 1 if change.get("has_changes") else 0
                summary_json = json.dumps(change.get("changes", []), ensure_ascii=False)
                db.execute(
                    "INSERT INTO config_changes (collection_id, device_id, detected_at, has_changes, added_lines, removed_lines, change_summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (collection_id, device_id, collected_at, has_changes,
                     change.get("summary", {}).get("added", 0),
                     change.get("summary", {}).get("removed", 0),
                     summary_json),
                )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                print(f"[SQLite] 配置变更解析失败: {e}")

        # 7. 写入验证结果
        if validation_results and validation_results != "{}":
            try:
                val = json.loads(validation_results)
                vs = val.get("summary", {})
                db.execute(
                    "INSERT INTO validation_results (collection_id, device_id, errors_count, warnings_count, info_count, details) VALUES (?, ?, ?, ?, ?, ?)",
                    (collection_id, device_id, vs.get("errors", 0), vs.get("warnings", 0), vs.get("info", 0),
                     json.dumps(val, ensure_ascii=False)),
                )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                print(f"[SQLite] 验证结果解析失败: {e}")

        # 8. 写入设备日志（含时间过滤去重）
        if logs_raw and not logs_raw.startswith('% 收集失败'):
            log_entries = parse_syslog_lines(logs_raw, device_type, collection_dt=collected_at)

            # 查询上次收集时间，用于过滤重复日志
            last_row = db.execute(
                "SELECT collected_at FROM collections "
                "WHERE device_id = ? AND id < ? AND phase = '1' "
                "ORDER BY id DESC LIMIT 1",
                (device_id, collection_id)
            ).fetchone()

            cutoff = ""
            if last_row:
                # 只保留上次收集时间之后的日志
                cutoff = last_row["collected_at"][:19]  # 截断到秒
            else:
                # 首次收集：保留最近 7 天
                from datetime import datetime as dt, timedelta
                try:
                    collected = dt.fromisoformat(collected_at)
                    cutoff = (collected - timedelta(days=7)).isoformat()[:19]
                except (ValueError, TypeError):
                    cutoff = ""

            # 过滤：保留 normalized_ts > cutoff 的条目
            filtered_entries = []
            for e in log_entries:
                norm_ts = e.get("normalized_ts", "")
                if not norm_ts:
                    # Cisco 无时间戳日志无法判断时间，全部保留
                    filtered_entries.append(e)
                elif not cutoff or norm_ts >= cutoff:
                    filtered_entries.append(e)

            if filtered_entries:
                log_rows = [
                    (collection_id, device_id, e["timestamp"], e["severity"], e["facility"], e["message"])
                    for e in filtered_entries
                ]
                print(f"[SQLite] 日志过滤: {len(log_entries)}→{len(filtered_entries)} (cutoff={cutoff})")
                db.executemany(
                    "INSERT INTO device_logs (collection_id, device_id, log_timestamp, severity, facility, message) VALUES (?, ?, ?, ?, ?, ?)",
                    log_rows,
                )

        db.commit()
        stats = {
            "status": "ok",
            "collection_id": collection_id,
            "port_snapshots": len(port_details),
            "port_errors": sum(len(v) for v in (port_errors or {}).values()),
            "neighbors": len(neighbors_data),
            "stp_snapshots": len(stp_data or []),
            "logs": len(logs_raw.splitlines()) if logs_raw else 0,
        }
        print(f"[SQLite] 数据已写入: {stats}")
        return stats

    except Exception as e:
        print(f"[SQLite] 写入失败: {e}")
        traceback.print_exc()
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


def _save_data(
    device_name: str, device_ip: str, device_type: str,
    week: str, data_dir: str, settings: Dict,
    running_config: str,
    startup_config: str,
    logs_raw: str, interface_status: str, version_info: str,
    interface_utilization: str, system_info: str, vsf_info: str, switch_info: str, route_info: str,
    validation_results: str, performance_results: str, change_results: str,
    software_version: str, serial_number: str, device_model: str = "",
    cdp_neighbors_raw: str = "", lldp_neighbors_raw: str = "",
    boot_history: str = "", system_uptime_seconds: int | None = None,
    platform: str = "",
    lacp_raw: str = "",
    stp_rows: list | None = None,
    svl_uptime_raw: str = "",
) -> None:
    """保存数据到本地"""

    device_base_dir = os.path.join(data_dir, device_name)
    week_dir = os.path.join(device_base_dir, week)
    os.makedirs(week_dir, exist_ok=True)
    print(f"[保存] 设备={device_name}, 周={week}, 目录={week_dir}")

    # 保存原始配置
    with open(os.path.join(week_dir, "running-config.raw"), "w", encoding="utf-8") as f:
        f.write(running_config)

    # startup-config：**只保留最新一份**（写在设备目录下，每次覆盖），不做周历史。
    # 理由：startup 变化极少（只在有人 save 时），按周存 52 份里 51 份是重复副本；
    # 而配置文本按周存一年是 62 MB。它的用途只有「与 running 比对」和应急取用。
    if startup_config and not startup_config.lstrip().startswith("%"):
        try:
            with open(os.path.join(device_base_dir, "startup-config.raw"), "w",
                      encoding="utf-8") as f:
                f.write(startup_config)
        except OSError as e:
            print(f"[保存警告] startup-config.raw 写入失败（不影响其余数据）: {e}")

    # 仅保留 running-config.raw 文件写入（双轨策略）
    # 其他所有数据仅写入 SQLite

    # 生成 neighbors.json (CDP/LLDP + ConfigParser 端口描述补充)
    _neighbors_in_memory = []  # 供后续 SQLite 写入使用，避免磁盘回读

    # 先解析 LAG 成员关系（需要在下游邻居补充时使用）
    lag_map: dict = _parse_lag_members(lacp_raw)
    lag_membership_json = json.dumps(lag_map, ensure_ascii=False) if lag_map else "{}"
    if lag_map:
        print(f"[LAG] 成员关系: {lag_map}")

    try:
        from analyzers.neighbor_parser import parse_cdp, parse_lldp, merge_neighbors, NeighborEntry
        cdp_entries = parse_cdp(cdp_neighbors_raw, device_type) if cdp_neighbors_raw else []
        lldp_entries = parse_lldp(lldp_neighbors_raw, device_type) if lldp_neighbors_raw else []
        merged = merge_neighbors(cdp_entries, lldp_entries)

        # 端口名归一化（Cisco 长名→短名、LAG 名统一）见 utils/port_names.py ——
        # 采集与配置审计必须共用同一套规则，否则审计看到的上行口与入库的邻居/生成树角色会对不上。
        # 规范化 CDP/LLDP 已有条目的端口名（CDP 输出通常已是短名，LLDP 格式多样）
        for e in merged:
            e.local_port = normalize_port_name(e.local_port)

        # 从 running-config 提取 admin down (shutdown) 端口，过滤不可靠的邻居数据
        shutdown_ports: set = set()
        if running_config and not running_config.startswith('%'):
            shutdown_ports = _extract_shutdown_ports(running_config, normalize_port_name)
            if shutdown_ports:
                merged = [e for e in merged if normalize_port_name(e.local_port) not in shutdown_ports]
                print(f"[邻居] 过滤 admin down 端口: {shutdown_ports}")

        # ---- LAG 逻辑端口补充: 从物理成员投票继承邻居信息 ----
        # 不依赖 running-config（config 失败时 LAG 链路仍要保留，
        # 否则物理成员端口会被拓扑隐藏、LAG 链路整体消失）
        if lag_map:
            try:
                seen_ports = set(
                    (normalize_port_name(e.local_port), e.neighbor_name)
                    for e in merged
                )
                extra_count = 0
                for log_port, phys_ports in lag_map.items():
                    if not phys_ports:
                        continue
                    log_port_norm = norm_lag_name(log_port)  # lag14 → lag 14
                    # 统计每个邻居在物理成员端口中出现的次数
                    neighbor_votes: dict[str, int] = {}
                    for pp in phys_ports:
                        norm_pp = normalize_port_name(pp)
                        for e in merged:
                            if normalize_port_name(e.local_port) == norm_pp:
                                nb = e.neighbor_name
                                neighbor_votes[nb] = neighbor_votes.get(nb, 0) + 1
                    if neighbor_votes:
                        # 多数投票确定邻居名；平局时所有最高票邻居都保留
                        # （成员端口连不同邻居时强行取一个，会让另一条链路从拓扑消失）
                        max_votes = max(neighbor_votes.values())
                        for main_nb, votes in neighbor_votes.items():
                            if votes < max_votes:
                                continue
                            log_key = (log_port_norm, main_nb)
                            if log_key not in seen_ports:
                                seen_ports.add(log_key)
                                # 从 merged 中找该邻居的类型信息
                                nb_type = ""
                                nb_plat = ""
                                for e in merged:
                                    if e.neighbor_name == main_nb:
                                        nb_type = e.neighbor_type
                                        nb_plat = e.neighbor_platform
                                        break
                                merged.append(NeighborEntry(
                                    local_port=log_port_norm,
                                    neighbor_name=main_nb,
                                    neighbor_type=nb_type,
                                    neighbor_platform=nb_plat,
                                    neighbor_desc='',
                                ))
                                extra_count += 1
                if extra_count:
                    print(f"[邻居] LAG 逻辑端口补充: {extra_count} 条")
            except Exception as e:
                print(f"[邻居] LAG 补充失败: {e}")

        # 补充: 从 running-config 端口描述中收集 CDP/LLDP 无法发现的设备
        if running_config and not running_config.startswith('%'):
            try:
                from analyzers.config_parser import ConfigParser
                cp = ConfigParser(device_type=device_type)
                config_entries = cp.parse(running_config)
                seen_ports = set(
                    (normalize_port_name(e.local_port), e.neighbor_name)
                    for e in merged
                )
                extra_count = 0
                for entry in config_entries:
                    if not entry.device_name:
                        continue
                    if entry.is_endpoint or not entry.device_type:
                        continue
                    # CDP/LLDP 优先；端口描述中同端口+同邻居名则跳过去重
                    key = (normalize_port_name(entry.name), entry.device_name)
                    if key not in seen_ports:
                        seen_ports.add(key)
                        merged.append(NeighborEntry(
                            local_port=normalize_port_name(entry.name),
                            neighbor_name=entry.device_name,
                            neighbor_type=entry.device_type,
                            neighbor_platform='',
                            neighbor_desc=entry.description[:80] if entry.description else '',
                        ))
                        extra_count += 1
                if extra_count:
                    print(f"[邻居] ConfigParser 补充: {extra_count} 条")
            except Exception as e:
                print(f"[邻居] ConfigParser 补充失败: {e}")

        neighbors_data = {
            "device": device_name,
            "week": week,
            "collected_at": __import__('datetime').datetime.now().isoformat(),
            "neighbors": [
                {
                    "local_port": e.local_port,
                    "neighbor_name": e.neighbor_name,
                    "neighbor_type": e.neighbor_type,
                    "neighbor_platform": e.neighbor_platform,
                    "neighbor_desc": e.neighbor_desc,
                    "neighbor_port": e.neighbor_port,
                }
                for e in merged
            ]
        }
        _neighbors_in_memory = neighbors_data["neighbors"]  # 保存引用供 SQLite 写入
        print(f"[保存] 邻居解析完成: {len(merged)} 条邻居记录（仅写 SQLite）")
    except Exception as e:
        print(f"[警告] 邻居解析失败: {e}")

    # 分析结果仅写入 SQLite（不再写 JSON 文件 + summary.txt）
    # 设备信息更新不再写 devices.yaml（由 SQLite UPSERT 完成）
    # 旧版本清理不再需要（仅 running-config.raw 一个文件）

    # 双轨写入: 写入 SQLite 数据库
    try:
        # 从 performance_results JSON 中提取端口详情和错误数据
        port_details = []
        port_errors_dict = {}
        if performance_results and performance_results != "{}":
            try:
                perf_json = json.loads(performance_results)
                iface_summary = perf_json.get("interface_summary", {})
                port_details = iface_summary.get("details", [])
                errors = perf_json.get("errors", {})
                port_errors_dict = errors.get("ports", {})
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                pass

        # 使用内存中已处理的邻居数据（避免磁盘回读）
        neighbors_list = _neighbors_in_memory

        sqlite_result = _save_to_sqlite(
            device_name=device_name,
            device_ip=device_ip,
            device_type=device_type,
            device_platform=platform,
            week=week,
            collected_at=datetime.now().isoformat(),
            running_config=running_config,
            startup_config=startup_config,
            logs_raw=logs_raw,
            performance_results=performance_results,
            validation_results=validation_results,
            change_results=change_results,
            software_version=software_version,
            serial_number=serial_number,
            device_model=device_model,
            # 堆叠成员号（Aruba VSF 的 Member ID / Cisco 成员表的 Switch 号；与序列号同源同序 1:1）
            member_ids=extract_member_ids(vsf_info, version_info),
            member_versions=extract_member_versions(version_info),
            # ROM 版本：Aruba 逐成员（show vsf detail）；Cisco 整机 BOOTLDR（show version）
            # 按成员数复制，保持「与序列号同序对齐」
            member_rom_versions=extract_member_rom_versions(
                vsf_info, version_info, _member_count(serial_number)
            ),
            member_uptimes=extract_member_uptimes(version_info, vsf_info, svl_uptime_raw),
            system_uptime_seconds=system_uptime_seconds,
            port_details=port_details,
            port_errors=port_errors_dict,
            neighbors_data=neighbors_list,
            boot_history=boot_history,
            lag_membership_json=lag_membership_json,
            stp_data=stp_rows,
        )
        # 写入完成后自动运行异常检测
        if isinstance(sqlite_result, dict) and sqlite_result.get("collection_id"):
            try:
                dev_id = _get_device_id(device_name)
                if dev_id is None:
                    print(f"[异常检测] 跳过 {device_name}: 未找到设备 ID")
                else:
                    from analyzers.anomaly_detector import AnomalyDetector
                    detector = AnomalyDetector(get_db())
                    alert_count = detector.detect_and_save(
                        device_id=dev_id,
                        collection_id=sqlite_result["collection_id"],
                        week=week,
                    )
                    if alert_count:
                        print(f"[异常检测] {device_name}: {alert_count} 条告警")
            except Exception as e:
                print(f"[异常检测] 失败: {e}")

    except Exception as e:
        print(f"[SQLite] 双轨写入失败（不影响文件存储）: {e}")


def _get_device_id(device_name: str) -> int | None:
    """从 SQLite 中查询设备 ID"""
    try:
        db = get_db()
        row = db.execute("SELECT id FROM devices WHERE name=?", (device_name,)).fetchone()
        return row["id"] if row else None
    except Exception:
        return None


# ================================================================
