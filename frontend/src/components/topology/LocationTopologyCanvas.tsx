import { useMemo, useState, useCallback, useRef } from 'react'
import {
  ReactFlow, Background, Controls, Panel, Handle, Position,
  Node, Edge, MarkerType, BaseEdge, EdgeLabelRenderer,
  useNodesState, useEdgesState,
  type NodeProps, type EdgeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Paper, Typography, IconButton, Stack, Tooltip } from '@mui/material'
import {
  Image as ImageIcon, AccountTree as VisioIcon,
  Hub as HubIcon, Lan as LanIcon, Router as RouterIcon,
  Security as SecurityIcon, Public as PublicIcon,
  Wifi as WifiIcon, Dns as DnsIcon,
} from '@mui/icons-material'
import { exportTopologyAsPng, assignEndpointLabels } from '../../shared/exportUtils'
import LabeledSmoothstepEdge from './LabeledSmoothstepEdge'
import type { LocationTopologyData } from '../../types/topology'
import DirectionPad from './DirectionPad'
import { getNodeColors, getDisplayType } from '../../shared/constants'

// ============================================================
// 布局常量
// ============================================================
const NODE_H = 104
const NODE_W = 260
const CORE_NODE_W = 560
const V_GAP = 240
const H_GAP = 60
const MIN_HANDLES = 1   // 每个 side group 最少 1 个 handle
const DETOUR_R = 30     // 绕行圆弧半径

