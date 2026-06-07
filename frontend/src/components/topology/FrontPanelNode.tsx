import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Box, Typography, Tooltip } from '@mui/material'

export interface PortData {
  id: string
  label: string
  fullName: string
  color?: string
  neighborName?: string
  connected: boolean
  direction?: 'top' | 'bottom'
}

export interface FrontPanelNodeData {
  label: string
  deviceType: string
  color: string
  isCenter: boolean
  ports: PortData[]
  memberLabel?: string
  /** 为 true 时只显示计数，不画端口视觉元素（端点聚合用） */
  compact?: boolean
}

export function getPortParity(name: string): 'odd' | 'even' {
  const nums = name.match(/\d+/g)
  if (!nums || nums.length === 0) return 'odd'
  const lastNum = parseInt(nums[nums.length - 1], 10)
  return lastNum % 2 === 0 ? 'even' : 'odd'
}

function shortIfName(name: string): string {
  const lagMatch = name.match(/^lag\s+(\d+)$/i)
  if (lagMatch) return `L${lagMatch[1]}`
  let short = name
    .replace(/^TwentyFiveGigE/i, 'T')
    .replace(/^GigabitEthernet/i, 'G')
    .replace(/^TenGigabitEthernet/i, 'Te')
    .replace(/^FastEthernet/i, 'F')
  const parts = short.split('/')
  if (parts.length >= 3 && /^\d+$/.test(parts[parts.length - 1])) return parts[parts.length - 1]
  if (parts.length === 2 && parts[0].length <= 3) return short
  if (short.length > 8) return short.slice(-6)
  return short
}

