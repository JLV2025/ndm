export interface Device {
  name: string
  ip: string
  type: string
  platform?: string
  location?: string
  notes?: string
  serial_number?: string
  version?: string
  username?: string
  password?: string
  last_synced?: string
  last_collected?: string
  [key: string]: string | undefined
}

export interface CollectResult {
  name: string
  ip: string
  status: 'success' | 'failed'
  running_lines?: number
  software_version?: string
  serial_number?: string
  error?: string
  type_mismatch?: boolean
  configured_type?: string
  device_type?: string
}

export interface BatchItemStatus {
  status: 'pending' | 'pinging' | 'collecting' | 'success' | 'failed'
  error?: string
  result?: Record<string, unknown>
}

export interface Session {
  username: string
  password: string
  deviceIp: string
  expiresAt: number
}
