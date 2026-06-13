/**
 * 全局共享常量 — 设备颜色、图例、端点前缀
 * 供各拓扑组件统一引用，消除重复定义
 */

// ============================================================
// 设备类型 → 单色（端口拓扑图用）
// ============================================================
export const DEVICE_COLORS: Record<string, string> = {
  switch: '#3B82F6',
  router: '#F59E0B',
  firewall: '#EF4444',
  wireless: '#8B5CF6',
  sdwan: '#F97316',
  esxi: '#06B6D4',
  server: '#06B6D4',
  printer: '#6366F1',
  mgmt: '#64748B',
}

/** 获取设备类型颜色，未知类型返回灰色 */
export function getDeviceColor(type: string): string {
  return DEVICE_COLORS[type] || '#94A3B8'
}

// ============================================================
// 设备颜色 — 工业级三件套（Location 拓扑图用）
// ============================================================
export interface NodeColorSet {
  fill: string
  glow: string
  border: string
}

export const NODE_COLORS: Record<string, NodeColorSet> = {
  'core-switch':   { fill: '#1E3A8A', glow: '#3B82F6', border: '#93C5FD' },  // 深蓝 → 蓝 → 浅蓝
  'access-switch': { fill: '#0F766E', glow: '#14B8A6', border: '#5EEAD4' },  // 深绿 → 绿 → 浅绿
  router:          { fill: '#B45309', glow: '#F59E0B', border: '#FCD34D' },  // 深橙 → 橙 → 浅橙
  firewall:        { fill: '#991B1B', glow: '#EF4444', border: '#FCA5A5' },  // 深红 → 红 → 浅红
  wireless:        { fill: '#5B21B6', glow: '#8B5CF6', border: '#C4B5FD' },  // 深紫 → 紫 → 浅紫
  sdwan:           { fill: '#7C2D12', glow: '#F97316', border: '#FDBA74' },  // 深棕 → 橙 → 浅橙
  server:          { fill: '#155E75', glow: '#06B6D4', border: '#67E8F9' },  // 深青 → 青 → 浅青
}

export function getNodeColors(type: string): NodeColorSet {
  return NODE_COLORS[type] || { fill: '#475569', glow: '#64748B', border: '#94A3B8' }
}

/** 根据后端 type + tier 计算前端显示类型（交换机拆分核心/接入） */
export function getDisplayType(type: string, tier: string): string {
  if (type === 'switch') {
    return tier === 'core' ? 'core-switch' : 'access-switch'
  }
  return type
}

// ============================================================
// 图例定义
// ============================================================
export interface LegendItem {
  type: string
  labelZh: string
  labelEn: string
  color: string
}

/** Location 拓扑图图例（按设备类型，交换机拆分核心/接入） */
export const TOPOLOGY_LEGEND: LegendItem[] = [
  { type: 'core-switch',   labelZh: '核心交换机',     labelEn: 'Core Switch',     color: '#3B82F6' },
  { type: 'access-switch', labelZh: '接入层交换机',   labelEn: 'Access Switch',    color: '#14B8A6' },
  { type: 'router',        labelZh: '路由器',         labelEn: 'Router',           color: '#F59E0B' },
  { type: 'firewall',      labelZh: '防火墙',         labelEn: 'Firewall',         color: '#EF4444' },
  { type: 'sdwan',         labelZh: 'SD-WAN',         labelEn: 'SD-WAN',           color: '#F97316' },
  { type: 'wireless',      labelZh: '无线控制器',     labelEn: 'Wireless Controller', color: '#8B5CF6' },
  { type: 'server',        labelZh: '服务器',         labelEn: 'Server',           color: '#06B6D4' },
]

/** 端口拓扑图图例（含端点和打印机） */
export const PORT_TOPOLOGY_LEGEND: LegendItem[] = [
  ...TOPOLOGY_LEGEND,
  { type: 'printer',  labelZh: '打印机',     labelEn: 'Printer',              color: '#6366F1' },
  { type: 'endpoint', labelZh: '端点设备',   labelEn: 'Endpoint',             color: '#94A3B8' },
]

// ============================================================
// 堆叠检测
// ============================================================
export const STACK_KEYWORDS = ['VSF', 'stackwise']

export function isStackLink(desc: string): boolean {
  return STACK_KEYWORDS.some((kw) => desc.toLowerCase().includes(kw.toLowerCase()))
}

/** LAG（链路聚合）逻辑接口 — 不是物理端口，端口连接图中需过滤 */
export function isLagInterface(iface: string): boolean {
  return /^lag\s*\d/i.test(iface)
}

// ============================================================
// 端点前缀聚合
// ============================================================
export const ENDPOINT_PREFIXES = [
  { prefix: 'Phone-',    label: '电话',   labelEn: 'Phones' },
  { prefix: 'Printer-',  label: '打印机', labelEn: 'Printers' },
  { prefix: 'AP',        label: '无线AP', labelEn: 'APs' },
  { prefix: 'Laptop-',   label: '笔记本', labelEn: 'Laptops' },
  { prefix: 'Internet-', label: '互联网', labelEn: 'Internet' },
]
