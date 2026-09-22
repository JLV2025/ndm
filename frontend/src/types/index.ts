export interface Device {
  name: string
  ip: string
  type: string
  platform?: string
  location?: string
  notes?: string
  serial_number?: string
  member_ids?: string
  model?: string
  version?: string
  username?: string
  password?: string
  last_synced?: string
  last_collected?: string
  uplink_ports?: string[]
  kind?: 'stack' | 'standalone' | 'member'
  stack_name?: string      // 成员行：所属堆叠（管理体名）
  member_no?: number       // 成员行：成员号
  [key: string]: unknown
}

/** 离线物理设备档案（device_members 表） */
export interface OfflineDevice {
  serial_number: string
  model?: string
  version?: string
  last_device?: string
  last_member?: string
  last_seen?: string
  first_seen?: string
}

export interface CollectResult {
  name: string
  ip: string
  status: 'success' | 'failed'
  running_lines?: number
  software_version?: string
  serial_number?: string
  model?: string
  error?: string
  type_mismatch?: boolean
  configured_type?: string
  device_type?: string
}

export interface BatchItemStatus {
  status: 'pending' | 'pinging' | 'collecting' | 'success' | 'failed'
  error?: string
  result?: Record<string, unknown>
  progress?: number  // 0-100，由轮询实时更新
  cmdDone?: number   // 已完成的命令数
  totalCmds?: number // 总命令数
}

export interface Session {
  username: string
  password: string
  deviceIp: string
  expiresAt: number
}

export interface PortInfo {
  name: string
  status: string
  status_up: boolean
  speed?: string
  mode?: string
  type?: string
  description?: string
  is_uplink: boolean
  uplink_type?: string
  rx_mbps?: number
  tx_mbps?: number
  total_mbps?: number
  rx_util_pct?: number
  tx_util_pct?: number
  total_util_pct?: number
}

export interface FrontPanelData {
  device_name: string
  ports: PortInfo[]
  total_ports: number
  up_ports: number
  down_ports: number
  disabled_ports: number
  error_ports: number
}

export type { NeighborNode, TopologyData } from './topology'

// ---------------------------------------------------------------- 配置审计

/** 一条审计发现（后端 engine.make_finding 的产物） */
export interface AuditFinding {
  rule_id: string
  title: string
  level: string                  // 五档建议强度
  source: string                 // 公司总部 / 厂商基线 / 组织规范
  severity: string               // shall / should / vendor / convention
  controls: string[]             // NIST 控制编号
  platform: string
  evidence: { line: number | null; text: string }[]
  /**
   * 证据涉及的行号（去重升序）。**前端标红只认这个**——
   * 实测 35/36 台配置带行尾空格，"拿证据文本回配置里搜"必然错位。
   */
  lines: number[]
  /** 是否可定位到行。命名类/全局策略类为 false，此时禁用「定位到行」按钮 */
  locatable: boolean
  current: string
  fix: string
  why: string
  note: string
  detail?: string
  expect?: string
  // 组合判定器补充字段
  check_kind?: string
  group?: string
  missing?: string[]
  satisfied?: string[]
  trigger?: string
  conflict?: string[]
  /**
   * 例外豁免信息（命中已登记的例外才有）。
   * status：active（生效中）/ expiring（即将到期，仍豁免）/ expired（已过期，
   * **不再豁免**但保留标注提醒复核）。生效中的条目不计入 counts，单列 exempt_count。
   */
  exempt?: AuditExemption
}

export interface AuditExemption {
  exception_id: string
  status: 'active' | 'expiring' | 'expired'
  approved_by: string
  reason: string
  compensating_control: string
  expires_at: string
}

/** 一条例外登记 */
export interface AuditException {
  id: string
  rule_id: string
  scope: { type: 'device' | 'site' | 'all'; value?: string }
  reason: string
  compensating_control: string
  approved_by: string
  approved_at: string
  expires_at: string
  revoked?: { at: string; by: string; reason: string }
  /** 推导状态，不是文件里的字段 */
  status: 'active' | 'expiring' | 'expired' | 'revoked'
  rule_title: string
  days_left: number | null
  source_file?: string
}

export interface AuditExceptionsResponse {
  exceptions: AuditException[]
  counts: Record<string, number>
  /** 例外表文件指纹——编辑/撤销时带回做乐观锁 */
  base_hash: string
}

// ---------------------------------------------------------------- 审计趋势与历史

export interface AuditRun {
  id: number
  started_at: string
  finished_at: string | null
  trigger: 'manual' | 'scheduled' | 'post_collect' | string
  ruleset_hash: string
  exceptions_hash: string | null
  device_count: number
  finding_count: number
  exempt_count: number
  status: string
}

/** 趋势图上的一个点 = 某一周的**最后一次**运行（本周无运行则该周不出现） */
export interface AuditTrendPoint {
  week: string                  // YYYY-WW（与配置目录的周格式一致）
  run_id: number
  started_at: string
  trigger: string
  device_count: number
  total: number                 // 建议数（未豁免）
  exempt: number                // 已批准例外数（生效中 + 即将到期）
  counts: Record<string, number>      // 未豁免，按档位
  by_source: Record<string, number>   // 未豁免，按来源
  devices: number               // 命中设备数（站点过滤后为过滤范围内）
  ruleset_changed: boolean      // 与前一个点相比，标准变过
  exceptions_changed: boolean   // 与前一个点相比，豁免变过
}

export interface AuditTrends {
  points: AuditTrendPoint[]
  site: string
  weeks: number
}

export interface AuditTrendDiffRule {
  rule_id: string
  title: string
  level: string
  from_count: number
  to_count: number
  delta: number                 // 负 = 收敛，正 = 恶化
  exempt_count: number
}

