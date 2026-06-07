import { useMemo } from 'react'
import {
  ReactFlow, Node, Edge, Background, Controls, MiniMap, MarkerType, type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Typography } from '@mui/material'
import { useI18n } from '../../i18n'
import type { NeighborNode } from '../../types/topology'
import FrontPanelNode, { getPortParity } from './FrontPanelNode'
import type { PortData } from './FrontPanelNode'

const TYPE_COLORS: Record<string, string> = {
  switch: '#3B82F6', router: '#F59E0B', firewall: '#EF4444',
  wireless: '#8B5CF6', sdwan: '#10B981', esxi: '#06B6D4',
  server: '#06B6D4', printer: '#6366F1', mgmt: '#64748B',
}
function getDeviceColor(type: string): string { return TYPE_COLORS[type] || '#94A3B8' }
const STACK_KEYWORDS = ['VSF', 'stackwise']
function isStackLink(desc: string): boolean { return STACK_KEYWORDS.some((kw) => desc.toLowerCase().includes(kw.toLowerCase())) }
const nodeTypes: NodeTypes = { frontPanel: FrontPanelNode }

// ====== 尺寸常量 ======
const CENTER_W = 620
const CENTER_H = 182
const NEIGHBOR_W = 240
const NEIGHBOR_H = 140
const COMPACT_W = 200
const COMPACT_H = 58
const H_GAP = 60        // 水平间距
const V_GAP = 160       // 交换机上下到第一行邻居的距离
const ROW_GAP = 110     // 邻居行间距
const MAX_PER_ROW = 5   // 每行最多设备数

const ENDPOINT_PREFIXES = [
  { prefix: 'Phone-', label: '电话', labelEn: 'Phones' },
  { prefix: 'Printer-', label: '打印机', labelEn: 'Printers' },
  { prefix: 'AP', label: '无线AP', labelEn: 'APs' },
  { prefix: 'Laptop-', label: '笔记本', labelEn: 'Laptops' },
  { prefix: 'Internet-', label: '互联网', labelEn: 'Internet' },
]

interface AggDevice {
  name: string
  type: string
  color: string
  is_endpoint: boolean
  entries: NeighborNode[]
  row: 'top' | 'bottom'
  compact: boolean
}

interface Props {
  deviceName: string; neighbors: NeighborNode[]
  stackMembers?: string[]; memberNeighbors?: Record<string, NeighborNode[]>
}

