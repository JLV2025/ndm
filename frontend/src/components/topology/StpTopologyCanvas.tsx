import { useMemo, useState, useCallback, useRef } from 'react'
import {
  ReactFlow, Background, Controls, Panel, Handle, Position,
  Node, Edge, BaseEdge, MarkerType, EdgeLabelRenderer,
  useNodesState, useEdgesState,
  type NodeProps, type EdgeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Paper, Typography, IconButton, Tooltip, Divider } from '@mui/material'
import {
  Image as ImageIcon,
  Hub as HubIcon,
  Lan as LanIcon,
} from '@mui/icons-material'
import { exportTopologyAsPng } from '../../shared/exportUtils'
import { getNodeColors, getDisplayType, vlanColor } from '../../shared/constants'
import { useI18n } from '../../i18n'
import type { StpTopologyData, StpNode } from '../../types/topology'

// ============================================================
// 布局常量
// ============================================================
const HEADER_H = 58
const CHIP_H = 24
const CHIP_W = 36
const CHIP_PITCH = 42
const NODE_PAD = 14
const NODE_H = HEADER_H + CHIP_H + 22
const H_GAP = 90
const V_GAP = 280
const ELBOW_R = 14
const EDGE_SPREAD = 4       // 同一层带内相邻边的垂直偏移（形成彩色"线束"）
const MIN_NODE_W = 340

// ============================================================
// 节点数据
// ============================================================
interface StpNodeData {
  node: StpNode
  allVlans: number[]
  width: number
  selectedVlan: number | null
  [key: string]: unknown
}

const handleStyle = (color: string): React.CSSProperties => ({
  width: 7, height: 7,
  background: '#0F172A', border: `1.5px solid ${color}`, borderRadius: '50%',
})

function chipTitle(n: StpNode, vlan: number): string {
  const c = n.vlans.find(x => x.vlan === vlan)
  if (!c) return `VLAN ${vlan}`
  const lines = [
    `VLAN ${vlan}`,
    c.is_root ? '根桥（本设备是该 VLAN 的根）' : `角色 ${c.role} · 状态 ${c.state}`,
    c.port ? `朝根端口 ${c.port}` : '',
    c.blocked ? '该 VLAN 存在阻塞端口' : '',
    c.priority != null ? `本桥优先级 ${c.priority}` : '',
    `根桥 MAC ${c.root_mac}`,
  ]
  return lines.filter(Boolean).join('\n')
}

