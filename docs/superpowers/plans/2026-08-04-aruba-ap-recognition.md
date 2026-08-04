# Aruba AP 识别实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `SZX.F11AP2.7C5F` 格式的 Aruba AP 通过 CDP/LLDP 主路径进入邻居数据，拓扑图聚合显示「无线AP ×N」并提取型号。

**Architecture:** 在 `neighbor_parser.py` 增加宽松 AP 名正则（只认格式不解析字段），5 个解析器的端点过滤分支改为「AP → 保留为端点条目（neighbor_type="AP"），其他端点照旧跳过」；`_extract_platform` 扩展 Aruba 型号；`topology.py` 将 neighbor_type="AP" 标记为 is_endpoint 走前端聚合路径。前端零改动（`ENDPOINT_TYPE_MAP` 已有 'AP': '无线AP'）。

**Tech Stack:** Python 3 (re, pytest)

## Global Constraints

- 注释与提交信息必须简体中文
- 每个逻辑变更单独提交
- `_is_endpoint` 语义不变：现有一切端点（Phone/Printer/`-AP`/AP 开头/MAC 后缀）行为保持，仅新增 `_is_ap` 分支放行 AP 名
- 端口描述路径（`config_parser.py`）、`role_verifier.py`、数据库、前端**均不改动**
- pytest 须在 `backend/` 目录下运行（模块 import 为 `from analyzers.xxx` 形式）
- 回归跑全量 pytest 后，若产生 `backend/tests/config/test_devices.yaml` 测试副作用，提交前需丢弃：`git checkout -- backend/tests/config/test_devices.yaml`
- 提交前跑 `gitnexus_detect_changes()` 验证改动范围仅限预期符号

---

### Task 1: AP 名识别核心（正则 + 辅助函数）

**Files:**
- Create: `backend/tests/test_neighbor_parser.py`
- Modify: `backend/analyzers/neighbor_parser.py:8-23`（正则区）与 `:79-81`（`_is_valid_network_device`）

**Interfaces:**
- Consumes: 无（独立新功能）
- Produces:
  - `AP_NAME_PATTERN`（str）：`\w{3}\.[\w-]+AP\d+\.[0-9A-Fa-f]{4}`，供 `AP_NAME_RE` 与 `DEVICE_NAME_SEARCH_RE` 复用，避免两处维护
  - `AP_NAME_RE`（re.Pattern）：`re.compile(rf'\b({AP_NAME_PATTERN})\b')`，捕获组 1 = 完整 AP 名
  - `_is_ap(name: str) -> bool`：AP_NAME_RE.fullmatch 判断
  - `_is_valid_network_device(name: str) -> bool`：原有判断 + AP_NAME_RE.fullmatch
  - `DEVICE_NAME_SEARCH_RE`：加入 `AP_NAME_PATTERN` 分支

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_neighbor_parser.py`：

```python
"""CDP/LLDP 邻居解析器测试 — 重点：Aruba AP 名识别"""
import pytest

from analyzers.neighbor_parser import (
    AP_NAME_RE,
    DEVICE_NAME_SEARCH_RE,
    _is_ap,
    _is_valid_network_device,
)


# ---- AP_NAME_RE ----

def test_ap_name_re_matches_standard():
    """标准 AP 名: 3位site + 点 + location + AP + 编号 + 点 + 4位MAC"""
    assert AP_NAME_RE.fullmatch("SZX.F11AP2.7C5F")


def test_ap_name_re_site_with_digit():
    """site code 含数字（KR3）也能匹配"""
    assert AP_NAME_RE.fullmatch("KR3.F11AP2.7C5F")


def test_ap_name_re_lowercase_mac():
    """MAC 小写也能匹配"""
    assert AP_NAME_RE.fullmatch("SZX.F11AP2.7c5f")


def test_ap_name_re_rejects_standard_device():
    """标准交换机名不是 AP 名"""
    assert not AP_NAME_RE.fullmatch("PVGD1SWI02")


def test_ap_name_re_rejects_old_ap_prefix():
    """旧式 AP 前缀名（AP-xxx）不属于新 AP 名格式"""
    assert not AP_NAME_RE.fullmatch("AP-515-LAB")


