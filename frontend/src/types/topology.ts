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
}

export interface TopologyData {
  device_name: string
  week?: string
  stack_members: string[]
  member_neighbors: Record<string, NeighborNode[]>
  neighbors: NeighborNode[]
  endpoints: NeighborNode[]
  network_devices: NeighborNode[]
}

// ============================================================
// Location 多设备拓扑 (新)
// ============================================================

export interface LocationNode {
  id: string
  label: string
  type: string         // switch / router / firewall / wireless / sdwan
  platform: string
  tier: 'wan' | 'core' | 'access' | 'unknown'
  is_location_device: boolean
  location: string
}

export interface LocationEdge {
  id: string
  source: string
  target: string
  source_interface: string
  target_interface: string
  is_cross_location: boolean
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
