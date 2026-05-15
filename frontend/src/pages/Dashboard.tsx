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
  CloudDownload,
  Security as SecurityIcon,
  Wifi as WifiIcon,
} from '@mui/icons-material'
import { deviceApi, collectorApi } from '../services/api'
import { sessionManager } from '../services/auth'

const Dashboard: React.FC = () => {
  const [devices, setDevices] = useState<any[]>([])
  const [stats, setStats] = useState({
    total: 0,
    cisco: 0,
    aruba: 0,
    collectedToday: 0,
  })
  const user = sessionManager.getSession()

  useEffect(() => {
    loadDevices()
  }, [])

  useEffect(() => {
    if (devices.length > 0) {
      const cisco = devices.filter((d) => d.type === 'cisco_ios').length
      const aruba = devices.filter((d) => d.type === 'aruba_osswitch').length
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
    } catch (error: any) {
      console.error('加载设备失败:', error)
    }
  }

  const [sortField, setSortField] = useState<string>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [deviceStatus, setDeviceStatus] = useState<Record<string, 'checking' | 'online' | 'offline'>>({})
  const [pinging, setPinging] = useState(false)
  const pingControllerRef = useRef<AbortController | null>(null)

  const sortedDevices = [...devices].sort((a: any, b: any) => {
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

  const pingAllDevices = async (deviceList: any[], signal?: AbortSignal) => {
    deviceList.forEach(async (device) => {
      try {
        const result = await collectorApi.ping(device.name, signal)
        setDeviceStatus((prev) => ({
          ...prev,
          [device.name]: result.reachable ? 'online' : 'offline',
        }))
      } catch (e: any) {
        if (e?.name === 'AbortError') return
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
    setPinging(false)
  }

  useEffect(() => {
    return () => {
      pingControllerRef.current?.abort()
    }
  }, [])

  const getTypeLabel = (type: string) => {
    if (type === 'cisco_ios') return 'Cisco IOS'
    if (type === 'aruba_osswitch') return 'Aruba OS'
    return type
  }

  // 设备类型色系
  const getDeviceColors = (type: string) => {
    if (type === 'cisco_ios') return {
      primary: '#3B82F6',
      bg: 'rgba(59, 130, 246, 0.12)',
      border: 'rgba(59, 130, 246, 0.25)',
    }
    if (type === 'aruba_osswitch') return {
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

  if (devices.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <Box sx={{ mb: 3 }}>
            <Server sx={{ fontSize: 64, color: 'text.disabled' }} />
          </Box>
          <Typography variant="h4" sx={{ color: 'text.primary', fontWeight: 700, mb: 1 }}>
            网络配置管理
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Cisco & Aruba 设备配置收集系统
          </Typography>
          <Button
            variant="contained"
            component={React.forwardRef<HTMLAnchorElement, React.HTMLProps<HTMLAnchorElement>>(
              (props, ref) => <a href="/devices" ref={ref} {...props} />
            )}
            sx={{ px: 4, py: 1.5, fontWeight: 700 }}
          >
            <Server sx={{ mr: 1, fontSize: 18 }} />
            添加设备
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
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
              <span style={{ color: '#22C55E' }}>Network</span>
              <span style={{ color: '#F8FAFC' }}>Engineer</span>
              <span style={{ color: '#4ADE80' }}>Pro</span>
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              实时监控 | 配置收集 | 性能分析
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
        <Grid item xs={12} sm={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Total Devices
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#3B82F6', fontWeight: 700, mt: 0.5 }}>
                    {stats.total}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    Active Monitored
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(59, 130, 246, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Server sx={{ color: '#3B82F6', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Cisco IOS
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#06B6D4', fontWeight: 700, mt: 0.5 }}>
                    {stats.cisco}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    Routers / Switches
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(6, 182, 212, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <CloudDownload sx={{ color: '#06B6D4', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Aruba OS
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#10B981', fontWeight: 700, mt: 0.5 }}>
                    {stats.aruba}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    Switches
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(16, 185, 129, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <SecurityIcon sx={{ color: '#10B981', fontSize: 24 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 设备表格 */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Device Inventory
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Total: {devices.length}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<WifiIcon />}
              onClick={handleRefreshStatus}
              disabled={pinging}
              sx={{ fontWeight: 600, fontSize: '0.75rem' }}
            >
              {pinging ? '刷新中...' : '刷新状态'}
            </Button>
          </Box>
        </Box>

        {pinging && (
          <Alert severity="info" sx={{ mb: 2, fontSize: '0.75rem' }}>
            正在 Ping 所有设备，请暂时不要切换页面...
            <LinearProgress sx={{ mt: 1 }} />
          </Alert>
        )}

        {devices.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Server sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
            <Typography variant="body1" color="text.secondary">
              No devices configured
            </Typography>
            <Button
              variant="contained"
              component={React.forwardRef<HTMLAnchorElement, React.HTMLProps<HTMLAnchorElement>>(
                (props, ref) => <a href="/devices" ref={ref} {...props} />
              )}
              sx={{ mt: 2 }}
            >
              Add Device
            </Button>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell onClick={() => handleSort('name')} sx={sortStyle('name')}>
                    Device {sortField === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell onClick={() => handleSort('type')} sx={sortStyle('type')}>
                    Type {sortField === 'type' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell>IP Address</TableCell>
                  <TableCell onClick={() => handleSort('location')} sx={sortStyle('location')}>
                    Location {sortField === 'location' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell>Serial Number</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Status</TableCell>
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
                          <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
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
                            return <Chip label="Checking..." size="small" sx={{ bgcolor: 'rgba(245,158,11,0.12)', color: 'warning.main', height: 20, fontSize: '0.65rem' }} />
                          }
                          if (status === 'online') {
                            return <Chip label="Online" size="small" sx={{ bgcolor: 'rgba(34,197,94,0.12)', color: 'success.main', height: 20, fontSize: '0.65rem' }} />
                          }
                          return <Chip label="Offline" size="small" sx={{ bgcolor: 'rgba(239,68,68,0.12)', color: 'error.main', height: 20, fontSize: '0.65rem' }} />
                        })()}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Container>
  )
}

export default Dashboard
