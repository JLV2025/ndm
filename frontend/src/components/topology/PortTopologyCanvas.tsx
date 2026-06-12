import { useMemo, useState, useCallback } from 'react'
import {
  ReactFlow, Node, Edge, Background, Controls, MarkerType, Handle, Position,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Typography, IconButton, Stack, Tooltip, Paper } from '@mui/material'
import {
  Image as ImageIcon, AccountTree as VisioIcon,
  Hub as HubIcon, Lan as LanIcon, Router as RouterIcon,
  Security as SecurityIcon, Public as PublicIcon,
  Wifi as WifiIcon, Dns as DnsIcon, DevicesOther as DevicesOtherIcon,
} from '@mui/icons-material'
import { toPng } from 'html-to-image'
import { getDeviceColor, getNodeColors, ENDPOINT_PREFIXES, isStackLink } from '../../shared/constants'
import type { NeighborNode } from '../../types/topology'
import DirectionPad from './DirectionPad'

// ============================================================
// 布局常量
// ============================================================
const SWITCH_W = 840
const SWITCH_H = 250
const HANDLE_SIZE = 8
const NEIGHBOR_W = 280
const NEIGHBOR_H = 110
const MANAGED_W = 320
const MANAGED_H = 110
const COMPACT_W = 190
const COMPACT_H = 56
const ROW_GAP = 140
const DEVICE_GAP = 44
const STACK_GAP = 24
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
}

