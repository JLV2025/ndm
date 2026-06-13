import { useMemo, useState, useCallback, useRef } from 'react'
import {
  ReactFlow, Node, Edge, Background, MarkerType, Handle, Position, BaseEdge,
  type NodeProps, type EdgeProps, type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Typography, IconButton, Tooltip, Stack, Paper } from '@mui/material'
import {
  Image as ImageIcon, AccountTree as VisioIcon,
  Add as ZoomInIcon, Remove as ZoomOutIcon, ZoomOutMap as FitViewIcon,
  Hub as HubIcon, Lan as LanIcon, Router as RouterIcon,
  Security as SecurityIcon, Public as PublicIcon,
  Wifi as WifiIcon, Dns as DnsIcon, DevicesOther as DevicesOtherIcon,
} from '@mui/icons-material'
import { toPng } from 'html-to-image'
import { getDeviceColor, getNodeColors, ENDPOINT_PREFIXES, isStackLink, isLagInterface, PORT_TOPOLOGY_LEGEND } from '../../shared/constants'
import { useI18n } from '../../i18n'
import type { NeighborNode } from '../../types/topology'
import DirectionPad from './DirectionPad'

// ============================================================
// 布局常量
// ============================================================
const SWITCH_W = 368
const SWITCH_H = 125
const HANDLE_SIZE = 8
const NEIGHBOR_W = 252
const NEIGHBOR_H = 83
const MANAGED_W = 288
const MANAGED_H = 83
const COMPACT_W = 172
const COMPACT_H = 42
const ROW_GAP = 140
const DEVICE_GAP = 44
const STACK_GAP = 24
const SIDEBAR_W = 104
const SWITCH_COLOR = '#3B82F6'

// ============================================================
// 设备图标 + 端口工具
// ============================================================
const DEVICE_ICONS: Record<string, React.ComponentType<any>> = {
  switch: LanIcon, router: RouterIcon, firewall: SecurityIcon,
  sdwan: PublicIcon, wireless: WifiIcon, server: DnsIcon,
  endpoint: DevicesOtherIcon, printer: DevicesOtherIcon,
}

function extractPortNumber(iface: string): number {
  const nums = iface.match(/\d+/g)
  if (!nums || nums.length === 0) return 0
  return parseInt(nums[nums.length - 1], 10)
}

const MODEL_PORT_COUNT: Record<string, number> = {
  '6300M': 48, '6300': 48, '6200M': 24, '6200': 24, '6200F': 24,
  '2930F': 24, '2930M': 24, '3560': 48, '3560G': 48, '3560X': 48,
  '2960X': 48, '2960': 48, 'C9500-24': 24, 'C9500': 48,
}

export function getPortCount(model: string): number {
  for (const [key, count] of Object.entries(MODEL_PORT_COUNT)) {
    if (model.toLowerCase().includes(key.toLowerCase())) return count
  }
  return 48
}

function getHandleX(index: number, total: number, nodeW: number = SWITCH_W): number {
  if (total <= 1) return nodeW / 2
  const pad = 32
  const gap = (nodeW - pad * 2) / (total - 1)
  return pad + index * gap
}

function isWanDevice(type: string, name: string): boolean {
  return type === 'router' || type === 'firewall' || type === 'sdwan'
    || name.startsWith('Internet') || name.startsWith('互联网')
}

function getEdgeColor(deviceType: string, deviceName: string): string {
  if (isWanDevice(deviceType, deviceName)) return getDeviceColor(deviceType)
  if (deviceType === 'switch') return getDeviceColor('switch')
  return getDeviceColor(deviceType)
}

// ============================================================
// 交换机节点（Handle 在上下边框）
// ============================================================
interface SwitchNodeData {
  label: string
  model?: string
  ip?: string
  topPorts: { id: string; label: string; color: string; neighborName: string }[]
  bottomPorts: { id: string; label: string; color: string; neighborName: string }[]
  color: string
  nodeWidth?: number
  handleRole?: 'source' | 'target'
}