# ---- _is_ap ----

def test_is_ap():
    assert _is_ap("SZX.F11AP2.7C5F")
    assert not _is_ap("PVGD1SWI02")
    assert not _is_ap("AP-515-LAB")
    assert not _is_ap("")


# ---- _is_valid_network_device（放行 AP 名） ----

def test_is_valid_network_device_accepts_ap():
    assert _is_valid_network_device("SZX.F11AP2.7C5F")


def test_is_valid_network_device_still_accepts_standard():
    assert _is_valid_network_device("PVGD1SWI02")
    assert _is_valid_network_device("GTSPEKESX01")


# ---- DEVICE_NAME_SEARCH_RE（输出行中能搜到 AP 名） ----

def test_search_re_finds_ap_in_lldp_line():
    """LLDP 行中能捕获 AP 名（带域名后缀时只捕获 AP 名本身）"""
    m = DEVICE_NAME_SEARCH_RE.search("SZX.F11AP2.7C5F Gi1/0/14 120 AP Aruba 515")
    assert m and m.group(1) == "SZX.F11AP2.7C5F"


def test_search_re_ap_with_domain_suffix():
    m = DEVICE_NAME_SEARCH_RE.search("SZX.F11AP2.7C5F.corp.com  Gi1/0/14")
    assert m and m.group(1) == "SZX.F11AP2.7C5F"


def test_search_re_does_not_mangle_standard_line():
    """标准设备名行行为不变"""
    m = DEVICE_NAME_SEARCH_RE.search("BJQD1RTW01.corp.com  Gi0/0/1")
    assert m and m.group(1) == "BJQD1RTW01"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/test_neighbor_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'AP_NAME_RE'`（等尚未定义）

- [ ] **Step 3: 最小实现**

在 `neighbor_parser.py` 正则区（`DEVICE_NAME_SEARCH_RE` 之后、`IFACE_SHORT_RE` 之前）新增：

```python
# Aruba AP 名: 3位site + 点 + location + AP + 编号 + 点 + 4位MAC
# 例: SZX.F11AP2.7C5F → {site: SZX, location: F11, num: 2, mac: 7C5F}
# 宽松模式只认格式不解析字段；site 含数字（KR3）也匹配
AP_NAME_PATTERN = r'\w{3}\.[\w-]+AP\d+\.[0-9A-Fa-f]{4}'
AP_NAME_RE = re.compile(rf'\b({AP_NAME_PATTERN})\b')
```

`DEVICE_NAME_SEARCH_RE` 增加 AP 分支（在标准网络设备分支后）：

```python
DEVICE_NAME_SEARCH_RE = re.compile(
    r'\b('
    r'GTS\w{3}(?:ESX|SRV)\d*'          # GTS 服务器
    r'|'
    r'\w{3}\w{2}(?:SWI|RTW|FWL|WLC|SDW|QIS)\d{2}'  # 标准网络设备
    r'|'
    r'\w{3}\.[\w-]+AP\d+\.[0-9A-Fa-f]{4}'  # Aruba AP (SZX.F11AP2.7C5F)，与 AP_NAME_PATTERN 同步
    r')\b'
)
```

> **注意**：SEARCH_RE 内直接嵌入 AP 名字面量，不用 `{AP_NAME_PATTERN}` 变量拼接——整体被包在单个捕获组 1 内，`dm.group(1)` 语义不变。若未来修改 AP 名模式，需同时更新 `AP_NAME_PATTERN` 与此处字面量（两处同步，可加注释互相指引）。

`_is_valid_network_device` 改为：

```python
def _is_valid_network_device(name: str) -> bool:
    """判断是否为有效网络设备名（含 Aruba AP 名）"""
    return bool(DEVICE_NAME_RE.fullmatch(name)) or bool(GTS_SERVER_NAME_RE.fullmatch(name)) or bool(AP_NAME_RE.fullmatch(name))