export default function TopologyCanvas({ deviceName, neighbors, stackMembers, memberNeighbors }: Props) {
  const { t } = useI18n()

  const validNeighbors = useMemo(() => neighbors.filter((n) => n.device_name && n.device_name !== ''), [neighbors])
  const externalNeighbors = useMemo(() => validNeighbors.filter((n) => !isStackLink(n.description)), [validNeighbors])
  const stackLinks = useMemo(() => validNeighbors.filter((n) => isStackLink(n.description)), [validNeighbors])
  const members = useMemo(() => (stackMembers && stackMembers.length > 1 ? stackMembers : null), [stackMembers])
  const hasStack = !!members
  const memberCount = hasStack ? members!.length : 1

  // ====== 设备分组 + 聚合 ======
  const { topDevs, bottomDevs } = useMemo(() => {
    // 收集所有外部连接
    const all = (hasStack ? members! : ['1']).flatMap((mid) =>
      (memberNeighbors?.[mid] || []).filter((n) => n.device_name && !isStackLink(n.description)),
    )

    // 按名字分组
    const devMap = new Map<string, NeighborNode[]>()
    for (const n of all) { if (!devMap.has(n.device_name)) devMap.set(n.device_name, []); devMap.get(n.device_name)!.push(n) }

    // 分离网络设备 vs 端点
    const network: Map<string, NeighborNode[]> = new Map()
    const eps: Map<string, NeighborNode[]> = new Map()
    for (const [name, entries] of devMap) {
      let prefix: string | null = null
      for (const ep of ENDPOINT_PREFIXES) { if (name.startsWith(ep.prefix)) { prefix = ep.prefix; break } }
      if (prefix) { if (!eps.has(prefix)) eps.set(prefix, []); eps.get(prefix)!.push(...entries) }
      else network.set(name, entries)
    }

    const top: AggDevice[] = []
    const bottom: AggDevice[] = []

    // 网络设备 → 按端口奇偶分上下
    for (const [name, entries] of network) {
      const parities = entries.map((e) => getPortParity(e.interface))
      const oddN = parities.filter((p) => p === 'odd').length
      const evenN = parities.length - oddN
      const row: 'top' | 'bottom' = oddN >= evenN ? 'top' : 'bottom'
      ;(row === 'top' ? top : bottom).push({
        name, type: entries[0].device_type, color: getDeviceColor(entries[0].device_type),
        is_endpoint: false, entries, row, compact: false,
      })
    }

    // 聚合端点
    for (const [prefix, entries] of eps) {
      const def = ENDPOINT_PREFIXES.find((e) => e.prefix === prefix)!
      // 端点放底部
      bottom.push({
        name: `${def.label} ×${entries.length}`,
        type: 'endpoint', color: '#94A3B8', is_endpoint: true,
        entries, row: 'bottom', compact: true,
      })
    }

    return { topDevs: top, bottomDevs: bottom }
  }, [hasStack, members, memberNeighbors])

  // ====== 拆分为多行 ======
  const splitRows = (devs: AggDevice[]): AggDevice[][] => {
    const rows: AggDevice[][] = []
    for (let i = 0; i < devs.length; i += MAX_PER_ROW) rows.push(devs.slice(i, i + MAX_PER_ROW))
    return rows
  }
  const topRows = useMemo(() => splitRows(topDevs), [topDevs])
  const bottomRows = useMemo(() => splitRows(bottomDevs), [bottomDevs])

  // ====== 计算最大行宽 ======
  const rowWidth = (row: AggDevice[]): number =>
    row.reduce((s, d) => s + (d.compact ? COMPACT_W : NEIGHBOR_W), 0) + Math.max(row.length - 1, 0) * H_GAP

  const switchesW = memberCount * CENTER_W + (memberCount - 1) * H_GAP

  const maxW = useMemo(() => {
    let m = switchesW
    for (const r of [...topRows, ...bottomRows]) m = Math.max(m, rowWidth(r))
    return m
  }, [topRows, bottomRows, switchesW])

  // ====== 中心 Y 计算 ======
  const centerY = useMemo(() => {
    const topH = topRows.length * NEIGHBOR_H + Math.max(topRows.length - 1, 0) * ROW_GAP
    const bottomH = bottomRows.length * NEIGHBOR_H + Math.max(bottomRows.length - 1, 0) * ROW_GAP
    const total = topH + V_GAP + CENTER_H + V_GAP + bottomH + 200
    return total / 2 + 80
  }, [topRows, bottomRows])

  const SWITCH_Y = centerY

  // ====== 构建节点 & 边 ======
  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const cc = '#2DD46E'

    // --- 中心交换机（居中） ---
    const switchStartX = (maxW - switchesW) / 2
    if (hasStack) {
      members!.forEach((mid, i) => {
        const name = `${deviceName}-0${mid}`
        const mports = memberNeighbors?.[mid]?.filter((n) => !isStackLink(n.description) && n.device_name) || []
        const ports: PortData[] = mports.map((n) => ({
          id: n.interface, label: n.interface, fullName: n.interface,
          color: getDeviceColor(n.device_type), neighborName: n.device_name,
          connected: true, direction: getPortParity(n.interface) === 'odd' ? 'top' : 'bottom',
        }))
        nodes.push({
          id: `center-${mid}`, type: 'frontPanel',
          position: { x: switchStartX + i * (CENTER_W + H_GAP), y: SWITCH_Y - CENTER_H / 2 },
          data: { label: name, deviceType: 'switch', color: cc, isCenter: true, ports, memberLabel: `Member ${mid}` },
        })
      })
      for (let i = 0; i < memberCount - 1; i++) {
        const sp = stackLinks.filter((n) => n.member === members![i] || n.member === members![i + 1])
        edges.push({
          id: `stack-${members![i]}-${members![i + 1]}`, source: `center-${members![i]}`, target: `center-${members![i + 1]}`,
          label: sp.map((n) => n.interface).join(', ') || 'VSF Stack',
          style: { stroke: '#2DD46E', strokeWidth: 5, strokeDasharray: '12,6' },
          labelStyle: { fontSize: 13, fill: '#2DD46E', fontWeight: 600 },
          labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9 }, animated: true,
        })
      }
    } else {
      const ports: PortData[] = externalNeighbors.map((n) => ({
        id: n.interface, label: n.interface, fullName: n.interface,
        color: getDeviceColor(n.device_type), neighborName: n.device_name,
        connected: true, direction: getPortParity(n.interface) === 'odd' ? 'top' : 'bottom',
      }))
      nodes.push({
        id: 'center', type: 'frontPanel',
        position: { x: switchStartX, y: SWITCH_Y - CENTER_H / 2 },
        data: { label: deviceName, deviceType: 'switch', color: cc, isCenter: true, ports, memberLabel: t('topology.centerDevice') },
      })
    }

    // --- 布局函数：一行设备居中 ---
    const layRow = (row: AggDevice[], rowCenterY: number) => {
      const w = rowWidth(row)
      let cx = (maxW - w) / 2
      row.forEach((dev) => {
        const dw = dev.compact ? COMPACT_W : NEIGHBOR_W
        const dh = dev.compact ? COMPACT_H : NEIGHBOR_H
        const ports: PortData[] = dev.entries.map((e) => ({
          id: e.interface, label: e.interface, fullName: e.interface,
          color: dev.color, neighborName: deviceName, connected: true,
          direction: 'top' as const,
        }))
        nodes.push({
          id: dev.name, type: 'frontPanel',
          position: { x: cx, y: rowCenterY - dh / 2 },
          data: { label: dev.name, deviceType: dev.type, color: dev.color, isCenter: false, ports, compact: dev.compact },
        })
        cx += dw + H_GAP
      })
    }

    // --- 上行区域（交换机上方）---
    const topRowStartY = SWITCH_Y - CENTER_H / 2 - V_GAP
    topRows.forEach((row, ri) => {
      layRow(row, topRowStartY - ri * (NEIGHBOR_H + ROW_GAP))
    })

    // --- 下行区域（交换机下方）---
    const bottomRowStartY = SWITCH_Y + CENTER_H / 2 + V_GAP
    bottomRows.forEach((row, ri) => {
      layRow(row, bottomRowStartY + ri * (NEIGHBOR_H + ROW_GAP))
    })

    // --- 连线 ---
    const allDevs = [...topDevs, ...bottomDevs]
    allDevs.forEach((dev) => {
      dev.entries.forEach((e) => {
        const sourceId = hasStack ? `center-${e.member || '1'}` : 'center'
        const ep = dev.is_endpoint
        edges.push({
          id: `e-${sourceId}-${dev.name}-${e.interface}`,
          source: sourceId, sourceHandle: e.interface,
          target: dev.name, targetHandle: e.interface,
          type: 'smoothstep',
          pathOptions: { borderRadius: 40, offset: 50 },
          style: {
            stroke: ep ? '#64748b' : dev.color,
            strokeWidth: ep ? 3 : 4.5,
            opacity: ep ? 0.5 : 1,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: dev.color, width: 16, height: 16 },
          label: dev.entries.length <= 1 ? undefined : e.interface,
          labelStyle: { fontSize: 11, fill: '#cbd5e1', fontWeight: 500 },
          labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9 },
        })
      })
    })

    return { nodes, edges }
  }, [topDevs, bottomDevs, topRows, bottomRows, maxW, centerY, hasStack, members, memberNeighbors, stackLinks, externalNeighbors, deviceName, t, memberCount, switchesW])

  if (validNeighbors.length === 0) {
    return <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500, color: 'text.secondary' }}><Typography sx={{ fontSize: '1.1rem' }}>{t('topology.noNeighbors')}</Typography></Box>
  }

  return (
    <Box sx={{ width: '100%', height: 'calc(100vh - 280px)', minHeight: 650, borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
      <style>{`.react-flow__controls-button{background:#1e293b!important;border:1px solid #334155!important;fill:#e2e8f0!important;width:32px!important;height:32px!important}.react-flow__controls-button svg{fill:#e2e8f0!important;max-width:16px!important;max-height:16px!important}.react-flow__controls-button:hover{background:#334155!important}.react-flow__controls{background:#0f172a!important;border:1px solid #1e293b!important;border-radius:8px!important;overflow:hidden!important}`}</style>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.25 }} minZoom={0.06} maxZoom={3} nodesDraggable nodesConnectable={false} elementsSelectable defaultEdgeOptions={{ type: 'smoothstep' }} proOptions={{ hideAttribution: true }}>
        <Background color="#1e293b" gap={24} />
        <Controls />
        <MiniMap style={{ background: '#0f172a', border: '1px solid #1e293b' }} nodeColor={(node) => { if (node.id.startsWith('center')) return '#2DD46E'; const d = node.data as any; return d?.color || '#475569' }} />
      </ReactFlow>
    </Box>
  )
}
