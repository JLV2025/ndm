import React, { useState, useEffect, useRef, useMemo } from 'react'
import {
  Box,
  Container,
  Paper,
  Typography,
  Card,
  CardContent,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Avatar,
  Alert,
  LinearProgress,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import {
  Storage as Server,
  Wifi as WifiIcon,
  CheckCircle,
  PauseCircle,
  ErrorOutline,
} from '@mui/icons-material'
import {
  PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis,
  Tooltip as RechartsTooltip, Legend,
  ResponsiveContainer,
  LineChart, Line, CartesianGrid,
} from 'recharts'
import { deviceApi, collectorApi, alertsApi } from '../services/api'
import { sessionManager } from '../services/auth'
import { useI18n } from '../i18n'
import { getDeviceColor, getTypeLabel } from '../components/devices/deviceUtils'
import type { Device } from '../types'

const DevicesLink = React.forwardRef<HTMLAnchorElement, React.HTMLProps<HTMLAnchorElement>>(
  (props, ref) => <a href="/devices" ref={ref} {...props} />
)

interface DashboardStats {
  device_count: number
  device_types: Record<string, number>
  port_stats: { total: number; up: number; down: number; disabled: number }
  error_ports: number
  top_traffic: Array<{
    device: string
    port: string
    total_mbps: number
    rx_mbps: number
    tx_mbps: number
  }>
  last_collection: string
  locations: string[]
}

// 图表配色 — 与 MUI Dark 主题对齐
const CHART_COLORS = {
  cisco: '#3B82F6',
  aruba: '#06B6D4',
  other: '#94A3B8',
  up: '#2DD46E',
  down: '#94A3B8',
  disabled: '#EF4444',
  rx: 'rgba(45, 212, 110, 0.35)',
  tx: '#2DD46E',
  bg: '#0F1223',
  grid: '#1E293B',
  text: '#94A3B8',
}

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: '#0F1223',
    border: '1px solid #1E293B',
    borderRadius: 6,
    fontSize: '0.75rem',
  },
}

