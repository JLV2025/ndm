import { useMemo, useState, useCallback, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Panel,
  Handle,
  Position,
  Node,
  Edge,
  MarkerType,
  EdgeLabelRenderer,
  BaseEdge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Paper, Typography, IconButton, Stack, Tooltip } from '@mui/material'
import { Image as ImageIcon, AccountTree as VisioIcon } from '@mui/icons-material'
import { toPng } from 'html-to-image'
import type { LocationTopologyData, LocationNode } from '../../types/topology'
import DirectionPad from './DirectionPad'
import { getNodeColors, getDisplayType } from '../../shared/constants'

// ============================================================
// 布局常量
// ============================================================
const NODE_W = 210
const NODE_H = 78
const H_GAP = 50       // 独立设备间水平间距
const STACK_GAP = 20   // 堆叠成员间水平间距（各层统一）
const V_GAP = 220      // 层间垂直间距

// ============================================================
// DeviceNode 数据接口
// ============================================================
interface DeviceNodeData {
  label: string
  displayType: string  // core-switch / access-switch / router / firewall / sdwan 等
  tier: string
  platform: string
  ip: string
  isLocationDevice: boolean
}

// ============================================================
// 节点组件 — 按设备类型染色
// ============================================================

function DeviceNode({ data }: { data: DeviceNodeData }) {
  const { label, displayType, platform, ip, isLocationDevice } = data
  const colors = getNodeColors(displayType)

  return (
    <Box
      sx={{
        width: NODE_W,
        height: NODE_H,
        borderRadius: '10px',
        border: isLocationDevice ? `2px solid ${colors.border}` : `1px solid ${colors.glow}40`,
        bgcolor: isLocationDevice ? `${colors.fill}20` : `${colors.glow}10`,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'all 180ms ease',
        backdropFilter: 'blur(4px)',
        boxShadow: isLocationDevice
          ? `0 0 24px ${colors.glow}60, 0 4px 12px ${colors.glow}40, inset 0 0 20px ${colors.glow}10`
          : `0 0 8px ${colors.glow}20`,
        '&:hover': {
          boxShadow: `0 0 36px ${colors.glow}80, 0 6px 18px ${colors.glow}60`,
          borderColor: colors.border,
        },
      }}
    >
      {/* 上下方向 Handle */}
      <Handle type="target" position={Position.Top} id="tt" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Top} id="st" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Bottom} id="sb" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Bottom} id="tb" style={{ visibility: 'hidden' }} />
      {/* 同层水平连线用 */}
      <Handle type="source" position={Position.Right} id="sr" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Left} id="tl" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Left} id="sl" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Right} id="tr" style={{ visibility: 'hidden' }} />

      {/* 第一行：设备名 */}
      <Typography
        sx={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.72rem',
          fontWeight: 700,
          color: colors.glow,
          lineHeight: 1.3,
          letterSpacing: '-0.01em',
          textShadow: `0 0 8px ${colors.glow}40`,
        }}
      >
        {label}
      </Typography>

      {/* 第二行：型号 */}
      {platform && (
        <Typography
          sx={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.52rem',
            fontWeight: 500,
            color: '#64748B',
            lineHeight: 1.3,
          }}
        >
          {platform}
        </Typography>
      )}

      {/* 第三行：IP */}
      {ip && (
        <Typography
          sx={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.52rem',
            fontWeight: 500,
            color: '#94A3B8',
            lineHeight: 1.3,
          }}
        >
          {ip}
        </Typography>
      )}
    </Box>
  )
}