function SwitchNode({ data }: NodeProps) {
  const { label, model, ip, topPorts, bottomPorts, color } = data as unknown as SwitchNodeData

  return (
    <Box sx={{
      width: SWITCH_W, height: SWITCH_H, position: 'relative',
      borderRadius: 2, border: '2px solid', borderColor: `${color}99`,
      bgcolor: `${color}08`,
      boxShadow: `0 0 32px ${color}22, 0 4px 16px rgba(0,0,0,0.55), inset 0 1px 0 ${color}14`,
      fontFamily: '"Fira Code","Consolas",monospace',
    }}>
      <Box sx={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <HubIcon sx={{ fontSize: 40, color, filter: `drop-shadow(0 0 8px ${color}80)` }} />
          <Typography sx={{ fontWeight: 700, fontSize: '1.35rem', color: '#e2e8f0', letterSpacing: '0.04em', textShadow: `0 0 20px ${color}30` }}>
            {label}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 3, mt: 0.5 }}>
          {model && <Typography sx={{ fontSize: '0.88rem', color: '#94A3B8', fontFamily: '"Fira Code",monospace', fontWeight: 500 }}>{model}</Typography>}
          {ip && <Typography sx={{ fontSize: '0.88rem', color: '#CBD5E1', fontFamily: '"Fira Code",monospace', fontWeight: 500 }}>{ip}</Typography>}
        </Box>
      </Box>
      <Box sx={{ position: 'absolute', top: SWITCH_H * 0.35, left: '15%', width: '70%', height: 1, background: `linear-gradient(90deg,transparent,${color}35,transparent)` }} />
      <Box sx={{ position: 'absolute', bottom: SWITCH_H * 0.35, left: '15%', width: '70%', height: 1, background: `linear-gradient(90deg,transparent,${color}35,transparent)` }} />

      {topPorts.map((p, idx) => {
        const x = getHandleX(idx, topPorts.length)
        return (
          <Box key={`tv-${p.id}`} sx={{ position: 'absolute', left: x - 16, top: -10, width: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2 }}>
            <Typography sx={{ fontSize: '0.65rem', color: '#94a3b8', mb: 0.3, fontFamily: '"Fira Code","Consolas",monospace', fontWeight: 500, lineHeight: 1, whiteSpace: 'nowrap' }}>{p.label}</Typography>
            <Handle id={p.id} type="source" position={Position.Top} style={{ position: 'relative', left: 0, top: 0, transform: 'none', width: HANDLE_SIZE, height: HANDLE_SIZE, background: p.color, borderRadius: 2, border: 'none' }} />
          </Box>
        )
      })}
      {bottomPorts.map((p, idx) => {
        const x = getHandleX(idx, bottomPorts.length)
        return (
          <Box key={`bv-${p.id}`} sx={{ position: 'absolute', left: x - 16, bottom: -10, width: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2 }}>
            <Handle id={p.id} type="source" position={Position.Bottom} style={{ position: 'relative', left: 0, bottom: 0, transform: 'none', width: HANDLE_SIZE, height: HANDLE_SIZE, background: p.color, borderRadius: 2, border: 'none' }} />
            <Typography sx={{ fontSize: '0.65rem', color: '#94a3b8', mt: 0.3, fontFamily: '"Fira Code","Consolas",monospace', fontWeight: 500, lineHeight: 1, whiteSpace: 'nowrap' }}>{p.label}</Typography>
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
  const { label, deviceType, color, compact, model, ip } = data as unknown as NeighborNodeData
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
      <Handle type="target" position={Position.Top} id="t"
        style={{ width: 9, height: 9, background: nc.border, border: `2px solid ${glowColor}`, borderRadius: '50%', top: -4, left: '50%', transform: 'translateX(-50%)' }} />
      <Handle type="target" position={Position.Bottom} id="b"
        style={{ width: 9, height: 9, background: nc.border, border: `2px solid ${glowColor}`, borderRadius: '50%', bottom: -4, left: '50%', transform: 'translateX(-50%)' }} />

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
  const isCore = (deviceNotes || '').includes('核心')
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null)
  const [offsets, setOffsets] = useState<Record<string, { dx: number; dy: number }>>({})

  // ====== 设备信息映射 ======
  const devInfo = useMemo(() => {
    const map = new Map<string, { type: string; ifaces: string[]; isEp: boolean; model: string; ip: string }>()
    const valid = neighbors.filter(n => n.device_name && !isStackLink(n.description))
    for (const n of valid) {
      let key: string; let dtype: string; let isEp: boolean; let prefixMatch = false
      for (const ep of ENDPOINT_PREFIXES) {
        if (n.device_name.startsWith(ep.prefix)) {
          key = ep.label; dtype = 'endpoint'; isEp = true; prefixMatch = true; break
        }
      }
      if (!prefixMatch) { key = n.device_name; dtype = n.device_type; isEp = n.is_endpoint }
      if (!map.has(key)) map.set(key, { type: dtype, ifaces: [], isEp, model: (n as any).neighbor_model || '', ip: (n as any).neighbor_ip || '' })
      map.get(key)!.ifaces.push(n.interface)
    }
    return map
  }, [neighbors])

  // ====== 构建行布局 ======
  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const valid = neighbors.filter(n => n.device_name && !isStackLink(n.description))

    // --- 分类设备 ---
    const wanList: DevRow[] = []
    const swList: DevRow[] = []
    const accessList: DevRow[] = []

    for (const [name, info] of devInfo) {
      const d: DevRow = { name, type: info.type, ifaces: info.ifaces, isEndpoint: info.isEp, model: info.model, ip: info.ip }
      if (isWanDevice(info.type, name)) wanList.push(d)
      else if (info.type === 'switch') swList.push(d)
      else accessList.push(d)
    }

    // --- 确定各行的设备列表 ---
    type RowDef = { label: string; devices: DevRow[]; isSwitch: boolean; stackGap: boolean }
    const rows: RowDef[] = []

    if (wanList.length > 0) rows.push({ label: 'WAN', devices: wanList, isSwitch: false, stackGap: false })

    // 交换机行（本设备，占位不放邻居节点）
    rows.push({ label: 'Switch', devices: [], isSwitch: true, stackGap: false })

    if (swList.length > 0) {
      rows.push({ label: 'AccessSwitches', devices: swList, isSwitch: false, stackGap: true })  // stackGap 表示堆叠交换机间距
    }

    // 末端设备
    if (accessList.length > 0) {
      if (isCore) {
        // 核心交换机 → 末端和接入交换机同行
        const lastRow = rows[rows.length - 1]
        if (lastRow && lastRow.label === 'AccessSwitches') {
          lastRow.devices.push(...accessList)
        } else {
          rows.push({ label: 'End', devices: accessList, isSwitch: false, stackGap: false })
        }
      } else {
        // 接入交换机 → 末端单独一行
        rows.push({ label: 'End', devices: accessList, isSwitch: false, stackGap: false })
      }
    }

    // 去掉空设备行
    const activeRows = rows.filter(r => r.isSwitch || r.devices.length > 0)

    // --- 交换机端口 ---
    const topPorts: { id: string; label: string; color: string; neighborName: string }[] = []
    const bottomPorts: { id: string; label: string; color: string; neighborName: string }[] = []

    for (const n of valid) {
      const pn = extractPortNumber(n.interface)
      const ec = getEdgeColor(n.device_type, n.device_name)
      if (pn % 2 === 0) bottomPorts.push({ id: n.interface, label: String(pn), color: ec, neighborName: n.device_name })
      else topPorts.push({ id: n.interface, label: String(pn), color: ec, neighborName: n.device_name })
    }
    topPorts.sort((a, b) => extractPortNumber(a.id) - extractPortNumber(b.id))
    bottomPorts.sort((a, b) => extractPortNumber(a.id) - extractPortNumber(b.id))

    // --- 计算行宽 ---
    function devW(dev: DevRow): number {
      if (dev.isEndpoint) return COMPACT_W
      if (dev.model || dev.ip) return MANAGED_W
      return NEIGHBOR_W
    }
    function devH(dev: DevRow): number {
      if (dev.isEndpoint) return COMPACT_H
      if (dev.model || dev.ip) return MANAGED_H
      return NEIGHBOR_H
    }
    function rowWidth(row: RowDef): number {
      if (row.isSwitch) return SWITCH_W
      const gap = row.stackGap ? STACK_GAP : DEVICE_GAP
      return row.devices.reduce((s, d) => s + devW(d), 0) + Math.max(row.devices.length - 1, 0) * gap
    }

    const maxRowW = Math.max(...activeRows.map(r => rowWidth(r)))
    const padX = 120
    const canvasW = maxRowW + padX * 2

    // --- 垂直布局 ---
    const switchRowIdx = activeRows.findIndex(r => r.isSwitch)
    const totalH = activeRows.length * NEIGHBOR_H
      + (activeRows.length - 1) * ROW_GAP
      + (activeRows.some(r => r.isSwitch) ? SWITCH_H - NEIGHBOR_H : 0)
      + 120

    // 构建节点
    let yCursor = 40

    for (const row of activeRows) {
      if (row.isSwitch) {
        // 交换机节点
        const switchX = (canvasW - SWITCH_W) / 2
        nodes.push({
          id: 'switch', type: 'switchNode',
          position: { x: switchX, y: yCursor },
          data: { label: deviceName, model: deviceModel, ip: deviceIp, topPorts, bottomPorts, color: SWITCH_COLOR },
        })
        yCursor += SWITCH_H + ROW_GAP
      } else {
        // 设备行 — 水平居中
        const gap = row.stackGap ? STACK_GAP : DEVICE_GAP
        const rw = row.devices.reduce((s, d) => s + devW(d), 0) + Math.max(row.devices.length - 1, 0) * gap
        const maxH = Math.max(...row.devices.map(d => devH(d)))
        const startX = (canvasW - rw) / 2
        let cx = startX
        for (const dev of row.devices) {
          const dc = getDeviceColor(dev.type)
          const dw = devW(dev)
          const dh = devH(dev)
          nodes.push({
            id: dev.name, type: 'neighborNode',
            position: { x: cx, y: yCursor + (maxH - dh) / 2 },
            data: { label: dev.name, deviceType: dev.type, color: dc, compact: dev.isEndpoint, model: dev.model, ip: dev.ip },
          })
          cx += dw + gap
        }
        yCursor += NEIGHBOR_H + ROW_GAP
      }
    }

    // --- 连线 ---
    // 判断目标设备在交换机上方还是下方
    const switchRowY = nodes.find(n => n.id === 'switch')?.position.y || 0
    const aboveSet = new Set<string>()
    const belowSet = new Set<string>()

    for (const n of nodes) {
      if (n.id === 'switch') continue
      if (n.position.y < switchRowY) aboveSet.add(n.id)
      else belowSet.add(n.id)
    }

    for (const n of valid) {
      let targetName = n.device_name
      for (const ep of ENDPOINT_PREFIXES) {
        if (n.device_name.startsWith(ep.prefix)) { targetName = ep.label; break }
      }
      // 上方设备从交换机底部出线，下方设备从交换机顶部出线？不对...
      // 上方设备(WAN)在交换机上面 → 交换机顶部 Handle 连上方设备底部 Handle
      // 下方设备(Access/End)在交换机下面 → 交换机底部 Handle 连下方设备顶部 Handle
      const isAbove = aboveSet.has(targetName)
      const targetHandle = isAbove ? 'b' : 't'
      const ec = getEdgeColor(n.device_type, n.device_name)
      const isWan = isWanDevice(n.device_type, n.device_name)
      edges.push({
        id: `e-${n.interface}-${targetName}`,
        source: 'switch', sourceHandle: n.interface,
        target: targetName, targetHandle,
        type: 'smoothstep',
        pathOptions: { borderRadius: 30, offset: 40 },
        style: { stroke: ec, strokeWidth: isWan ? 3 : 2.5, opacity: 0.85 },
        markerEnd: { type: MarkerType.ArrowClosed, color: ec, width: 8, height: 8 },
      })
    }

    return { nodes, edges }
  }, [devInfo, isCore, deviceName, deviceModel, neighbors])

  // ====== 交互 ======
  const onNodeClick = useCallback((_e: React.MouseEvent, n: Node) => {
    if (n.id !== 'switch' && !n.id.startsWith('_')) setSelectedTarget(p => p === n.id ? null : n.id)
  }, [])
  const onEdgeClick = useCallback((_e: React.MouseEvent, e: Edge) => {
    if (e.target && e.target !== 'switch') setSelectedTarget(p => p === e.target ? null : e.target)
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
      if (n.id === 'switch' || n.id.startsWith('_')) return n
      return n.id === selectedTarget
        ? { ...n, data: { ...n.data, highlighted: true }, selected: true }
        : { ...n, style: { opacity: 0.15 } }
    })
  }, [positionedNodes, selectedTarget])

  const finalEdges = useMemo(() => {
    if (!selectedTarget) return edges
    return edges.map(e =>
      e.target === selectedTarget
        ? { ...e, style: { ...e.style, strokeWidth: 4, opacity: 1 }, animated: true }
        : { ...e, style: { ...e.style, opacity: 0.05 }, markerEnd: undefined }
    )
  }, [edges, selectedTarget])

  if (neighbors.filter(n => n.device_name && !isStackLink(n.description)).length === 0) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500 }}>
        <Typography sx={{ fontSize: '1.25rem', color: 'text.secondary' }}>未发现邻居设备</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ width: '100%', height: '100%', borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider', bgcolor: '#0a0e1a', position: 'relative' }}>
      <style>{`.react-flow__controls-button{background:#1e293b!important;border:1px solid #334155!important;fill:#e2e8f0!important;width:32px!important;height:32px!important}.react-flow__controls-button svg{fill:#e2e8f0!important;max-width:16px!important;max-height:16px!important}.react-flow__controls-button:hover{background:#334155!important}.react-flow__controls{background:#0f172a!important;border:1px solid #1e293b!important;border-radius:8px!important;overflow:hidden!important}.react-flow__edge{cursor:pointer!important}`}</style>
      <ReactFlow
        nodes={finalNodes} edges={finalEdges} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.04, duration: 200 }}
        minZoom={0.1} maxZoom={3}
        nodesDraggable
        onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} onPaneClick={onPaneClick}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={24} />
        <Controls />
      </ReactFlow>

      {/* 导出 */}
      <Paper sx={{ position: 'absolute', top: 12, right: 12, zIndex: 20, borderRadius: 2, bgcolor: 'rgba(15, 18, 35, 0.85)', backdropFilter: 'blur(8px)', border: '1px solid #334155', px: 0.5, py: 0.3 }}>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Tooltip title="Export PNG">
            <IconButton size="small" onClick={() => {
              const el = document.querySelector('.react-flow') as HTMLElement
              if (el) toPng(el, { backgroundColor: '#0a0e1a', pixelRatio: 2 }).then((u: string) => {
                const a = document.createElement('a'); a.download = `port-topology-${deviceName}.png`; a.href = u; a.click()
              })
            }} sx={{ color: '#94a3b8', '&:hover': { color: '#2DD46E' }, p: 0.5 }}>
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
            }} sx={{ color: '#94a3b8', '&:hover': { color: '#8B5CF6' }, p: 0.5 }}>
              <VisioIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Paper>

      {/* 方向键 */}
      {selectedTarget && (
        <Box sx={{ position: 'absolute', bottom: 16, left: 16, zIndex: 20 }}>
          <DirectionPad
            step={40}
            onUp={() => setOffsets(p => ({ ...p, [selectedTarget]: { dx: (p[selectedTarget]?.dx || 0), dy: (p[selectedTarget]?.dy || 0) - 40 } }))}
            onDown={() => setOffsets(p => ({ ...p, [selectedTarget]: { dx: (p[selectedTarget]?.dx || 0), dy: (p[selectedTarget]?.dy || 0) + 40 } }))}
            onLeft={() => setOffsets(p => ({ ...p, [selectedTarget]: { dx: (p[selectedTarget]?.dx || 0) - 40, dy: (p[selectedTarget]?.dy || 0) } }))}
            onRight={() => setOffsets(p => ({ ...p, [selectedTarget]: { dx: (p[selectedTarget]?.dx || 0) + 40, dy: (p[selectedTarget]?.dy || 0) } }))}
            onReset={() => setOffsets({})}
          />
        </Box>
      )}
    </Box>
  )
}
