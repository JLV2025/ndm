import { useMemo, useState, useCallback, useRef } from 'react'
import {
  ReactFlow, Background, Controls, Panel, Handle, Position,
  Node, Edge, MarkerType,
  useNodesState, useEdgesState,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Paper, Typography, IconButton, Stack, Tooltip } from '@mui/material'
import {
  Image as ImageIcon, AccountTree as VisioIcon,
  Hub as HubIcon, Lan as LanIcon, Router as RouterIcon,
  Security as SecurityIcon, Public as PublicIcon,
  Wifi as WifiIcon, Dns as DnsIcon,
} from '@mui/icons-material'
import { toPng } from 'html-to-image'
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
const HANDLE_COUNT = 5
const CORE_HANDLE_COUNT = 9

// tier 层级顺序
const TIER_ORDER = ['wan', 'core', 'access'] as const
const TIER_RANK: Record<string, number> = { wan: 3, core: 2, access: 1 }

function nodeW(tier: string): number { return tier === 'core' ? CORE_NODE_W : NODE_W }
function handleCount(tier: string): number { return tier === 'core' ? CORE_HANDLE_COUNT : HANDLE_COUNT }

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
interface DeviceNodeData { label: string; displayType: string; tier: string; platform: string; ip: string; isLocationDevice: boolean }

// ============================================================
// 节点组件
// ============================================================
function DeviceNode({ data }: NodeProps) {
  const { label, displayType, tier, platform, ip, isLocationDevice } = data as DeviceNodeData
  const colors = getNodeColors(displayType)
  const Icon = DEVICE_ICONS[displayType] || null
  const w = nodeW(tier); const hc = handleCount(tier)

  const hs = (): React.CSSProperties => ({
    position: 'absolute', width: 7, height: 7,
    background: colors.border, border: `2px solid ${colors.glow}`, borderRadius: '50%',
  })

  return (
    <Box sx={{
      width: w, height: NODE_H, borderRadius: '10px',
      border: isLocationDevice ? `2px solid ${colors.border}` : `1px solid ${colors.glow}40`,
      bgcolor: isLocationDevice ? `${colors.fill}20` : `${colors.glow}10`,
      position: 'relative', display: 'flex', alignItems: 'center', gap: 1.5, px: 2.5,
      cursor: 'pointer', transition: 'all 180ms ease', backdropFilter: 'blur(4px)',
      boxShadow: isLocationDevice
        ? `0 0 24px ${colors.glow}60, 0 4px 12px ${colors.glow}40`
        : `0 0 8px ${colors.glow}20`,
      '&:hover': {
        boxShadow: `0 0 36px ${colors.glow}80, 0 6px 18px ${colors.glow}60`,
        borderColor: colors.border,
      },
    }}>
      {Icon && <Icon sx={{ fontSize: tier === 'core' ? 36 : 30, color: colors.glow, flexShrink: 0, filter: `drop-shadow(0 0 4px ${colors.glow}50)` }} />}

      {/* 顶部 Handle */}
      {Array.from({ length: hc }).map((_, i) => (
        <Handle key={`st-${i}`} type="source" position={Position.Top} id={`st-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (hc + 1)) * 100}%`, top: -3 }} />
      ))}
      {Array.from({ length: hc }).map((_, i) => (
        <Handle key={`tt-${i}`} type="target" position={Position.Top} id={`tt-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (hc + 1)) * 100}%`, top: -3 }} />
      ))}
      {/* 底部 Handle */}
      {Array.from({ length: hc }).map((_, i) => (
        <Handle key={`sb-${i}`} type="source" position={Position.Bottom} id={`sb-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (hc + 1)) * 100}%`, bottom: -3 }} />
      ))}
      {Array.from({ length: hc }).map((_, i) => (
        <Handle key={`tb-${i}`} type="target" position={Position.Bottom} id={`tb-${i}`}
          style={{ ...hs(), left: `${((i + 1) / (hc + 1)) * 100}%`, bottom: -3 }} />
      ))}

      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 0.3 }}>
        <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '1rem', fontWeight: 700, color: colors.glow, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {label}
        </Typography>
        {platform && (
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.7rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {platform}
          </Typography>
        )}
        {ip && (
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.7rem', fontWeight: 500, color: '#CBD5E1', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ip}
          </Typography>
        )}
      </Box>
    </Box>
  )
}

