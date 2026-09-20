# CFG-Aruba 合规检查项（公司标准简化版）

> **用途**：设备配置合规性审计的**检查项清单**，作为 NDM 配置审计功能中「公司规范层」规则的来源。
> **来源**：`CFG-Aruba.docx`（Qorvo Network Infrastructure Standards v1.0，2026-07-07）。英文原文保真 + 中文导读的**完整转换版**在 OneDrive：`01-DocWiKi/01_network_configuration/CFG-Aruba.md`（含各章中文导读、配置示例、勘误说明）。本文件是面向检查落地的**简化版**。
> **适用平台**：Aruba CX（AOS-CX 10.x）
> **强度约定**：`必查` = 原文 `shall`（强制）；`建议` = 原文 `should`（推荐）；`人工` = 流程类，无法由配置文本自动判定

---

## 一、检查项

### 第 4 章 管理面基线

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH4-1 | 启用了 SSH 用于 CLI 管理 | 必查 | 存在 `ssh server vrf <VRF>`（`default` 或 `mgmt` 至少其一） |
| CH4-2 | 启用了 SNMPv3 用于监控 | 必查 | 存在 `snmpv3 user <NAME>` |
| CH4-3 | 放行 ICMP（排障与连通性验证） | 必查 | 管理 ACL 中存在 `permit icmp`；无全局 ICMP 抑制 |
| CH4-4 | 使用 MGMT_ACL 限制管理访问 | 必查 | 存在 `access-list ip MGMT_ACL` **且已应用**（`apply access-list ip MGMT_ACL control-plane vrf <VRF>`） |
| CH4-5 | 可选管理协议（REST/HTTPS、gNMI、Telemetry）需经批准 | 建议 | 检测到 `https-server`、gNMI、Telemetry 相关配置时列为「需确认是否已批准」 |
| CH4-6 | REST API 以 HTTPS 提供 | 建议 | `https-server vrf <VRF>` 已启用且 REST 为 `access-mode read-only` |

### 第 5 章 AAA

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH5-1 | 管理认证使用集中式 AAA | 必查 | 存在 `aaa authentication login default group <GRP> local`（方法列表含集中式服务器组，且以 `local` 兜底） |
| CH5-2 | 集中式 AAA 提供认证、授权、计费 | 建议 | 认证 `aaa authentication`；授权 `aaa authorization commands`；计费 `aaa accounting all-mgmt` |
| CH5-3 | 至少部署两台 AAA 服务器 | 建议 | `tacacs-server host` / `radius-server host` 计数 ≥ 2 |
| CH5-4 | AAA 服务器尽量分布在不同站点/地域 | 建议 | 服务器主机名/地址前缀分属不同站点代号（如 `pvg0` / `sin0` / `ede0`）→ 需人工确认 |
| CH5-5 | 设备配置为与多台 AAA 服务器通信 | 必查 | `aaa group server <proto> <GRP>` 下 `server` 条目 ≥ 2 |
| CH5-6 | 存在本地 break-glass 账号 | 必查 | 存在 `user <NAME> group administrators`（本地账号） |
| CH5-7 | 本地认证仅在集中式 AAA 不可用时使用 | 必查 | 方法列表中 `group` 在 `local` **之前**（如 `... group qorvo-tacacs local`） |
| CH5-8 | break-glass 使用后立即改密 | 人工 | 流程要求 |
| CH5-9 | 管理角色尽量集中管理 | 人工 | 流程要求 |

### 第 6 章 管理访问 ACL（MGMT_ACL）

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH6-1 | 管理 ACL 名称固定为 `MGMT_ACL` | 必查 | ACL 名精确匹配 `MGMT_ACL` |
| CH6-2 | 来源使用批准的管理网段/主机 | 必查 | 条目引用批准的管理网段与主机定义 |
| CH6-3 | 逐协议放行，且引用批准来源 | 必查 | 每条 `permit` 均带协议与端口（`tcp ... eq 22`、`udp ... eq 161`、`tcp ... eq 443`） |
| CH6-4 | **禁止**整段/整机放行 | 必查 | 不得出现 `permit ip <SUBNET> any`、`permit ip host <HOST> any`（无协议与端口的宽泛条目） |
| CH6-5 | ICMP 允许 `any any` | 必查 | 存在 `permit icmp any any` |
| CH6-6 | 末尾默认拒绝并记录日志 | 必查 | 存在 `deny ip any any log` 作为末条 |
| CH6-7 | MGMT_ACL 实际生效（已应用） | 必查 | `apply access-list ip MGMT_ACL control-plane vrf mgmt` 与/或 `... vrf default` 存在 |
| CH6-8 | 跑路由协议的设备为协议流量预留 permit | 必查 | 若存在 `router ospf/bgp/isis`，MGMT_ACL 中需有对应协议的 permit（否则 `deny any` 会中断邻居） |

### 第 7 章 SSH

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH7-1 | SSH 为交互式 CLI 管理的唯一协议 | 必查 | 无 telnet 相关启用（AOS-CX 默认无 telnet，检测到即异常） |
| CH7-2 | 配置 SSH 空闲超时 | 必查 | 存在 `cli-session` → `timeout <分钟>`（**注意：`ssh server idle-timeout` 不是 AOS-CX 命令**） |
| CH7-3 | 管理认证使用集中式 AAA | 必查 | 同 CH5-1 |
| CH7-4 | 加密算法符合企业安全标准 | 建议 | `cli-session` 建议同时设 `max-per-user`；SSH 算法使用平台默认（已禁 SSHv1） |
| CH7-5 | 可选证书认证（需批准） | 建议 | 检测到证书认证配置时列为「需确认是否已批准」 |

