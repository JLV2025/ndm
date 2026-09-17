export interface NeighborNode {
  interface: string
  description: string
  device_name: string
  device_type: string
  site_code?: string
  dc?: string
  device_number?: string
  is_endpoint: boolean
  member?: string
  neighbor_ip?: string
  neighbor_model?: string
  neighbor_members?: string[]
  neighbor_notes?: string
  neighbor_interface?: string
  /** 端口物理断开（status_up=0），图上显示红叉警告 */
  port_down?: boolean
}

export interface TopologyData {
  device_name: string
  week?: string
  stack_members: string[]
  member_neighbors: Record<string, NeighborNode[]>
  neighbors: NeighborNode[]
  endpoints: NeighborNode[]
  network_devices: NeighborNode[]
  device_notes?: string
  device_model?: string
  device_ip?: string
  member_models?: Record<string, string>
}

// ============================================================
// Location 多设备拓扑 (新)
// ============================================================

export interface LocationNode {
  id: string
  label: string
  type: string         // switch / router / firewall / wireless / sdwan
  platform: string
  model: string        // 硬件型号 (如 "JL659A 6300M")
  ip: string           // 设备管理 IP
  tier: 'wan' | 'core' | 'access' | 'unknown'
  is_location_device: boolean
  location: string
  stack_group: string  // 堆叠组标识 (逻辑设备名)，非堆叠为空
  physical_index: number
  physical_count: number
}

export interface LocationEdge {
  id: string
  source: string
  target: string
  source_interface: string
  target_interface: string
  is_cross_location: boolean
  /** 端点端口物理断开（status_up=0），图上显示红叉警告 */
  source_port_down?: boolean
  target_port_down?: boolean
}

export interface LocationTopologyData {
  location: string
  device_count: number
  node_count: number
  skipped_count: number
  skipped_devices: string[]
  nodes: LocationNode[]
  edges: LocationEdge[]
}

// ============================================================
// 站点 STP 生成树拓扑 (新)
// ============================================================

/** 节点上的 VLAN 伪端口摘要（role/state 取朝根方向的端口） */
export interface StpVlanChip {
  vlan: number
  is_root: boolean            // 该 VLAN 上本设备是根桥（含本地孤立 VLAN）
  role: string                // root / designated / ...
  state: string               // forwarding / blocking / ...
  port: string | null         // 朝根方向的端口（根桥为 null）
  blocked: boolean            // 该 VLAN 内是否存在阻塞端口
  priority: number | null     // 本桥优先级（Cisco 显示含 sys-id-ext）
  root_priority: number | null
  root_mac: string            // 归一化根 MAC（无分隔符小写）
}

export interface StpNode {
  id: string
  label: string
  type: string                // switch
  ip: string
  model: string
  notes: string
  tier: 'wan' | 'core' | 'access' | 'unknown'
  mode: string                // 归一化：rapid-pvst / pvst / mstp
  has_stp_data: boolean
  is_root_bridge: boolean     // 站点级根桥（本地孤立 VLAN 的根不算）
  vlans: StpVlanChip[]
  layer: number | null        // STP 深度（根 = 1）
}

export interface StpEdge {
  source: string
  target: string
  vlan: number
  source_port: string
  target_port: string
  source_role: string
  source_state: string
  target_role: string
  target_state: string
  forwarding: boolean         // 两端均转发
}

export interface StpModeCheck {
  consistent: boolean
  families: string[]
  modes: Record<string, string>
}

export interface StpTopologyData {
  location: string
  nodes: StpNode[]
  edges: StpEdge[]
  summary: { node_count: number; edge_count: number; vlan_count: number; vlans: number[] }
  root_outside_site: boolean
  outside_root_macs: string[]
  mode_check: StpModeCheck
}
