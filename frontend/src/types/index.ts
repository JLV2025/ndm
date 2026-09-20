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