### 第 8 章 SNMPv3

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH8-1 | **不得**配置 SNMPv1/v2c | 必查 | 无 `snmp-server community`；建议存在 `snmp-server snmpv3-only` |
| CH8-2 | 使用 SNMPv3 AuthPriv | 必查 | `snmpv3 user <NAME>` 同时含 `auth` 与 `priv`（缺一不可） |
| CH8-3 | SNMP 访问通过 MGMT_ACL 限制 | 必查 | 关联 CH6 检查项（UDP 161 仅批准来源） |
| CH8-4 | SNMP 代理已在目标 VRF 启用 | 必查 | 存在 `snmp-server vrf <VRF>`（**注意：`snmpv3 enable` 不是 AOS-CX 命令**） |

### 第 9 章 NTP

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH9-1 | 使用企业内部 NTP 服务器 | 必查 | `ntp server <地址>` 全部为内部地址；**不得**出现公网域名（如 `pool.ntp.org`） |
| CH9-2 | 至少配置两台 NTP 服务器 | 建议 | `ntp server` 计数 ≥ 2 |
| CH9-3 | NTP 功能实际启用 | 必查 | 存在 `ntp enable` |
| CH9-4 | 监控同步状态 | 人工 | 运维要求（`show ntp status`） |

### 第 10 章 Syslog

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| CH10-1 | 使用集中式 syslog 收集器 | 必查 | 存在 `logging <地址>` |
| CH10-2 | 配置两台收集器 | 建议 | `logging` 条目计数 ≥ 2 |
| CH10-3 | 使用 UTC 时间戳 | 建议 | 需与收集器侧时区策略一并确认（设备侧 `clock timezone`）→ 需人工确认 |
| CH10-4 | 日志级别符合企业策略 | 建议 | `logging ... severity <级别>`（未显式指定时为默认 `info`） |

### 跨章节配套项（公司惯例，标准未显式要求但影响功能可用性）

| ID | 检查项 | 强度 | 判定提示 |
|---|---|---|---|
| OPS-1 | 管理流量的源接口已固定 | 必查 | `ip source-interface radius\|tacacs\|ntp\|syslog interface <接口>` 逐项存在 |
| OPS-2 | AAA 服务器主机名可本地解析 | 必查 | 若 `radius-server host <主机名>`，需有对应 `ip dns host <主机名> <IP>` |
| OPS-3 | AAA 故障时允许放行 | 建议 | 存在 `aaa authentication allow-fail-through` |
| OPS-4 | 操作计费已启用 | 建议 | 存在 `aaa accounting all-mgmt default start-stop group <GRP>` |

---

## 二、已知问题（命令勘误，勿据此建规则）

转换总部文档时发现两处命令在 AOS-CX 中**不存在**，照抄会报错，已反馈待确认：

| 章节 | 原文命令 | 问题 | 正确做法 |
|---|---|---|---|
| 第 7 章 | `ssh server idle-timeout 15` | AOS-CX 无此命令 | `cli-session` → `timeout 15`（单位分钟，默认 30，范围 0–4320） |
| 第 8 章 | `snmpv3 enable` | AOS-CX 无此命令 | `snmp-server vrf <VRF>`（启用代理）；`snmp-server snmpv3-only`（禁 v1/v2c） |

另有两处**配套缺失**（命令能敲，但功能不完整）：

| 章节 | 缺失 | 影响 |
|---|---|---|
| 第 6 章 | ACL 定义后未说明如何应用 | 不应用则完全不生效 → 检查项 CH6-7 |
| 第 9/10 章 | 未提源接口命令 | 请求/日志源地址不固定，服务器侧难以识别 → 检查项 OPS-1 |

---

## 三、不纳入自动检查的条款

以下条款属于流程或运维要求，配置文本无法判定，应在审计结果中标注「需人工判断」而非报为问题：

- 第 3 章全部（例外必须有业务理由、补偿控制、批准人、定期复核）
- CH5-8（break-glass 使用后改密）
- CH5-9（管理角色集中管理）
- CH9-4（监控 NTP 同步状态）
- CH10-3 的收集器侧时区处理

---

## 四、附录：现网已知缺口（2026-09 实测，供规则优先级参考）

对现网 18 台 Aruba CX 最新采集配置的实测覆盖情况：

| 检查项 | 覆盖 | 说明 |
|---|---|---|
| CH10-1/2 Syslog | **0/18** | 全网未配置，缺口最大 |
| CH6-x MGMT_ACL | **0/18** | 全网无任何 ACL |
| CH7-2 SSH 空闲超时 | **0/18** | `cli-session` 亦为 0 —— 与勘误相关，很可能因命令写错而未落地 |
| CH9-1 内部 NTP | 7/18 偏离 | 混配 `pool.ntp.org` 公网源 |
| CH8-1 禁 v1/v2c | 1/18 不合规 | 一台仍有 `snmp-server community` |
| CH8-2 SNMPv3 AuthPriv | 17/18 | 缺 1 台 |
| CH8-4 SNMP 代理启用 | 12/18 | `snmp-server vrf` 缺失 |
| CH5-1 集中式 AAA | 18/18 | 达标 |
| CH5-2 计费 | 14/18 | 缺 4 台 |
| OPS-1 源接口 | tacacs 14 / ntp 12 / radius 10 | 覆盖不均 |
| OPS-2 DNS 静态解析 | 达标 | AAA 主机名均有 `ip dns host` |
| CH4-6 REST 只读 | 13/18 | 缺 5 台 |

**规则优先级建议**：CH10（Syslog）→ CH6（MGMT_ACL）→ CH7-2（空闲超时）→ CH9-1（公网 NTP）→ CH8-1/2（SNMP）。
其中 CH10 与 CH6 属于**全网集体性缺失**，建议在审计结果中作为「集体性漏配」单独成类，避免产生 18 条重复条目。