// ============================================================
// 跨层绕行自定义边（WAN ↔ Access）
// ============================================================
function DetourEdge({
  id, sourceX, sourceY, targetX, targetY,
  data, markerEnd, markerStart, style, label,
}: EdgeProps) {
  const { gap1Y, gap2Y, detourX, highlighted, srcPort, tgtPort, srcLabelRow, tgtLabelRow } = (data || {}) as any
  const hl = !!highlighted
  const dimmed = (style?.opacity as number) != null && (style.opacity as number) < 0.1
  if (gap1Y == null || gap2Y == null || detourX == null) {
    return <BaseEdge id={id} path={`M ${sourceX} ${sourceY} L ${targetX} ${targetY}`} style={{ stroke: (style?.stroke as string) || '#94A3B8', strokeWidth: (style?.strokeWidth as number) || 2.5, fill: 'none', opacity: (style?.opacity as number) ?? 1 }} markerEnd={markerEnd} markerStart={markerStart} />
  }
  const R = DETOUR_R
  const lc = (style?.stroke as string) || '#94A3B8'
  const sw = (style?.strokeWidth as number) || 2.5
  const opacity = (style?.opacity as number) ?? 1

  let path = ''
  let labelX = 0
  let labelY = 0

  // SVG Y 轴向下。CW(sweep=1): 右→下→左→上→右；CCW(sweep=0): 右→上→左→下→右
  if ((sourceY || 0) < (targetY || 0)) {
    path = [
      `M ${sourceX} ${sourceY}`,
      `L ${sourceX} ${gap1Y - R}`,
      `A ${R} ${R} 0 0 0 ${sourceX + R} ${gap1Y}`,
      `L ${detourX - R} ${gap1Y}`,
      `A ${R} ${R} 0 0 1 ${detourX} ${gap1Y + R}`,
      `L ${detourX} ${gap2Y - R}`,
      `A ${R} ${R} 0 0 1 ${detourX - R} ${gap2Y}`,
      `L ${targetX + R} ${gap2Y}`,
      `A ${R} ${R} 0 0 0 ${targetX} ${gap2Y + R}`,
      `L ${targetX} ${targetY}`,
    ].join(' ')
    labelX = ((sourceX + (detourX || 0)) / 2)
    labelY = gap1Y - 15
  } else {
    path = [
      `M ${sourceX} ${sourceY}`,
      `L ${sourceX} ${gap2Y + R}`,
      `A ${R} ${R} 0 0 1 ${sourceX + R} ${gap2Y}`,
      `L ${detourX - R} ${gap2Y}`,
      `A ${R} ${R} 0 0 0 ${detourX} ${gap2Y - R}`,
      `L ${detourX} ${gap1Y + R}`,
      `A ${R} ${R} 0 0 0 ${detourX - R} ${gap1Y}`,
      `L ${targetX + R} ${gap1Y}`,
      `A ${R} ${R} 0 0 1 ${targetX} ${gap1Y - R}`,
      `L ${targetX} ${targetY}`,
    ].join(' ')
    labelX = ((sourceX + (detourX || 0)) / 2)
    labelY = gap2Y - 15
  }

  const epLab = {
    fontSize: hl ? 14 : 12, fontWeight: hl ? 700 : (500 as const),
    color: hl ? '#2DD46E' : '#1e293b',
    fontFamily: '"Fira Code", monospace',
    pointerEvents: 'all' as const, whiteSpace: 'nowrap' as const,
    background: hl ? '#DCFCE7' : 'rgba(255,255,255,0.92)',
    padding: hl ? '2px 6px' : '1px 5px', borderRadius: 3,
    opacity: dimmed ? 0 : 1,
  }

  const srcDY = 20 + (srcLabelRow || 0) * 22
  const tgtDY = 20 + (tgtLabelRow || 0) * 22
  // 绕行边的 source 用 bottom handle, target 用 top handle
  // 方向 ↓: source 在上, target 在下
  // 方向 ↑: source 在下, target 在上

  return (
    <>
      <BaseEdge id={id} path={path} style={{ stroke: lc, strokeWidth: sw, fill: 'none', opacity }} markerEnd={markerEnd} markerStart={markerStart} />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              background: hl ? '#0A1A0F' : '#0F172A',
              padding: hl ? '3px 8px' : '2px 6px', borderRadius: 4,
              fontSize: hl ? 14 : 13, fontWeight: hl ? 700 : 500,
              color: hl ? '#2DD46E' : '#E2E8F0',
              fontFamily: '"Fira Code", monospace',
              pointerEvents: 'all' as const, whiteSpace: 'nowrap' as const,
              opacity: dimmed ? 0 : 0.92,
            }}
            className="nodrag nopan"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
      <EdgeLabelRenderer>
        {srcPort && (
          <div style={{ ...epLab, position: 'absolute', transform: `translate(-50%, -50%) translate(${sourceX}px, ${sourceY + srcDY}px)` }} className="nodrag nopan">{srcPort}</div>
        )}
        {tgtPort && (
          <div style={{ ...epLab, position: 'absolute', transform: `translate(-50%, -50%) translate(${targetX}px, ${targetY - tgtDY}px)` }} className="nodrag nopan">{tgtPort}</div>
        )}
      </EdgeLabelRenderer>
    </>
  )
}

// tier 层级顺序
const TIER_ORDER = ['wan', 'core', 'access'] as const
const TIER_RANK: Record<string, number> = { wan: 3, core: 2, access: 1 }

function nodeW(tier: string): number { return tier === 'core' ? CORE_NODE_W : NODE_W }

// ============================================================
// 设备图标
// ============================================================
const DEVICE_ICONS: Record<string, React.ComponentType<any>> = {
  'core-switch': HubIcon, 'access-switch': LanIcon,
  router: RouterIcon, firewall: SecurityIcon,
  sdwan: PublicIcon, wireless: WifiIcon, server: DnsIcon,
}

// ============================================================
// DeviceNode 数据
// ============================================================
type HandleGroup = 'st' | 'tt' | 'sb' | 'tb'
interface DeviceNodeData {
  label: string; displayType: string; tier: string
  platform: string; ip: string; isLocationDevice: boolean
  handles: Record<HandleGroup, number>
}

// ============================================================
// 端口缩写
// ============================================================
function shortPort(port: string): string {
  return port
    .replace(/^GigabitEthernet/, 'Gi')
    .replace(/^TenGigabitEthernet/, 'Te')
    .replace(/^TwentyFiveGigE/, 'Tw')
    .replace(/^FortyGigabitEthernet/, 'Fo')
    .replace(/^HundredGigE/, 'Hu')
    .replace(/^FastEthernet/, 'Fa')
}

