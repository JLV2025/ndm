# CFG-CISCO 合规检查项（公司标准简化版）

> **用途**：设备配置合规性审计的**检查项清单**，作为 NDM 配置审计功能中「公司规范层」规则的来源（与 `CFG-Aruba-checklist.md` 并列）。
> **来源**：`CFG-CISCO.docx`（Qorvo Network Infrastructure Standards v1.0，2026-06-26）。英文原文保真 + 中文导读的**完整转换版**在 OneDrive：`01-DocWiKi/01_network_configuration/CFG-CISCO.md`。
> **强度约定**：`必查` = 原文 `shall`；`建议` = 原文 `should`；`人工` = 流程类，无法由配置文本判定
>
> **⚠️ 平台错配（最重要的一条）**：本基线的**主要参考实现是 Nexus 9000 / NX-OS v7**，IOS 只是"可选参考示例"。但 **Qorvo 现网 18 台 Cisco 全部是 IOS / IOS-XE / IOS 路由器，没有任何 Nexus**。因此**判定提示必须同时支持两种命令形式**，且 IOS 形式才是当前实际生效的那一套；NX-OS 形式为将来引入 Nexus 预留。

---

## 一、检查项

### 第 4 章 管理面基线

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH4-1 | 启用了 SSH 用于 CLI 管理 | 必查 | NX-OS：`feature ssh`；IOS：`ip ssh version 2` 或 `crypto key generate rsa` |
| CH4-2 | 启用了 SNMPv3 用于监控 | 必查 | NX-OS：`feature snmp`；IOS：`snmp-server group`（还需要 user，见 CH8-2） |
| CH4-3 | 放行 ICMP（排障与连通性验证） | 必查 | 管理 ACL 中存在 `permit icmp any any` |
| CH4-4 | 使用 MGMT_ACL 限制管理访问 | 必查 | 存在名为 `MGMT_ACL` 的 ACL **且已应用**（见 CH6-7） |
| CH4-5 | 可选管理协议（HTTPS/NX-API、gNMI、RESTCONF、Telemetry）需经批准 | 建议 | 检测到 `ip http secure-server`、`nxapi`、`telemetry`、`restconf` 等时列为「需确认是否已批准」 |
| CH4-6 | **关闭明文 HTTP 管理面**（本章"仅批准协议"的具体落地） | 必查 | IOS：存在 `no ip http server`（IOS 中 `ip http server` **默认开启**） |

### 第 5 章 AAA

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH5-1 | 管理认证使用集中式 AAA | 必查 | NX-OS：`aaa authentication login default group <GRP> local`；IOS：`aaa new-model` + 同名命令 |
| CH5-2 | 集中式 AAA 提供认证、授权、计费 | 建议 | 授权：`aaa authorization commands`（NX-OS）/ `aaa authorization exec` + `aaa authorization commands 1\|15`（IOS）；计费：`aaa accounting ... start-stop group <GRP>` |
| CH5-3 | 至少部署两台 AAA 服务器 | 建议 | 服务器定义或组内 `server` 条目 ≥ 2 |
| CH5-4 | AAA 服务器尽量分布在不同站点/地域 | 建议 | 服务器主机名/地址前缀分属不同站点代号 → 需人工确认 |
| CH5-5 | 设备配置为与多台 AAA 服务器通信 | 必查 | `aaa group server tacacs+\|radius <GRP>` 下引用 ≥ 2 台服务器 |
| CH5-6 | 存在本地 break-glass 账号 | 必查 | 存在本地 `username <NAME> privilege 15` / `role network-admin` |
| CH5-7 | 本地认证仅在集中式 AAA 不可用时使用 | 必查 | 方法列表中 `group` 在 `local` **之前** |
| CH5-8 | break-glass 使用后立即改密 | 人工 | 流程要求 |
| CH5-9 | 管理角色尽量集中管理 | 人工 | 流程要求 |
| CH5-10 | AAA 服务器密钥不得以明文存储 | 必查 | NX-OS 用 `key 7 <KEY>`（7 = 已加密）；IOS 下发后应回显为 `key 7` 或 `type 7`，出现明文 `key <明文>` 即为问题 |