function SwitchNode({ data }: NodeProps) {
  const { label, model, ip, topPorts, bottomPorts, color, nodeWidth, handleRole } = data as unknown as SwitchNodeData
  const nodeW = nodeWidth || SWITCH_W
  const ht = handleRole || 'source'

  return (
    <Box sx={{
      width: nodeW, height: SWITCH_H, position: 'relative',
      borderRadius: 2, border: '2px solid', borderColor: `${color}99`,
      bgcolor: `${color}08`,
      boxShadow: `0 0 32px ${color}22, 0 4px 16px rgba(0,0,0,0.55), inset 0 1px 0 ${color}14`,
      fontFamily: '"Fira Code","Consolas",monospace',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {/* 三排文字：名称 / 型号 / IP */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <HubIcon sx={{ fontSize: 28, color, filter: `drop-shadow(0 0 6px ${color}80)`, flexShrink: 0 }} />
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
          <Typography sx={{ fontWeight: 700, fontSize: '1rem', color: '#e2e8f0', letterSpacing: '0.04em', textShadow: `0 0 20px ${color}30`, lineHeight: 1.3 }}>
            {label}
          </Typography>
          {model && <Typography sx={{ fontSize: '0.8rem', color: '#94A3B8', fontFamily: '"Fira Code",monospace', fontWeight: 500, lineHeight: 1.3 }}>{model}</Typography>}
          {ip && <Typography sx={{ fontSize: '0.8rem', color: '#CBD5E1', fontFamily: '"Fira Code",monospace', fontWeight: 500, lineHeight: 1.3 }}>{ip}</Typography>}
        </Box>
      </Box>

      {topPorts.map((p, idx) => {
        const x = getHandleX(idx, topPorts.length, nodeW)
        return (
          <Box key={`tv-${p.id}`} sx={{ position: 'absolute', left: x - 16, top: 0, width: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2 }}>
            <Handle id={p.id} type={ht} position={Position.Top} style={{ position: 'relative', left: 0, top: 0, transform: 'none', width: HANDLE_SIZE, height: HANDLE_SIZE, background: p.color, borderRadius: 2, border: 'none' }} />
            <Typography sx={{ fontSize: '0.85rem', color: '#94a3b8', mt: 0.2, fontFamily: '"Fira Code","Consolas",monospace', fontWeight: 600, lineHeight: 1, whiteSpace: 'nowrap' }}>{p.label}</Typography>
          </Box>
        )
      })}
      {bottomPorts.map((p, idx) => {
        const x = getHandleX(idx, bottomPorts.length, nodeW)
        return (
          <Box key={`bv-${p.id}`} sx={{ position: 'absolute', left: x - 16, bottom: 0, width: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2 }}>
            <Typography sx={{ fontSize: '0.85rem', color: '#94a3b8', mb: 0.2, fontFamily: '"Fira Code","Consolas",monospace', fontWeight: 600, lineHeight: 1, whiteSpace: 'nowrap' }}>{p.label}</Typography>
            <Handle id={p.id} type={ht} position={Position.Bottom} style={{ position: 'relative', left: 0, bottom: 0, transform: 'none', width: HANDLE_SIZE, height: HANDLE_SIZE, background: p.color, borderRadius: 2, border: 'none' }} />
          </Box>
        )
      })}
    </Box>
  )
}

// ============================================================
// 邻居设备（拓扑风格：图标 + 名称 + 型号 + IP，Handle 上下各一个）
// ============================================================
interface NeighborNodeData {
  label: string; deviceType: string; color: string; compact: boolean
  model?: string; ip?: string
  handleMode?: 'top' | 'bottom' | 'both'
}

function toDisplayType(type: string): string {
  if (type === 'switch') return 'access-switch'
  if (type === 'router') return 'router'
  if (type === 'firewall') return 'firewall'
  if (type === 'sdwan') return 'sdwan'
  if (type === 'wireless') return 'wireless'
  if (type === 'server' || type === 'esxi') return 'server'
  return 'server'
}

function NeighborDeviceNode({ data, selected }: NodeProps) {
  const { label, deviceType, color, compact, model, ip, handleMode } = data as unknown as NeighborNodeData
  const dt = toDisplayType(deviceType)
  const nc = getNodeColors(dt)
  const Icon = DEVICE_ICONS[deviceType] || DevicesOtherIcon
  const w = compact ? COMPACT_W : NEIGHBOR_W
  const h = compact ? COMPACT_H : NEIGHBOR_H
  const isHl = selected || (data as any).highlighted
  const glowColor = nc.glow

  return (
    <Box sx={{
      width: w, height: h, borderRadius: '10px',
      border: '2px solid', borderColor: isHl ? '#e2e8f0' : nc.border,
      bgcolor: `${nc.fill}20`,
      position: 'relative', display: 'flex', alignItems: 'center', gap: 1.5, px: 2,
      cursor: 'pointer', transition: 'all 180ms ease', backdropFilter: 'blur(4px)',
      boxShadow: isHl
        ? `0 0 32px ${glowColor}99, 0 4px 16px ${glowColor}66`
        : `0 0 32px ${glowColor}99, 0 4px 16px ${glowColor}66`,
      '&:hover': { boxShadow: `0 0 48px ${glowColor}CC, 0 6px 24px ${glowColor}99`, borderColor: nc.border },
    }}>
      {(handleMode !== 'bottom') && (
        <Handle type="target" position={Position.Top} id="t"
          style={{ width: 9, height: 9, background: nc.border, border: `2px solid ${glowColor}`, borderRadius: '50%', top: -4, left: '50%', transform: 'translateX(-50%)' }} />
      )}
      {(handleMode !== 'top') && (
        <Handle type="target" position={Position.Bottom} id="b"
          style={{ width: 9, height: 9, background: nc.border, border: `2px solid ${glowColor}`, borderRadius: '50%', bottom: -4, left: '50%', transform: 'translateX(-50%)' }} />
      )}

      <Icon sx={{ fontSize: compact ? 32 : 36, color: glowColor, flexShrink: 0, filter: `drop-shadow(0 0 8px ${glowColor}80)` }} />
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 0.2 }}>
        <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '1rem', fontWeight: 700, color: glowColor, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textShadow: `0 0 10px ${glowColor}66` }}>
          {label}
        </Typography>
        {model && (
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.82rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{model}</Typography>
        )}
        {ip && (
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.82rem', fontWeight: 500, color: '#CBD5E1', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ip}</Typography>
        )}
      </Box>
    </Box>
  )
}