export default function FrontPanelNode({ data, selected }: NodeProps) {
  const { label, ports, color, isCenter, memberLabel, compact } = data as unknown as FrontPanelNodeData
  const connectedPorts = (ports || []).filter((p) => p.connected)

  const topPorts = isCenter
    ? connectedPorts.filter((p) => p.direction === 'top')
    : connectedPorts
  const bottomPorts = isCenter
    ? connectedPorts.filter((p) => p.direction !== 'top')
    : []

  const nodeW = isCenter ? 620 : compact ? 200 : 240
  const nodeH = isCenter ? 118 : compact ? 58 : 76
  const portW = 14
  const portH = 9
  const labelAreaH = compact ? 0 : 32

  const getPortX = (index: number, total: number) => {
    if (total <= 1) return nodeW / 2
    const pad = 22
    const gap = (nodeW - pad * 2) / (total - 1)
    return pad + index * gap
  }

  const totalTop = topPorts.length
  const totalBottom = bottomPorts.length
  const rootH = compact ? nodeH : (totalTop > 0 ? labelAreaH : 0) + nodeH + (totalBottom > 0 ? labelAreaH : 0)
  const bodyTop = compact ? 0 : (totalTop > 0 ? labelAreaH : 0)

  const deviceFontSize = isCenter ? '1.2rem' : compact ? '0.92rem' : '1rem'
  const portFontSize = '0.78rem'
  const labelFontSize = '0.85rem'

  // 设备主体组件
  const body = (
    <Box sx={{
      position: 'absolute', top: bodyTop, left: 0, width: nodeW, height: nodeH, borderRadius: 2,
      border: '2px solid', borderColor: selected ? '#e2e8f0' : `${color}99`,
      background: `linear-gradient(180deg, ${color}25 0%, ${color}0A 100%)`,
      boxShadow: selected ? `0 0 24px ${color}44, inset 0 1px 0 ${color}18` : `0 4px 12px rgba(0,0,0,0.45), inset 0 1px 0 ${color}12`,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      transition: 'box-shadow 0.2s, border-color 0.2s',
    }}>
      {isCenter && (
        <Box sx={{ position: 'absolute', top: 9, left: '50%', transform: 'translateX(-50%)', width: '65%', height: 1, background: `linear-gradient(90deg,transparent,${color}30,transparent)` }} />
      )}
      <Typography sx={{ fontWeight: 700, fontSize: deviceFontSize, color: '#e2e8f0', lineHeight: 1.3, textAlign: 'center', px: 2, fontFamily: '"JetBrains Mono","Consolas",monospace', letterSpacing: '0.03em' }}>
        {label}
      </Typography>
      {isCenter && memberLabel && (
        <Typography sx={{ fontSize: labelFontSize, color, fontWeight: 600, mt: 0.35, letterSpacing: '0.08em' }}>
          {memberLabel}
        </Typography>
      )}
      {!isCenter && (
        <Typography sx={{ fontSize: '0.78rem', color: '#94a3b8', mt: 0.25, fontWeight: 500 }}>
          {totalTop} 端口
        </Typography>
      )}
    </Box>
  )

  return (
    <Box sx={{ position: 'relative', width: nodeW, height: rootH }}>
      {/* 上行端口视觉（compact 模式跳过） */}
      {!compact && totalTop > 0 && connectedPorts
        .filter((p) => p.direction === 'top')
        .map((port, idx, arr) => {
          const x = getPortX(idx, arr.length)
          return (
            <Tooltip key={`v-${port.id}`} title={`${port.fullName} → ${port.neighborName || ''}`} arrow placement="top">
              <Box sx={{ position: 'absolute', left: x, top: 3, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', zIndex: 2 }}>
                <Box sx={{ width: portW, height: portH, borderRadius: 0.5, bgcolor: port.color || '#475569', border: '1px solid', borderColor: `${port.color || '#475569'}99`, mb: 0.4, transition: 'transform 0.15s', '&:hover': { transform: 'scale(1.5)' } }} />
                {arr.length < 20 && <Typography sx={{ fontSize: portFontSize, color: '#cbd5e1', textAlign: 'center', lineHeight: 1.1, whiteSpace: 'nowrap', fontFamily: '"JetBrains Mono","Consolas",monospace', fontWeight: 500 }}>{shortIfName(port.fullName)}</Typography>}
              </Box>
            </Tooltip>
          )
        })
      }

      {body}

      {/* 下行端口视觉（compact 模式跳过） */}
      {!compact && totalBottom > 0 && connectedPorts
        .filter((p) => p.direction !== 'top')
        .map((port, idx, arr) => {
          const x = getPortX(idx, arr.length)
          return (
            <Tooltip key={`v-${port.id}`} title={`${port.fullName} → ${port.neighborName || ''}`} arrow placement="bottom">
              <Box sx={{ position: 'absolute', left: x, top: bodyTop + nodeH + 3, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', zIndex: 2 }}>
                <Box sx={{ width: portW, height: portH, borderRadius: 0.5, bgcolor: port.color || '#475569', border: '1px solid', borderColor: `${port.color || '#475569'}99`, mb: 0.4, '&:hover': { transform: 'scale(1.5)' } }} />
                {arr.length < 20 && <Typography sx={{ fontSize: portFontSize, color: '#cbd5e1', textAlign: 'center', lineHeight: 1.1, whiteSpace: 'nowrap', fontFamily: '"JetBrains Mono","Consolas",monospace', fontWeight: 500 }}>{shortIfName(port.fullName)}</Typography>}
              </Box>
            </Tooltip>
          )
        })
      }

      {/* Handles（始终渲染，即使 compact 模式） */}
      {connectedPorts
        .filter((p) => p.direction === 'top')
        .map((port, idx, arr) => {
          const x = getPortX(idx, arr.length)
          return (
            <Handle key={`h-${port.id}`} type={isCenter ? 'source' : 'target'} id={port.id} position={Position.Top}
              style={{ left: x, transform: 'translateX(-50%)', width: 22, height: 14, background: 'transparent', border: 'none', borderRadius: 0, top: -7 }}
              title={port.fullName} />
          )
        })
      }
      {connectedPorts
        .filter((p) => p.direction !== 'top')
        .map((port, idx, arr) => {
          const x = getPortX(idx, arr.length)
          return (
            <Handle key={`h-${port.id}`} type={isCenter ? 'source' : 'target'} id={port.id} position={Position.Bottom}
              style={{ left: x, transform: 'translateX(-50%)', width: 22, height: 14, background: 'transparent', border: 'none', borderRadius: 0, bottom: -7 }}
              title={port.fullName} />
          )
        })
      }
    </Box>
  )
}