```

新增 `_is_ap`（放在 `_is_endpoint` 定义之前）：

```python
def _is_ap(name: str) -> bool:
    """判断是否为 Aruba AP 名（宽松模式，只认格式不解析字段）
    例: SZX.F11AP2.7C5F → {site: SZX, location: F11, num: 2, mac: 7C5F}"""
    return bool(AP_NAME_RE.fullmatch(name or ""))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/test_neighbor_parser.py -v`
Expected: PASS（10 passed）

- [ ] **Step 5: 提交**

```bash
cd F:/projects/ndm && git add backend/tests/test_neighbor_parser.py backend/analyzers/neighbor_parser.py && git commit -m "功能：AP 名识别核心——宽松 AP 名正则 + _is_ap + 校验放行"
```

---

### Task 2: 5 个解析器 AP 保留分支

**Files:**
- Modify: `backend/analyzers/neighbor_parser.py:205-211`（parse_cdp_cisco）、`:272-278`（parse_lldp_cisco）、`:349-355`（parse_cdp_aruba）、`:428-432`（parse_lldp_aruba）、`:527-533`（parse_lldp_aruba_detail）
- Test: `backend/tests/test_neighbor_parser.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `_is_ap()`、`_is_valid_network_device()`（含 AP）、`DEVICE_NAME_SEARCH_RE`（含 AP）
- Produces: 各解析器对 AP 名输出 `NeighborEntry(neighbor_name=AP名, neighbor_type="AP", ...)`；其他端点行为不变（仍跳过）

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_neighbor_parser.py`：

```python
from analyzers.neighbor_parser import parse_cdp_cisco, parse_lldp_cisco, parse_cdp_aruba, parse_lldp_aruba, parse_lldp_aruba_detail


# ---- Aruba LLDP 表格格式 ----