// ============================================================
// 统计原始边 → 每个节点每 group 需多少 handle
// ============================================================
function countHandleNeeds(
  rawEdges: { source: string; target: string }[],
  tiers: Record<string, string>,
): Record<string, Record<HandleGroup, number>> {
  const cnt: Record<string, Record<HandleGroup, number>> = {}
  const zero = (): Record<HandleGroup, number> => ({ st: 0, tt: 0, sb: 0, tb: 0 })
  const ensure = (id: string) => { if (!cnt[id]) cnt[id] = zero() }

  for (const e of rawEdges) {
    const sr = TIER_RANK[tiers[e.source]] ?? 0
    const tr = TIER_RANK[tiers[e.target]] ?? 0
    ensure(e.source); ensure(e.target)
    if (sr > tr)       { cnt[e.source].sb++; cnt[e.target].tt++ }
    else if (sr < tr)  { cnt[e.source].st++; cnt[e.target].tb++ }
    else               { cnt[e.source].sb++; cnt[e.target].tb++ }
  }
  // 每组至少 MIN_HANDLES
  for (const c of Object.values(cnt)) {
    c.st = Math.max(c.st, MIN_HANDLES)
    c.tt = Math.max(c.tt, MIN_HANDLES)
    c.sb = Math.max(c.sb, MIN_HANDLES)
    c.tb = Math.max(c.tb, MIN_HANDLES)
  }
  return cnt
}

// ============================================================
// 节点组件 — 按实际需求动态创建 handle
// ============================================================
function DeviceNode({ data }: NodeProps) {
  const { label, displayType, tier, platform, ip, handles } = data as DeviceNodeData
  const colors = getNodeColors(displayType)
  const Icon = DEVICE_ICONS[displayType] || null
  const w = nodeW(tier)

  const hs = (): React.CSSProperties => ({
    position: 'absolute', width: 9, height: 9,
    background: colors.border, border: `2px solid ${colors.glow}`, borderRadius: '50%',
  })

  return (
    <Box sx={{
      width: w, height: NODE_H, borderRadius: '10px',
      border: `2px solid ${colors.border}`,
      bgcolor: `${colors.fill}20`,
      position: 'relative', display: 'flex', alignItems: 'center', gap: 1.5, px: 2.5,
      cursor: 'pointer', transition: 'all 180ms ease', backdropFilter: 'blur(4px)',
      boxShadow: `0 0 32px ${colors.glow}99, 0 4px 16px ${colors.glow}66`,
      '&:hover': {
        boxShadow: `0 0 48px ${colors.glow}CC, 0 6px 24px ${colors.glow}99`,
        borderColor: colors.border,
      },
    }}>
      {Icon && <Icon sx={{ fontSize: tier === 'core' ? 40 : 34, color: colors.glow, flexShrink: 0, filter: `drop-shadow(0 0 8px ${colors.glow}80)` }} />}

      {/* 顶部 Source Handle */}
      {Array.from({ length: handles.st }).map((_, i) => (
        <Handle key={`st-${i}`} type="source" position={Position.Top} id={`st-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (handles.st + 1)) * 100}%`, top: -3 }} />
      ))}
      {/* 顶部 Target Handle */}
      {Array.from({ length: handles.tt }).map((_, i) => (
        <Handle key={`tt-${i}`} type="target" position={Position.Top} id={`tt-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (handles.tt + 1)) * 100}%`, top: -3 }} />
      ))}
      {/* 底部 Source Handle */}
      {Array.from({ length: handles.sb }).map((_, i) => (
        <Handle key={`sb-${i}`} type="source" position={Position.Bottom} id={`sb-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (handles.sb + 1)) * 100}%`, bottom: -3 }} />
      ))}
      {/* 底部 Target Handle */}
      {Array.from({ length: handles.tb }).map((_, i) => (
        <Handle key={`tb-${i}`} type="target" position={Position.Bottom} id={`tb-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (handles.tb + 1)) * 100}%`, bottom: -3 }} />
      ))}

      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 0.3 }}>
        <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '1.25rem', fontWeight: 700, color: colors.glow, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textShadow: `0 0 10px ${colors.glow}66` }}>
          {label}
        </Typography>
        {platform && (
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.875rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {platform}
          </Typography>
        )}
        {ip && (
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.875rem', fontWeight: 500, color: '#CBD5E1', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textShadow: '0 0 6px rgba(203,213,225,0.15)' }}>
            {ip}
          </Typography>
        )}
      </Box>
    </Box>
  )
}