### 第 6 章 管理访问 ACL（MGMT_ACL）

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH6-1 | 管理 ACL 名称固定为 `MGMT_ACL` | 必查 | NX-OS：`ip access-list MGMT_ACL`；IOS：`ip access-list extended MGMT_ACL`。**注意现网有 `ACL-NMS-SNMPv3` 等其他 ACL，不能替代命名要求** |
| CH6-2 | 来源使用批准的管理网段/主机 | 必查 | 条目引用批准的管理网段与主机 |
| CH6-3 | 逐协议放行，且引用批准来源 | 必查 | 每条 `permit` 均带协议与端口（`tcp ... eq 22`、`udp ... eq 161`、`tcp ... eq 443`） |
| CH6-4 | **禁止**整段/整机放行 | 必查 | 不得出现 `permit ip <SUBNET> any`、`permit ip host <HOST> any` |
| CH6-5 | ICMP 允许 `any any` | 必查 | 存在 `permit icmp any any` |
| CH6-6 | 末尾默认拒绝并记录日志 | 必查 | 存在 `deny ip any any log` |
| CH6-7 | MGMT_ACL 实际生效（已应用） | 必查 | NX-OS：`interface mgmt0` → `ip access-group MGMT_ACL in` / `line vty` → `access-class MGMT_ACL in`；IOS：同上（IOS 示例给出了应用方式） |
| CH6-8 | 跑路由协议的设备为协议流量预留 permit | 必查 | 若存在 `router ospf/bgp/eigrp`，MGMT_ACL 需有对应协议 permit，否则 `deny any` 会中断邻居 |

### 第 7 章 SSH

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH7-1 | SSH 为交互式 CLI 管理的唯一协议 | 必查 | `transport input ssh`（不含 telnet）；telnet 相关配置出现即异常 |
| CH7-2 | 配置 SSH 空闲超时 | 必查 | **IOS**：`line vty` 下 `exec-timeout <分钟> <秒>`（现网统一 `15 0`）；**NX-OS**：文档示例为 `ssh timeout 600`（**该命令待核实**），较新版本记为 `ssh idle-timeout <秒>`（默认 0 = 不限） |
| CH7-3 | 管理认证使用集中式 AAA | 必查 | 同 CH5-1 |
| CH7-4 | 加密算法符合企业安全标准 | 建议 | NX-OS：`ssh key rsa 2048 force`（NX-OS 主机密钥默认仅 RSA 1024）、`ssh version 2`；IOS：`ip ssh version 2` |
| CH7-5 | 限制认证尝试次数 | 建议 | NX-OS：`ssh login-attempts <N>`（默认 3、范围 1–10；示例放宽到 5，若要更严可保持 3）；IOS：`login block-for` / `login delay` |
| CH7-6 | 可选证书认证（需批准） | 建议 | 检测到证书认证配置时列为「需确认是否已批准」 |

### 第 8 章 SNMPv3

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH8-1 | **不得**配置 SNMPv1/v2c | 必查 | 无 `snmp-server community`（明文团体字即凭据，**RW 团体字风险最高**） |
| CH8-2 | 使用 SNMPv3 AuthPriv | 必查 | `snmp-server user <NAME> <GROUP> v3 auth <…> priv <…>` —— **auth 与 priv 缺一不可，且用户必须存在**（只有 group 不算达标） |
| CH8-3 | SNMPv3 组与用户成对存在 | 必查 | 存在 `snmp-server group <GRP> v3 priv` 时，**必须**有引用该组的 `snmp-server user`；有组无用户 = SNMPv3 不可用 |
| CH8-4 | SNMP 访问通过 MGMT_ACL 限制 | 必查 | 关联 CH6（UDP 161 仅批准来源）；专用 NMS ACL 不能替代 MGMT_ACL 命名要求 |
| CH8-5 | SNMP 源接口固定 | 建议 | NX-OS：`snmp-server source-interface informs\|traps mgmt0`；IOS：`snmp-server trap-source <接口>` |
| CH8-6 | 认证算法强度 | 建议 | `auth sha` 为 SHA-1，建议升级到 `sha256` 等更强算法 |

