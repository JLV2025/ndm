# Aruba AP 识别设计（2026-08-04）

## 背景与目标

Aruba AP 命名规则：三位 site code + location + AP 编号 + 四位 MAC 地址，如 `SZX.F11AP2.7C5F`（SZX 站点，F11 楼，AP 编号 2，MAC 后四位 7C5F）。

当前系统中该格式 AP **完全消失**：CDP/LLDP 邻居解析捕获不到 → 端口描述识别不了 → 拓扑图中看不到任何 AP。

**目标**：让 CDP/LLDP 发现的 AP 进入邻居数据，拓扑图中聚合显示「无线AP ×N」，并提取 AP 型号（如 515）显示。端口描述路径（config_parser）不动——AP 响应 LLDP，名字正则无需覆盖所有变体（用户决策：CDP/LLDP 能拿到设备类型，正则只需宽松捕获，CDP/LLDP 不响应的设备才依赖端口描述，AP 不属于此类）。

**展示形式**：端点聚合（用户确认），与现有 Phone/Printer 一致；顺带扩展型号提取（用户确认）。

## 当前识别逻辑与 AP 消失原因

### 主路径：CDP/LLDP 邻居发现（`neighbor_parser.py`）

5 种解析器（Cisco CDP/LLDP、Aruba CDP/LLDP/LLDP-detail），每个邻居条目依次过三道门槛：

1. **捕获设备名** — `DEVICE_NAME_SEARCH_RE`：只认 10 位标准名 `\w{3}\w{2}(SWI|RTW|FWL|WLC|SDW|QIS)\d{2}` 和 GTS 服务器 → 匹配不到**整条丢弃**
2. **端点过滤** — `_is_endpoint()`：SEP/Phone/Laptop/Printer/TL-/-AP/AP 开头/已知 MAC 后缀 → 端点不进邻居列表
3. **类型提取** — `_extract_type()` 取名字第 6-8 位查 TYPE_MAP；`_extract_platform()` 只认 Cisco 型号

### 补充路径：端口描述解析（`config_parser.py` + `collector_service.py:1152`）

专给 CDP/LLDP 不响应的设备。规则优先级：关键词端点 → GTS 服务器 → 标准设备名 → 通用名-用途后缀。`collector_service.py:1166` 明确跳过 `is_endpoint` 条目。

### AP 消失的确切原因

| 路径 | 卡在哪 |
|---|---|
| CDP/LLDP 主路径 | 捕获正则（门槛 1）不认 AP 名 → 整条邻居直接丢弃 |
| 端口描述补充路径 | `\bAP\b`/`\bAP-` 匹配不到 `.F11AP2.`（AP 前后是字母数字，非独立词）；即便识别为端点，1166 行也跳过 |
| 前端聚合 | `ENDPOINT_PREFIXES` 前缀 `'AP'` 匹配不到（名以 SZX 开头） |

## 设计方案

核心思路：**主路径（CDP/LLDP）宽松捕获 AP 名 + 端点标记**，与用户「CDP/LLDP 能拿到设备类型，名字正则无需覆盖所有可能」的判断一致。

### 改动点①：`backend/analyzers/neighbor_parser.py`（核心）

新增宽松 AP 名正则（只认格式，不解析字段）：

```python
# AP 名: 3位site + 点 + location + AP + 编号 + 点 + 4位MAC
# 例: SZX.F11AP2.7C5F
AP_NAME_RE = re.compile(r'\b(\w{3}\.[\w-]+AP\d+\.[0-9A-Fa-f]{4})\b')
```

四类小改：

1. `DEVICE_NAME_SEARCH_RE` 加入 AP 模式 → 5 个解析器（Cisco CDP/LLDP、Aruba CDP/LLDP/LLDP-detail）都能从输出行搜到 AP 名；`_strip_domain` 复用逻辑同步受益
2. `_is_valid_network_device()` 放行 AP 名（Aruba LLDP 与 LLDP-detail 的校验门槛）
3. 新增 `_is_ap()`；5 个解析器的端点过滤分支改为：

```python
device_name = dm.group(1)
if _is_ap(device_name):
    neighbor_type = "AP"          # AP 保留为端点条目
elif _is_endpoint(device_name):
    continue                       # 其他端点照旧跳过（语义不变）
else:
    neighbor_type = _extract_type(device_name)
```

4. `_extract_platform()` 扩展 Aruba 型号（当前只认 `WS-C\d+`/`AIR-`/`C\d{4}`/cisco 格式）：

```python
# 追加: Aruba 型号（LLDP System-Description / CDP Platform 列）
# 例: "Aruba 515 (RW5) ..." → "Aruba 515"；"AP-515" → "AP-515"
```

### 改动点②：`backend/api/topology.py`（1 行）

`get_device_topology`（端口连接图数据组装）中 CDP/LLDP 条目：

```python
"is_endpoint": False,            # 改前
"is_endpoint": nb.get("neighbor_type", "") == "AP",   # 改后
```

AP 条目自动进入 `endpoints` 列表 → 前端聚合路径。

### 数据流变化

```
CDP/LLDP 输出 ──► AP_NAME_RE 捕获（不再丢弃）
              ──► neighbor_type="AP" 入库（neighbors 表现成字段，无迁移）
              ──► topology API is_endpoint=True
              ──► 前端 getEndpointLabel：ENDPOINT_TYPE_MAP['AP']='无线AP'（constants.ts:118 已有）
              ──► 聚合节点「无线AP ×N」，型号显示（_extract_platform 扩展后）
```

### 前端零改动

`ENDPOINT_TYPE_MAP` 已有 `'AP': '无线AP'`，聚合逻辑走 `device_type` 映射路径（`PortTopologyCanvas.tsx:400`），无需加前缀规则。

## 不改动的部分

- **`config_parser.py`**：端口描述路径不动（AP 响应 LLDP）
- **`role_verifier.py`**：只核查交换机，AP 不在设备清单
- **数据库**：neighbors 表 neighbor_type 现成字段，无迁移
- **前端**：零改动

## 风险与边界

- `_is_endpoint` 语义**不变**：现有一切端点（Phone/Printer/`-AP`/AP 开头/MAC 后缀）行为保持，仅新增 `_is_ap` 分支放行 AP 名（GitNexus 影响面 HIGH：4 个解析器直接调用，影响邻居收集全流程，需回归验证）
- 端口 DOWN 告警：AP 端口掉线会正常告警（合理行为，AP 掉线值得告警）
- 宽松正则边界：`\w{3}\.` 前缀 + AP 标识锚定，不会误匹配标准设备名（`.` 打断 10 位连续模式）；AP 名带域名后缀（如 .local）时 `\b` 边界保证只捕获 AP 名部分

## 验证方案

1. 跑现有 pytest（`backend/tests/`，确认不破坏现有解析行为）
2. 手工构造 LLDP/LLDP-detail 样例（含 `SZX.F11AP2.7C5F`），验证 5 个解析器均能捕获 AP 条目且其他端点行为不变
3. 验证 `_extract_platform` 对 Aruba 型号（"Aruba 515" / "AP-515"）的提取