// ============================================================
// 交换机节点：头部（名字/模式/根桥徽章）+ VLAN 伪端口行
// ============================================================
function StpSwitchNode({ data }: NodeProps) {
  const { node, width, selectedVlan } = data as unknown as StpNodeData
  const { t } = useI18n()
  const displayType = getDisplayType(node.type, node.tier)
  const colors = getNodeColors(displayType)
  const Icon = node.tier === 'core' ? HubIcon : LanIcon
  const isRoot = node.is_root_bridge

  const chipX = (i: number) => NODE_PAD + i * CHIP_PITCH + CHIP_W / 2

  return (
    <Box sx={{
      width, height: NODE_H, position: 'relative', borderRadius: '10px',
      border: `2px solid ${isRoot ? '#FACC15' : colors.border}`,
      bgcolor: `${colors.fill}20`,
      backdropFilter: 'blur(4px)',
      boxShadow: isRoot
        ? `0 0 44px #FACC1577, 0 4px 16px #FACC1544`
        : `0 0 32px ${colors.glow}99, 0 4px 16px ${colors.glow}66`,
    }}>
      {/* 每个 VLAN 一个 handle（底=source / 底=target / 顶=target），与 chip 对位 */}
      {node.vlans.map((c, i) => (
        <Handle key={`b-${c.vlan}`} type="source" position={Position.Bottom} id={`b-${c.vlan}`}
          style={{ ...handleStyle(vlanColor(c.vlan, (data as unknown as StpNodeData).allVlans)), left: chipX(i), bottom: -3 }} />
      ))}
      {node.vlans.map((c, i) => (
        <Handle key={`t-${c.vlan}`} type="target" position={Position.Top} id={`t-${c.vlan}`}
          style={{ ...handleStyle(vlanColor(c.vlan, (data as unknown as StpNodeData).allVlans)), left: chipX(i), top: -3 }} />
      ))}

      {/* 头部 */}
      <Box sx={{ height: HEADER_H, display: 'flex', alignItems: 'center', gap: 1.2, px: 2, pt: 1 }}>
        <Icon sx={{ fontSize: 26, color: isRoot ? '#FACC15' : colors.glow, flexShrink: 0, filter: `drop-shadow(0 0 8px ${isRoot ? '#FACC15' : colors.glow}80)` }} />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
            <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.95rem', fontWeight: 700, color: isRoot ? '#FACC15' : colors.glow, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {node.label}
            </Typography>
            {isRoot && (
              <Box component="span" sx={{ px: 0.7, py: 0.1, borderRadius: '4px', bgcolor: '#FACC1522', border: '1px solid #FACC1566', color: '#FACC15', fontSize: '0.62rem', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {t('topology.stpRootBadge')}
              </Box>
            )}
          </Box>
          <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.68rem', color: '#94A3B8', lineHeight: 1.3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {node.has_stp_data ? `${node.mode}${node.ip ? ` · ${node.ip}` : ''}` : t('topology.stpNoData')}
          </Typography>
        </Box>
      </Box>

      {/* VLAN 伪端口行 */}
      {node.has_stp_data ? (
        <Box sx={{ position: 'absolute', left: NODE_PAD, right: NODE_PAD, top: HEADER_H - 4, display: 'flex', gap: `${CHIP_PITCH - CHIP_W}px` }}>
          {node.vlans.map(c => {
            const color = vlanColor(c.vlan, (data as unknown as StpNodeData).allVlans)
            const dim = selectedVlan != null && selectedVlan !== c.vlan
            return (
              <Box key={c.vlan} title={chipTitle(node, c.vlan)} sx={{
                width: CHIP_W, height: CHIP_H, borderRadius: '5px', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px',
                bgcolor: `${color}22`,
                border: c.blocked ? `1.5px dashed ${color}` : `1.5px solid ${c.is_root ? '#FACC15' : color}`,
                opacity: dim ? 0.25 : 1, transition: 'opacity 150ms ease',
                cursor: 'default',
              }}>
                <Typography sx={{ fontFamily: '"Fira Code", monospace', fontSize: '0.62rem', fontWeight: 700, color, lineHeight: 1 }}>
                  {c.vlan}
                </Typography>
                {c.is_root && <Box component="span" sx={{ fontSize: '0.55rem', color: '#FACC15', lineHeight: 1 }}>★</Box>}
                {!c.is_root && c.blocked && <Box component="span" sx={{ fontSize: '0.55rem', color: '#F87171', lineHeight: 1 }}>✕</Box>}
              </Box>
            )
          })}
        </Box>
      ) : (
        <Box sx={{ position: 'absolute', left: NODE_PAD, right: NODE_PAD, top: HEADER_H, textAlign: 'center' }}>
          <Typography sx={{ fontSize: '0.66rem', color: '#64748B' }}>{t('topology.stpNoDataHint')}</Typography>
        </Box>
      )}
    </Box>
  )
}

// ============================================================
// 边：竖直下探 → 水平管道（按 VLAN 着色）→ 落向目标
// ============================================================
function StpVlanEdge({ id, sourceX, sourceY, targetX, targetY, data, markerEnd, style }: EdgeProps) {
  const d = (data || {}) as any
  const pipeY: number | undefined = d.pipeY
  const r = ELBOW_R
  const dashed = !!d.dashed
  const dimmed = !!d.dimmed
  const highlighted = !!d.highlighted
  const stroke = (style?.stroke as string) || '#94A3B8'
  const width = highlighted ? 4.5 : 2.4
  const opacity = dimmed ? 0.05 : (highlighted ? 1 : (dashed ? 0.45 : 0.92))

  let path = ''
  const midX = (sourceX + targetX) / 2
  const midY = pipeY ?? (sourceY + targetY) / 2

  if (pipeY == null || sourceY > pipeY || targetY < pipeY) {
    // 兜底（同层边等异常几何）：平滑曲线
    path = `M ${sourceX} ${sourceY} C ${sourceX} ${sourceY + 70}, ${targetX} ${targetY - 70}, ${targetX} ${targetY}`
  } else if (targetX >= sourceX) {
    path = [
      `M ${sourceX} ${sourceY}`,
      `L ${sourceX} ${pipeY - r}`,
      `Q ${sourceX} ${pipeY} ${sourceX + r} ${pipeY}`,
      `L ${targetX - r} ${pipeY}`,
      `Q ${targetX} ${pipeY} ${targetX} ${pipeY + r}`,
      `L ${targetX} ${targetY}`,
    ].join(' ')
  } else {
    path = [
      `M ${sourceX} ${sourceY}`,
      `L ${sourceX} ${pipeY - r}`,
      `Q ${sourceX} ${pipeY} ${sourceX - r} ${pipeY}`,
      `L ${targetX + r} ${pipeY}`,
      `Q ${targetX} ${pipeY} ${targetX} ${pipeY + r}`,
      `L ${targetX} ${targetY}`,
    ].join(' ')
  }

  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd}
        style={{ stroke, strokeWidth: width, opacity, fill: 'none', strokeDasharray: dashed ? '7 5' : undefined }} />
      {d.detailLabel && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${midX}px,${midY - 12}px)`,
              background: 'rgba(2,6,23,0.92)', border: `1px solid ${stroke}`,
              padding: '2px 7px', borderRadius: 4,
              fontSize: 12, fontWeight: 600, color: stroke,
              fontFamily: '"Fira Code", monospace',
              pointerEvents: 'none', whiteSpace: 'nowrap', zIndex: 1000,
            }}
            className="nodrag nopan"
          >
            {d.detailLabel}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { stpSwitch: StpSwitchNode }
const edgeTypes = { stpVlan: StpVlanEdge }

// ============================================================
// 布局：按 STP 深度分层，层内居中
// ============================================================
interface LayoutResult {
  rfNodes: Node<StpNodeData>[]
  rawEdges: Edge[]
  allVlans: number[]
}

function buildLayout(data: StpTopologyData): LayoutResult {
  const allVlans = data.summary.vlans
  const widths = new Map<string, number>()
  for (const n of data.nodes) {
    widths.set(n.id, Math.max(MIN_NODE_W, NODE_PAD * 2 + Math.max(n.vlans.length, 1) * CHIP_PITCH))
  }

  const layerOf = new Map<string, number | null>()
  for (const n of data.nodes) layerOf.set(n.id, n.layer)
  const numericLayers = data.nodes.map(n => n.layer).filter((l): l is number => l != null)
  const maxLayer = numericLayers.length ? Math.max(...numericLayers) : 0
  const lastRow = maxLayer + 1   // 无 STP 数据的设备放最后一行

  const rows = new Map<number, StpNode[]>()
  for (const n of data.nodes) {
    const row = n.layer ?? lastRow
    if (!rows.has(row)) rows.set(row, [])
    rows.get(row)!.push(n)
  }
  const rowKeys = Array.from(rows.keys()).sort((a, b) => a - b)

  const rowWidth = (arr: StpNode[]) =>
    arr.reduce((s, n) => s + (widths.get(n.id) || MIN_NODE_W), 0)
    + Math.max(arr.length - 1, 0) * H_GAP
  const maxW = Math.max(...rowKeys.map(k => rowWidth(rows.get(k)!)), MIN_NODE_W)

  const positions = new Map<string, { x: number; y: number }>()
  const rowY = new Map<number, number>()
  rowKeys.forEach((k, idx) => {
    const arr = [...rows.get(k)!].sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }))
    const w = rowWidth(arr)
    let x = (maxW - w) / 2
    const y = idx * (NODE_H + V_GAP)
    rowY.set(k, y)
    for (const n of arr) {
      positions.set(n.id, { x, y })
      x += (widths.get(n.id) || MIN_NODE_W) + H_GAP
    }
  })

  // 层带的水平管道 Y（源层底边与目标层顶边的中点）
  const pipeYFor = (srcLayer: number, tgtLayer: number): number => {
    const srcY = rowY.get(srcLayer) ?? 0
    const tgtY = rowY.get(tgtLayer) ?? srcY + NODE_H + V_GAP
    return (srcY + NODE_H + tgtY) / 2
  }

  // 同一层带内的边排序后均匀分配垂直偏移 → 彩色"线束"
  const bandEdges = new Map<string, typeof data.edges>()
  for (const e of data.edges) {
    const sl = layerOf.get(e.source) ?? lastRow
    const tl = layerOf.get(e.target) ?? lastRow
    const key = `${sl}-${tl}`
    if (!bandEdges.has(key)) bandEdges.set(key, [])
    bandEdges.get(key)!.push(e)
  }
  const offsetOf = new Map<string, number>()
  for (const [key, arr] of bandEdges) {
    const sorted = [...arr].sort((a, b) =>
      a.vlan - b.vlan || a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
    sorted.forEach((e, i) => {
      const off = (i - (sorted.length - 1) / 2) * EDGE_SPREAD
      offsetOf.set(`${e.source}|${e.target}|${e.vlan}`, off)
    })
    void key
  }

  const rfNodes: Node<StpNodeData>[] = data.nodes.map(n => ({
    id: n.id,
    type: 'stpSwitch',
    position: positions.get(n.id) || { x: 0, y: 0 },
    data: { node: n, allVlans, width: widths.get(n.id) || MIN_NODE_W, selectedVlan: null },
    draggable: false,
  }))

  const rawEdges: Edge[] = data.edges.map(e => {
    const color = vlanColor(e.vlan, allVlans)
    const sl = layerOf.get(e.source) ?? lastRow
    const tl = layerOf.get(e.target) ?? lastRow
    const off = offsetOf.get(`${e.source}|${e.target}|${e.vlan}`) ?? 0
    const pipeY = pipeYFor(Math.min(sl, tl), Math.max(sl, tl)) + off
    const detail = `V${e.vlan} · ${e.source_port || '?'} → ${e.target_port || '?'}`
    return {
      id: `stp-${e.source}-${e.target}-${e.vlan}`,
      source: e.source,
      target: e.target,
      sourceHandle: `b-${e.vlan}`,
      targetHandle: `t-${e.vlan}`,
      type: 'stpVlan',
      style: { stroke: color },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 7, height: 7 },
      data: { pipeY, dashed: !e.forwarding, edge: e, detail },
    }
  })

  return { rfNodes, rawEdges, allVlans }
}

// ============================================================
// 组件主体
// ============================================================
interface Props {
  location: string
  data: StpTopologyData
}

export default function StpTopologyCanvas({ location, data }: Props) {
  const { t } = useI18n()
  const rfRef = useRef<HTMLDivElement>(null)
  const [selectedVlan, setSelectedVlan] = useState<number | null>(null)
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const { rfNodes, rawEdges, allVlans } = useMemo(() => buildLayout(data), [data])

  const [nodes, , onNodesChange] = useNodesState(rfNodes)
  const [edges, , onEdgesChange] = useEdgesState(rawEdges)

  // VLAN 高亮：选中 VLAN 的边全亮，其余淡出；悬停的边显示端口明细
  const finalEdges = useMemo(() => edges.map(e => {
    const vlan = (e.data as any)?.edge?.vlan as number | undefined
    const highlighted = selectedVlan != null && vlan === selectedVlan
    const dimmed = selectedVlan != null && vlan !== selectedVlan
    return {
      ...e,
      data: { ...(e.data || {}), highlighted, dimmed, detailLabel: e.id === hoveredEdge ? (e.data as any)?.detail : undefined },
      zIndex: highlighted ? 10 : 0,
    }
  }), [edges, selectedVlan, hoveredEdge])

  const finalNodes = useMemo(() => nodes.map(n => ({
    ...n,
    data: { ...n.data, selectedVlan },
  })), [nodes, selectedVlan])

  const exportPng = useCallback(() => {
    const el = rfRef.current
    if (!el) return
    setExporting(true)
    exportTopologyAsPng(el, `stp-topology-${location}-${Date.now()}.png`).finally(() => setExporting(false))
  }, [location])

  const modeCheck = data.mode_check

  return (
    <Box ref={rfRef} sx={{ width: '100%', height: '100%', position: 'relative' }}>
      <style>{`
        .react-flow__controls-button{background:#1E293B!important;border-bottom:1px solid #334155!important;fill:#94A3B8!important;color:#94A3B8!important;width:28px!important;height:28px!important;border-radius:6px!important}
        .react-flow__controls-button svg{fill:#94A3B8!important}
        .react-flow__controls-button:hover{background:#334155!important;fill:#E2E8F0!important}
        .react-flow__controls{border-radius:8px!important;overflow:hidden!important;box-shadow:0 4px 16px rgba(0,0,0,0.4)!important}
      `}</style>

      <ReactFlow
        nodes={finalNodes} edges={finalEdges}
        nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onEdgeMouseEnter={(_, e) => setHoveredEdge(e.id)}
        onEdgeMouseLeave={() => setHoveredEdge(null)}
        onPaneClick={() => { setSelectedVlan(null); setHoveredEdge(null) }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        minZoom={0.05} maxZoom={3}
        onInit={(inst) => setTimeout(() => inst.fitView({ padding: 0.15, duration: 300, maxZoom: 1.2 }), 60)}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1E293B" gap={32} size={0.6} />

        <Controls position="bottom-left" style={{ display: 'flex', flexDirection: 'row', gap: 2, background: '#1E293BBB', backdropFilter: 'blur(8px)', borderRadius: 8, padding: 2 }} />

        {/* 站点头部告警：模式不一致 */}
        {!modeCheck.consistent && (
          <Panel position="top-center">
            <Paper sx={{ px: 2, py: 1, borderRadius: 2, bgcolor: 'rgba(245,158,11,0.15)', border: '1px solid #F59E0B40', backdropFilter: 'blur(8px)' }}>
              <Typography sx={{ fontSize: '0.75rem', color: '#FBBF24', fontFamily: '"Fira Code", monospace' }}>
                ⚠ {t('topology.stpModeInconsistent')}
                {': ' + Object.entries(modeCheck.modes).map(([k, v]) => `${k}=${v}`).join('，')}
              </Typography>
            </Paper>
          </Panel>
        )}

        {/* 根在站点外 */}
        {data.root_outside_site && (
          <Panel position="top-center">
            <Paper sx={{ px: 2, py: 1, mt: !modeCheck.consistent ? 5 : 0, borderRadius: 2, bgcolor: 'rgba(56,189,248,0.12)', border: '1px solid #38BDF840', backdropFilter: 'blur(8px)' }}>
              <Typography sx={{ fontSize: '0.75rem', color: '#7DD3FC', fontFamily: '"Fira Code", monospace' }}>
                ℹ {t('topology.stpRootOutside')}：{data.outside_root_macs.join(', ')}
              </Typography>
            </Paper>
          </Panel>
        )}
      </ReactFlow>

      {/* 左侧 VLAN 图例（点击高亮单个 VLAN 的生成树） */}
      <Paper sx={{
        position: 'absolute', top: 16, left: 16, zIndex: 10, maxHeight: '70%',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        borderRadius: 2, bgcolor: 'rgba(15,23,42,0.88)', backdropFilter: 'blur(10px)',
        border: '1px solid #334155', boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}>
        <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#94A3B8', px: 1.4, pt: 1, pb: 0.6 }}>
          {t('topology.stpVlanLegend')}
        </Typography>
        <Box sx={{ overflowY: 'auto', px: 1.4, pb: 0.8 }}>
          <Box onClick={() => setSelectedVlan(null)} sx={{
            display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer', py: 0.25,
            opacity: selectedVlan == null ? 1 : 0.5,
          }}>
            <Box sx={{ width: 12, height: 12, borderRadius: '3px', border: '1.5px solid #94A3B8' }} />
            <Typography sx={{ fontSize: '0.72rem', fontFamily: '"Fira Code", monospace', color: '#CBD5E1' }}>
              {t('topology.stpAllVlans')}
            </Typography>
          </Box>
          {allVlans.map(v => (
            <Box key={v} onClick={() => setSelectedVlan(selectedVlan === v ? null : v)} sx={{
              display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer', py: 0.25,
              opacity: selectedVlan == null || selectedVlan === v ? 1 : 0.35,
            }}>
              <Box sx={{ width: 12, height: 12, borderRadius: '3px', bgcolor: `${vlanColor(v, allVlans)}33`, border: `1.5px solid ${vlanColor(v, allVlans)}` }} />
              <Typography sx={{ fontSize: '0.72rem', fontFamily: '"Fira Code", monospace', color: '#E2E8F0' }}>
                VLAN {v}
              </Typography>
            </Box>
          ))}
        </Box>
        <Divider sx={{ borderColor: '#334155' }} />
        <Box sx={{ px: 1.4, py: 0.8 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.2 }}>
            <Box component="span" sx={{ fontSize: '0.7rem', color: '#FACC15' }}>★</Box>
            <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>{t('topology.stpLegendRoot')}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.2 }}>
            <Box sx={{ width: 22, height: 0, borderTop: '2px solid #94A3B8' }} />
            <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>{t('topology.stpLegendFwd')}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.2 }}>
            <Box sx={{ width: 22, height: 0, borderTop: '2px dashed #F87171' }} />
            <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>{t('topology.stpLegendBlk')}</Typography>
          </Box>
        </Box>
      </Paper>

      {/* 导出 PNG */}
      <Paper sx={{ position: 'absolute', top: 16, right: 16, zIndex: 10, borderRadius: 2, bgcolor: 'rgba(15,23,42,0.88)', backdropFilter: 'blur(10px)', border: '1px solid #334155', px: 0.5, py: 0.3, boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}>
        <Tooltip title={t('topology.exportPng')}>
          <IconButton size="small" disabled={exporting} onClick={exportPng} sx={{ color: '#94A3B8', '&:hover': { color: '#2DD46E' }, p: 0.5 }}>
            <ImageIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Paper>
    </Box>
  )
}