### 第 9 章 NTP

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH9-1 | 使用企业内部 NTP 服务器 | 必查 | NTP 服务器地址全部为内部地址；不得出现公网 NTP 域名 |
| CH9-2 | 至少配置两台 NTP 服务器 | 建议 | `ntp server` 条目计数 ≥ 2 |
| CH9-3 | NTP 实际生效 | 必查 | NX-OS：`clock protocol ntp`（**必须显式选择，否则不生效**）+ NTP 服务器；IOS：无此步骤 |
| CH9-4 | NTP 源接口/VRF 固定 | 建议 | NX-OS：`ntp source-interface mgmt0` + `use-vrf management`；IOS：`ntp source <接口>` |
| CH9-5 | 监控同步状态 | 人工 | 运维要求（`show ntp status`） |

### 第 10 章 Syslog

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| CH10-1 | 使用集中式 syslog 收集器 | 必查 | NX-OS：`logging server <IP>`；IOS：`logging host <IP>` |
| CH10-2 | 配置两台收集器 | 建议 | 收集器条目计数 ≥ 2 |
| CH10-3 | 日志级别已设定 | 建议 | NX-OS：`logging server <IP> <级别 0-7>`；IOS：`logging trap <级别>` |
| CH10-4 | 毫秒级时间戳 | 建议 | NX-OS：`logging timestamp milliseconds`；IOS：`service timestamps log datetime msec`（可加 `localtime` 或 `show-timezone`） |
| CH10-5 | 源接口固定 | 必查 | NX-OS：`logging source-interface mgmt0`；IOS：`logging source-interface <接口>` |
| CH10-6 | UTC 时间戳 | 建议 | 需与收集器侧时区处理策略一并确认 → 需人工确认 |

### 跨章节配套项

| ID | 检查项 | 强度 | 判定提示（NX-OS / IOS） |
|---|---|---|---|
| OPS-1 | 管理流量的源接口已固定 | 必查 | IOS：`ip tacacs source-interface`、`ip radius source-interface`、`logging source-interface`；NX-OS：`… use-vrf management` + 各 source-interface |
| OPS-2 | 控制台日志收敛 | 建议 | NX-OS/IOS：`no logging console`（避免刷屏影响故障处置） |
| OPS-3 | 本地日志缓冲区 | 建议 | NX-OS：`logging logfile messages <大小> <级别>`；IOS：`logging buffered <大小> <级别>` |

---

## 二、已知问题（命令待核实，勿据此建硬规则）

| 章节 | 原文命令 | 问题 | 处理建议 |
|---|---|---|---|
| 第 7 章 | `ssh timeout 600` | 未能从公开文档确认该命令及其取值范围；NX-OS 较新版本把该能力记为 **`ssh idle-timeout <秒>`（默认 0 = 不限空闲）** | 在目标平台用 `ssh ?` 现场确认。**无论用哪条命令，NX-OS 默认不限空闲，必须显式配置** |

**配套缺失 2 处**（命令能敲，但功能不完整）：

| 章节 | 缺失 | 影响 |
|---|---|---|
| 第 6 章 | NX-OS 示例未说明 ACL 如何应用（IOS 示例给了） | NX-OS 侧不应用则不生效 → 检查项 CH6-7 |
| 第 5/9/10 章 | 未强调源接口/管理 VRF 配套 | 服务器侧源地址不稳定 → 检查项 OPS-1、CH9-4、CH10-5 |

