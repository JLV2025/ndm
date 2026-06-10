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
const NODE_W = 210
const NODE_H = 78
const H_GAP = 50
const V_GAP = 220

// ============================================================
// 设备颜色 — 工业级调色板（更高对比度 + 发光效果）
// ============================================================
const TYPE_COLORS: Record<string, { fill: string; glow: string; border: string }> = {
  switch:   { fill: '#2563EB', glow: '#3B82F6', border: '#60A5FA' },
  router:   { fill: '#D97706', glow: '#F59E0B', border: '#FBBF24' },
  firewall: { fill: '#DC2626', glow: '#EF4444', border: '#F87171' },
  wireless: { fill: '#7C3AED', glow: '#8B5CF6', border: '#A78BFA' },
  sdwan:    { fill: '#059669', glow: '#10B981', border: '#34D399' },
  server:   { fill: '#0891B2', glow: '#06B6D4', border: '#22D3EE' },
  unknown:  { fill: '#475569', glow: '#64748B', border: '#94A3B8' },
}

// ============================================================
// 节点组件 — 强化视觉层次
// ============================================================

function DeviceNode({ data }: { data: any }) {
  const { label, deviceType, platform, ip, isLocationDevice } = data
  const colors = TYPE_COLORS[deviceType] || TYPE_COLORS.unknown

  return (
    <Box
      sx={{
        width: NODE_W,
        height: NODE_H,
        borderRadius: '10px',
        border: isLocationDevice ? `2px solid ${colors.border}` : `1.5px solid ${colors.fill}50`,
        bgcolor: isLocationDevice ? `${colors.fill}20` : `${colors.fill}0A`,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'all 180ms ease',
        backdropFilter: 'blur(4px)',
        boxShadow: isLocationDevice
          ? `0 0 20px ${colors.glow}30, inset 0 0 20px ${colors.glow}08`
          : 'none',
        '&:hover': {
          boxShadow: `0 0 24px ${colors.glow}50`,
          borderColor: colors.border,
        },
      }}
    >
      {/* 8 方向 Handle */}
      <Handle type="target" position={Position.Top} id="tt" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Top} id="st" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Bottom} id="sb" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Bottom} id="tb" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Right} id="sr" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Right} id="tr" style={{ visibility: 'hidden' }} />
      <Handle type="target" position={Position.Left} id="tl" style={{ visibility: 'hidden' }} />
      <Handle type="source" position={Position.Left} id="sl" style={{ visibility: 'hidden' }} />

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

  // 三层布局 + 边生成（修复 Handle ID 匹配）
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    const rfNodes: Node[] = []
    const maxPerRow = Math.max(tiers.wan.length, tiers.core.length, tiers.access.length, 1)
    const canvasW = maxPerRow * (NODE_W + H_GAP) + H_GAP

    const layRow = (items: typeof data.nodes, tierY: number) => {
      // 按 stack_group 分组，堆叠成员上下排列
      const stackOffset = 12  // 同组内成员垂直间距
      const processed = new Set<string>()
      let colX = 0
      items.forEach((node) => {
        if (processed.has(node.id)) return
        processed.add(node.id)

        if (node.stack_group && node.physical_count > 1) {
          // 堆叠成员: 同一逻辑设备的所有物理成员放在同一列，上下叠放
          const siblings = items.filter(n => n.stack_group === node.stack_group && !processed.has(n.id))
          siblings.forEach(s => processed.add(s.id))
          const allMembers = [node, ...siblings].sort((a, b) => a.physical_index - b.physical_index)
          const groupTotalH = allMembers.length * (NODE_H + stackOffset) - stackOffset
          const groupStartY = tierY - groupTotalH / 2 + NODE_H / 2
          allMembers.forEach((member, mi) => {
            rfNodes.push({
              id: member.id,
              type: 'deviceNode',
              position: { x: colX, y: groupStartY + mi * (NODE_H + stackOffset) },
              data: {
                label: member.label,
                deviceType: member.type,
                platform: member.model || member.platform,
                ip: member.ip,
                isLocationDevice: member.is_location_device,
              },
            })
          })
          colX += NODE_W + H_GAP
        } else {
          // 非堆叠: 正常排列
          rfNodes.push({
            id: node.id,
            type: 'deviceNode',
            position: { x: colX, y: tierY },
            data: {
              label: node.label,
              deviceType: node.type,
              platform: node.model || node.platform,
              ip: node.ip,
              isLocationDevice: node.is_location_device,
            },
          })
          colX += NODE_W + H_GAP
        }
      })
    }

    let currentY = 0
    layRow(tiers.wan, currentY)
    currentY += tiers.wan.length > 0 ? NODE_H + V_GAP : 0
    layRow(tiers.core, currentY)
    currentY += tiers.core.length > 0 ? NODE_H + V_GAP : 0
    layRow(tiers.access, currentY)

    // 位置映射
    const posMap: Record<string, { x: number; y: number }> = {}
    for (const n of rfNodes) {
      posMap[n.id] = { x: n.position.x, y: n.position.y }
    }

    const rfEdges: Edge[] = data.edges.map((e, i) => {
      const srcPos = posMap[e.source]
      const tgtPos = posMap[e.target]
      let sourceHandle = 'sb'      // 默认 source → bottom
      let targetHandle = 'tt'      // 默认 target → top
      let sourcePosition: Position = Position.Bottom
      let targetPosition: Position = Position.Top

      if (srcPos && tgtPos) {
        const dx = tgtPos.x - srcPos.x
        const dy = tgtPos.y - srcPos.y

        if (Math.abs(dy) > Math.abs(dx)) {
          // 垂直主导
          if (dy > 0) {
            // 目标在下方: source=bottom, target=top
            sourceHandle = 'sb'; targetHandle = 'tt'
            sourcePosition = Position.Bottom; targetPosition = Position.Top
          } else {
            // 目标在上方: source=top, target=bottom
            sourceHandle = 'st'; targetHandle = 'tb'
            sourcePosition = Position.Top; targetPosition = Position.Bottom
          }
        } else {
          // 水平主导
          if (dx > 0) {
            // 目标在右侧: source=right, target=left
            sourceHandle = 'sr'; targetHandle = 'tl'
            sourcePosition = Position.Right; targetPosition = Position.Left
          } else {
            // 目标在左侧: source=left, target=right
            sourceHandle = 'sl'; targetHandle = 'tr'
            sourcePosition = Position.Left; targetPosition = Position.Right
          }
        }
      }

      // 连线颜色取源/目标设备中有颜色的那个
      const srcType = data.nodes.find(n => n.id === e.source)?.type || 'unknown'
      const tgtType = data.nodes.find(n => n.id === e.target)?.type || 'unknown'
      const lineColor = srcType !== 'unknown'
        ? (TYPE_COLORS[srcType] || TYPE_COLORS.unknown).border
        : (TYPE_COLORS[tgtType] || TYPE_COLORS.unknown).border

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
        style: { stroke: lineColor, strokeWidth: 2.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: lineColor, width: 18, height: 18 },
        labelStyle: {
          fill: '#E2E8F0',
          fontSize: '0.62rem',
          fontWeight: 600,
          fontFamily: '"JetBrains Mono", monospace',
        },
        labelBgStyle: {
          fill: '#0F172A',
          fillOpacity: 0.85,
          rx: 3,
          ry: 3,
        },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 3,
        pathOptions: { borderRadius: 12 },
      }
    })

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
          type: 'smoothstep',
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
