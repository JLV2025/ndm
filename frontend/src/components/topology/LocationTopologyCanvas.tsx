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
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Paper, Typography, IconButton, Stack, Tooltip } from '@mui/material'
import { Image as ImageIcon, AccountTree as VisioIcon } from '@mui/icons-material'
import { toPng } from 'html-to-image'
import type { LocationTopologyData } from '../../types/topology'
import DirectionPad from './DirectionPad'

// ============================================================
// 布局常量
// ============================================================
const NODE_W = 200
const NODE_H = 58
const H_GAP = 40       // 设备间水平间距
const V_GAP = 200      // 层间垂直间距

// ============================================================
// 设备颜色 (与现有 LEGEND_ITEMS 一致)
// ============================================================
const TYPE_COLORS: Record<string, string> = {
  switch: '#3B82F6',
  router: '#F59E0B',
  firewall: '#EF4444',
  wireless: '#8B5CF6',
  sdwan: '#10B981',
  server: '#06B6D4',
  unknown: '#94A3B8',
}

// ============================================================
// 节点组件
// ============================================================

function DeviceNode({ data }: { data: any }) {
  const { label, deviceType, platform, isLocationDevice } = data
  const color = TYPE_COLORS[deviceType] || TYPE_COLORS.unknown
  const borderStyle = isLocationDevice ? '2px solid' : '1px dashed'

  return (
    <Box
      sx={{
        width: NODE_W,
        height: NODE_H,
        borderRadius: 1.5,
        border: borderStyle,
        borderColor: color,
        bgcolor: `${color}15`,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'box-shadow 150ms',
        '&:hover': {
          boxShadow: `0 0 16px ${color}40`,
        },
      }}
    >
      <Handle type="target" position={Position.Top} id="t" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Bottom} id="b" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Right} id="r" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Left} id="l" style={{ visibility: 'hidden' }} />
      <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color, lineHeight: 1.2 }}>
        {label}
      </Typography>
      {platform && (
        <Typography sx={{ fontSize: '0.55rem', color: '#64748b', lineHeight: 1.1 }}>
          {platform}
        </Typography>
      )}
    </Box>
  )
}