export interface AuditTrendDiff {
  from: { run_id: number; week: string; started_at: string; trigger: string } | null
  to: { run_id: number; week: string; started_at: string; trigger: string } | null
  rules: AuditTrendDiffRule[]
  converged: number
  worsened: number
  reason?: string               // 数据不足时的可读原因（不造数）
}

/** AI 专家简报 —— 把确定性结论讲成人话（不落库，随时可重新生成） */
export interface AuditBriefing {
  briefing: string
  provider: string
  scope: 'device' | 'network'
  run_id?: number
  generated_at: string
}

/** 单次运行的明细（下钻） */
export interface AuditRunFinding {
  device_name: string
  rule_id: string
  level: string
  source: string
  severity: string
  title: string
  detail: string
  lines: number[]
  controls: string[]
  exempt_by: string | null
  exempt: AuditExemption | null
}

export interface AuditRunDetail {
  run: AuditRun
  findings: AuditRunFinding[]
}

/** 按发现看设备（by-rule 聚合的反向视图）：一条发现命中了哪些设备 */
export interface AuditByRuleItem {
  rule_id: string
  title: string
  level: string
  source: string
  fix: string                                      // 修复命令（规则级模板，带入批量执行用）
  count: number                                    // 未豁免命中台数
  exempt_count: number                             // 豁免台数（生效中 + 即将到期）
  devices: { name: string; location: string; current: string }[]  // 命中设备（含现状片段）
}

export interface AuditByRule {
  run_id: number
  rules: AuditByRuleItem[]
}

// ---------------------------------------------------------------- 设备生命周期（EoL / 保修）

/** 刷新可用性：未配 Cisco 凭据时 available=false + 可读原因（手工登记不受影响） */
export interface LifecycleRefreshStatus {
  available: boolean
  reason: string
}

export interface LifecycleModelEol {
  model: string
  description?: string
  end_of_sale?: string
  end_of_support?: string
  announcement?: string
  bulletin?: string
  bulletin_url?: string
  source?: string            // api（Cisco EoX）| manual
  fetched_at?: string
  updated_by?: string
  note?: string
}

export interface LifecycleSerial {
  serial: string
  warranty_end?: string     // YYYY-MM-DD（保修，不是服务合同）
  note?: string
  source?: string
  verified_at?: string
  verified_by?: string
}

export interface DeviceLifecycle {
  device_name: string
  models: string[]
  model_eol: LifecycleModelEol[]
  serials: LifecycleSerial[]
  extra_rows: LifecycleSerial[]
  refresh: LifecycleRefreshStatus
}

export interface LifecycleImportResult {
  matched: { device_name: string; serial: string; warranty_end: string }[]
  unmatched: string[]
  ambiguous: { serial: string; devices: string[] }[]
  invalid: string[]
}

export interface LifecycleOverviewRow {
  device_name: string
  models: string[]
  serials: string[]
  registered: number
  warranty_end: string
  verified_at: string
  eol_announced: boolean
}

/** 单台审计的完整返回体 */
export interface AuditEnvelope {
  device: string
  location: string
  platform: string
  model: string
  week: string
  collected_at: string
  /** 配置原文——面板必须渲染这一份（与引擎判定的是同一份文本） */
  config: string
  config_hash: string
  /** 配置是否可用于审计；false 时看 reason，界面要解释"为什么没结果" */
  usable: boolean
  reason: string
  ruleset_hash: string
  generated_at: string
  findings: AuditFinding[]
  counts: Record<string, number>
  /** 已批准例外条数（生效中 + 即将到期）——不计入 counts，界面单列一行 */
  exempt_count: number
  port_roles: Record<string, { role: string; confidence: string; reasons: string[] }>
}

export interface AuditRule {
  id: string
  title: string
  level: string
  source: string
  severity: string
  platforms: string[]
  controls: string[]
  check: string
  params: Record<string, unknown>
  only_sites: string[]
  exempt_sites: string[]
  fix: string
  why: string
  note: string
  enabled: boolean
  superseded_by: string
  disabled_reason: string
  source_file: string
}

export interface AuditRuleset {
  rules: AuditRule[]
  rule_files: string[]
  ruleset_hash: string
  layer_priority: Record<string, number>
  levels: string[]
  platforms: string[]
  sites: Record<string, string[]>
  naming: Record<string, unknown>
  vlans: Record<string, unknown>
}

export interface AuditRun {
  id: number
  started_at: string
  finished_at: string | null
  trigger: string
  ruleset_hash: string
  device_count: number
  finding_count: number
  status: string
}

// ---------------------------------------------------------------- 批量执行（命令下发）

/** 命令预检结果（黑名单三态；blocked 非空 = 拒绝执行） */
export interface BatchCheckResult {
  commands: string[]
  blocked: { cmd: string; reason: string }[]
  warnings: { cmd: string; reason: string }[]
}

/** 单台执行结果（status: success | failed | blocked） */
export interface BatchExecuteResult {
  device: string
  status: 'success' | 'failed' | 'blocked'
  output: string
  error: string
}

/** 一个执行批次（命令全文只存一份；统计字段来自 history 端点） */
export interface BatchRun {
  batch_id: string
  created_at: string
  username: string
  mode: string
  save_config: number
  command_text: string
  device_count: number
  note: string
  success_count?: number
  failed_count?: number
  done_count?: number
}

export interface BatchResultRow {
  device_name: string
  status: string
  output: string
  error: string
  started_at: string
  finished_at: string
}

export interface BatchHistoryDetail {
  batch: BatchRun
  results: BatchResultRow[]
}
