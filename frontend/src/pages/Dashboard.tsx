import React, { useState, useEffect, useRef } from 'react'
import {
  Box,
  Container,
  Paper,
  Typography,
  Grid,
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
} from '@mui/material'
import {
  Storage as Server,
  Wifi as WifiIcon,
  CheckCircle,
  PauseCircle,
  ErrorOutline,
} from '@mui/icons-material'
import { deviceApi, collectorApi } from '../services/api'
import { sessionManager } from '../services/auth'
import { useI18n } from '../i18n'
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
  const user = sessionManager.getSession()

  useEffect(() => {
    loadDevices()
    loadDashboardStats()
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

  const [sortField, setSortField] = useState<string>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [deviceStatus, setDeviceStatus] = useState<Record<string, 'checking' | 'online' | 'offline'>>({})
  const [pinging, setPinging] = useState(false)
  const pingControllerRef = useRef<AbortController | null>(null)

  const sortedDevices = [...devices].sort((a: Device, b: Device) => {
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
    deviceList.forEach(async (device) => {
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
    })
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

  const getTypeLabel = (type: string) => {
    if (type === 'cisco_ios') return t('dashboard.cisco')
    if (type === 'aruba_aoscx') return t('dashboard.aruba')
    return type
  }

  const getDeviceColors = (type: string) => {
    if (type === 'cisco_ios') return {
      primary: '#3B82F6',
      bg: 'rgba(59, 130, 246, 0.12)',
      border: 'rgba(59, 130, 246, 0.25)',
    }
    if (type === 'aruba_aoscx') return {
      primary: '#06B6D4',
      bg: 'rgba(6, 182, 212, 0.12)',
      border: 'rgba(6, 182, 212, 0.25)',
    }
    return {
      primary: '#94A3B8',
      bg: 'rgba(148, 163, 184, 0.08)',
      border: 'rgba(148, 163, 184, 0.15)',
    }
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

  if (devices.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
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
    <Container maxWidth="lg" sx={{ py: 3 }}>
      {/* 顶部标题 */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, color: 'primary.main', letterSpacing: '0.05em' }}>
              Network Device Management
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              {t('app.tagline')}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {dashboardStats && (
              <>
                <Typography variant="caption" color="text.secondary">
                  {t('dashboard.lastCollection')}: {formatRelativeTime(dashboardStats.last_collection)}
                </Typography>
                {dashboardStats.locations.map((loc) => (
                  <Chip key={loc} label={loc} size="small" sx={{ bgcolor: 'rgba(34,197,94,0.1)', color: 'success.main', height: 20, fontSize: '0.65rem' }} />
                ))}
              </>
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
      </Paper>

      {/* 统计卡片 */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {t('dashboard.totalDevicesCard')}
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#3B82F6', fontWeight: 700, mt: 0.5 }}>
                    {dashboardStats?.device_count ?? stats.total}
                  </Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 1.5, bgcolor: 'rgba(59, 130, 246, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Server sx={{ color: '#3B82F6', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {t('dashboard.activePorts')}
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#22C55E', fontWeight: 700, mt: 0.5 }}>
                    {dashboardStats?.port_stats.up ?? 0}
                  </Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 1.5, bgcolor: 'rgba(34, 197, 94, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <CheckCircle sx={{ color: '#22C55E', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {t('dashboard.idlePorts')}
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#94A3B8', fontWeight: 700, mt: 0.5 }}>
                    {(dashboardStats?.port_stats.down ?? 0) + (dashboardStats?.port_stats.disabled ?? 0)}
                  </Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 1.5, bgcolor: 'rgba(148, 163, 184, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <PauseCircle sx={{ color: '#94A3B8', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {t('dashboard.errorPorts')}
                  </Typography>
                  <Typography variant="h3" sx={{ color: dashboardStats?.error_ports ? '#EF4444' : '#22C55E', fontWeight: 700, mt: 0.5 }}>
                    {dashboardStats?.error_ports ?? 0}
                  </Typography>
                </Box>
                <Box sx={{ width: 48, height: 48, borderRadius: 1.5, bgcolor: 'rgba(239, 68, 68, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ErrorOutline sx={{ color: dashboardStats?.error_ports ? '#EF4444' : '#22C55E', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 上行流量 Top 10 */}
      {dashboardStats && dashboardStats.top_traffic.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>{t('dashboard.topTraffic')}</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>#</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>设备</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>端口</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>RX Mbps</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>TX Mbps</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>总 Mbps</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {dashboardStats.top_traffic.map((item, idx) => (
                  <TableRow key={`${item.device}-${item.port}`} hover>
                    <TableCell sx={{ color: 'text.secondary', fontWeight: 600 }}>{idx + 1}</TableCell>
                    <TableCell>
                      <Typography variant="body2" component="a" href={`/devices/${item.device}`} sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
                        {item.device}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{item.port}</TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{item.rx_mbps.toFixed(2)}</TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{item.tx_mbps.toFixed(2)}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: 'success.main' }}>
                          {item.total_mbps.toFixed(2)}
                        </Typography>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min((item.total_mbps / (dashboardStats.top_traffic[0]?.total_mbps || 1)) * 100, 100)}
                          sx={{ flex: 1, height: 6, borderRadius: 3, bgcolor: 'rgba(34,197,94,0.1)', '& .MuiLinearProgress-bar': { bgcolor: '#22C55E' } }}
                        />
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* 设备表格 */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {t('dashboard.deviceInventory')}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="caption" color="text.secondary">
              {t('dashboard.total')}: {devices.length}
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
          <Table>
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
                        <Typography variant="body2" component="a" href={`/devices/${device.name}`} sx={{ color: 'primary.main', textDecoration: 'none', fontWeight: 500, '&:hover': { textDecoration: 'underline' } }}>
                          {device.name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getTypeLabel(device.type)}
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
                    <TableCell>{device.ip}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{device.location || '-'}</TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem', fontFamily: '"JetBrains Mono", monospace' }}>
                      {device.serial_number || '-'}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem', fontFamily: '"JetBrains Mono", monospace' }}>
                      {device.version || '-'}
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const status = deviceStatus[device.name]
                        if (!status) {
                          return <Chip label="-" size="small" sx={{ bgcolor: 'rgba(148,163,184,0.08)', color: 'text.secondary', height: 20, fontSize: '0.65rem' }} />
                        }
                        if (status === 'checking') {
                          return <Chip label={t('dashboard.checking')} size="small" sx={{ bgcolor: 'rgba(245,158,11,0.12)', color: 'warning.main', height: 20, fontSize: '0.65rem' }} />
                        }
                        if (status === 'online') {
                          return <Chip label={t('dashboard.online')} size="small" sx={{ bgcolor: 'rgba(34,197,94,0.12)', color: 'success.main', height: 20, fontSize: '0.65rem' }} />
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