const nodeTypes = { deviceNode: DeviceNode }

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

  // 分层分组
  const tiers = useMemo(() => {
    const wan: typeof data.nodes = []
    const core: typeof data.nodes = []
    const access: typeof data.nodes = []
    for (const n of data.nodes) {
      if (n.tier === 'wan') wan.push(n)
      else if (n.tier === 'core') core.push(n)
      else access.push(n)
    }
    return { wan, core, access }
  }, [data.nodes])

  // 手工三层布局
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    const rfNodes: Node[] = []
    const maxPerRow = Math.max(tiers.wan.length, tiers.core.length, tiers.access.length, 1)
    const canvasW = maxPerRow * (NODE_W + H_GAP) + H_GAP

    const layRow = (items: typeof data.nodes, tierY: number) => {
      const rowW = items.length * (NODE_W + H_GAP) - H_GAP
      const startX = (canvasW - rowW) / 2
      items.forEach((node, i) => {
        rfNodes.push({
          id: node.id,
          type: 'deviceNode',
          position: { x: startX + i * (NODE_W + H_GAP), y: tierY },
          data: {
            label: node.label,
            deviceType: node.type,
            platform: node.platform,
            isLocationDevice: node.is_location_device,
          },
        })
      })
    }

    let currentY = 0
    layRow(tiers.wan, currentY)
    currentY += tiers.wan.length > 0 ? NODE_H + V_GAP : 0
    layRow(tiers.core, currentY)
    currentY += tiers.core.length > 0 ? NODE_H + V_GAP : 0
    layRow(tiers.access, currentY)

    // Build position map for smart edge routing
    const posMap: Record<string, { x: number; y: number }> = {}
    for (const n of rfNodes) {
      posMap[n.id] = { x: n.position.x, y: n.position.y }
    }

    const rfEdges: Edge[] = data.edges.map((e, i) => {
      const srcPos = posMap[e.source]
      const tgtPos = posMap[e.target]
      let sourcePosition: Position = Position.Bottom
      let targetPosition: Position = Position.Top
      let sourceHandle = 'b'
      let targetHandle = 't'

      if (srcPos && tgtPos) {
        const dx = tgtPos.x - srcPos.x
        const dy = tgtPos.y - srcPos.y
        if (Math.abs(dy) > Math.abs(dx)) {
          if (dy > 0) {
            sourcePosition = Position.Bottom; targetPosition = Position.Top
            sourceHandle = 'b'; targetHandle = 't'
          } else {
            sourcePosition = Position.Top; targetPosition = Position.Bottom
            sourceHandle = 't'; targetHandle = 'b'
          }
        } else {
          if (dx > 0) {
            sourcePosition = Position.Right; targetPosition = Position.Left
            sourceHandle = 'r'; targetHandle = 'l'
          } else {
            sourcePosition = Position.Left; targetPosition = Position.Right
            sourceHandle = 'l'; targetHandle = 'r'
          }
        }
      }

      return {
        id: e.id || `e-${i}`,
        source: e.source,
        target: e.target,
        type: 'smoothstep',
        sourcePosition,
        targetPosition,
        sourceHandle,
        targetHandle,
        label: e.source_interface,
        style: { stroke: '#64748b', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#64748b' },
        labelStyle: { fontSize: '0.55rem', fill: '#94a3b8' },
      }
    })

    return { nodes: rfNodes, edges: rfEdges }
  }, [tiers, data.edges])

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
      return { ...e, style: { ...e.style, opacity: 0.08 } }
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
    /* reset done */
  }, [])

  // PNG 导出
  const exportPng = useCallback(() => {
    if (!rfRef.current) return
    const flowEl = rfRef.current.querySelector('.react-flow') as HTMLElement
    if (flowEl) {
      toPng(flowEl, { backgroundColor: '#0f1223', pixelRatio: 2 }).then((dataUrl: string) => {
        const link = document.createElement('a')
        link.download = `topology-${location}-${Date.now()}.png`
        link.href = dataUrl
        link.click()
      })
    }
  }, [location])

  // Visio 导出
  const exportVisio = useCallback(() => {
    const apiBase = import.meta.env.PROD ? 'http://localhost:8002/api' : '/api'
    fetch(`${apiBase}/topology/export/visio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
      .then((res) => {
        if (!res.ok) throw new Error('Export failed')
        return res.blob()
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.download = `topology-${location}.vdx`
        link.href = url
        link.click()
        URL.revokeObjectURL(url)
      })
      .catch(console.error)
  }, [location, data])

  return (
    <Box ref={rfRef} sx={{ width: '100%', height: '100%', position: 'relative' }}>
      <style>{`
        .react-flow__controls-button {
          background: #1e293b !important;
          border-bottom: 1px solid #334155 !important;
          fill: #94a3b8 !important;
          color: #94a3b8 !important;
          width: 28px !important;
          height: 28px !important;
        }
        .react-flow__controls-button svg {
          fill: #94a3b8 !important;
        }
        .react-flow__controls-button:hover {
          background: #334155 !important;
        }
      `}</style>

      <ReactFlow
        nodes={positionedNodes}
        edges={finalEdges}
        nodeTypes={nodeTypes}
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
      >
        <Background color="#1e293b" gap={40} />
        <Controls position="bottom-left" />

        {/* Skipped warning */}
        {data.skipped_count > 0 && (
          <Panel position="top-center">
            <Paper
              sx={{
                px: 2, py: 1, borderRadius: 1.5,
                bgcolor: 'rgba(245, 158, 11, 0.12)', border: '1px solid #F59E0B40',
              }}
            >
              <Typography sx={{ fontSize: '0.7rem', color: '#F59E0B' }}>
                Skipped {data.skipped_count}: {data.skipped_devices.join(', ')}
              </Typography>
            </Paper>
          </Panel>
        )}

      </ReactFlow>

      {/* 方向键盘 — 左侧，Controls 上方 */}
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
          borderRadius: 2, bgcolor: 'rgba(15, 18, 35, 0.85)', backdropFilter: 'blur(8px)',
          border: '1px solid #334155', px: 0.5, py: 0.3,
        }}
      >
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Tooltip title="Export PNG">
            <IconButton size="small" onClick={exportPng} sx={{ color: '#94a3b8', '&:hover': { color: '#2DD46E' }, p: 0.5 }}>
              <ImageIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Export Visio">
            <IconButton size="small" onClick={exportVisio} sx={{ color: '#94a3b8', '&:hover': { color: '#8B5CF6' }, p: 0.5 }}>
              <VisioIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Paper>
    </Box>
  )
}
