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
}

export interface CollectResult {
  name: string
  ip: string
  status: 'success' | 'failed'
  running_lines?: number
  software_version?: string
  serial_number?: string
  error?: string
}

export interface Session {
  username: string
  password: string
  deviceIp: string
  expiresAt: number
}