const Dashboard: React.FC = () => {
  const { t } = useI18n()
  const [devices, setDevices] = useState<Device[]>([])
  const [stats, setStats] = useState({
    total: 0,
    cisco: 0,
    aruba: 0,
    collectedToday: 0,
  })
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null)
  const [configHistory, setConfigHistory] = useState<{ weeks: string[]; series: Array<{ device: string; data: Array<{ week: string; config_lines: number; timestamp: string }> }> } | null>(null)
  const [uniqueLocations, setUniqueLocations] = useState<string[]>([])
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [alertCount, setAlertCount] = useState(0)
  const user = sessionManager.getSession()

  useEffect(() => {
    loadDevices()
    loadDashboardStats()
    loadConfigHistory()
    loadAlertCount()
  }, [])

  useEffect(() => {
    if (devices.length > 0) {
      const cisco = devices.filter((d) => d.type === 'cisco_ios').length
      const aruba = devices.filter((d) => d.type === 'aruba_aoscx').length
      setStats({
        total: devices.length,
        cisco,
        aruba,
        collectedToday: new Set(devices.map((d) => d.last_collected)).size,
      })
      const locations = [...new Set(devices.map(d => d.location).filter((l): l is string => !!l))].sort()
      setUniqueLocations(locations)
    }
  }, [devices])

  const loadDevices = async () => {
    try {
      const response = await deviceApi.list()
      setDevices(response.data)
    } catch (error: unknown) {
      console.error('加载设备失败:', error)
    }
  }

  const loadDashboardStats = async () => {
    try {
      const response = await fetch('/api/stats/overview')
      if (response.ok) {
        setDashboardStats(await response.json())
      }
    } catch (error: unknown) {
      console.error('加载统计失败:', error)
    }
  }

  const loadConfigHistory = async () => {
    try {
      const response = await fetch('/api/stats/config-history')
      if (response.ok) {
        setConfigHistory(await response.json())
      }
    } catch (error: unknown) {
      console.error('加载配置历史失败:', error)
    }
  }

  const loadAlertCount = async () => {
    try {
      const res = await alertsApi.summary()
      setAlertCount(res.data?.total || 0)
    } catch { /* ignore */ }
  }

  const [sortField, setSortField] = useState<string>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [deviceStatus, setDeviceStatus] = useState<Record<string, 'checking' | 'online' | 'offline'>>({})
  const [pinging, setPinging] = useState(false)
  const pingControllerRef = useRef<AbortController | null>(null)

  const filteredDevices = selectedLocation
    ? devices.filter((d) => (d.location || '').toUpperCase() === selectedLocation.toUpperCase())
    : devices

  // 堆叠设备拆分：序列号逗号分隔 → 每成员单独一行，逻辑设备名不显示
  const physicalDevices = useMemo(() => {
    const result: Array<Device & { logicalName: string; memberIndex: number; memberCount: number }> = []
    for (const d of filteredDevices) {
      const snRaw = d.serial_number || ''
      const snList = snRaw.split(',').map(s => s.trim()).filter(Boolean)
      if (snList.length <= 1) {
        // 非堆叠设备，直接显示
        result.push({ ...d, logicalName: d.name, memberIndex: 0, memberCount: 1 })
        continue
      }
      // 堆叠设备：拆分成员，逻辑设备自己不显示
      const padWidth = String(snList.length).length
      const modelRaw = d.model || ''
      const modelList = modelRaw.split(',').map(m => m.trim()).filter(Boolean)
      snList.forEach((sn, i) => {
        const idx = i + 1
        const suffix = String(idx).padStart(padWidth, '0')
        const memberModel = modelList[i] || modelList[modelList.length - 1] || ''
        result.push({
          ...d,
          name: `${d.name}-${suffix}`,
          logicalName: d.name,
          serial_number: sn,
          model: memberModel,
          memberIndex: idx,
          memberCount: snList.length,
        })
      })
    }
    return result
  }, [filteredDevices])

  const sortedDevices = [...physicalDevices].sort((a: Device, b: Device) => {
    const va = (a[sortField] || '').toString().toLowerCase()
    const vb = (b[sortField] || '').toString().toLowerCase()
    return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
  })

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const sortStyle = (field: string) => ({
    cursor: 'pointer',
    userSelect: 'none',
    '&:hover': { color: 'primary.main' },
    color: sortField === field ? 'primary.main' : 'text.secondary',
  } as const)

  const pingAllDevices = async (deviceList: Device[], signal?: AbortSignal) => {
    await Promise.all(deviceList.map(async (device) => {
      try {
        const result = await collectorApi.ping(device.name, signal)
        setDeviceStatus((prev) => ({
          ...prev,
          [device.name]: result.reachable ? 'online' : 'offline',
        }))
      } catch (e: unknown) {
        if (e instanceof DOMException && e.name === 'AbortError') return
        setDeviceStatus((prev) => ({ ...prev, [device.name]: 'offline' }))
      }
    }))
  }

  const handleRefreshStatus = async () => {
    if (devices.length === 0) return
    setPinging(true)
    const initialStatus: Record<string, 'checking' | 'online' | 'offline'> = {}
    devices.forEach((d) => { initialStatus[d.name] = 'checking' })
    setDeviceStatus(initialStatus)

    pingControllerRef.current = new AbortController()
    await pingAllDevices(devices, pingControllerRef.current.signal)
    await loadDevices()
    setPinging(false)
  }

  useEffect(() => {
    return () => {
      pingControllerRef.current?.abort()
    }
  }, [])

  // getDeviceColors 基于 deviceUtils.getDeviceColor，统一属性名
  const getDeviceColors = (type: string) => {
    const c = getDeviceColor(type)
    return { primary: c.primary, bg: c.secondary, border: c.border }
  }

  const formatRelativeTime = (isoStr: string) => {
    if (!isoStr) return '-'
    const diff = Date.now() - new Date(isoStr).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return t('common.relTimeJustNow')
    if (mins < 60) return t('common.relTimeMinutesAgo').replace('{n}', String(mins))
    const hours = Math.floor(mins / 60)
    if (hours < 24) return t('common.relTimeHoursAgo').replace('{n}', String(hours))
    const days = Math.floor(hours / 24)
    return t('common.relTimeDaysAgo').replace('{n}', String(days))
  }

  // 图表数据
  const deviceTypeChartData = useMemo(() => {
    const typeLabels: Record<string, string> = {
      'cisco_ios': t('dashboard.cisco'),
      'aruba_aoscx': t('dashboard.aruba'),
    }
    const types = dashboardStats?.device_types ?? {}
    return Object.entries(types).map(([name, value]) => ({
      name: typeLabels[name] || name,
      value,
    }))
  }, [dashboardStats, t])

  const portStatusChartData = useMemo(() => [{
    name: 'All',
    UP: dashboardStats?.port_stats.up ?? 0,
    Down: dashboardStats?.port_stats.down ?? 0,
    Disabled: dashboardStats?.port_stats.disabled ?? 0,
  }], [dashboardStats])

  const trafficChartData = useMemo(() =>
    (dashboardStats?.top_traffic ?? []).map(item => ({
      name: `${item.device}:${item.port}`,
      device: item.device,
      port: item.port,
      rx: item.rx_mbps,
      tx: item.tx_mbps,
    }))
  , [dashboardStats])

  // 设备折线配色
  const DEVICE_LINE_COLORS = ['#3B82F6', '#2DD46E', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316']

  const configHistoryChartData = useMemo(() => {
    if (!configHistory?.weeks?.length || !configHistory?.series?.length) return { data: [], devices: [] as string[], subtitle: '' }
    // 只显示配置行数有变化的设备（至少两周不同），最多10条
    const changed: Array<{ device: string; data: Array<{ week: string; config_lines: number; timestamp: string }>; lastChange: string }> = []
    const unchanged: Array<{ device: string; data: Array<{ week: string; config_lines: number; timestamp: string }> }> = []
    configHistory.series.forEach(s => {
      const lines = s.data.map(d => d.config_lines)
      const hasChange = lines.length > 1 && new Set(lines).size > 1
      if (hasChange) {
        changed.push({ ...s, lastChange: s.data[s.data.length - 1]?.timestamp ?? '' })
      } else {
        unchanged.push(s)
      }
    })
    // 有变化的排前面（最近变化优先），没变化的排后面，总计最多10条
    changed.sort((a, b) => b.lastChange.localeCompare(a.lastChange))
    const visible = [...changed, ...unchanged].slice(0, 10)
    const devices = visible.map(s => s.device)
    const subtitle = configHistory.series.length > 10
      ? `（${configHistory.series.length} 台中显示有变化的 10 台）`
      : configHistory.series.length > visible.length
        ? `（${configHistory.series.length} 台中 ${visible.length} 台有变化）`
        : ''
    return {
      data: configHistory.weeks.map(week => {
        const point: Record<string, string | number> = { week }
        visible.forEach(s => {
          const dp = s.data.find(d => d.week === week)
          point[s.device] = dp?.config_lines ?? null
        })
        return point
      }),
      devices,
      subtitle,
    }
  }, [configHistory])

  // 热力图数据：设备×周次间隔的配置行数变化量
  const heatmapData = useMemo(() => {
    if (!configHistory?.weeks?.length || !configHistory?.series?.length) return { devices: [] as string[], columns: [] as string[], grid: [] as Array<Array<{ delta: number | null; prev: number | null; next: number | null }>> }
    const weeks = configHistory.weeks
    if (weeks.length < 2) return { devices: [] as string[], columns: [] as string[], grid: [] }
    const columns = weeks.slice(1).map((w, i) => `${weeks[i]}→${w}`)
    // 取 configHistoryChartData 中已筛选的设备，维持一致
    const rowDevices = configHistoryChartData.devices
    const grid = rowDevices.map(deviceName => {
      const sd = configHistory.series.find(s => s.device === deviceName)
      if (!sd) return columns.map(() => ({ delta: null, prev: null, next: null }))
      return columns.map((_, ci) => {
        const prevWeek = weeks[ci]
        const nextWeek = weeks[ci + 1]
        const prev = sd.data.find(d => d.week === prevWeek)
        const next = sd.data.find(d => d.week === nextWeek)
        if (prev && next) {
          return { delta: next.config_lines - prev.config_lines, prev: prev.config_lines, next: next.config_lines }
        }
        return { delta: null, prev: prev?.config_lines ?? null, next: next?.config_lines ?? null }
      })
    })
    return { devices: rowDevices, columns, grid }
  }, [configHistory, configHistoryChartData.devices])

  // 热力图 delta → 颜色（绿=新增行，红=删除行）
  const heatmapColor = (delta: number | null): string => {
    if (delta === null) return 'transparent'
    if (delta === 0) return '#1E293B'
    const maxVal = 50 // 超过50行变化视为最大色深
    const ratio = Math.min(Math.abs(delta) / maxVal, 1)
    if (delta > 0) {
      // 绿色渐变
      const g = Math.round(60 + 195 * ratio)
      return `rgb(0,${g},0)`
    }
    // 红色渐变
    const r = Math.round(60 + 195 * ratio)
    return `rgb(${r},0,0)`
  }

  // 4 张统计卡片：配置数组驱动，消除复制粘贴
  const statCardDefs = useMemo(() => [
    { accent: '#3B82F6', label: t('dashboard.totalDevicesCard'), value: dashboardStats?.device_count ?? stats.total },
    { accent: '#2DD46E', label: t('dashboard.activePorts'), value: dashboardStats?.port_stats.up ?? 0 },
    { accent: '#94A3B8', label: t('dashboard.idlePorts'), value: (dashboardStats?.port_stats.down ?? 0) + (dashboardStats?.port_stats.disabled ?? 0) },
    { accent: '#EF4444', label: t('dashboard.errorPorts'), value: dashboardStats?.error_ports ?? 0, danger: true },
    { accent: '#F59E0B', label: t('alerts.title'), value: alertCount, danger: alertCount > 0, link: '/alerts' },
  ], [dashboardStats, stats.total, alertCount, t])

  const statCardsColumn = (
    <Box sx={{ width: 240, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 0.5, height: '100%' }}>
      {statCardDefs.map((def: any, i) => (
        <Card
          key={i}
          sx={{
            flex: 1, display: 'flex', bgcolor: `${def.accent}0F`, border: `1px solid ${def.accent}26`,
            cursor: def.link ? 'pointer' : 'default',
            '&:hover': def.link ? { boxShadow: 2 } : {},
          }}
          onClick={def.link ? () => { window.location.href = def.link } : undefined}
        >
          <CardContent sx={{ p: '8px 12px !important', display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', width: '100%', '&:last-child': { pb: '8px !important' } }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem', lineHeight: 1.3 }}>
              {def.label}
            </Typography>
            <Typography sx={{ color: def.danger && def.value > 0 ? '#EF4444' : def.accent, fontWeight: 700, fontSize: '1.4rem', lineHeight: 1.2 }}>
              {def.value}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  )

  // 三个图表
  const chartsRow = dashboardStats && (
    <>
      {/* 设备类型环形图 */}
      <Paper sx={{ flex: 0.7, p: 1.5, minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mb: 0.5, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.65rem' }}>
          {t('dashboard.chartDeviceTypes')}
        </Typography>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={deviceTypeChartData}
              cx="50%" cy="50%"
              innerRadius={35} outerRadius={70}
              dataKey="value"
              stroke="none"
            >
              {deviceTypeChartData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.name === 'Cisco IOS' ? CHART_COLORS.cisco : entry.name === 'Aruba CX' ? CHART_COLORS.aruba : CHART_COLORS.other}
                />
              ))}
            </Pie>
            <RechartsTooltip {...TOOLTIP_STYLE} />
            <Legend
              wrapperStyle={{ fontSize: '0.65rem', color: CHART_COLORS.text }}
              iconType="circle"
              iconSize={8}
            />
          </PieChart>
        </ResponsiveContainer>
      </Paper>

      {/* 端口状态堆叠柱状图 */}
      <Paper sx={{ flex: 0.7, p: 1.5, minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mb: 0.5, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.65rem' }}>
          {t('dashboard.chartPortStatus')}
        </Typography>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={portStatusChartData} barCategoryGap="30%">
            <XAxis dataKey="name" tick={false} axisLine={{ stroke: CHART_COLORS.grid }} />
            <YAxis tick={{ fill: CHART_COLORS.text, fontSize: 11 }} axisLine={false} tickLine={false} />
            <RechartsTooltip {...TOOLTIP_STYLE} />
            <Legend
              wrapperStyle={{ fontSize: '0.65rem', color: CHART_COLORS.text }}
              iconType="rect"
              iconSize={8}
            />
            <Bar dataKey="UP" fill={CHART_COLORS.up} stackId="a" radius={[0, 0, 0, 0]} />
            <Bar dataKey="Down" fill={CHART_COLORS.down} stackId="a" />
            <Bar dataKey="Disabled" fill={CHART_COLORS.disabled} stackId="a" />
          </BarChart>
        </ResponsiveContainer>
      </Paper>

      {/* 流量排行水平条形图 */}
      <Paper sx={{ flex: 1.1, p: 1.5, minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mb: 0.5, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.65rem' }}>
          {t('dashboard.chartTrafficRank')}
        </Typography>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={trafficChartData} layout="vertical" barSize={12} barCategoryGap="30%" margin={{ left: 0, right: 8, top: 0, bottom: 0 }}>
            <YAxis type="category" dataKey="name" tick={{ fill: CHART_COLORS.text, fontSize: 9, fontFamily: '"Fira Code", monospace', textAnchor: 'end' }} width={130} axisLine={false} tickLine={false} />
            <XAxis type="number" tick={{ fill: CHART_COLORS.text, fontSize: 9 }} axisLine={{ stroke: CHART_COLORS.grid }} tickLine={false} />
            <RechartsTooltip
              cursor={false}
              contentStyle={{
                backgroundColor: '#0F1223',
                border: '1px solid #1E293B',
                borderRadius: 6,
                fontSize: '0.75rem',
                color: '#F8FAFC',
              }}
              labelStyle={{ color: '#94A3B8' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '0.65rem', color: CHART_COLORS.text }}
              iconType="rect"
              iconSize={8}
            />
            <Bar dataKey="rx" name={t('dashboard.chartRx')} fill={CHART_COLORS.rx} stackId="a" />
            <Bar dataKey="tx" name={t('dashboard.chartTx')} fill={CHART_COLORS.tx} stackId="a" />
          </BarChart>
        </ResponsiveContainer>
      </Paper>
    </>
  )

  if (devices.length === 0) {
    return (
      <Container maxWidth={false} sx={{ py: 4 }}>
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <Box sx={{ mb: 3 }}>
            <Server sx={{ fontSize: 64, color: 'text.disabled' }} />
          </Box>
          <Typography variant="h4" sx={{ color: 'text.primary', fontWeight: 700, mb: 1 }}>
            {t('app.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {t('app.subtitle')}
          </Typography>
          <Button
            variant="contained"
            component={DevicesLink}
            sx={{ px: 4, py: 1.5, fontWeight: 700 }}
          >
            <Server sx={{ mr: 1, fontSize: 18 }} />
            {t('dashboard.addDevice')}
          </Button>
        </Paper>
      </Container>
    )
  }

  return (
    <Container maxWidth={false} sx={{ py: 2 }}>
      {/* 页面头部 — 左侧绿色装饰条 */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'flex-start', gap: 2, flexShrink: 0 }}>
        <Box
          sx={{
            width: 4, height: 48, borderRadius: 2,
            bgcolor: 'primary.main',
            boxShadow: '0 0 12px rgba(45, 212, 110, 0.35)',
            flexShrink: 0, mt: 0.5,
          }}
        />
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.25, letterSpacing: '-0.01em' }}>
            NDM Dashboard
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.85rem', ml: 0.5 }}>
            {t('app.tagline')}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {dashboardStats && (
            <Typography variant="caption" color="text.secondary">
              {t('dashboard.lastCollection')}: {formatRelativeTime(dashboardStats.last_collection)}
            </Typography>
          )}
          {user && (
            <Chip
              label={user.username}
              avatar={
                <Avatar sx={{ bgcolor: 'info.main', width: 28, height: 28 }}>
                  {user.username.charAt(0).toUpperCase()}
                </Avatar>
              }
              size="small"
              sx={{ bgcolor: 'rgba(59, 130, 246, 0.12)', color: 'info.main' }}
              />
            )}
        </Box>
      </Box>

      {/* 行1: 统计卡片 + 三图表并排 */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, height: 300 }}>
        {statCardsColumn}
        {chartsRow || (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              {t('dashboard.noDevices')}
            </Typography>
          </Box>
        )}
      </Box>

      {/* 行2: 配置变更趋势（折线图 + 热力图并排） */}
      {configHistoryChartData.devices.length > 0 && (
        <Box sx={{ display: 'flex', gap: 2, mb: 2, height: 220 }}>
          {/* 折线图 */}
          <Paper sx={{ flex: 1, p: 1.5, minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mb: 0.5, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.65rem' }}>
              {t('dashboard.chartConfigHistory')} {configHistoryChartData.subtitle}
            </Typography>
            <ResponsiveContainer width="100%" height={175}>
              <LineChart data={configHistoryChartData.data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" />
                <XAxis dataKey="week" tick={{ fill: CHART_COLORS.text, fontSize: 10 }} axisLine={{ stroke: CHART_COLORS.grid }} tickLine={false} />
                <YAxis tick={{ fill: CHART_COLORS.text, fontSize: 10 }} axisLine={false} tickLine={false} width={50} />
                <RechartsTooltip
                  contentStyle={{ backgroundColor: '#0F1223', border: '1px solid #1E293B', borderRadius: 6, fontSize: '0.75rem', color: '#F8FAFC' }}
                  labelStyle={{ color: '#94A3B8' }}
                />
                <Legend
                  wrapperStyle={{ fontSize: '0.65rem', color: CHART_COLORS.text }}
                  iconType="line"
                  iconSize={10}
                />
                {configHistoryChartData.devices.map((device, i) => (
                  <Line
                    key={device}
                    type="monotone"
                    dataKey={device}
                    name={device}
                    stroke={DEVICE_LINE_COLORS[i % DEVICE_LINE_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 3, strokeWidth: 1 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Paper>

          {/* 热力图 */}
          {heatmapData.devices.length > 0 && (
            <Paper sx={{ flex: 1, p: 1.5, minWidth: 0, overflow: 'auto' }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mb: 0.5, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.65rem' }}>
                {t('dashboard.chartHeatmap')}
              </Typography>
              <Box sx={{ display: 'flex' }}>
                {/* Y轴 — 设备名 */}
                <Box sx={{ display: 'flex', flexDirection: 'column', flexShrink: 0, pr: 0.5 }}>
                  <Box sx={{ height: 24 }} />
                  {heatmapData.devices.map(d => (
                    <Box key={d} sx={{ height: 24, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                      <Typography sx={{ fontSize: 9, fontFamily: '"Fira Code", monospace', color: CHART_COLORS.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 120 }}>
                        {d}
                      </Typography>
                    </Box>
                  ))}
                </Box>
                {/* 热力图网格 */}
                <Box sx={{ flex: 1, overflow: 'auto' }}>
                  {/* X轴 — 周次间隔 */}
                  <Box sx={{ display: 'flex', height: 24 }}>
                    {heatmapData.columns.map(col => (
                      <Box key={col} sx={{ flex: 1, minWidth: 36, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography sx={{ fontSize: 8, color: CHART_COLORS.text, whiteSpace: 'nowrap' }}>
                          {col}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                  {/* 数据格 */}
                  {heatmapData.devices.map((d, ri) => (
                    <Box key={d} sx={{ display: 'flex', height: 24 }}>
                      {heatmapData.grid[ri]?.map((cell, ci) => (
                        <Box key={ci} sx={{
                          flex: 1, minWidth: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          bgcolor: heatmapColor(cell.delta),
                          border: '1px solid rgba(255,255,255,0.06)',
                          position: 'relative',
                        }} title={cell.delta !== null ? `${d} →${heatmapData.columns[ci]}: Δ${cell.delta > 0 ? '+' : ''}${cell.delta} 行` : t('dashboard.chartHeatmapNodata')}>
                          {cell.delta !== null ? (
                            <Typography sx={{ fontSize: 8, fontWeight: 700, color: cell.delta === 0 ? '#64748B' : '#F8FAFC', fontFamily: '"Fira Code", monospace' }}>
                              {cell.delta === 0 ? '0' : `${cell.delta > 0 ? '+' : ''}${cell.delta}`}
                            </Typography>
                          ) : (
                            <Typography sx={{ fontSize: 8, color: '#475569' }}>—</Typography>
                          )}
                        </Box>
                      ))}
                    </Box>
                  ))}
                </Box>
              </Box>
            </Paper>
          )}
        </Box>
      )}

      {/* 位置筛选 */}
      {uniqueLocations.length > 0 && (
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', mr: 0.5 }}>
            {t('devices.filterByLocation')}:
          </Typography>
          <ToggleButtonGroup
            value={selectedLocation}
            exclusive
            onChange={(_, v) => setSelectedLocation(v)}
            size="small"
          >
            <ToggleButton value={null}>ALL</ToggleButton>
            {uniqueLocations.map((loc) => (
              <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
      )}

      {/* 设备表格 — 全宽 */}
      <Paper sx={{ p: 2, overflow: 'auto' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {t('dashboard.deviceInventory')}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="caption" color="text.secondary">
              {t('dashboard.total')}: {sortedDevices.length}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<WifiIcon />}
              onClick={handleRefreshStatus}
              disabled={pinging}
              sx={{ fontWeight: 600, fontSize: '0.75rem' }}
            >
              {pinging ? t('dashboard.refreshing') : t('dashboard.refreshStatus')}
            </Button>
          </Box>
        </Box>

        {pinging && (
          <Alert severity="info" sx={{ mb: 2, fontSize: '0.75rem' }}>
            {t('dashboard.pinging')}
            <LinearProgress sx={{ mt: 1 }} />
          </Alert>
        )}

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell onClick={() => handleSort('name')} sx={sortStyle('name')}>
                  {t('dashboard.device')} {sortField === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </TableCell>
                <TableCell onClick={() => handleSort('type')} sx={sortStyle('type')}>
                  {t('dashboard.type')} {sortField === 'type' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </TableCell>
                <TableCell>{t('dashboard.ipAddress')}</TableCell>
                <TableCell onClick={() => handleSort('location')} sx={sortStyle('location')}>
                  {t('dashboard.location')} {sortField === 'location' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </TableCell>
                <TableCell>{t('dashboard.serialNumber')}</TableCell>
                <TableCell>{t('dashboard.model')}</TableCell>
                <TableCell>{t('dashboard.version')}</TableCell>
                <TableCell>{t('dashboard.status')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedDevices.map((device) => {
                const colors = getDeviceColors(device.type)
                return (
                  <TableRow key={device.name} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Avatar
                          sx={{
                            bgcolor: colors.bg,
                            color: colors.primary,
                            mr: 1,
                            width: 28,
                            height: 28,
                            border: '1px solid',
                            borderColor: colors.border,
                          }}
                        >
                          <Server sx={{ fontSize: 14 }} />
                        </Avatar>
                        <Typography variant="body2" component="a" href={`/devices/${(device as any).logicalName || device.name}`} sx={{ color: 'primary.main', textDecoration: 'none', fontWeight: 500, '&:hover': { textDecoration: 'underline' } }}>
                          {device.name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getTypeLabel(device.type, t)}
                        size="small"
                        sx={{
                          bgcolor: colors.bg,
                          color: colors.primary,
                          border: '1px solid',
                          borderColor: colors.border,
                          fontWeight: 500,
                          height: 20,
                          fontSize: '0.65rem',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.8rem' }}>{device.ip}</TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>{device.location || '-'}</TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem', fontFamily: '"Fira Code", monospace' }}>
                      {device.serial_number || '-'}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem', fontFamily: '"Fira Code", monospace' }}>
                      {device.model || '-'}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem', fontFamily: '"Fira Code", monospace' }}>
                      {device.version || '-'}
                    </TableCell>
                    <TableCell>
                      {(() => {
                        // 堆叠设备用逻辑设备名查状态（所有成员共享同一 IP/Ping 状态）
                        const lookupName = (device as any).logicalName || device.name
                        const status = deviceStatus[lookupName]
                        if (!status) {
                          return <Chip label="-" size="small" sx={{ bgcolor: 'rgba(148,163,184,0.08)', color: 'text.secondary', height: 20, fontSize: '0.65rem' }} />
                        }
                        if (status === 'checking') {
                          return <Chip label={t('dashboard.checking')} size="small" sx={{ bgcolor: 'rgba(245,158,11,0.12)', color: 'warning.main', height: 20, fontSize: '0.65rem' }} />
                        }
                        if (status === 'online') {
                          return <Chip label={t('dashboard.online')} size="small" sx={{ bgcolor: 'rgba(45,212,110,0.12)', color: 'success.main', height: 20, fontSize: '0.65rem' }} />
                        }
                        return <Chip label={t('dashboard.offline')} size="small" sx={{ bgcolor: 'rgba(239,68,68,0.12)', color: 'error.main', height: 20, fontSize: '0.65rem' }} />
                      })()}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Container>
  )
}

export default Dashboard