> 对照：Aruba 版基线发现了两处**命令不存在**级别的硬错误（`ssh server idle-timeout`、`snmpv3 enable`），Cisco 版**没有这类错误**。

---

## 三、不纳入自动检查的条款

- 第 3 章全部（例外必须有业务理由、补偿控制、批准人、定期复核）
- CH5-8（break-glass 使用后改密）、CH5-9（管理角色集中管理）
- CH9-5（监控 NTP 同步状态）
- CH10-6 的收集器侧时区处理

---

## 四、附录：现网已知缺口（2026-09 实测，18 台）

**平台构成**：`cisco_ios` 14 / `cisco_ios_router` 3 / `cisco_ios_xe` 1 —— **无 Nexus**，故 IOS 形式为当前实际生效的那一套。

| 检查项 | 覆盖 | 说明 |
|---|---|---|
| **CH8-2/8-3 SNMPv3 用户** | **0/18** ❌ | `snmp-server group ... v3 priv` **18/18**，但 `snmp-server user` **0/18** → **有组无用户，SNMPv3 实际不可用**（本次审计头号必报项） |
| **CH8-1 禁 v1/v2c** | **4/18 不合规** ❌ | 仍有明文 `snmp-server community`，其中含 **1 个 RW 读写团体字**，优先清理（属凭据暴露） |
| **CH6-x MGMT_ACL** | **0/18** ❌ | 全网无一台使用 `MGMT_ACL` 命名；现存 ACL 为 `ACL-NMS-SNMPv3`、`CISCO-CWA-URL-REDIRECT-ACL`、`clearpass-redirect`、`default-port-acl`、`102` |
| **CH10-1 syslog** | 10/18 ⚠️ | `logging host` 10、`logging trap` 9、`logging source-interface` **仅 1** |
| **CH4-6 明文 HTTP** | 7/18 ⚠️ | 仅 7 台显式 `no ip http server`；IOS 默认开启 → 约 11 台明文 HTTP 管理面未关闭 |
| CH7-1 `transport input ssh` | 16/18 ⚠️ | 缺 2 台 |
| CH7-2 空闲超时 | **18/18** ✅ | IOS 用 `exec-timeout 15 0` 实现（15 分钟） |
| CH7-4 `ip ssh version 2` | 15/18 ⚠️ | 缺 3 台 |
| CH9-1 内部 NTP | 18/18 ✅ | 全部 `10.8.26.10`，**无公网源**（优于 Aruba 侧） |
| CH9-2 NTP 服务器数量 | **1 台** ⚠️ | 未达"至少两台" |
| CH5-1 集中式 AAA | 18/18 ✅ | `aaa new-model` + `aaa group server tacacs+ qorvo-tacacs` + `aaa group server radius qorvo-radius` |
| CH5-2 计费 | 覆盖良好 ✅ | `aaa accounting commands 1\|15`、`aaa accounting dot1x`、`aaa accounting update periodic 5` |
| OPS-1 源接口 | 部分 ⚠️ | `ip tacacs/radius source-interface Vlan255` 覆盖良好；`logging source-interface` 仅 1/18 |
| — | BPDU Guard | 14/18 ⚠️ | 公司惯例项（基线未覆盖） |
| — | DAI / IPSG | 0/18 | 公司惯例项（基线未覆盖） |

**规则优先级建议**：CH8-1/8-2/8-3（SNMPv3 有组无用户 + v2c 团体字）→ CH6（MGMT_ACL 全网缺失）→ CH10（syslog 覆盖不足）→ CH4-6（关闭明文 HTTP）→ CH7 收口。

**集体性缺失提示**：CH6（MGMT_ACL）与 CH8-2/8-3（SNMPv3 用户）均为**全网集体性缺失**，审计结果应单独成类，避免产生 18 条重复条目。
