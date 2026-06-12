import { useMemo, useState, useCallback } from 'react'
import {
  ReactFlow, Node, Edge, Background, Controls, MarkerType, type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Typography, IconButton, Stack, Tooltip, Paper, keyframes } from '@mui/material'
import { Image as ImageIcon, AccountTree as VisioIcon } from '@mui/icons-material'
import { toPng } from 'html-to-image'
import { useI18n } from '../../i18n'
import type { NeighborNode } from '../../types/topology'
import type { LocationTopologyData, LocationNode, LocationEdge } from '../../types/topology'
import FrontPanelNode, { getPortParity } from './FrontPanelNode'
import type { PortData } from './FrontPanelNode'
import DirectionPad from './DirectionPad'
import { getDeviceColor, isStackLink, ENDPOINT_PREFIXES } from '../../shared/constants'
import LocationTopologyCanvas from './LocationTopologyCanvas'

const nodeTypes: NodeTypes = { frontPanel: FrontPanelNode }

const canvasFadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`

// ====== 尺寸常量 ======
const CENTER_W = 620
const CENTER_BODY_H = 118
const CENTER_LABEL_H = 32
const NEIGHBOR_W = 240
const NEIGHBOR_H = 140
const COMPACT_W = 200
const COMPACT_H = 58
const H_GAP = 60
const V_GAP = 160
const ROW_GAP = 110
const MAX_PER_ROW = 5

/** 判断端口拓扑是否符合三层结构：有 WAN 设备 + 中心交换机 + 终端设备 */
function fitsThreeTier(neighbors: NeighborNode[]): boolean {
  const all = neighbors.filter(n => n.device_name)
  const hasWan = all.some(n => n.device_type === 'router' || n.device_type === 'firewall' || n.device_type === 'sdwan'
    || n.device_name.startsWith('Internet') || n.device_name.startsWith('互联网'))
  const hasAccess = all.some(n => n.is_endpoint || n.device_type === 'wireless' || n.device_type === 'printer')
  return hasWan && hasAccess
}

/** NeighborNode 数据转换为 LocationTopologyData（三层结构） */
function neighborsToLocationData(
  deviceName: string, neighbors: NeighborNode[],
  stackMembers?: string[], memberNeighbors?: Record<string, NeighborNode[]>,
): LocationTopologyData {
  const nodes: LocationNode[] = []
  const edges: LocationEdge[] = []
  let ei = 0

  // 处理多个 stack 成员 vs 单个设备
  const hasStack = stackMembers && stackMembers.length > 1
  const members = hasStack ? stackMembers! : ['1']

  // 收集所有中心端口
  type MemberPort = { member: string; iface: string; targetName: string; targetType: string }
  const allPorts: MemberPort[] = []

  for (const mid of members) {
    const memberName = hasStack ? `${deviceName}-0${mid}` : deviceName
    const nbrs = hasStack
      ? (memberNeighbors?.[mid] || []).filter(n => n.device_name && !isStackLink(n.description))
      : neighbors.filter(n => n.device_name && !isStackLink(n.description))

    for (const n of nbrs) {
      allPorts.push({ member: memberName, iface: n.interface, targetName: n.device_name, targetType: n.device_type })
    }
  }

  // 统计目标设备类型（含端点聚合组）
  const devMap = new Map<string, { type: string; entries: MemberPort[] }>()
  for (const p of allPorts) {
    let key: string; let dtype: string
    if (p.targetType && !p.targetName.startsWith('Internet') && !p.targetName.startsWith('互联网')) {
      // 检查是否是端点前缀匹配
      let isEp = false
      for (const ep of ENDPOINT_PREFIXES) {
        if (p.targetName.startsWith(ep.prefix)) { key = ep.label; dtype = 'endpoint'; isEp = true; break }
      }
      if (!isEp) { key = p.targetName; dtype = p.targetType }
    } else {
      key = p.targetName
      dtype = p.targetType || 'endpoint'
    }
    if (!devMap.has(key)) devMap.set(key, { type: dtype, entries: [] })
    devMap.get(key)!.entries.push(p)
  }

  // 分配 tier
  function tierFor(type: string, isCenter: boolean): string {
    if (isCenter) return 'core'
    if (type === 'router' || type === 'firewall' || type === 'sdwan') return 'wan'
    // Internet / 互联网 归入 WAN
    return 'access'
  }

  // 中心设备节点
  const centerIds: string[] = []
  for (const mid of members) {
    const memberName = hasStack ? `${deviceName}-0${mid}` : deviceName
    centerIds.push(memberName)
    nodes.push({
      id: memberName, label: memberName, type: 'switch',
      platform: '', model: '', ip: '',
      tier: 'core', is_location_device: true, location: deviceName,
      stack_group: hasStack ? deviceName : '',
      physical_index: hasStack ? parseInt(mid, 10) : 1,
      physical_count: members.length,
    })
  }

  // 邻居设备节点 + 边
  const addedNodes = new Set<string>()
  for (const [name, dev] of devMap) {
    const actualTier = (name.startsWith('Internet') || name.startsWith('互联网')) ? 'wan'
      : (dev.type === 'wireless' || dev.type === 'printer' || dev.type === 'endpoint') ? 'access'
      : tierFor(dev.type, false)
    const isEp = dev.type === 'endpoint'

    const nodeId = name
    if (!addedNodes.has(nodeId)) {
      addedNodes.add(nodeId)
      const count = dev.entries.length
      nodes.push({
        id: nodeId,
        label: isEp ? `${name} ×${count}` : name,
        type: dev.type === 'endpoint' ? 'server' : dev.type,
        platform: isEp ? `${count} 端口` : '', model: '', ip: '',
        tier: actualTier,
        is_location_device: false, location: deviceName,
        stack_group: '', physical_index: 1, physical_count: 1,
      })
    }

    // 为每个物理连接创建边
    for (const p of dev.entries) {
      edges.push({
        id: `pe-${ei++}`,
        source: p.member,
        target: nodeId,
        source_interface: p.iface,
        target_interface: '',
        is_cross_location: false,
      })
    }
  }

  return {
    location: deviceName,
    device_count: centerIds.length + addedNodes.size,
    node_count: nodes.length,
    skipped_count: 0,
    skipped_devices: [],
    nodes,
    edges,
  }
}

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

  // ====== 三层结构检测 + 数据转换 ======
  const allNeighbors = useMemo(() =>
    hasStack
      ? members!.flatMap(mid => (memberNeighbors?.[mid] || []))
      : validNeighbors,
    [hasStack, members, memberNeighbors, validNeighbors],
  )

  const threeTierData = useMemo(() => {
    if (!fitsThreeTier(allNeighbors)) return null
    return neighborsToLocationData(deviceName, allNeighbors, stackMembers, memberNeighbors)
  }, [allNeighbors, deviceName, stackMembers, memberNeighbors])

  // ====== 设备分组 + 聚合（始终计算，hooks 数量恒定）======
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
  const centerFullH = CENTER_LABEL_H * 2 + CENTER_BODY_H
  const centerY = useMemo(() => {
    const topH = topRows.length * NEIGHBOR_H + Math.max(topRows.length - 1, 0) * ROW_GAP
    const bottomH = bottomRows.length * NEIGHBOR_H + Math.max(bottomRows.length - 1, 0) * ROW_GAP
    const total = topH + V_GAP + centerFullH + V_GAP + bottomH + 200
    return total / 2 + 80
  }, [topRows, bottomRows])

  const SWITCH_Y = centerY

  const switchPosY = (hasTop: boolean) => {
    const bodyTop = hasTop ? CENTER_LABEL_H : 0
    return SWITCH_Y - bodyTop - CENTER_BODY_H / 2
  }

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
        const hasTopP = ports.some((p: PortData) => p.direction === 'top')
        nodes.push({
          id: `center-${mid}`, type: 'frontPanel',
          position: { x: switchStartX + i * (CENTER_W + H_GAP), y: switchPosY(hasTopP) },
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
      const hasTopS = ports.some((p: PortData) => p.direction === 'top')
      nodes.push({
        id: 'center', type: 'frontPanel',
        position: { x: switchStartX, y: switchPosY(hasTopS) },
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
    const topRowEdgeY = SWITCH_Y - CENTER_LABEL_H - CENTER_BODY_H / 2
    const topRowStartY = topRowEdgeY - V_GAP
    topRows.forEach((row, ri) => {
      layRow(row, topRowStartY - ri * (NEIGHBOR_H + ROW_GAP))
    })

    // --- 下行区域（交换机下方）---
    const bottomRowEdgeY = SWITCH_Y + CENTER_LABEL_H + CENTER_BODY_H / 2
    const bottomRowStartY = bottomRowEdgeY + V_GAP
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
          markerEnd: { type: MarkerType.ArrowClosed, color: ep ? '#64748b' : dev.color, width: 10, height: 10 },
          label: dev.entries.length <= 1 ? undefined : e.interface,
          labelStyle: { fontSize: 11, fill: '#cbd5e1', fontWeight: 500 },
          labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9 },
        })
      })
    })

    return { nodes, edges }
  }, [topDevs, bottomDevs, topRows, bottomRows, maxW, centerY, hasStack, members, memberNeighbors, stackLinks, externalNeighbors, deviceName, t, memberCount, switchesW])

  // ====== 点击高亮 ======
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null)

  const onNodeClick = useCallback((_event: React.MouseEvent, n: Node) => {
    if (!n.id.startsWith('center')) setSelectedTarget(p => p === n.id ? null : n.id)
  }, [])

  const onEdgeClick = useCallback((_event: React.MouseEvent, e: Edge) => {
    if (e.target && !e.target.startsWith('center') && !e.id.startsWith('stack-')) {
      setSelectedTarget(p => p === e.target ? null : e.target)
    }
  }, [])

  const onPaneClick = useCallback(() => setSelectedTarget(null), [])

  // ====== 偏移状态 ======
  const [offsets, setOffsets] = useState<Record<string, { dx: number; dy: number }>>({})

  const positionedNodes = useMemo(() =>
    nodes.map(n => {
      const off = offsets[n.id]; if (!off) return n
      return { ...n, position: { x: n.position.x + off.dx, y: n.position.y + off.dy } }
    }), [nodes, offsets])

  const finalNodes = useMemo(() => {
    if (!selectedTarget) return positionedNodes
    return positionedNodes.map(n => {
      if (n.id.startsWith('center')) return n
      return n.id === selectedTarget
        ? { ...n, data: { ...n.data, highlighted: true }, selected: true }
        : { ...n, style: { opacity: 0.2 } }
    })
  }, [positionedNodes, selectedTarget])

  const finalEdges = useMemo(() => {
    if (!selectedTarget) return edges
    return edges.map(e => {
      const isStack = e.id.startsWith('stack-')
      if (isStack) return e
      return e.target === selectedTarget
        ? { ...e, style: { ...e.style, strokeWidth: 5, opacity: 1 }, animated: true }
        : { ...e, style: { ...e.style, opacity: 0.06 }, markerEnd: undefined }
    })
  }, [edges, selectedTarget])

  if (validNeighbors.length === 0) {
    return <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500, color: 'text.secondary' }}><Typography sx={{ fontSize: '1.1rem' }}>{t('topology.noNeighbors')}</Typography></Box>
  }

  // 符合三层结构 → 使用三层布局渲染
  if (threeTierData) {
    return (
      <Box sx={{ width: '100%', height: '100%', minHeight: 650, borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider', bgcolor: '#0a0e1a', animation: `${canvasFadeIn} 0.5s ease`, position: 'relative' }}>
        <LocationTopologyCanvas location={deviceName} data={threeTierData} />
      </Box>
    )
  }

  return (
    <Box sx={{ width: '100%', height: '100%', minHeight: 650, borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider', bgcolor: '#0a0e1a', animation: `${canvasFadeIn} 0.5s ease`, position: 'relative' }}>
      <style>{`.react-flow__controls-button{background:#1e293b!important;border:1px solid #334155!important;fill:#e2e8f0!important;width:32px!important;height:32px!important}.react-flow__controls-button svg{fill:#e2e8f0!important;max-width:16px!important;max-height:16px!important}.react-flow__controls-button:hover{background:#334155!important}.react-flow__controls{background:#0f172a!important;border:1px solid #1e293b!important;border-radius:8px!important;overflow:hidden!important}.react-flow__edge{cursor:pointer!important}`}</style>
      <ReactFlow nodes={finalNodes} edges={finalEdges} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.3 }}
        minZoom={0.06} maxZoom={3}
        nodesConnectable={false} elementsSelectable nodesFocusable={false}
        defaultEdgeOptions={{ type: 'smoothstep' }}
        proOptions={{ hideAttribution: true }}
        onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} onPaneClick={onPaneClick}
      >
        <Background color="#1e293b" gap={24} />
        <Controls />
      </ReactFlow>

      {/* 方向键盘 */}
      {selectedTarget && (
        <Box sx={{ position: 'absolute', bottom: 250, left: 16, zIndex: 20 }}>
          <DirectionPad
            step={40}
            onUp={() => setOffsets(p => ({...p,[selectedTarget]:{dx:(p[selectedTarget]?.dx||0),dy:(p[selectedTarget]?.dy||0)-40}}))}
            onDown={() => setOffsets(p => ({...p,[selectedTarget]:{dx:(p[selectedTarget]?.dx||0),dy:(p[selectedTarget]?.dy||0)+40}}))}
            onLeft={() => setOffsets(p => ({...p,[selectedTarget]:{dx:(p[selectedTarget]?.dx||0)-40,dy:(p[selectedTarget]?.dy||0)}}))}
            onRight={() => setOffsets(p => ({...p,[selectedTarget]:{dx:(p[selectedTarget]?.dx||0)+40,dy:(p[selectedTarget]?.dy||0)}}))}
            onReset={() => setOffsets({})}
          />
        </Box>
      )}

      {/* 导出按钮 */}
      {neighbors.length > 0 && (
        <Paper
          sx={{
            position: 'absolute', top: 16, right: 16, zIndex: 20,
            borderRadius: 2, bgcolor: 'rgba(15, 18, 35, 0.85)', backdropFilter: 'blur(8px)',
            border: '1px solid #334155', px: 0.5, py: 0.3,
          }}
        >
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Tooltip title="Export PNG">
              <IconButton size="small" onClick={() => {
                const el = document.querySelector('.react-flow') as HTMLElement
                if (el) toPng(el, { backgroundColor: '#0f1223', pixelRatio: 2 }).then((u: string) => {
                  const a = document.createElement('a'); a.download = `port-topology-${deviceName}.png`; a.href = u; a.click()
                })
              }} sx={{ color: '#94a3b8', '&:hover': { color: '#2DD46E' }, p: 0.5 }}>
                <ImageIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Export Visio">
              <IconButton size="small" onClick={() => {
                const exportData = {
                  nodes: finalNodes.map(n => ({ id: n.id, label: n.data.label, type: n.data.deviceType, platform: n.data.platform || '' })),
                  edges: finalEdges.map(e => ({ source: e.source, target: e.target, source_interface: e.data?.label || e.label || '' })),
                }
                import('../../services/api').then(({ topologyApi }) => {
                  topologyApi.exportVisio(exportData).then(b => {
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
      )}
    </Box>
  )
}