const nodeTypes = { deviceNode: DeviceNode }

// ============================================================
// 边数据
// ============================================================
interface UniqueEdge {
  source: string; target: string
  source_interface: string; target_interface: string
}
interface LocationEdge {
  source: string; target: string
  source_interface: string; target_interface: string
  is_cross_location: boolean
}

function dedupeEdges(rawEdges: LocationEdge[]): UniqueEdge[] {
  const m = new Map<string, UniqueEdge>()
  for (const e of rawEdges) {
    const k = [e.source, e.target].sort().join('||')
    if (!m.has(k)) m.set(k, { source: e.source, target: e.target, source_interface: e.source_interface, target_interface: e.target_interface })
    else {
      const ex = m.get(k)!
      if (e.source_interface) ex.source_interface = ex.source_interface ? `${ex.source_interface},${e.source_interface}` : e.source_interface
      if (e.target_interface) ex.target_interface = ex.target_interface ? `${ex.target_interface},${e.target_interface}` : e.target_interface
    }
  }
  return [...m.values()]
}

// ============================================================
// Handle 分配：就近原则 — 上对下(sb→tt)，下对上(st→tb)
// ============================================================
function assignHandleIds(
  edges: UniqueEdge[],
  tiers: Record<string, string>,
): Record<string, { src: string; tgt: string }> {
  const assign: Record<string, { src: string; tgt: string }> = {}
  const counters: Record<string, Record<string, number>> = {}

  function next(nodeId: string, group: string, max: number): number {
    if (!counters[nodeId]) counters[nodeId] = {}
    if (counters[nodeId][group] === undefined) counters[nodeId][group] = 0
    const idx = counters[nodeId][group] % max
    counters[nodeId][group]++
    return idx
  }

  for (const e of edges) {
    const srcRank = TIER_RANK[tiers[e.source]] ?? 0
    const tgtRank = TIER_RANK[tiers[e.target]] ?? 0
    const srcHc = handleCount(tiers[e.source])
    const tgtHc = handleCount(tiers[e.target])

    let srcHandle: string, tgtHandle: string

    if (srcRank > tgtRank) {
      // source 在上层 → target 在下层：源 Bottom 出，目标 Top 入
      srcHandle = `sb-${next(e.source, 'sb', srcHc)}`
      tgtHandle = `tt-${next(e.target, 'tt', tgtHc)}`
    } else if (srcRank < tgtRank) {
      // source 在下层 → target 在上层：源 Top 出，目标 Bottom 入
      srcHandle = `st-${next(e.source, 'st', srcHc)}`
      tgtHandle = `tb-${next(e.target, 'tb', tgtHc)}`
    } else {
      // 同层：不处理
      srcHandle = 'sb-0'
      tgtHandle = 'tt-0'
    }

    assign[`${e.source}||${e.target}`] = { src: srcHandle, tgt: tgtHandle }
  }
  return assign
}

// ============================================================
// 三层固定行布局：WAN → Core → Access
// ============================================================
function tieredLayout(
  nodes: { id: string; tier: string }[],
): Record<string, { x: number; y: number }> {
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
    currentY += NODE_H + V_GAP
  }

  return positions
}

// ============================================================
// 组件主体
// ============================================================
interface Props { location: string; data: LocationTopologyData }

