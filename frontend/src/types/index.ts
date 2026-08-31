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

/** 物理设备（堆叠拆分后的展示用对象） */
export interface PhysicalDevice {
  name: string           // 物理设备名，如 "BJQD1SWI01-01"
  logical_name: string   // 逻辑堆叠设备名，如 "BJQD1SWI01"
  ip: string
  type: string
  platform?: string
  location?: string
  notes?: string
  serial_number?: string
  model?: string
  version?: string
  last_synced?: string
  physical_index: number  // 序号 1-based
  physical_count: number  // 堆叠成员总数
  status?: string
}