const nodeTypes = { switchNode: SwitchNode, neighborNode: NeighborDeviceNode }
const edgeTypes = { pipe: PipeEdge }

/** 堆叠成员标签格式化：PVGD1SWI01-M1 → PVGD1SWI01 (Member 1) */
function formatDevLabel(name: string): string {
  const m = name.match(/^(.+)-M(\d+)$/)
  return m ? `${m[1]} (Member ${m[2]})` : name
}

// ============================================================
// 管道走线组件
// ============================================================
function PipeEdge({ id, sourceX, sourceY, targetX, targetY, data, markerEnd, style }: EdgeProps) {
  const d = useMemo(() => {
    const { horizPipes, vertPipeX, sourcePipeIdx, targetPipeIdx, swap } = (data || {}) as {
      horizPipes: number[]; vertPipeX: number; sourcePipeIdx: number; targetPipeIdx: number; swap?: boolean
    }
    if (horizPipes == null || vertPipeX == null) {
      return `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`
    }

    // swap=true: 邻居高层 → 路径从 target 出发到 source
    const sx = swap ? targetX : sourceX
    const sy = swap ? targetY : sourceY
    const tx = swap ? sourceX : targetX
    const ty = swap ? sourceY : targetY
    const sp = sourcePipeIdx  // 始终是高层管道
    const tp = targetPipeIdx  // 始终是低层管道

    const CORNER_R = 12
    let waypoints: number[][]
    if (sp === tp) {
      const py = horizPipes[sp]
      waypoints = [[sx, sy], [sx, py], [tx, py], [tx, ty]]
    } else {
      const spy = horizPipes[sp]
      const tpy = horizPipes[tp]
      const vx = vertPipeX
      waypoints = [[sx, sy], [sx, spy], [vx, spy], [vx, tpy], [tx, tpy], [tx, ty]]
    }
    return buildRoundedPath(waypoints, CORNER_R)
  }, [sourceX, sourceY, targetX, targetY, data])

  return <BaseEdge id={id} path={d} markerEnd={markerEnd} style={style} />
}

function clamp(v: number, lo: number, hi: number): number { return Math.max(lo, Math.min(hi, v)) }

/** 用二次贝塞尔在拐角处生成圆弧过渡 */
function buildRoundedPath(pts: number[][], r: number): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i - 1]
    const [x1, y1] = pts[i]
    const [x2, y2] = pts[i + 1]
    const dx1 = x1 - x0, dy1 = y1 - y0
    const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1) || 1
    const dx2 = x2 - x1, dy2 = y2 - y1
    const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2) || 1
    const cr = Math.min(r, len1, len2)
    const ax = x1 - (dx1 / len1) * cr, ay = y1 - (dy1 / len1) * cr
    const bx = x1 + (dx2 / len2) * cr, by = y1 + (dy2 / len2) * cr
    d += ` L ${ax} ${ay}`
    d += ` Q ${x1} ${y1} ${bx} ${by}`
  }
  const last = pts[pts.length - 1]
  d += ` L ${last[0]} ${last[1]}`
  return d
}

// ============================================================
// 主组件
// ============================================================
interface DevRow { name: string; type: string; ifaces: string[]; isEndpoint: boolean; model: string; ip: string }

interface Props {
  deviceName: string; neighbors: NeighborNode[]
  stackMembers?: string[]; memberNeighbors?: Record<string, NeighborNode[]>
  deviceNotes?: string; deviceModel?: string; deviceIp?: string
}

