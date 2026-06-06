import React, { useState, useCallback, useMemo } from 'react'
import { Box, Paper, Typography, Tooltip, Chip } from '@mui/material'
import type { PortInfo } from '../../types'

interface FrontPanelProps {
  ports: PortInfo[]
  deviceName: string
  deviceType?: string
  devicePlatform?: string
}

const PORT_SIZE = 28
const PORT_GAP = 4
const SFP_GAP = 16

const LEGEND_ITEMS = [
  { color: '#2DD46E', label: 'UP' },
  { color: '#F59E0B', label: 'UP (>80% Util)' },
  { color: '#EF4444', label: 'Error/Down' },
  { color: '#1E293B', label: 'Down/Disabled' },
] as const

/** 端口状态 → 颜色映射 */
function getPortColor(port: PortInfo): string {
  if (port.status === 'err-disabled' || port.status === 'error') return '#EF4444'
  if (!port.status_up) return '#1E293B'
  const util = port.total_util_pct ?? ((port.rx_mbps ?? 0) + (port.tx_mbps ?? 0))
  if (util > 80) return '#F59E0B'
  return '#2DD46E'
}

/** 简化端口标签 */
function getPortLabel(port: PortInfo): string {
  const parts = port.name.split('/')
  const last = parts[parts.length - 1]
  if (port.name.startsWith('Te') || port.name.startsWith('Twe')) return 'T' + last
  if (port.name.startsWith('Hu')) return 'H' + last
  if (port.name.startsWith('Fo')) return 'F' + last
  if (port.name.startsWith('Fi')) return '5' + last
  if (port.name.startsWith('lag')) return port.name.toUpperCase()
  return last
}

/** 提取端口数字 */
function getPortNumber(port: PortInfo): number {
  const parts = port.name.split('/')
  return parseInt(parts[parts.length - 1]) || 0
}

/** 按 slot 分组 + 排序 */
function groupPortsBySlot(ports: PortInfo[]): Map<number, PortInfo[]> {
  const groups = new Map<number, PortInfo[]>()
  for (const port of ports) {
    if (/^(vlan|loopback|lag|Po)/i.test(port.name)) continue
    const m = port.name.match(/^(?:Gi|Te|Twe|Fa|Hu|Fo|Fi|Eth)?(\d+)\//)
    const slot = m ? parseInt(m[1]) : 0
    if (!groups.has(slot)) groups.set(slot, [])
    groups.get(slot)!.push(port)
  }
  for (const [, group] of groups) {
    group.sort((a, b) => getPortNumber(a) - getPortNumber(b))
  }
  return groups
}

/** 高速上行端口前缀 (Cisco: Hu=100G, Fo=40G, Fi=5G) */
const UPLINK_PREFIXES = /^(Hu|Fo|Fi)/i

/** 判断端口是否为上行/SPF+ 端口（前缀优先 + 数字阈值回退） */
function isUplinkPort(port: PortInfo, allSlotPorts: PortInfo[]): boolean {
  if (UPLINK_PREFIXES.test(port.name)) return true
  const maxNum = Math.max(...allSlotPorts.map(getPortNumber))
  const num = getPortNumber(port)
  if (maxNum >= 52) return num > 48
  if (maxNum === 28) return num > 24
  return false
}

/** 判断端口是否为 10Gb */
function isTenGbPort(port: PortInfo, allSlotPorts: PortInfo[], platform?: string): boolean {
  if (platform && /C9500/i.test(platform)) return true
  return isUplinkPort(port, allSlotPorts)
}

/** 将端口列表拆分为奇偶两行 */
function splitOddEven(ports: PortInfo[]): [PortInfo[], PortInfo[]] {
  const odd: PortInfo[] = []
  const even: PortInfo[] = []
  for (const port of ports) {
    if (getPortNumber(port) % 2 === 1) odd.push(port)
    else even.push(port)
  }
  return [odd, even]
}

// ============ 端口方块 (memo 防闪烁) ============

interface PortBlockProps {
  port: PortInfo
  onHover: (port: PortInfo | null) => void
  tenGbPorts?: Set<string>
}

const PortBlock = React.memo<PortBlockProps>(({ port, onHover, tenGbPorts }) => {
  const color = getPortColor(port)
  const label = getPortLabel(port)
  const isUp = port.status_up
  const isTenGb = tenGbPorts?.has(port.name) ?? false

  return (
    <Tooltip
      title={
        <Box sx={{ fontSize: '0.7rem' }}>
          <Box sx={{ fontWeight: 600 }}>{port.name}</Box>
          <Box>状态: {port.status} | Speed: {port.speed || '-'} Mbps</Box>
          {port.mode && <Box>模式: {port.mode}</Box>}
          {port.description && <Box>描述: {port.description}</Box>}
          {port.is_uplink && <Box sx={{ color: '#F59E0B' }}>上行链路</Box>}
          {(port.rx_mbps !== undefined || port.tx_mbps !== undefined) && (
            <Box>RX: {((port.rx_mbps ?? 0)).toFixed(2)} / TX: {((port.tx_mbps ?? 0)).toFixed(2)} Mbps</Box>
          )}
        </Box>
      }
      arrow
      placement="top"
      slotProps={{ popper: { sx: { pointerEvents: 'none' } } }}
    >
      <Box
        onMouseEnter={() => onHover(port)}
        onMouseLeave={() => onHover(null)}
        sx={{
          width: PORT_SIZE,
          height: PORT_SIZE,
          borderRadius: 0.5,
          bgcolor: color,
          border: port.is_uplink ? '2px solid #F59E0B' : '1px solid rgba(255,255,255,0.05)',
          boxShadow: port.is_uplink ? '0 0 4px rgba(245,158,11,0.5)' : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: 'transform 0.15s, box-shadow 0.15s',
          '&:hover': {
            transform: 'scale(1.25)',
            zIndex: 10,
            boxShadow: '0 0 8px rgba(255,255,255,0.25)',
          },
        }}
      >
        <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: isTenGb ? '#EF4444' : (isUp ? '#000' : '#64748B'), lineHeight: 1, userSelect: 'none' }}>
          {label}
        </Typography>
      </Box>
    </Tooltip>
  )
})