// ============================================================
// 自定义正交折线边 — 直接渲染 path
// 3 段（相邻层）: 源端口→间隙→水平→目标端口
// 5 段（跨层 WAN↔Access）: 源端口→间隙→绕行 X→下层间隙→水平→目标端口
// ============================================================
function GapOrthoEdge({
  id, data, markerEnd, markerStart, style, label,
}: {
  id: string; sourceX: number; sourceY: number; targetX: number; targetY: number;
  data?: { path?: string; lineColor?: string; midLabelX?: number; midLabelY?: number };
  markerEnd?: string; markerStart?: string; style?: React.CSSProperties; label?: string;
}) {
  const d = data || {}
  const lc = d.lineColor || (style?.stroke as string) || '#94A3B8'
  const sw = (style?.strokeWidth as number) || 2.5
  const path = d.path || ''

  return (
    <>
      <BaseEdge id={id} path={path} style={{ stroke: lc, strokeWidth: sw }} markerEnd={markerEnd} markerStart={markerStart} />
      {label && d.midLabelX != null && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${d.midLabelX}px,${d.midLabelY}px)`,
              background: '#0F172A',
              padding: '2px 6px',
              borderRadius: 3,
              fontSize: '0.62rem',
              fontWeight: 600,
              color: '#E2E8F0',
              fontFamily: '"JetBrains Mono", monospace',
              pointerEvents: 'all',
              whiteSpace: 'nowrap',
              opacity: 0.92,
            }}
            className="nodrag nopan"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { deviceNode: DeviceNode }
const edgeTypes = { gapOrtho: GapOrthoEdge }

// ============================================================
// 组件主体
// ============================================================

interface Props {
  location: string
  data: LocationTopologyData
}

export default function LocationTopologyCanvas({ location, data }: Props) {
  const rfRef = useRef<HTMLDivElement>(null)
  const [offsets, setOffsets] = useState<Record<string, { dx: number; dy: number }>>({})
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // 分层分组（每层内按设备名排序，同类设备相邻）
  const tiers = useMemo(() => {
    const nameOrder = (a: typeof data.nodes[0], b: typeof data.nodes[0]) =>
      a.label.localeCompare(b.label, undefined, { numeric: true, sensitivity: 'base' })
    const wan: typeof data.nodes = []
    const core: typeof data.nodes = []
    const access: typeof data.nodes = []
    for (const n of data.nodes) {
      if (n.tier === 'wan') wan.push(n)
      else if (n.tier === 'core') core.push(n)
      else access.push(n)
    }
    wan.sort(nameOrder)
    core.sort(nameOrder)
    access.sort(nameOrder)
    return { wan, core, access }
  }, [data.nodes])

  // 三层布局 + 边生成
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    const rfNodes: Node[] = []

    /** 收集一层所有节点（相对 x=0），返回该层总宽度 */
    const buildRowNodes = (items: typeof data.nodes, tierY: number): number => {
      const processed = new Set<string>()
      let colX = 0
      let firstPlaced = false

      for (let i = 0; i < items.length; i++) {
        const node = items[i]
        if (processed.has(node.id)) continue
        processed.add(node.id)

        // 非首个设备加 H_GAP 间隔
        if (firstPlaced) colX += H_GAP
        firstPlaced = true

        if (node.stack_group && node.physical_count > 1) {
          const siblings = items.filter(n => n.stack_group === node.stack_group && !processed.has(n.id))
          siblings.forEach(s => processed.add(s.id))
          const allMembers = [node, ...siblings].sort((a, b) => a.physical_index - b.physical_index)
          allMembers.forEach((member, mi) => {
            if (mi > 0) colX += STACK_GAP
            rfNodes.push({
              id: member.id,
              type: 'deviceNode',
              position: { x: colX, y: tierY },
              data: {
                label: member.label,
                displayType: getDisplayType(member.type, member.tier),
                tier: member.tier,
                platform: member.model || member.platform,
                ip: member.ip,
                isLocationDevice: member.is_location_device,
              },
            })
            colX += NODE_W
          })
        } else {
          rfNodes.push({
            id: node.id,
            type: 'deviceNode',
            position: { x: colX, y: tierY },
            data: {
              label: node.label,
              displayType: getDisplayType(node.type, node.tier),
              tier: node.tier,
              platform: node.model || node.platform,
              ip: node.ip,
              isLocationDevice: node.is_location_device,
            },
          })
          colX += NODE_W
        }
      }
      return colX  // 总宽度（末尾无多余间距）
    }

    // 逐层构建，记录每层的宽度 + 对应的节点下标范围
    let currentY = 0
    const rowWidths: number[] = []
    const rowStartIdx: number[] = []
    const rowY: number[] = []

    // WAN 层
    if (tiers.wan.length > 0) {
      rowStartIdx.push(rfNodes.length)
      rowWidths.push(buildRowNodes(tiers.wan, currentY))
      rowY.push(currentY)
      currentY += NODE_H + V_GAP
    }
    // Core 层
    if (tiers.core.length > 0) {
      rowStartIdx.push(rfNodes.length)
      rowWidths.push(buildRowNodes(tiers.core, currentY))
      rowY.push(currentY)
      currentY += NODE_H + V_GAP
    }
    // Access 层
    if (tiers.access.length > 0) {
      rowStartIdx.push(rfNodes.length)
      rowWidths.push(buildRowNodes(tiers.access, currentY))
      rowY.push(currentY)
    }

    rowStartIdx.push(rfNodes.length)  // 哨兵

    // 计算全局最大行宽，每层相对居中偏移
    const maxRowW = Math.max(...rowWidths, NODE_W)
    for (let ri = 0; ri < rowWidths.length; ri++) {
      const offsetX = (maxRowW - rowWidths[ri]) / 2
      if (offsetX > 0) {
        for (let i = rowStartIdx[ri]; i < rowStartIdx[ri + 1]; i++) {
          rfNodes[i].position = { x: rfNodes[i].position.x + offsetX, y: rfNodes[i].position.y }
        }
      }
    }

    // ─────── 位置映射 ───────
    const posMap: Record<string, { x: number; y: number }> = {}
    const nodeCenterX: Record<string, number> = {}
    for (const n of rfNodes) {
      posMap[n.id] = { x: n.position.x, y: n.position.y }
      nodeCenterX[n.id] = n.position.x + NODE_W / 2
    }

    const tierRank: Record<string, number> = { wan: 3, core: 2, access: 1, unknown: 0 }
    const tierToRow: Record<string, number> = {}
    if (tiers.wan.length > 0) tierToRow.wan = 0
    if (tiers.core.length > 0) tierToRow.core = tiers.wan.length > 0 ? 1 : 0
    if (tiers.access.length > 0) tierToRow.access = (tiers.wan.length > 0 ? 1 : 0) + (tiers.core.length > 0 ? 1 : 0)

    // 间隙中心 Y
    const gapCenter: number[] = []
    for (let i = 0; i < rowY.length - 1; i++) {
      gapCenter.push((rowY[i] + NODE_H + rowY[i + 1]) / 2)
    }

    // 核心层 X 范围（跨层绕行用）
    let coreMinX = Infinity, coreMaxX = -Infinity
    for (const n of tiers.core) {
      const p = posMap[n.id]; if (p) {
        coreMinX = Math.min(coreMinX, p.x)
        coreMaxX = Math.max(coreMaxX, p.x + NODE_W)
      }
    }

    const DETOUR_GAP = 30   // 绕行距核心层外侧间距
    const LAYER_SP = 24     // 同空隙内层间距

    // ─────── 合并双向边 ───────
    type PairEdge = { a: string; b: string; ports: { fromA: string[]; fromB: string[] } }
    const pairEdges = new Map<string, PairEdge>()
    for (const e of data.edges) {
      const key = e.source < e.target ? `${e.source}||${e.target}` : `${e.target}||${e.source}`
      if (!pairEdges.has(key)) {
        pairEdges.set(key, { a: e.source, b: e.target, ports: { fromA: [], fromB: [] } })
      }
      const pe = pairEdges.get(key)!
      if (e.source === pe.a) pe.ports.fromA.push(e.source_interface)
      else pe.ports.fromB.push(e.source_interface)
    }

    // 构建每条边的元信息
    type EdgeMeta = {
      pairKey: string
      a: string; b: string
      aTier: string; bTier: string
      sameTier: boolean; crossTier: boolean
      higherDisplay: string; lineColor: string
      label: string
    }
    const allEdges: EdgeMeta[] = []

    for (const [pkey, pe] of pairEdges) {
      const aNode = data.nodes.find(n => n.id === pe.a)
      const bNode = data.nodes.find(n => n.id === pe.b)
      const aTier = aNode?.tier || 'unknown'
      const bTier = bNode?.tier || 'unknown'
      const aDisplay = aNode ? getDisplayType(aNode.type, aTier) : 'unknown'
      const bDisplay = bNode ? getDisplayType(bNode.type, bTier) : 'unknown'
      const higherDisplay = tierRank[aTier] >= tierRank[bTier] ? aDisplay : bDisplay
      const lineColor = getNodeColors(higherDisplay).border
      const aPorts = pe.ports.fromA.join(',')
      const bPorts = pe.ports.fromB.join(',')
      const label = [aPorts, bPorts].filter(Boolean).join(' / ')
      const aRow = tierToRow[aTier] ?? 0; const bRow = tierToRow[bTier] ?? 0
      const sameTier = aRow === bRow
      const crossTier = Math.abs(aRow - bRow) === 2

      allEdges.push({ pairKey: pkey, a: pe.a, b: pe.b, aTier, bTier, sameTier, crossTier, higherDisplay, lineColor, label })
    }

    // ─────── 每间隙收集所有经过的边（相邻层 + 跨层），同层边不参与 ───
    const gapEdgeKeys: string[][] = gapCenter.map(() => [])
    for (const em of allEdges) {
      if (em.sameTier) continue  // 同层边不进入间隙路由
      const aRow = tierToRow[em.aTier] ?? 0
      const bRow = tierToRow[em.bTier] ?? 0
      if (em.crossTier) {
        if (gapCenter.length >= 2) {
          gapEdgeKeys[0].push(em.pairKey)
          gapEdgeKeys[1].push(em.pairKey)
        }
      } else {
        const gapIdx = Math.min(aRow, bRow)
        if (gapIdx < gapCenter.length) gapEdgeKeys[gapIdx].push(em.pairKey)
      }
    }

    // 每间隙按 source 设备 X 排序，确定各边在该间隙的层序号
    const edgeByKey = new Map(allEdges.map(e => [e.pairKey, e]))
    // 存储每条边在每个间隙的层索引（-1 表示不经过该间隙）
    const edgeGapLayers = new Map<string, number[]>()

    for (const em of allEdges) {
      const layers: number[] = gapCenter.map(() => -1)
      edgeGapLayers.set(em.pairKey, layers)
    }

    for (let gi = 0; gi < gapCenter.length; gi++) {
      const keys = gapEdgeKeys[gi]
      // 按 source 设备 X 排序
      keys.sort((ka, kb) => {
        const ea = edgeByKey.get(ka)!
        const eb = edgeByKey.get(kb)!
        return (nodeCenterX[ea.a] ?? 0) - (nodeCenterX[eb.a] ?? 0)
      })
      for (let li = 0; li < keys.length; li++) {
        const layers = edgeGapLayers.get(keys[li])!
        layers[gi] = li
      }
    }

    // ─────── 选取绕行 X（跨层边就近到核心层侧，垂直分层避免重叠）───────
    const V_LAYER_SP = 18  // 垂直线段层间距

    const detourXForEdge = (em: EdgeMeta): number => {
      const aRow = tierToRow[em.aTier] ?? 0
      const aCX = nodeCenterX[em.a] ?? 0
      const layers = edgeGapLayers.get(em.pairKey)!
      // 源在 WAN 层走 gap[0]，源在 Access 层走 gap[1]
      const srcGapIdx = aRow === 0 ? 0 : 1
      const srcGapLayer = layers[srcGapIdx]
      // 源在核心左侧 → 绕左侧，右侧 → 绕右侧
      const midCoreX = (coreMinX + coreMaxX) / 2
      const baseX = aCX < midCoreX ? coreMinX - DETOUR_GAP : coreMaxX + DETOUR_GAP
      // 同侧多条跨层边——垂直段按层序号偏移
      return baseX + (aCX < midCoreX ? -1 : 1) * (srcGapLayer - ((gapEdgeKeys[srcGapIdx].length - 1) / 2)) * V_LAYER_SP
    }

    // ─────── 生成 SVG path ───────
    const rfEdges: Edge[] = []

    for (const em of allEdges) {
      const aPos = posMap[em.a]; const bPos = posMap[em.b]
      const aCX = nodeCenterX[em.a] ?? 0; const bCX = nodeCenterX[em.b] ?? 0
      const layers = edgeGapLayers.get(em.pairKey)!

      let path: string, source: string, target: string
      let sourceHandle: string, targetHandle: string
      let srcPos: Position, tgtPos: Position
      let midLabelX: number, midLabelY: number

      if (em.sameTier) {
        // ─── 同层水平直连 — 标签放在该层上方间隙中 ───
        const lineY = aPos!.y + NODE_H / 2  // 设备垂直中点（走线用）
        if (aCX <= bCX) {
          source = em.a; target = em.b
          sourceHandle = 'sr'; srcPos = Position.Right
          targetHandle = 'tl'; tgtPos = Position.Left
          path = `M ${aPos!.x + NODE_W},${lineY} L ${bPos!.x},${lineY}`
        } else {
          source = em.a; target = em.b
          sourceHandle = 'sl'; srcPos = Position.Left
          targetHandle = 'tr'; tgtPos = Position.Right
          path = `M ${aPos!.x},${lineY} L ${bPos!.x + NODE_W},${lineY}`
        }
        // 标签放在该层上方 24px 处，不被设备方框遮挡
        midLabelX = (aCX + bCX) / 2
        midLabelY = aPos!.y - 24
      } else if (em.crossTier) {
        // ─── 跨层 7 段路径 ───
        const detourX = detourXForEdge(em)
        // gap1Y = WAN-Core gap lane; gap2Y = Core-Access gap lane
        const g0Len = gapEdgeKeys[0].length; const g1Len = gapEdgeKeys[1].length
        const gap1Y = gapCenter[0] + (layers[0] - (g0Len - 1) / 2) * LAYER_SP
        const gap2Y = gapCenter[1] + (layers[1] - (g1Len - 1) / 2) * LAYER_SP
        const aRow = tierToRow[em.aTier] ?? 0
        const isTopDown = aRow === 0  // WAN → Access

        if (isTopDown) {
          source = em.a; target = em.b
          sourceHandle = 'sb'; srcPos = Position.Bottom
          targetHandle = 'tt'; tgtPos = Position.Top
          const sy = aPos!.y + NODE_H  // WAN 设备底部
          const ty = bPos!.y            // Access 设备顶部
          // ①垂直下到 gap1 ②水平到 detourX ③垂直下到 gap2 ④水平到目标 X ⑤垂直到目标
          path = `M ${aCX},${sy} L ${aCX},${gap1Y} L ${detourX},${gap1Y} L ${detourX},${gap2Y} L ${bCX},${gap2Y} L ${bCX},${ty}`
          midLabelX = (detourX + bCX) / 2; midLabelY = gap2Y
        } else {
          source = em.a; target = em.b
          sourceHandle = 'st'; srcPos = Position.Top
          targetHandle = 'tb'; tgtPos = Position.Bottom
          const sy = aPos!.y             // Access 设备顶部
          const ty = bPos!.y + NODE_H    // WAN 设备底部
          path = `M ${aCX},${sy} L ${aCX},${gap2Y} L ${detourX},${gap2Y} L ${detourX},${gap1Y} L ${bCX},${gap1Y} L ${bCX},${ty}`
          midLabelX = (aCX + detourX) / 2; midLabelY = gap2Y
        }
      } else {
        // ─── 相邻层 3 段路径 ───
        const gi = Math.min(tierToRow[em.aTier] ?? 0, tierToRow[em.bTier] ?? 0)
        const gLen = gapEdgeKeys[gi].length
        const laneY = gapCenter[gi] + (layers[gi] - (gLen - 1) / 2) * LAYER_SP

        if (aPos!.y <= bPos!.y) {
          source = em.a; target = em.b
          sourceHandle = 'sb'; srcPos = Position.Bottom
          targetHandle = 'tt'; tgtPos = Position.Top
          const sy = aPos!.y + NODE_H; const ty = bPos!.y
          path = `M ${aCX},${sy} L ${aCX},${laneY} L ${bCX},${laneY} L ${bCX},${ty}`
        } else {
          source = em.a; target = em.b
          sourceHandle = 'st'; srcPos = Position.Top
          targetHandle = 'tb'; tgtPos = Position.Bottom
          const sy = aPos!.y; const ty = bPos!.y + NODE_H
          path = `M ${aCX},${sy} L ${aCX},${laneY} L ${bCX},${laneY} L ${bCX},${ty}`
        }
        midLabelX = (aCX + bCX) / 2; midLabelY = laneY
      }

      rfEdges.push({
        id: `e-${em.a}-${em.b}`,
        source, target,
        type: 'gapOrtho',
        sourcePosition: srcPos, targetPosition: tgtPos,
        sourceHandle, targetHandle,
        data: { path, lineColor: em.lineColor, midLabelX, midLabelY },
        label: em.label || undefined,
        style: { stroke: em.lineColor, strokeWidth: 2.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: em.lineColor, width: 18, height: 18 },
        markerStart: { type: MarkerType.ArrowClosed, color: em.lineColor, width: 18, height: 18 },
      })
    }

    return { nodes: rfNodes, edges: rfEdges }
  }, [tiers, data.edges, data.nodes])

  // 应用偏移
  const positionedNodes = useMemo(() => {
    return layoutNodes.map((n) => {
      const off = offsets[n.id]
      if (off) {
        return { ...n, position: { x: n.position.x + off.dx, y: n.position.y + off.dy } }
      }
      return n
    })
  }, [layoutNodes, offsets])

  // 选中关联边高亮
  const finalEdges = useMemo(() => {
    if (!selectedNodeId) return layoutEdges
    return layoutEdges.map((e) => {
      if (e.source === selectedNodeId || e.target === selectedNodeId) {
        return { ...e, style: { ...e.style, stroke: '#2DD46E', strokeWidth: 4 }, animated: true }
      }
      return { ...e, style: { ...e.style, opacity: 0.06 }, labelStyle: { ...e.labelStyle, opacity: 0.06 } }
    })
  }, [layoutEdges, selectedNodeId])

  const onNodeClick = useCallback((_event: any, node: Node) => {
    setSelectedNodeId((prev) => (prev === node.id ? null : node.id))
  }, [])

  const onPaneClick = useCallback(() => setSelectedNodeId(null), [])

  // 方向键
  const moveSelected = useCallback((dx: number, dy: number) => {
    if (!selectedNodeId) return
    setOffsets((prev) => {
      const cur = prev[selectedNodeId] || { dx: 0, dy: 0 }
      return { ...prev, [selectedNodeId]: { dx: cur.dx + dx, dy: cur.dy + dy } }
    })
  }, [selectedNodeId])

  const resetOffsets = useCallback(() => {
    setOffsets({})
  }, [])

  // PNG 导出
  const exportPng = useCallback(() => {
    if (!rfRef.current) return
    const flowEl = rfRef.current.querySelector('.react-flow') as HTMLElement
    if (flowEl) {
      toPng(flowEl, { backgroundColor: '#0a0d1a', pixelRatio: 2 }).then((dataUrl: string) => {
        const link = document.createElement('a')
        link.download = `topology-${location}-${Date.now()}.png`
        link.href = dataUrl
        link.click()
      })
    }
  }, [location])

  // Visio 导出 — 通过 API 服务层
  const exportVisio = useCallback(() => {
    import('../../services/api').then(({ topologyApi }) => {
      topologyApi.exportVisio(data).then((blob) => {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.download = `topology-${location}.vdx`
        link.href = url
        link.click()
        URL.revokeObjectURL(url)
      }).catch(console.error)
    })
  }, [location, data])

  return (
    <Box ref={rfRef} sx={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* 暗色主题注入 */}
      <style>{`
        .react-flow__controls-button {
          background: #1E293B !important;
          border-bottom: 1px solid #334155 !important;
          fill: #94A3B8 !important;
          color: #94A3B8 !important;
          width: 28px !important;
          height: 28px !important;
          border-radius: 6px !important;
        }
        .react-flow__controls-button svg {
          fill: #94A3B8 !important;
        }
        .react-flow__controls-button:hover {
          background: #334155 !important;
          fill: #E2E8F0 !important;
        }
        .react-flow__controls {
          border-radius: 8px !important;
          overflow: hidden !important;
          box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important;
        }
        .react-flow__edge-textbg {
          fill: #0F172A !important;
        }
        /* 选中节点发光动画 */
        .react-flow__node.selected .MuiBox-root {
          box-shadow: 0 0 24px rgba(45, 212, 110, 0.5) !important;
        }
      `}</style>

      <ReactFlow
        nodes={positionedNodes}
        edges={finalEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.1}
        maxZoom={3}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          type: 'gapOrtho',
          animated: false,
        }}
      >
        <Background color="#1E293B" gap={32} size={0.6} />

        {/* 网络网格叠加 — 微妙的六边形纹理 */}
        <svg
          style={{
            position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
            pointerEvents: 'none', opacity: 0.04, zIndex: 0,
          }}
        >
          <pattern id="hexGrid" width="40" height="69.28" patternUnits="userSpaceOnUse">
            <path
              d="M40 11.55l-10-5.77-10 5.77v11.55l10 5.77 10-5.77V11.55zM20 46.19l-10-5.77-10 5.77v11.55l10 5.77 10-5.77V46.19zM0 11.55l-10-5.77-10 5.77v11.55l10 5.77 10-5.77V11.55z"
              fill="none"
              stroke="#3B82F6"
              strokeWidth="0.5"
            />
          </pattern>
          <rect width="100%" height="100%" fill="url(#hexGrid)" />
        </svg>

        <Controls
          position="bottom-left"
          style={{
            display: 'flex', flexDirection: 'row', gap: 2,
            background: '#1E293BBB', backdropFilter: 'blur(8px)',
            borderRadius: 8, padding: 2,
          }}
        />

        {/* Skipped 设备警告 */}
        {data.skipped_count > 0 && (
          <Panel position="top-center">
            <Paper
              sx={{
                px: 2, py: 1, borderRadius: 2,
                bgcolor: 'rgba(245, 158, 11, 0.15)',
                border: '1px solid #F59E0B40',
                backdropFilter: 'blur(8px)',
              }}
            >
              <Typography sx={{ fontSize: '0.7rem', color: '#FBBF24', fontFamily: '"JetBrains Mono", monospace' }}>
                ⚠ {data.skipped_count} 台设备无邻居数据: {data.skipped_devices.join(', ')}
              </Typography>
            </Paper>
          </Panel>
        )}

      </ReactFlow>

      {/* 方向键 — 选中节点时显示 */}
      {selectedNodeId && (
        <Box sx={{ position: 'absolute', bottom: 200, left: 16, zIndex: 20 }}>
          <DirectionPad
            step={10}
            onUp={() => moveSelected(0, -10)}
            onDown={() => moveSelected(0, 10)}
            onLeft={() => moveSelected(-10, 0)}
            onRight={() => moveSelected(10, 0)}
            onReset={resetOffsets}
          />
        </Box>
      )}

      {/* 导出按钮 — 右上角 */}
      <Paper
        sx={{
          position: 'absolute', top: 16, right: 16, zIndex: 10,
          borderRadius: 2,
          bgcolor: 'rgba(15, 23, 42, 0.88)',
          backdropFilter: 'blur(10px)',
          border: '1px solid #334155',
          px: 0.5, py: 0.3,
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        }}
      >
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Tooltip title="导出 PNG">
            <IconButton size="small" onClick={exportPng} sx={{ color: '#94A3B8', '&:hover': { color: '#2DD46E' }, p: 0.5 }}>
              <ImageIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="导出 Visio">
            <IconButton size="small" onClick={exportVisio} sx={{ color: '#94A3B8', '&:hover': { color: '#8B5CF6' }, p: 0.5 }}>
              <VisioIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Paper>
    </Box>
  )
}