export default function LocationTopologyCanvas({ location, data }: Props) {
  const rfRef = useRef<HTMLDivElement>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const { initialNodes, initialEdges } = useMemo(() => {
    const layoutInputs: { id: string; tier: string }[] = []
    const nodeSet = new Set<string>()
    const tierMap: Record<string, string> = {}

    for (const n of data.nodes) {
      if (nodeSet.has(n.id)) continue; nodeSet.add(n.id)
      layoutInputs.push({ id: n.id, tier: n.tier })
      tierMap[n.id] = n.tier
    }

    const uniqueEdges = dedupeEdges(data.edges)
    const positions = tieredLayout(layoutInputs)
    const handleAssign = assignHandleIds(uniqueEdges, tierMap)

    // ReactFlow nodes
    const rfNodes: Node<DeviceNodeData>[] = []
    for (const n of data.nodes) {
      const pos = positions[n.id] || { x: 0, y: 0 }
      rfNodes.push({
        id: n.id, type: 'deviceNode', position: pos,
        data: {
          label: n.label, displayType: getDisplayType(n.type, n.tier), tier: n.tier,
          platform: n.model || n.platform, ip: n.ip, isLocationDevice: n.is_location_device,
        },
      })
    }

    // ReactFlow edges
    const rfEdges: Edge[] = []
    for (const e of uniqueEdges) {
      const pairKey = `${e.source}||${e.target}`
      const revKey = `${e.target}||${e.source}`
      const h = handleAssign[pairKey] || handleAssign[revKey] || { src: 'sb-0', tgt: 'tt-0' }

      // 颜色 = 较高层级设备的颜色
      const srcNode = data.nodes.find(n => n.id === e.source)
      const tgtNode = data.nodes.find(n => n.id === e.target)
      const srcDisp = srcNode ? getDisplayType(srcNode.type, srcNode.tier) : 'unknown'
      const tgtDisp = tgtNode ? getDisplayType(tgtNode.type, tgtNode.tier) : 'unknown'
      const srcRank = TIER_RANK[srcNode?.tier || ''] ?? 0
      const tgtRank = TIER_RANK[tgtNode?.tier || ''] ?? 0
      const higherDisp = srcRank >= tgtRank ? srcDisp : tgtDisp
      const lineColor = getNodeColors(higherDisp).border

      const portsLabel = [e.source_interface, e.target_interface].filter(Boolean).join(' / ')

      rfEdges.push({
        id: `e-${e.source}-${e.target}`,
        source: e.source, target: e.target,
        sourceHandle: h.src, targetHandle: h.tgt,
        type: 'smoothstep',
        pathOptions: { borderRadius: 40, offset: 40 },
        label: portsLabel || undefined,
        style: { stroke: lineColor, strokeWidth: 2.5 },
        labelStyle: { fontSize: 12, fill: '#CBD5E1', fontWeight: 500 },
        labelBgStyle: { fill: '#0F172A', fillOpacity: 0.9 },
        markerEnd: { type: MarkerType.ArrowClosed, color: lineColor, width: 8, height: 8 },
        markerStart: { type: MarkerType.ArrowClosed, color: lineColor, width: 8, height: 8 },
      })
    }

    return { initialNodes: rfNodes, initialEdges: rfEdges }
  }, [data])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const prevRef = useRef(data)
  if (prevRef.current !== data) { prevRef.current = data; setNodes(initialNodes); setEdges(initialEdges) }

  // 高亮
  const finalEdges = useMemo(() => {
    if (!selectedNodeId) return edges
    return edges.map(e => {
      if (e.source === selectedNodeId || e.target === selectedNodeId)
        return { ...e, style: { ...e.style, stroke: '#2DD46E', strokeWidth: 4 }, animated: true }
      return { ...e, style: { ...e.style, opacity: 0.06 }, labelStyle: { opacity: 0.06 } }
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
    if (el) toPng(el, { backgroundColor: '#0a0d1a', pixelRatio: 2 }).then(u => {
      const a = document.createElement('a'); a.download = `topology-${location}-${Date.now()}.png`; a.href = u; a.click()
    })
  }, [location])

  const exportVisio = useCallback(() => {
    import('../../services/api').then(({ topologyApi }) => {
      topologyApi.exportVisio(data).then(b => {
        const u = URL.createObjectURL(b); const a = document.createElement('a')
        a.download = `topology-${location}.vdx`; a.href = u; a.click(); URL.revokeObjectURL(u)
      }).catch(console.error)
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
        nodes={nodes} edges={finalEdges} nodeTypes={nodeTypes}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick} onPaneClick={onPaneClick}
        fitView fitViewOptions={{ padding: 0.35 }} minZoom={0.05} maxZoom={3}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1E293B" gap={32} size={0.6} />

        <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.04, zIndex: 0 }}>
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
          <Tooltip title="导出 PNG"><IconButton size="small" onClick={exportPng} sx={{ color:'#94A3B8','&:hover':{color:'#2DD46E'}, p:0.5 }}><ImageIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="导出 Visio"><IconButton size="small" onClick={exportVisio} sx={{ color:'#94A3B8','&:hover':{color:'#8B5CF6'}, p:0.5 }}><VisioIcon fontSize="small" /></IconButton></Tooltip>
        </Stack>
      </Paper>
    </Box>
  )
}