export default function PortTopologyCanvas({
  deviceName, neighbors, stackMembers, memberNeighbors, deviceNotes, deviceModel, deviceIp,
}: Props) {
  const isCore = /核心|core/i.test(deviceNotes || '')
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null)
  const [offsets, setOffsets] = useState<Record<string, { dx: number; dy: number }>>({})
  const rfInstance = useRef<ReactFlowInstance | null>(null)
  const { t, lang } = useI18n()

  // ====== 邻居堆叠检测 ======
  const neighborStackMap = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const n of neighbors) {
      const nm = (n as any).neighbor_members as string[] | undefined
      if (nm && nm.length > 1 && n.device_name) m.set(n.device_name, nm)
    }
    return m
  }, [neighbors])

  // ====== 设备信息映射（堆叠邻居展开为多成员） ======
  const devInfo = useMemo(() => {
    const map = new Map<string, { type: string; ifaces: string[]; isEp: boolean; model: string; ip: string }>()
    const valid = neighbors.filter(n => n.device_name && n.device_name !== deviceName && !isStackLink(n.description) && !isLagInterface(n.interface))
    // 收集每个逻辑设备的全部 ifaces
    const raw = new Map<string, { type: string; ifaces: string[]; isEp: boolean; model: string; ip: string }>()
    for (const n of valid) {
      let key: string; let dtype: string; let isEp: boolean
      const pfx = ENDPOINT_PREFIXES.find(ep => n.device_name.startsWith(ep.prefix))
      if (pfx) { key = pfx.label; dtype = 'endpoint'; isEp = true }
      else { key = n.device_name; dtype = n.device_type; isEp = n.is_endpoint }
      if (!raw.has(key)) raw.set(key, { type: dtype, ifaces: [], isEp, model: (n as any).neighbor_model || '', ip: (n as any).neighbor_ip || '' })
      raw.get(key)!.ifaces.push(n.interface)
    }
    // 展开堆叠邻居
    for (const [name, info] of raw) {
      const stk = neighborStackMap.get(name)
      if (stk && info.type === 'switch') {
        stk.forEach((m, mi) => {
          const mk = `${name}-M${m}`
          map.set(mk, { ...info, ifaces: info.ifaces.filter((_, i) => i % stk.length === mi) })
        })
      } else {
        map.set(name, info)
      }
    }
    return map
  }, [neighbors, neighborStackMap])

  // ====== 模板：分层构建 ======
  const { nodes, edges, horizPipes: pipeLines, vertPipeX: vertLineX } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const valid = neighbors.filter(n => n.device_name && n.device_name !== deviceName && !isStackLink(n.description) && !isLagInterface(n.interface))
    const hasStack = !!(stackMembers && stackMembers.length > 1 && memberNeighbors)

    // 判断邻居交换机是否为上游核心（YAML notes 含"核心"/"Core"/"core"）
    // 堆叠展开名 PVGD1SWI01-M1 → 原始名 PVGD1SWI01，查找 neighbors
    function isCoreSwitch(name: string): boolean {
      const orig = name.replace(/-M\d+$/, '')
      const notes = (neighbors.find(n => n.device_name === orig) as any)?.neighbor_notes || ''
      const nLow = notes.toLowerCase()
      return nLow.includes('核心') || nLow.includes('core')
    }

    // 分类
    const wanList: DevRow[] = []
    const upstreamCoreList: DevRow[] = []
    const downstreamSwList: DevRow[] = []
    const endpointList: DevRow[] = []

    for (const [name, info] of devInfo) {
      const d: DevRow = { name, type: info.type, ifaces: info.ifaces, isEndpoint: info.isEp, model: info.model, ip: info.ip }
      if (isWanDevice(info.type, name)) { wanList.push(d) }
      else if (info.type === 'switch') {
        if (isCoreSwitch(name)) { upstreamCoreList.push(d) }
        else { downstreamSwList.push(d) }
      }
      else { endpointList.push(d) }
    }

    // 模板层：空层折叠
    interface Layer { label: string; isSelectedSwitch: boolean; devs: DevRow[]; stackGap: boolean }
    const layers: Layer[] = []

    if (isCore) {
      if (wanList.length > 0) layers.push({ label: 'WAN', isSelectedSwitch: false, devs: wanList, stackGap: false })
      layers.push({ label: 'Core', isSelectedSwitch: true, devs: [], stackGap: false })
      const L3 = [...downstreamSwList, ...endpointList]
      if (L3.length > 0) layers.push({ label: 'Access', isSelectedSwitch: false, devs: L3, stackGap: true })
    } else {
      if (wanList.length > 0) layers.push({ label: 'WAN', isSelectedSwitch: false, devs: wanList, stackGap: false })
      if (upstreamCoreList.length > 0) layers.push({ label: 'Core', isSelectedSwitch: false, devs: upstreamCoreList, stackGap: false })
      layers.push({ label: 'Access', isSelectedSwitch: true, devs: [], stackGap: false })
      const L4 = [...downstreamSwList, ...endpointList]
      if (L4.length > 0) layers.push({ label: 'End', isSelectedSwitch: false, devs: L4, stackGap: false })
    }

    // 折叠空层：移除无设备的非交换机行
    const activeLayers = layers.filter(l => l.isSelectedSwitch || l.devs.length > 0)

    function devW(d: DevRow): number { return d.isEndpoint ? COMPACT_W : (d.model || d.ip) ? MANAGED_W : NEIGHBOR_W }
    function devH(d: DevRow): number { return d.isEndpoint ? COMPACT_H : (d.model || d.ip) ? MANAGED_H : NEIGHBOR_H }
    function layerW(l: Layer): number {
      if (l.isSelectedSwitch) return (hasStack ? stackMembers!.length : 1) * SWITCH_W + ((hasStack ? stackMembers!.length : 1) - 1) * STACK_GAP
      const gap = l.stackGap ? STACK_GAP : DEVICE_GAP
      return l.devs.reduce((s, d) => s + (isSwitchDevice(d) ? SWITCH_W : devW(d)), 0) + Math.max(l.devs.length - 1, 0) * gap
    }
    function isSwitchDevice(d: DevRow): boolean {
      return !d.isEndpoint && d.type === 'switch'
    }
    function layerRowH(l: Layer): number {
      if (l.isSelectedSwitch) return SWITCH_H
      if (l.devs.some(d => isSwitchDevice(d))) return SWITCH_H
      return Math.max(NEIGHBOR_H, ...l.devs.map(d => devH(d)))
    }
    // handle 模板：交换机=both(switchNode), 首层非交换机=bottom, 末层非交换机=top, 端点=top
    function resolveHandleMode(layerIdx: number, totalLayers: number, dev: DevRow): 'top' | 'bottom' | 'switch' {
      if (dev.isEndpoint) return 'top'
      if (!dev.isEndpoint && dev.type === 'switch') return 'switch'
      if (layerIdx === 0) return 'bottom'                           // 首层非交换机
      if (layerIdx === totalLayers - 1) return 'top'                // 末层非交换机
      return 'bottom'  // 中间层非交换机默认 bottom（理论上不会出现）
    }

    const maxLayerW = Math.max(...activeLayers.map(l => layerW(l)))
    const canvasW = maxLayerW + 240
    let yCursor = 40
    const rowMetas: { yStart: number; maxH: number; maxRight: number; }[] = []
    const switchNodeIdSet = new Set<string>()
    let maxDeviceRight = 0

    // 选中交换机端口构建
    function buildSwitchPorts(ifaceList: NeighborNode[]): { top: typeof allTopPorts; bottom: typeof allTopPorts } {
      const allTopPorts: { id: string; label: string; color: string; neighborName: string }[] = []
      const allBottomPorts: { id: string; label: string; color: string; neighborName: string }[] = []
      for (const n of ifaceList) {
        const pn = extractPortNumber(n.interface)
        const ec = getEdgeColor(n.device_type, n.device_name)
        if (pn % 2 === 0) allBottomPorts.push({ id: n.interface, label: String(pn), color: ec, neighborName: n.device_name })
        else allTopPorts.push({ id: n.interface, label: String(pn), color: ec, neighborName: n.device_name })
      }
      allTopPorts.sort((a, b) => extractPortNumber(a.id) - extractPortNumber(b.id))
      allBottomPorts.sort((a, b) => extractPortNumber(a.id) - extractPortNumber(b.id))
      return { top: allTopPorts, bottom: allBottomPorts }
    }

    // 渲染每层
    for (const layer of activeLayers) {
      const rowYStart = yCursor
      const lw = layerW(layer)
      const startX = (canvasW - lw) / 2

      if (layer.isSelectedSwitch) {
        if (hasStack) {
          let cx = startX
          for (const member of stackMembers!) {
            const memberValid = (memberNeighbors![member] || [])
              .filter(n => n.device_name && n.device_name !== deviceName && !isStackLink(n.description) && !isLagInterface(n.interface))
            const { top, bottom } = buildSwitchPorts(memberValid)
            const nid = `switch-${member}`
            switchNodeIdSet.add(nid)
            nodes.push({ id: nid, type: 'switchNode', position: { x: cx, y: yCursor },
              data: { label: `${deviceName} (Member ${member})`, model: deviceModel, ip: deviceIp, topPorts: top, bottomPorts: bottom, color: SWITCH_COLOR, handleRole: 'source' } })
            maxDeviceRight = Math.max(maxDeviceRight, cx + SWITCH_W)
            cx += SWITCH_W + STACK_GAP
          }
        } else {
          const { top, bottom } = buildSwitchPorts(valid)
          const sx = (canvasW - SWITCH_W) / 2
          switchNodeIdSet.add('switch')
          nodes.push({ id: 'switch', type: 'switchNode', position: { x: sx, y: yCursor },
            data: { label: deviceName, model: deviceModel, ip: deviceIp, topPorts: top, bottomPorts: bottom, color: SWITCH_COLOR, handleRole: 'source' } })
          maxDeviceRight = Math.max(maxDeviceRight, sx + SWITCH_W)
        }
        rowMetas.push({ yStart: rowYStart, maxH: SWITCH_H, maxRight: startX + lw })
        yCursor += SWITCH_H + ROW_GAP
      } else {
        const gap = layer.stackGap ? STACK_GAP : DEVICE_GAP
        const rowH = layerRowH(layer)
        let cx = startX
        for (const dev of layer.devs) {
          const dc = getDeviceColor(dev.type)
          const dw = isSwitchDevice(dev) ? SWITCH_W : devW(dev)
          const dh = isSwitchDevice(dev) ? SWITCH_H : devH(dev)
          if (isSwitchDevice(dev) && dev.ifaces.length > 0) {
            const sTop: { id: string; label: string; color: string; neighborName: string }[] = []
            const sBot: { id: string; label: string; color: string; neighborName: string }[] = []
            for (const iface of dev.ifaces) {
              const pn = extractPortNumber(iface)
              const ec = getDeviceColor(dev.type)
              if (pn % 2 === 0) sBot.push({ id: iface, label: String(pn), color: ec, neighborName: dev.name })
              else sTop.push({ id: iface, label: String(pn), color: ec, neighborName: dev.name })
            }
            sTop.sort((a, b) => extractPortNumber(a.id) - extractPortNumber(b.id))
            sBot.sort((a, b) => extractPortNumber(a.id) - extractPortNumber(b.id))
            switchNodeIdSet.add(dev.name)
            nodes.push({ id: dev.name, type: 'switchNode', position: { x: cx, y: yCursor },
              data: { label: formatDevLabel(dev.name), model: dev.model, ip: dev.ip, topPorts: sTop, bottomPorts: sBot, color: SWITCH_COLOR, nodeWidth: dw, handleRole: 'target' } })
          } else {
            const hm = resolveHandleMode(activeLayers.indexOf(layer), activeLayers.length, dev)
            nodes.push({ id: dev.name, type: 'neighborNode', position: { x: cx, y: yCursor + (rowH - dh) / 2 },
              data: { label: formatDevLabel(dev.name), deviceType: dev.type, color: dc, compact: dev.isEndpoint, model: dev.model, ip: dev.ip, handleMode: hm === 'switch' ? 'both' : hm } })
          }
          maxDeviceRight = Math.max(maxDeviceRight, cx + dw)
          cx += dw + gap
        }
        rowMetas.push({ yStart: rowYStart, maxH: rowH, maxRight: startX + lw })
        yCursor += rowH + ROW_GAP
      }
    }

    // ============ 管道系统 ============
    const horizPipes: number[] = []
    if (rowMetas.length > 0) {
      horizPipes.push(rowMetas[0].yStart - ROW_GAP * 0.55)
      for (let i = 0; i < rowMetas.length - 1; i++) {
        const prevBottom = rowMetas[i].yStart + rowMetas[i].maxH
        const nextTop = rowMetas[i + 1].yStart
        horizPipes.push((prevBottom + nextTop) / 2)
      }
      const last = rowMetas[rowMetas.length - 1]
      horizPipes.push(last.yStart + last.maxH + ROW_GAP * 0.55)
    }
    const vertPipeX = maxDeviceRight + 100

    // ============ 连线 ============
    const edgeSources: { srcNodeId: string; neighbor: NeighborNode; srcIsTopHandle: boolean }[] = []
    if (hasStack) {
      for (const member of stackMembers!) {
        for (const n of (memberNeighbors![member] || [])) {
          if (!n.device_name || n.device_name === deviceName || isStackLink(n.description) || isLagInterface(n.interface)) continue
          edgeSources.push({ srcNodeId: `switch-${member}`, neighbor: n, srcIsTopHandle: extractPortNumber(n.interface) % 2 !== 0 })
        }
      }
    } else {
      for (const n of valid) {
        edgeSources.push({ srcNodeId: 'switch', neighbor: n, srcIsTopHandle: extractPortNumber(n.interface) % 2 !== 0 })
      }
    }

    const nodeToRow = new Map<string, number>()
    for (const n of nodes) {
      for (let i = rowMetas.length - 1; i >= 0; i--) {
        if (n.position.y >= rowMetas[i].yStart) { nodeToRow.set(n.id, i); break }
      }
      if (!nodeToRow.has(n.id)) nodeToRow.set(n.id, 0)
    }

    for (const { srcNodeId, neighbor: n, srcIsTopHandle } of edgeSources) {
      let targetName = n.device_name
      const stk = neighborStackMap.get(n.device_name)
      if (stk) {
        const ifaceIdx = valid.filter(v => v.device_name === n.device_name).findIndex(v => v.interface === n.interface)
        const memberIdx = ifaceIdx >= 0 ? ifaceIdx % stk.length : 0
        targetName = `${n.device_name}-M${stk[memberIdx]}`
      }
      for (const ep of ENDPOINT_PREFIXES) { if (n.device_name.startsWith(ep.prefix)) { targetName = ep.label; break } }
      const srcRow = nodeToRow.get(srcNodeId) ?? 0
      const tgtRow = nodeToRow.get(targetName) ?? (rowMetas.length - 1)
      const tgtNode = nodes.find(nn => nn.id === targetName)

      // targetHandle（面向连接的方向）
      const targetIsTop = tgtNode?.type === 'switchNode'
        ? extractPortNumber(n.interface) % 2 !== 0
        : tgtRow > srcRow  // 目标在源下方 → 用目标的上部 handle
      const targetHandle = tgtNode?.type === 'switchNode' ? n.interface : (targetIsTop ? 't' : 'b')

      // 管道索引：top handle → pipe[row], bottom handle → pipe[row+1]
      const srcPipe = clamp(srcIsTopHandle ? srcRow : srcRow + 1, 0, horizPipes.length - 1)
      const tgtPipe = clamp(targetIsTop ? tgtRow : tgtRow + 1, 0, horizPipes.length - 1)

      // 物理连线方向：高层设备出发。高层行号更小
      const swap = tgtRow < srcRow  // 邻居在上方（高层）→ swap 路径
      const pipeSrc = swap ? tgtPipe : srcPipe  // 高层设备的管道
      const pipeTgt = swap ? srcPipe : tgtPipe  // 低层设备的管道

      const ec = getEdgeColor(n.device_type, n.device_name)
      const isWan = isWanDevice(n.device_type, n.device_name)
      edges.push({
        id: `e-${srcNodeId}-${n.interface}-${targetName}`,
        source: srcNodeId, sourceHandle: n.interface,
        target: targetName, targetHandle,
        type: 'pipe',
        data: { horizPipes, vertPipeX, sourcePipeIdx: pipeSrc, targetPipeIdx: pipeTgt, swap },
        style: { stroke: ec, strokeWidth: isWan ? 3 : 2.5, opacity: 0.85 },
        markerEnd: { type: MarkerType.ArrowClosed, color: ec, width: 8, height: 8 },
      })
    }

    return { nodes, edges, horizPipes, vertPipeX }
  }, [devInfo, isCore, deviceName, deviceModel, deviceIp, neighbors, stackMembers, memberNeighbors, neighborStackMap])


  // ====== 交互 ======
  const onNodeClick = useCallback((_e: React.MouseEvent, n: Node) => {
    if (!n.id.startsWith('_')) setSelectedTarget(p => p === n.id ? null : n.id)
  }, [])
  const onEdgeClick = useCallback((_e: React.MouseEvent, e: Edge) => {
    if (e.source) setSelectedTarget(p => p === e.source ? null : e.source)
  }, [])
  const onPaneClick = useCallback(() => setSelectedTarget(null), [])

  const positionedNodes = useMemo(() =>
    nodes.map(n => {
      const off = offsets[n.id]; if (!off) return n
      return { ...n, position: { x: n.position.x + off.dx, y: n.position.y + off.dy } }
    }), [nodes, offsets])

  const finalNodes = useMemo(() => {
    if (!selectedTarget) return positionedNodes
    return positionedNodes.map(n => {
      if (n.id.startsWith('_')) return n
      return n.id === selectedTarget
        ? { ...n, data: { ...n.data, highlighted: true }, selected: true }
        : { ...n, style: { opacity: 0.15 } }
    })
  }, [positionedNodes, selectedTarget])

  const finalEdges = useMemo(() => {
    if (!selectedTarget) return edges
    const isSwitchSelected = selectedTarget.startsWith('switch')
    return edges.map(e => {
      const match = isSwitchSelected ? e.source === selectedTarget : e.source === selectedTarget || e.target === selectedTarget
      return match
        ? { ...e, style: { ...e.style, strokeWidth: 4, opacity: 1 }, animated: true }
        : { ...e, style: { ...e.style, opacity: 0.05 }, markerEnd: undefined }
    })
  }, [edges, selectedTarget])

  if (neighbors.filter(n => n.device_name && n.device_name !== deviceName && !isStackLink(n.description) && !isLagInterface(n.interface)).length === 0) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500 }}>
        <Typography sx={{ fontSize: '1.25rem', color: 'text.secondary' }}>未发现邻居设备</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider', bgcolor: '#0a0e1a' }}>
      <style>{`.react-flow__edge{cursor:pointer!important}`}</style>

      {/* 左侧控件栏 — 图例 / 导出 / 方向键 / 缩放，均分垂直空间 */}
      <Box
        sx={{
          width: SIDEBAR_W, flexShrink: 0,
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between', py: 1, px: 0.5,
          bgcolor: 'rgba(15, 18, 35, 0.92)', borderRight: '1px solid', borderColor: 'divider',
        }}
      >
        {/* 图例 */}
        <Paper
          sx={{
            px: 0.6, py: 0.4, borderRadius: 2,
            bgcolor: 'rgba(15, 18, 35, 0.82)', backdropFilter: 'blur(10px)',
            border: '1px solid', borderColor: 'divider',
          }}
        >
          <Typography sx={{ fontSize: '0.5rem', fontWeight: 700, color: 'text.disabled', mb: 0.3, letterSpacing: '0.04em', textTransform: 'uppercase', textAlign: 'center' }}>
            {t('topology.legend')}
          </Typography>
          <Stack gap={0.1}>
            {PORT_TOPOLOGY_LEGEND.map((item) => (
              <Box key={item.type} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <Box sx={{ width: 6, height: 6, borderRadius: '2px', bgcolor: item.color, flexShrink: 0 }} />
                <Typography sx={{ fontSize: '0.5rem', fontWeight: 500, color: '#cbd5e1', lineHeight: 1.2, whiteSpace: 'nowrap' }}>
                  {lang === 'zh' ? item.labelZh : item.labelEn}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Paper>

        {/* 导出 */}
        <Paper
          sx={{
            px: 0.3, py: 0.2, borderRadius: 2, display: 'flex', justifyContent: 'center',
            bgcolor: 'rgba(15, 18, 35, 0.82)', backdropFilter: 'blur(10px)',
            border: '1px solid #334155',
          }}
        >
          <Stack direction="row" spacing={0.1} alignItems="center">
            <Tooltip title="Export PNG">
              <IconButton size="small" onClick={() => {
                const el = document.querySelector('.react-flow') as HTMLElement
                if (el) toPng(el, { backgroundColor: '#0a0e1a', pixelRatio: 2 }).then((u: string) => {
                  const a = document.createElement('a'); a.download = `port-topology-${deviceName}.png`; a.href = u; a.click()
                })
              }} sx={{ color: '#94a3b8', '&:hover': { color: '#2DD46E' }, p: 0.4 }}>
                <ImageIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Export Visio">
              <IconButton size="small" onClick={() => {
                import('../../services/api').then(({ topologyApi }) => {
                  topologyApi.exportVisio({ nodes: finalNodes.map(n => ({ id: n.id, label: n.data.label, type: n.data.deviceType, platform: n.data.platform || '' })), edges: finalEdges.map(e => ({ source: e.source, target: e.target, source_interface: e.data?.label || e.label || '' })) }).then((b: Blob) => {
                    const u = URL.createObjectURL(b); const a = document.createElement('a')
                    a.download = `port-topology-${deviceName}.vdx`; a.href = u; a.click()
                  })
                })
              }} sx={{ color: '#94a3b8', '&:hover': { color: '#8B5CF6' }, p: 0.4 }}>
                <VisioIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        </Paper>

        {/* 方向键（隐藏时占位，保持布局稳定） */}
        <Box sx={{ display: 'flex', justifyContent: 'center', visibility: selectedTarget ? 'visible' : 'hidden' }}>
          <DirectionPad
            step={40}
            onUp={() => setOffsets(p => ({ ...p, [selectedTarget!]: { dx: (p[selectedTarget!]?.dx || 0), dy: (p[selectedTarget!]?.dy || 0) - 40 } }))}
            onDown={() => setOffsets(p => ({ ...p, [selectedTarget!]: { dx: (p[selectedTarget!]?.dx || 0), dy: (p[selectedTarget!]?.dy || 0) + 40 } }))}
            onLeft={() => setOffsets(p => ({ ...p, [selectedTarget!]: { dx: (p[selectedTarget!]?.dx || 0) - 40, dy: (p[selectedTarget!]?.dy || 0) } }))}
            onRight={() => setOffsets(p => ({ ...p, [selectedTarget!]: { dx: (p[selectedTarget!]?.dx || 0) + 40, dy: (p[selectedTarget!]?.dy || 0) } }))}
            onReset={() => setOffsets({})}
          />
        </Box>

        {/* 缩放按钮 — 水平排列 */}
        <ZoomControls instance={rfInstance.current} />
      </Box>

      {/* 画布区域 */}
      <Box sx={{ flex: 1, position: 'relative' }}>
        <ReactFlow
          nodes={finalNodes} edges={finalEdges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
          fitView fitViewOptions={{ padding: 0.04, duration: 200 }}
          minZoom={0.1} maxZoom={3}
          nodesDraggable
          onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} onPaneClick={onPaneClick}
          onInit={(inst) => { rfInstance.current = inst }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e293b" gap={24} />
        </ReactFlow>
      </Box>
    </Box>
  )
}

// ============================================================
// 水平缩放控件（替代 ReactFlow Controls）
// ============================================================
function ZoomControls({ instance }: { instance: ReactFlowInstance | null }) {
  const btnSx = { color: '#94a3b8', '&:hover': { color: '#e2e8f0' }, p: 0.4 }

  return (
    <Paper
      sx={{
        px: 0.3, py: 0.2, borderRadius: 2, display: 'flex', justifyContent: 'center',
        bgcolor: 'rgba(15, 18, 35, 0.82)', backdropFilter: 'blur(10px)',
        border: '1px solid #334155',
      }}
    >
      <Stack direction="row" spacing={0.1} alignItems="center">
        <IconButton size="small" onClick={() => instance?.zoomIn({ duration: 200 })} sx={btnSx}>
          <ZoomInIcon fontSize="small" />
        </IconButton>
        <IconButton size="small" onClick={() => instance?.zoomOut({ duration: 200 })} sx={btnSx}>
          <ZoomOutIcon fontSize="small" />
        </IconButton>
        <IconButton size="small" onClick={() => instance?.fitView({ duration: 200, padding: 0.04 })} sx={{ ...btnSx, color: '#64748b' }}>
          <FitViewIcon fontSize="small" />
        </IconButton>
      </Stack>
    </Paper>
  )
}