const nodeTypes = { deviceNode: DeviceNode }
const edgeTypes = { detour: DetourEdge, labeledSmoothstep: LabeledSmoothstepEdge }

// ============================================================
// 三层固定行布局：WAN → Core → Access
// ============================================================
function tieredLayout(
  nodes: { id: string; tier: string }[],
): { positions: Record<string, { x: number; y: number }>; coreRight: number } {
  const groups: Record<string, { id: string; tier: string }[]> = { wan: [], core: [], access: [] }
  for (const n of nodes) {
    const t = groups[n.tier] ? n.tier : 'access'
    groups[t].push(n)
  }
  for (const t of TIER_ORDER) {
    groups[t].sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true, sensitivity: 'base' }))
  }

  const tierWidths: Record<string, number> = {}
  for (const t of TIER_ORDER) {
    if (groups[t].length === 0) { tierWidths[t] = 0; continue }
    tierWidths[t] = groups[t].length * nodeW(t) + Math.max(groups[t].length - 1, 0) * H_GAP
  }
  const maxW = Math.max(...TIER_ORDER.map(t => tierWidths[t]), NODE_W)

  const positions: Record<string, { x: number; y: number }> = {}
  let coreRight = 0
  let currentY = 0
  for (const t of TIER_ORDER) {
    const row = groups[t]; if (row.length === 0) continue
    const wPer = nodeW(t); const rowW = tierWidths[t]
    const offsetX = (maxW - rowW) / 2
    let x = offsetX
    for (const n of row) {
      positions[n.id] = { x, y: currentY }
      x += wPer + H_GAP
    }
    // 记录核心层最右侧 x 坐标
    if (t === 'core') coreRight = offsetX + rowW
    currentY += NODE_H + V_GAP
  }

  return { positions, coreRight }
}

// ============================================================
// 组件主体
// ============================================================
interface Props { location: string; data: LocationTopologyData }