PortBlock.displayName = 'PortBlock'

// ============ 端口行组件 ============

const PortRow: React.FC<{
  ports: PortInfo[]
  onHover: (port: PortInfo | null) => void
  tenGbPorts?: Set<string>
}> = React.memo(({ ports, onHover, tenGbPorts }) => (
  <>
    {ports.map((port) => (
      <td key={port.name} style={{ width: PORT_SIZE, height: PORT_SIZE, padding: 0, lineHeight: 0 }}>
        <PortBlock port={port} onHover={onHover} tenGbPorts={tenGbPorts} />
      </td>
    ))}
  </>
))

PortRow.displayName = 'PortRow'

// ============ 路由器端口树 ============

interface RouterPortGroup {
  baseName: string
  parent: PortInfo | null
  children: PortInfo[]
}

/** 构建路由器接口层级树：子端口（.255 / :15）缩进在父接口下方 */
function buildRouterPortTree(ports: PortInfo[]): RouterPortGroup[] {
  const filtered = ports.filter(p => !/^service-engine/i.test(p.name))
  const groups = new Map<string, { parent: PortInfo | null; children: PortInfo[] }>()

  for (const port of filtered) {
    const m = port.name.match(/^(.+?)[.:]\d+$/)
    const baseName = m ? m[1] : port.name

    if (!groups.has(baseName)) {
      groups.set(baseName, { parent: null, children: [] })
    }

    const group = groups.get(baseName)!
    if (m) {
      group.children.push(port)
    } else {
      group.parent = port
    }
  }

  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, g]) => ({
      baseName: name,
      parent: g.parent,
      children: g.children.sort((a, b) => a.name.localeCompare(b.name)),
    }))
}

// ============ 主组件 ============

