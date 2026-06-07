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