export default function LocationTopologyCanvas({ location, data }: Props) {
  const rfRef = useRef<HTMLDivElement>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const { initialNodes, initialEdges } = useMemo(() => {
    const tierMap: Record<string, string> = {}
    const layoutInputs: { id: string; tier: string }[] = []
    const nodeSet = new Set<string>()

    for (const n of data.nodes) {
      if (nodeSet.has(n.id)) continue; nodeSet.add(n.id)
      tierMap[n.id] = n.tier
      layoutInputs.push({ id: n.id, tier: n.tier })
    }

    const rawEdges = data.edges  // 不去重，每条物理连接独立
    const handleCounts = countHandleNeeds(rawEdges, tierMap)
    const { positions, coreRight } = tieredLayout(layoutInputs)

    // 绕行坐标
    const gap1Y = NODE_H + V_GAP / 2        // WAN↔Core 间隙中线
    const gap2Y = NODE_H * 2 + V_GAP * 1.5  // Core↔Access 间隙中线
    const detourX = coreRight + 300           // 绕行垂直主干 x

    // 为缺少 handle 统计的节点补默认值（如 skipped devices）
    for (const n of data.nodes) {
      if (!handleCounts[n.id]) handleCounts[n.id] = { st: 1, tt: 1, sb: 1, tb: 1 }
    }

    // ReactFlow nodes
    const rfNodes: Node<DeviceNodeData>[] = data.nodes.map(n => ({
      id: n.id, type: 'deviceNode' as const,
      position: positions[n.id] || { x: 0, y: 0 },
      data: {
        label: n.label, displayType: getDisplayType(n.type, n.tier), tier: n.tier,
        platform: n.model || n.platform, ip: n.ip, isLocationDevice: n.is_location_device,
        handles: handleCounts[n.id],
      },
    }))

    // ReactFlow edges — 每条物理连接独立，动态分配 handle
    const edgeCounters: Record<string, Record<string, number>> = {}
    const nextHandle = (nodeId: string, g: HandleGroup): number => {
      if (!edgeCounters[nodeId]) edgeCounters[nodeId] = {}
      if (edgeCounters[nodeId][g] === undefined) edgeCounters[nodeId][g] = 0
      const max = handleCounts[nodeId]?.[g] || 1
      const idx = edgeCounters[nodeId][g] % max
      edgeCounters[nodeId][g]++
      return idx
    }

    const rfEdges: Edge[] = []
    for (let ei = 0; ei < rawEdges.length; ei++) {
      const e = rawEdges[ei]
      const sr = TIER_RANK[tierMap[e.source]] ?? 0
      const tr = TIER_RANK[tierMap[e.target]] ?? 0

      let srcHandle: string, tgtHandle: string, sameTier: boolean
      if (sr > tr) {
        srcHandle = `sb-${nextHandle(e.source, 'sb')}`
        tgtHandle = `tt-${nextHandle(e.target, 'tt')}`
        sameTier = false
      } else if (sr < tr) {
        srcHandle = `st-${nextHandle(e.source, 'st')}`
        tgtHandle = `tb-${nextHandle(e.target, 'tb')}`
        sameTier = false
      } else {
        srcHandle = `sb-${nextHandle(e.source, 'sb')}`
        tgtHandle = `tb-${nextHandle(e.target, 'tb')}`
        sameTier = true
      }

      const srcNode = data.nodes.find(n => n.id === e.source)
      const tgtNode = data.nodes.find(n => n.id === e.target)
      const srcDisp = srcNode ? getDisplayType(srcNode.type, srcNode.tier) : 'unknown'
      const tgtDisp = tgtNode ? getDisplayType(tgtNode.type, tgtNode.tier) : 'unknown'
      const higherDisp = sr >= tr ? srcDisp : tgtDisp
      const lineColor = getNodeColors(higherDisp).border

      const srcPort = shortPort(e.source_interface || '') || undefined
      const tgtPort = shortPort(e.target_interface || '') || undefined

      // srcSide / tgtSide 由 handle 前缀决定（st=source top, sb=source bottom, tt=target top, tb=target bottom）
      const srcSide = (srcHandle.startsWith('st') ? 'top' : 'bottom') as 'top' | 'bottom'
      const tgtSide = (tgtHandle.startsWith('tt') ? 'top' : 'bottom') as 'top' | 'bottom'

      // 跨层（WAN↔Access）用绕行边，其他用 smoothstep + 端点标签
      const cross = Math.abs(sr - tr) >= 2

      const base: Edge = {
        id: `e-${e.source}-${e.target}-${ei}`,
        source: e.source, target: e.target,
        sourceHandle: srcHandle, targetHandle: tgtHandle,
        type: cross ? 'detour' : 'labeledSmoothstep',
        style: { stroke: lineColor, strokeWidth: 2.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: lineColor, width: 8, height: 8 },
        markerStart: { type: MarkerType.ArrowClosed, color: lineColor, width: 8, height: 8 },
        data: { srcPort, tgtPort, srcSide, tgtSide },
      }

      if (cross) {
        // 绕行边：保留原 label（中点）用于 DetourEdge 渲染
        const midLabel = [srcPort, tgtPort].filter(Boolean).join(' / ') || undefined
        rfEdges.push({
          ...base,
          data: { ...base.data, gap1Y, gap2Y, detourX, label: midLabel },
        })
      } else {
        rfEdges.push({
          ...base,
          pathOptions: sameTier ? { borderRadius: 40, offset: 50 } : { borderRadius: 40, offset: 40 },
        })
      }
    }

    // 端点标签碰撞避免 — 预计算每 (nodeId, side) 的 handle 总数
    const hc = new Map<string, number>()
    for (const e of rfEdges) {
      for (const [nodeId, handle] of [[e.source, e.sourceHandle], [e.target, e.targetHandle]] as const) {
        if (!handle) continue
        const idx = parseInt(handle.split('-').pop() || '0') || 0
        const side = handle.startsWith('st') || handle.startsWith('tt') ? 'top' : 'bottom'
        hc.set(`${nodeId}:${side}`, Math.max(hc.get(`${nodeId}:${side}`) || 0, idx + 1))
      }
    }

    const labeledEdges = assignEndpointLabels(
      rfEdges,
      (e, side) => {
        const nodeId = side === 'src' ? e.source : e.target
        const pos = positions[nodeId]
        if (!pos) return 0
        const handle = side === 'src' ? e.sourceHandle : e.targetHandle
        const idx = parseInt((handle || '').split('-').pop() || '0') || 0
        const tier = data.nodes.find(n => n.id === nodeId)?.tier || 'access'
        const w = nodeW(tier)
        const sd = (handle || '').startsWith('st') || (handle || '').startsWith('tt') ? 'top' : 'bottom'
        const total = hc.get(`${nodeId}:${sd}`) || 1
        return pos.x + w * (idx + 1) / (total + 1)
      },
      e => (e.data as any)?.srcPort || '',
      e => (e.data as any)?.tgtPort || '',
    )

    return { initialNodes: rfNodes, initialEdges: labeledEdges }
  }, [data])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const prevRef = useRef(data)
  if (prevRef.current !== data) { prevRef.current = data; setNodes(initialNodes); setEdges(initialEdges) }

  // 高亮 — 选中节点的连线绿色加粗提至顶层
  const finalEdges = useMemo(() => {
    if (!selectedNodeId) return edges
    return edges.map(e => {
      if (e.source === selectedNodeId || e.target === selectedNodeId)
        return {
          ...e,
          data: { ...(e.data || {}), highlighted: true },
          className: 'ndm-edge-highlighted',
          style: { ...e.style, stroke: '#2DD46E', strokeWidth: 4 },
          animated: true,
          zIndex: 10,
        }
      return {
        ...e,
        style: { ...e.style, stroke: e.style?.stroke, opacity: 0.06 },
        zIndex: 0,
      }
    })
  }, [edges, selectedNodeId])

  const onNodeClick = useCallback((_: any, n: Node) => setSelectedNodeId(p => p === n.id ? null : n.id), [])
  const onPaneClick = useCallback(() => setSelectedNodeId(null), [])

  const moveSelected = useCallback((dx: number, dy: number) => {
    if (!selectedNodeId) return
    setNodes(nds => nds.map(n => n.id === selectedNodeId ? { ...n, position: { x: n.position.x + dx, y: n.position.y + dy } } : n))
  }, [selectedNodeId, setNodes])

  const resetOffsets = useCallback(() => { setNodes(initialNodes) }, [initialNodes, setNodes])

  const exportPng = useCallback(() => {
    if (!rfRef.current) return
    const el = rfRef.current.querySelector('.react-flow') as HTMLElement
    if (!el) return
    setExporting(true)
    exportTopologyAsPng(el, `topology-${location}-${Date.now()}.png`).finally(() => setExporting(false))
  }, [location])

  const exportVisio = useCallback(() => {
    setExporting(true)
    import('../../services/api').then(({ topologyApi }) => {
      topologyApi.exportVisio(data).then(b => {
        const u = URL.createObjectURL(b); const a = document.createElement('a')
        a.download = `topology-${location}.vsdx`; a.href = u; document.body.appendChild(a); a.click()
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(u) }, 1000)
      }).catch(console.error).finally(() => setExporting(false))
    })
  }, [location, data])

  return (
    <Box ref={rfRef} sx={{ width: '100%', height: '100%', position: 'relative' }}>
      <style>{`
        .react-flow__controls-button{background:#1E293B!important;border-bottom:1px solid #334155!important;fill:#94A3B8!important;color:#94A3B8!important;width:28px!important;height:28px!important;border-radius:6px!important}
        .react-flow__controls-button svg{fill:#94A3B8!important}
        .react-flow__controls-button:hover{background:#334155!important;fill:#E2E8F0!important}
        .react-flow__controls{border-radius:8px!important;overflow:hidden!important;box-shadow:0 4px 16px rgba(0,0,0,0.4)!important}
        .react-flow__node.selected .MuiBox-root{box-shadow:0 0 24px rgba(45,212,110,0.5)!important}
      `}</style>

      <ReactFlow
        nodes={nodes} edges={finalEdges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick} onPaneClick={onPaneClick}
        fitView fitViewOptions={{ padding: 0.35 }} minZoom={0.05} maxZoom={3}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1E293B" gap={32} size={0.6} />

        <svg className="ndm-hex-grid" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.08, zIndex: 0 }}>
          <pattern id="hexGrid" width="40" height="69.28" patternUnits="userSpaceOnUse">
            <path d="M40 11.55l-10-5.77-10 5.77v11.55l10 5.77 10-5.77V11.55zM20 46.19l-10-5.77-10 5.77v11.55l10 5.77 10-5.77V46.19zM0 11.55l-10-5.77-10 5.77v11.55l10 5.77 10-5.77V11.55z" fill="none" stroke="#3B82F6" strokeWidth="0.5" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#hexGrid)" />
        </svg>

        <Controls position="bottom-left" style={{ display: 'flex', flexDirection: 'row', gap: 2, background: '#1E293BBB', backdropFilter: 'blur(8px)', borderRadius: 8, padding: 2 }} />

        {data.skipped_count > 0 && (
          <Panel position="top-center">
            <Paper sx={{ px: 2, py: 1, borderRadius: 2, bgcolor: 'rgba(245,158,11,0.15)', border: '1px solid #F59E0B40', backdropFilter: 'blur(8px)' }}>
              <Typography sx={{ fontSize: '0.75rem', color: '#FBBF24', fontFamily: '"Fira Code", monospace' }}>
                ⚠ {data.skipped_count} 台设备无邻居数据: {data.skipped_devices.join(', ')}
              </Typography>
            </Paper>
          </Panel>
        )}
      </ReactFlow>

      {selectedNodeId && (
        <Box sx={{ position: 'absolute', bottom: 200, left: 16, zIndex: 20 }}>
          <DirectionPad step={10}
            onUp={() => moveSelected(0, -10)} onDown={() => moveSelected(0, 10)}
            onLeft={() => moveSelected(-10, 0)} onRight={() => moveSelected(10, 0)}
            onReset={resetOffsets} />
        </Box>
      )}

      <Paper sx={{ position: 'absolute', top: 16, right: 16, zIndex: 10, borderRadius: 2, bgcolor: 'rgba(15,23,42,0.88)', backdropFilter: 'blur(10px)', border: '1px solid #334155', px: 0.5, py: 0.3, boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Tooltip title="导出 PNG"><IconButton size="small" disabled={exporting} onClick={exportPng} sx={{ color:'#94A3B8','&:hover':{color:'#2DD46E'}, p:0.5 }}><ImageIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="导出 Visio"><IconButton size="small" disabled={exporting} onClick={exportVisio} sx={{ color:'#94A3B8','&:hover':{color:'#8B5CF6'}, p:0.5 }}><VisioIcon fontSize="small" /></IconButton></Tooltip>
        </Stack>
      </Paper>
    </Box>
  )
}