const FrontPanel: React.FC<FrontPanelProps> = ({ ports, deviceName: _deviceName, deviceType, devicePlatform }) => {
  const [hoveredPort, setHoveredPort] = useState<PortInfo | null>(null)
  const groups = useMemo(() => groupPortsBySlot(ports), [ports])
  const lagPorts = useMemo(() => ports.filter((p) => /^lag/i.test(p.name)), [ports])
  const routerTree = useMemo(
    () => (deviceType === 'cisco_ios_router' ? buildRouterPortTree(ports) : null),
    [ports, deviceType],
  )

  /** 10Gb 端口名称集合（红色数字） */
  const tenGbPorts = useMemo(() => {
    const s = new Set<string>()
    for (const [_, slotPorts] of groups) {
      for (const port of slotPorts) {
        if (isTenGbPort(port, slotPorts, devicePlatform)) {
          s.add(port.name)
        }
      }
    }
    return s
  }, [groups, devicePlatform])

  const handleHover = useCallback((port: PortInfo | null) => {
    setHoveredPort(port)
  }, [])

  // ========== 路由器面板 ==========
  if (deviceType === 'cisco_ios_router' && routerTree) {
    if (routerTree.length === 0) {
      return (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">无接口数据</Typography>
        </Paper>
      )
    }

    return (
      <Box>
        {/* 图例 */}
        <Paper sx={{ p: 1.5, mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mr: 1 }}>
            图例:
          </Typography>
          {LEGEND_ITEMS.map((item) => (
            <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box sx={{ width: 14, height: 14, borderRadius: 0.5, bgcolor: item.color, border: '1px solid rgba(255,255,255,0.1)' }} />
              <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>{item.label}</Typography>
            </Box>
          ))}
        </Paper>

        {/* 端口详情栏 */}
        <Paper
          sx={{
            p: 1.5,
            mb: 2,
            minHeight: 52,
            display: 'flex',
            gap: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
            bgcolor: hoveredPort ? 'rgba(45,212,110,0.05)' : 'rgba(148,163,184,0.03)',
            transition: 'background-color 0.2s',
          }}
        >
          {hoveredPort ? (
            <>
              <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: '"JetBrains Mono", monospace' }}>
                {hoveredPort.name}
              </Typography>
              <Chip label={hoveredPort.status} size="small" sx={{ bgcolor: hoveredPort.status_up ? 'rgba(45,212,110,0.12)' : 'rgba(148,163,184,0.08)', color: hoveredPort.status_up ? 'success.main' : 'text.secondary', height: 20, fontSize: '0.65rem' }} />
              {hoveredPort.speed && <Typography variant="caption" color="text.secondary">{hoveredPort.speed} Mbps</Typography>}
              {hoveredPort.type && <Typography variant="caption" color="text.secondary">{hoveredPort.type}</Typography>}
              {hoveredPort.description && <Typography variant="caption" color="text.secondary">{hoveredPort.description}</Typography>}
              {(hoveredPort.rx_mbps !== undefined || hoveredPort.tx_mbps !== undefined) && (
                <Typography variant="caption" sx={{ fontFamily: '"JetBrains Mono", monospace', color: 'success.main' }}>
                  RX: {((hoveredPort.rx_mbps ?? 0)).toFixed(2)} / TX: {((hoveredPort.tx_mbps ?? 0)).toFixed(2)} Mbps
                </Typography>
              )}
            </>
          ) : (
            <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.7rem' }}>
              鼠标悬停端口查看详情
            </Typography>
          )}
        </Paper>

        {/* 接口层级列表 */}
        {routerTree.map((group) => (
          <Paper key={group.baseName} sx={{ p: 1.5, mb: 1 }}>
            {/* 父接口 */}
            {group.parent && (
              <Box
                onMouseEnter={() => handleHover(group.parent)}
                onMouseLeave={() => handleHover(null)}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 1, py: 0.5, px: 1,
                  borderRadius: 1, cursor: 'pointer',
                  '&:hover': { bgcolor: 'rgba(45,212,110,0.08)' },
                }}
              >
                <Box sx={{
                  width: 12, height: 12, borderRadius: 0.5, flexShrink: 0,
                  bgcolor: getPortColor(group.parent),
                  border: '1px solid rgba(255,255,255,0.1)',
                }} />
                <Typography sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem', fontWeight: 600, flex: 1 }}>
                  {group.parent.name}
                </Typography>
                <Chip label={group.parent.status} size="small"
                  sx={{
                    height: 18, fontSize: '0.6rem',
                    bgcolor: group.parent.status_up ? 'rgba(45,212,110,0.12)' : 'rgba(148,163,184,0.08)',
                    color: group.parent.status_up ? 'success.main' : 'text.secondary',
                  }}
                />
                {group.parent.speed && <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{group.parent.speed} Mbps</Typography>}
                {group.parent.type && <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>{group.parent.type}</Typography>}
              </Box>
            )}
            {/* 子接口 */}
            {group.children.map((child) => (
              <Box
                key={child.name}
                onMouseEnter={() => handleHover(child)}
                onMouseLeave={() => handleHover(null)}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 1, py: 0.5, px: 1, pl: 4,
                  borderRadius: 1, cursor: 'pointer',
                  '&:hover': { bgcolor: 'rgba(45,212,110,0.08)' },
                }}
              >
                <Box sx={{
                  width: 10, height: 10, borderRadius: 0.5, flexShrink: 0,
                  bgcolor: getPortColor(child),
                  border: '1px solid rgba(255,255,255,0.1)',
                }} />
                <Typography sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.7rem', flex: 1, color: 'text.secondary' }}>
                  {child.name}
                </Typography>
                <Chip label={child.status} size="small"
                  sx={{
                    height: 16, fontSize: '0.55rem',
                    bgcolor: child.status_up ? 'rgba(45,212,110,0.12)' : 'rgba(148,163,184,0.08)',
                    color: child.status_up ? 'success.main' : 'text.secondary',
                  }}
                />
                {child.speed && <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>{child.speed} Mbps</Typography>}
              </Box>
            ))}
            {/* 无父接口：显示占位 */}
            {!group.parent && group.children.length === 0 && (
              <Typography variant="caption" color="text.disabled" sx={{ pl: 1 }}>{group.baseName}（无状态数据）</Typography>
            )}
          </Paper>
        ))}
      </Box>
    )
  }

  // ========== 交换机面板（原有逻辑） ==========

  if (groups.size === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">无物理端口数据</Typography>
      </Paper>
    )
  }

  return (
    <Box>
      {/* 图例 */}
      <Paper sx={{ p: 1.5, mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mr: 1 }}>
          图例:
        </Typography>
        {LEGEND_ITEMS.map((item) => (
          <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 14, height: 14, borderRadius: 0.5, bgcolor: item.color, border: '1px solid rgba(255,255,255,0.1)' }} />
            <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>{item.label}</Typography>
          </Box>
        ))}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 1 }}>
          <Box sx={{ width: 14, height: 14, borderRadius: 0.5, bgcolor: '#2DD46E', border: '2px solid #F59E0B', boxShadow: '0 0 4px #F59E0B' }} />
          <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>上行链路</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#EF4444', fontWeight: 700 }}>49</Typography>
          <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>10Gb 端口</Typography>
        </Box>
      </Paper>

      {/* 端口详情栏 — 固定高度，始终渲染，避免布局偏移导致闪烁 */}
      <Paper
        sx={{
          p: 1.5,
          mb: 2,
          minHeight: 52,
          display: 'flex',
          gap: 2,
          flexWrap: 'wrap',
          alignItems: 'center',
          bgcolor: hoveredPort ? 'rgba(45,212,110,0.05)' : 'rgba(148,163,184,0.03)',
          transition: 'background-color 0.2s',
        }}
      >
        {hoveredPort ? (
          <>
            <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: '"JetBrains Mono", monospace' }}>
              {hoveredPort.name}
            </Typography>
            <Chip label={hoveredPort.status} size="small" sx={{ bgcolor: hoveredPort.status_up ? 'rgba(45,212,110,0.12)' : 'rgba(148,163,184,0.08)', color: hoveredPort.status_up ? 'success.main' : 'text.secondary', height: 20, fontSize: '0.65rem' }} />
            {hoveredPort.speed && <Typography variant="caption" color="text.secondary">{hoveredPort.speed} Mbps</Typography>}
            {hoveredPort.mode && <Typography variant="caption" color="text.secondary">{hoveredPort.mode}</Typography>}
            {hoveredPort.type && <Typography variant="caption" color="text.secondary">{hoveredPort.type}</Typography>}
            {hoveredPort.description && <Typography variant="caption" color="text.secondary">{hoveredPort.description}</Typography>}
            {hoveredPort.is_uplink && <Chip label="Uplink" size="small" sx={{ bgcolor: 'rgba(245,158,11,0.12)', color: 'warning.main', height: 20, fontSize: '0.65rem' }} />}
            {(hoveredPort.rx_mbps !== undefined || hoveredPort.tx_mbps !== undefined) && (
              <Typography variant="caption" sx={{ fontFamily: '"JetBrains Mono", monospace', color: 'success.main' }}>
                RX: {((hoveredPort.rx_mbps ?? 0)).toFixed(2)} Mbps / TX: {((hoveredPort.tx_mbps ?? 0)).toFixed(2)} Mbps
              </Typography>
            )}
          </>
        ) : (
          <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.7rem' }}>
            鼠标悬停端口查看详情
          </Typography>
        )}
      </Paper>

      {/* 各 Slot 端口面板 — 表格布局 */}
      {[...groups.entries()].sort(([a], [b]) => a - b).map(([slot, slotPorts]) => {
        const regularPorts = slotPorts.filter(p => !isUplinkPort(p, slotPorts))
        const sfpPorts = slotPorts.filter(p => isUplinkPort(p, slotPorts))
        const [regOdd, regEven] = splitOddEven(regularPorts)
        const [sfpOdd, sfpEven] = splitOddEven(sfpPorts)
        const hasSfp = sfpOdd.length > 0 || sfpEven.length > 0

        return (
          <Paper key={slot} sx={{ p: 2, mb: 2, overflow: 'auto' }}>
            <Typography variant="subtitle2" sx={{ mb: 1.5, color: 'text.secondary', fontWeight: 600 }}>
              Slot {slot} — {slotPorts.length} 端口
              {deviceType === 'aruba_aoscx' && ' (Aruba CX)'}
              {deviceType === 'cisco_ios' && ' (Cisco IOS)'}
            </Typography>

            <Box
              component="table"
              sx={{
                borderCollapse: 'separate',
                borderSpacing: `${PORT_GAP}px`,
                m: 0,
                p: 0,
              }}
            >
              <tbody>
                {/* 奇数行（上排） */}
                {(regOdd.length > 0 || sfpOdd.length > 0) && (
                  <tr>
                    <PortRow ports={regOdd} onHover={handleHover} tenGbPorts={tenGbPorts} />
                    {hasSfp && <td style={{ width: SFP_GAP - PORT_GAP, padding: 0 }} />}
                    <PortRow ports={sfpOdd} onHover={handleHover} tenGbPorts={tenGbPorts} />
                  </tr>
                )}
                {/* 偶数行（下排） */}
                {(regEven.length > 0 || sfpEven.length > 0) && (
                  <tr>
                    <PortRow ports={regEven} onHover={handleHover} tenGbPorts={tenGbPorts} />
                    {hasSfp && <td style={{ width: SFP_GAP - PORT_GAP, padding: 0 }} />}
                    <PortRow ports={sfpEven} onHover={handleHover} tenGbPorts={tenGbPorts} />
                  </tr>
                )}
              </tbody>
            </Box>
          </Paper>
        )
      })}

      {/* LAG 端口 */}
      {lagPorts.length > 0 && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1.5, color: 'text.secondary', fontWeight: 600 }}>
            LAG 端口
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
            {lagPorts.map((port) => {
              const color = getPortColor(port)
              return (
                <Tooltip key={port.name} title={`${port.name}: ${port.status}`} arrow>
                  <Box
                    onMouseEnter={() => handleHover(port)}
                    onMouseLeave={() => handleHover(null)}
                    sx={{
                      px: 1.5,
                      py: 0.5,
                      borderRadius: 1,
                      bgcolor: color + '22',
                      border: '2px solid ' + color,
                      cursor: 'pointer',
                      '&:hover': { transform: 'scale(1.05)' },
                    }}
                  >
                    <Typography variant="caption" sx={{ fontWeight: 600, fontFamily: '"JetBrains Mono", monospace', fontSize: '0.7rem' }}>
                      {port.name}
                    </Typography>
                  </Box>
                </Tooltip>
              )
            })}
          </Box>
        </Paper>
      )}
    </Box>
  )
}

export default FrontPanel