def test_lldp_aruba_keeps_ap_and_skips_phone():
    """AP 保留为端点条目；Phone 端点照旧跳过"""
    text = """LOCAL-PORT  CHASSIS-ID         PORT-ID  PORT-DESC  TTL  SYS-NAME
1/1/14      8c:44:a5:2c:2c:10  1/1/14   AP          120  SZX.F11AP2.7C5F
1/1/15      8c:44:a5:2c:2c:11  1/1/15   IPPHONE     120  Phone-101"""
    entries = parse_lldp_aruba(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


# ---- Aruba LLDP detail 格式 ----

def test_lldp_aruba_detail_keeps_ap():
    text = """LLDP Neighbor Information

Port                           : 1/1/14
Neighbor System-Name           : SZX.F11AP2.7C5F
Neighbor System-Description    : Aruba 515 (RW5) ArubaOS 10.x
Neighbor Port-ID               : 1/1/14
Neighbor Port-Desc             : AP
"""
    entries = parse_lldp_aruba_detail(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


# ---- Aruba CDP ----

def test_cdp_aruba_keeps_ap():
    text = """Port        Device ID                Platform                 Capability
1/1/6       BJQD1RTW01.corp.com      cisco C8300-1N1S-4T2X    IRS
1/1/14      SZX.F11AP2.7C5F          Aruba 515                AP
"""
    entries = parse_cdp_aruba(text)
    assert len(entries) == 2
    ap = [e for e in entries if e.neighbor_name == "SZX.F11AP2.7C5F"][0]
    assert ap.neighbor_type == "AP"


# ---- Cisco CDP / LLDP ----

def test_cdp_cisco_keeps_ap():
    text = """Device ID              Local Intrfce  Holdtme  Capability  Platform  Port ID
SZX.F11AP2.7C5F        Gi1/0/14       135      AP          Aruba 515  Gi1/0/14
"""
    entries = parse_cdp_cisco(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


def test_lldp_cisco_keeps_ap():
    text = """Device ID           Local Intf  Hold-time  Capability  Port ID
SZX.F11AP2.7C5F     Gi1/0/14    120        AP          Gi1/0/14
"""
    entries = parse_lldp_cisco(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "SZX.F11AP2.7C5F"
    assert entries[0].neighbor_type == "AP"


def test_cdp_cisco_standard_device_unchanged():
    """标准交换机行为不变"""
    text = """Device ID              Local Intrfce  Holdtme  Capability  Platform  Port ID
BJQD1SWI02             Gi1/0/1        135      S          WS-C2960X  Gi1/0/1
"""
    entries = parse_cdp_cisco(text)
    assert len(entries) == 1
    assert entries[0].neighbor_name == "BJQD1SWI02"
    assert entries[0].neighbor_type == "switch"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/test_neighbor_parser.py -v`
Expected: 新增 6 个用例 FAIL（AP 条目被跳过 → `assert len(entries) == 1` 失败）；Task 1 的 10 个用例仍 PASS

- [ ] **Step 3: 实现**

5 个解析器的过滤分支统一改为「AP → 保留为端点条目，其他端点 → 跳过」：

`parse_cdp_cisco`（原 `neighbor_parser.py:209-211`）：

```python
        device_name = dm.group(1)
        if _is_ap(device_name):
            device_type = "AP"
        elif _is_endpoint(device_name):
            continue
        else:
            device_type = _extract_type(device_name)
```

并把 `neighbor_type=_extract_type(device_name)` 改为 `neighbor_type=device_type`。

`parse_lldp_cisco`（原 `:276-278`）：同样替换，并改 `neighbor_type=_extract_type(device_name)` 为 `neighbor_type=device_type`。

`parse_cdp_aruba`（原 `:353-355`）：同样替换，并改 `neighbor_type=_extract_type(device_name)` 为 `neighbor_type=device_type`。

`parse_lldp_aruba`（原 `:428-432`）：

```python
        device_name = _strip_domain(sys_name_raw)
        if not _is_valid_network_device(device_name):
            continue
        if _is_ap(device_name):
            device_type = "AP"
        elif _is_endpoint(device_name):
            continue
        else:
            device_type = _extract_type(device_name)
```

并改 `neighbor_type=_extract_type(device_name)` 为 `neighbor_type=device_type`。

`parse_lldp_aruba_detail`（原 `:527-533`）：同样替换（`neighbor_name = _strip_domain(neighbor_name)` 后的两行校验保持不变），并改 `neighbor_type=_extract_type(neighbor_name)` 为 `neighbor_type=device_type`。

> **注意**：5 处都保留原有「先校验 → 再分支」的顺序。Cisco 两个解析器与 Aruba CDP 用 `DEVICE_NAME_SEARCH_RE` 已能搜到 AP 名，直接进入分支；Aruba 两个 LLDP 解析器依赖 `_is_valid_network_device` 放行（Task 1 已完成）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/test_neighbor_parser.py -v`
Expected: PASS（16 passed）

- [ ] **Step 5: 提交**

```bash
cd F:/projects/ndm && git add backend/analyzers/neighbor_parser.py && git commit -m "功能：5 个 CDP/LLDP 解析器保留 AP 为端点条目（其他端点行为不变）"
```

---

### Task 3: _extract_platform 扩展 Aruba 型号

**Files:**
- Modify: `backend/analyzers/neighbor_parser.py:128-134`（`_extract_platform`）
- Test: `backend/tests/test_neighbor_parser.py`（追加）

**Interfaces:**
- Consumes: 无（独立函数）
- Produces: `_extract_platform(text)` 支持 Aruba 型号：`Aruba 515`、`AP-515` 等；Cisco 原有匹配不变

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_neighbor_parser.py`：

```python
from analyzers.neighbor_parser import _extract_platform


def test_extract_platform_aruba():
    """LLDP System-Description 中的 Aruba 型号"""
    assert _extract_platform("Aruba 515 (RW5) ArubaOS 10.x") == "Aruba 515"
    assert _extract_platform("Aruba 635 (RW6)") == "Aruba 635"


def test_extract_platform_ap_dash():
    """CDP Platform 列中的 AP-xxx 型号"""
    assert _extract_platform("AP-515") == "AP-515"


def test_extract_platform_cisco_unchanged():
    """Cisco 原有匹配不变"""
    assert _extract_platform("WS-C3560G-48TS") == "WS-C3560G-48TS"
    assert _extract_platform("cisco C8300-1N1S-4T2X") == "C8300-1N1S-4T2X"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/test_neighbor_parser.py::test_extract_platform_aruba -v`
Expected: FAIL（`_extract_platform` 返回空串，现有正则不匹配 Aruba 型号）

- [ ] **Step 3: 实现**

`_extract_platform` 增加 Aruba 分支：

```python
def _extract_platform(text: str) -> str:
    """从文本中提取设备平台/型号（Cisco + Aruba）"""
    m = re.search(
        r'(WS-C\d+[^\s]*|AIR-[^\s]+|C\d{4}[^\s]*|c?[iI]sco\s+[A-Z]\d+[^\s]*)'
        r'|(Aruba\s+\S+|AP-\d{3}[A-Za-z0-9-]*)',
        text
    )
    if not m:
        return ""
    return m.group(1) or m.group(2)
```

> **说明**：Cisco 分支保持原捕获组 1；`Aruba\s+\S+` 匹配 LLDP System-Description 中的 "Aruba 515"，`AP-\d{3}[A-Za-z0-9-]*` 匹配 CDP Platform 列中的 "AP-515"。返回 `m.group(1) or m.group(2)` 兼容两种分支，Cisco 原有匹配不变。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/test_neighbor_parser.py -v`
Expected: PASS（19 passed）

- [ ] **Step 5: 提交**

```bash
cd F:/projects/ndm && git add backend/analyzers/neighbor_parser.py && git commit -m "功能：_extract_platform 支持 Aruba AP 型号（Aruba 515 / AP-515）"
```

---

### Task 4: topology.py 端点标记 + 全量回归

**Files:**
- Modify: `backend/api/topology.py:270`（`get_device_topology` 内 CDP/LLDP 条目组装）

**Interfaces:**
- Consumes: SQLite neighbors 表 `neighbor_type="AP"`（Task 2 产出）
- Produces: 端口连接图 API 中 AP 条目 `is_endpoint=True` → 进入 `endpoints` 列表 → 前端 `ENDPOINT_TYPE_MAP['AP']='无线AP'` 聚合显示

- [ ] **Step 1: 修改拓扑组装逻辑**

`backend/api/topology.py:270`：

```python
"is_endpoint": False,
```

改为：

```python
"is_endpoint": nb.get("neighbor_type", "") == "AP",
```

> **说明**：CDP/LLDP 条目中 `neighbor_type="AP"` 的 AP 端点标记为 is_endpoint；其余网络设备（switch/router 等）保持 False 不变。`get_device_topology` 后续逻辑（`topology.py:376-377`）自动把 is_endpoint=True 的条目归入 `endpoints`，前端 `getEndpointLabel`（`PortTopologyCanvas.tsx:400`）经 `ENDPOINT_TYPE_MAP['AP']='无线AP'` 聚合为「无线AP ×N」节点。

- [ ] **Step 2: 全量回归**

Run: `cd F:/projects/ndm/backend && python -m pytest tests/ -v`
Expected: PASS（现有测试全绿；API 无 DB 依赖的单测，本步验证解析器改动未破坏现有收集流程）

若产生测试副作用文件（`backend/tests/config/test_devices.yaml`）：

```bash
git checkout -- backend/tests/config/test_devices.yaml
```

- [ ] **Step 3: 验证改动范围**

Run: GitNexus `detect_changes(scope="unstaged")`
Expected: 仅 `neighbor_parser.py`（AP_NAME_RE/_is_ap/_is_valid_network_device/DEVICE_NAME_SEARCH_RE/_extract_platform/5 个解析器）与 `topology.py`（get_device_topology）符号变化，无意外影响

- [ ] **Step 4: 提交**

```bash
cd F:/projects/ndm && git add backend/api/topology.py && git commit -m "功能：拓扑图将 CDP/LLDP 发现的 AP 标记为端点（无线AP ×N 聚合）"
```

---

## 验收标准（全部完成即功能交付）

1. `python -m pytest tests/` 全绿
2. 构造含 `SZX.F11AP2.7C5F` 的 LLDP/LLDP-detail/CDP 输出，5 个解析器均产出 `NeighborEntry(neighbor_type="AP")`
3. Phone/Printer/`-AP`/AP 开头等既有端点行为不变
4. 端口连接图 API：AP 条目 `is_endpoint=True`，前端聚合「无线AP ×N」
5. `_extract_platform` 能提取 "Aruba 515" / "AP-515"
