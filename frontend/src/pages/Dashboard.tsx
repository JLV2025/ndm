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

  // 加载统计数据
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
    '&:hover': { color: '#34d399' },
    color: sortField === field ? '#34d399' : '#94a3b8',
  } as const)

  const [sortField, setSortField] = useState<string>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [deviceStatus, setDeviceStatus] = useState<Record<string, 'checking' | 'online' | 'offline'>>({})
  const [pinging, setPinging] = useState(false)
  const pingControllerRef = useRef<AbortController | null>(null)

  // Ping 所有设备并更新状态
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

  // 手动刷新所有设备状态
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

  // 切换页面时取消进行中的 Ping
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

  const getDeviceColor = (type: string) => {
    if (type === 'cisco_ios') return {
      bgcolor: 'rgba(59, 130, 246, 0.2)',
      color: '#3b82f6',
      border: '1px solid rgba(59, 130, 246, 0.3)',
    }
    if (type === 'aruba_osswitch') return {
      bgcolor: 'rgba(6, 182, 212, 0.2)',
      color: '#06b6d4',
      border: '1px solid rgba(6, 182, 212, 0.3)',
    }
    return {
      bgcolor: 'rgba(148, 163, 184, 0.1)',
      color: '#94a3b8',
      border: '1px solid rgba(148, 163, 184, 0.2)',
    }
  }

  if (devices.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '60vh',
            bgcolor: '#0a0f1a',
            borderRadius: 3,
            border: '1px solid rgba(52, 211, 153, 0.1)',
            p: { xs: 4, md: 6 },
          }}
        >
          <Box
            sx={{
              width: 120,
              height: 120,
              mx: 'auto',
              mb: 3,
              borderRadius: '50%',
              border: '3px solid rgba(52, 211, 153, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                inset: 0,
                borderRadius: '50%',
                background: 'conic-gradient(from 0deg, rgba(52, 211, 153, 0.1), rgba(52, 211, 153, 0.3), rgba(52, 211, 153, 0.1))',
                animation: 'spin 3s linear infinite',
              }}
            />
            <Server sx={{ fontSize: 60, color: '#34d399', position: 'relative', zIndex: 1 }} />
          </Box>
          <Typography variant="h4" sx={{ color: '#fff', fontWeight: 700, mb: 1 }}>
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
            sx={{
              textTransform: 'uppercase',
              px: 4,
              py: 1.5,
              fontSize: '1rem',
              fontWeight: 700,
              letterSpacing: '0.025em',
              bgcolor: '#2563eb',
              '&:hover': {
                bgcolor: '#3b82f6',
                boxShadow: '0 0 24px rgba(37, 99, 235, 0.4)',
              },
            }}
          >
            <Server sx={{ mr: 1, fontSize: 18 }} />
            添加设备
          </Button>
        </Box>
      </Container>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      {/* 顶部标题栏 */}
      <Paper
        sx={{
          p: 3,
          bgcolor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          mb: 3,
          borderRadius: 2,
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" sx={{ color: '#fff', fontWeight: 700, mb: 1 }}>
              <span style={{ color: '#2563eb' }}>Network</span>
              <span style={{ color: '#06b6d4' }}>Engineer</span>
              <span style={{ color: '#34d399' }}>Pro</span>
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
                  <Avatar sx={{ bgcolor: '#06b6d4', width: 32, height: 32 }}>
                    {user.username.charAt(0).toUpperCase()}
                  </Avatar>
                }
                size="small"
                sx={{ bgcolor: 'rgba(6, 182, 212, 0.15)', color: '#06b6d4' }}
              />
            )}
          </Box>
        </Box>
      </Paper>

      {/* 统计卡片 */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* 总设备数 */}
        <Grid item xs={12} sm={4}>
          <Card
            sx={{
              height: '100%',
              position: 'relative',
              overflow: 'hidden',
              '&::before': {
                content: '""',
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1), transparent)',
                pointerEvents: 'none',
              },
            }}
          >
            {/* 装饰性边角 */}
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                left: 8,
                right: 8,
                bottom: 8,
                border: '1px solid rgba(59, 130, 246, 0.2)',
              }}
            />
            <CardContent sx={{ position: 'relative', zIndex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1 }}>
                    Total Devices
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#3b82f6', fontWeight: 700 }}>
                    {stats.total}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Active Monitored
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: 56,
                    height: 56,
                    borderRadius: 2,
                    bgcolor: 'rgba(59, 130, 246, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Server sx={{ color: '#3b82f6', fontSize: 28 }} />
                </Box>
              </Box>
            </CardContent>
            {/* 底部发光条 */}
            <Box
              sx={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: 2,
                background: 'linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.5), transparent)',
              }}
            />
          </Card>
        </Grid>

        {/* Cisco 设备 */}
        <Grid item xs={12} sm={4}>
          <Card
            sx={{
              height: '100%',
              position: 'relative',
              overflow: 'hidden',
              '&::before': {
                content: '""',
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.1), transparent)',
                pointerEvents: 'none',
              },
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                left: 8,
                right: 8,
                bottom: 8,
                border: '1px solid rgba(6, 182, 212, 0.2)',
              }}
            />
            <CardContent sx={{ position: 'relative', zIndex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1 }}>
                    Cisco IOS
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#06b6d4', fontWeight: 700 }}>
                    {stats.cisco}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Cisco Routers/Switches
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: 56,
                    height: 56,
                    borderRadius: 2,
                    bgcolor: 'rgba(6, 182, 212, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <CloudDownload sx={{ color: '#06b6d4', fontSize: 28 }} />
                </Box>
              </Box>
            </CardContent>
            <Box
              sx={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: 2,
                background: 'linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.5), transparent)',
              }}
            />
          </Card>
        </Grid>

        {/* Aruba 设备 */}
        <Grid item xs={12} sm={4}>
          <Card
            sx={{
              height: '100%',
              position: 'relative',
              overflow: 'hidden',
              '&::before': {
                content: '""',
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1), transparent)',
                pointerEvents: 'none',
              },
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                left: 8,
                right: 8,
                bottom: 8,
                border: '1px solid rgba(16, 185, 129, 0.2)',
              }}
            />
            <CardContent sx={{ position: 'relative', zIndex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1 }}>
                    Aruba OS
                  </Typography>
                  <Typography variant="h3" sx={{ color: '#10b981', fontWeight: 700 }}>
                    {stats.aruba}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Aruba Switches
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: 56,
                    height: 56,
                    borderRadius: 2,
                    bgcolor: 'rgba(16, 185, 129, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <SecurityIcon sx={{ color: '#10b981', fontSize: 28 }} />
                </Box>
              </Box>
            </CardContent>
            <Box
              sx={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: 2,
                background: 'linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.5), transparent)',
              }}
            />
          </Card>
        </Grid>
      </Grid>

      {/* 设备表格 */}
      <Paper
        sx={{
          p: 2,
          bgcolor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          borderRadius: 2,
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600 }}>
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
              sx={{
                textTransform: 'none', fontWeight: 600, fontSize: '0.75rem',
                border: '1px solid rgba(52, 211, 153, 0.4)',
                color: '#34d399', bgcolor: 'rgba(52, 211, 153, 0.05)',
                '&:hover': { bgcolor: 'rgba(52, 211, 153, 0.15)', borderColor: '#34d399' },
              }}
            >
              {pinging ? '刷新中...' : '刷新状态'}
            </Button>
          </Box>
        </Box>

        {pinging && (
          <Alert severity="info" sx={{ mb: 2, bgcolor: 'rgba(34, 211, 238, 0.08)', border: '1px solid rgba(34, 211, 238, 0.3)', color: '#22d3ee', fontSize: '0.75rem' }}>
            正在 Ping 所有设备，请暂时不要切换页面...
            <LinearProgress sx={{ mt: 1, bgcolor: 'rgba(34, 211, 238, 0.1)', '& .MuiLinearProgress-bar': { bgcolor: '#22d3ee' } }} />
          </Alert>
        )}

        {devices.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Server sx={{ fontSize: 60, color: 'rgba(148, 163, 184, 0.3)', mb: 2 }} />
            <Typography variant="body1" color="text.secondary">
              No devices configured
            </Typography>
            <Button
              variant="contained"
              component={React.forwardRef<HTMLAnchorElement, React.HTMLProps<HTMLAnchorElement>>(
                (props, ref) => <a href="/devices" ref={ref} {...props} />
              )}
              sx={{ mt: 2, textTransform: 'none' }}
            >
              Add Device
            </Button>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell onClick={() => handleSort('name')} sx={{ ...sortStyle('name'), fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    Device {sortField === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell onClick={() => handleSort('type')} sx={{ ...sortStyle('type'), fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    Type {sortField === 'type' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    IP Address
                  </TableCell>
                  <TableCell onClick={() => handleSort('location')} sx={{ ...sortStyle('location'), fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    Location {sortField === 'location' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    Serial Number
                  </TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    Version
                  </TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', py: 0.75 }}>
                    Status
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedDevices.map((device) => {
                  const colors = getDeviceColor(device.type)
                  return (
                    <TableRow
                      key={device.name}
                      hover
                      sx={{
                        '&:hover': {
                          bgcolor: 'rgba(52, 211, 153, 0.05)',
                        },
                        '& .MuiTableCell-root': {
                          py: 0.5,
                        },
                      }}
                    >
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Avatar
                            sx={{
                              bgcolor: colors.bgcolor,
                              color: colors.color,
                              mr: 1,
                              width: 30,
                              height: 30,
                              border: '1px solid',
                              borderColor: colors.color,
                            }}
                          >
                            <Server sx={{ fontSize: 16 }} />
                          </Avatar>
                          <Typography variant="body2" sx={{ color: '#e2e8f0', fontWeight: 500, fontSize: '0.8rem' }}>
                            {device.name}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={getTypeLabel(device.type)}
                          size="small"
                          sx={{
                            bgcolor: colors.bgcolor,
                            color: colors.color,
                            border: '1px solid',
                            borderColor: colors.color,
                            fontWeight: 500,
                            height: 18,
                            fontSize: '0.65rem',
                            '& .MuiChip-label': { px: 0.75 },
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ color: '#e2e8f0', fontSize: '0.8rem' }}>{device.ip}</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>{device.location || '-'}</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontSize: '0.75rem', fontFamily: '"Fira Code",monospace' }}>
                        {device.serial_number || '-'}
                      </TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontSize: '0.75rem', fontFamily: '"Fira Code",monospace' }}>
                        {device.version || '-'}
                      </TableCell>
                      <TableCell>
                        {(() => {
                          const status = deviceStatus[device.name]
                          if (!status) {
                            return (
                              <Chip
                                label="-"
                                size="small"
                                sx={{
                                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                                  color: '#94a3b8',
                                  border: '1px solid rgba(148, 163, 184, 0.2)',
                                  fontWeight: 500,
                                  height: 18,
                                  fontSize: '0.65rem',
                                  '& .MuiChip-label': { px: 0.75 },
                                }}
                              />
                            )
                          }
                          if (status === 'checking') {
                            return (
                              <Chip
                                label="Checking..."
                                size="small"
                                sx={{
                                  bgcolor: 'rgba(250, 204, 21, 0.15)',
                                  color: '#facc15',
                                  border: '1px solid rgba(250, 204, 21, 0.3)',
                                  fontWeight: 500,
                                  height: 18,
                                  fontSize: '0.65rem',
                                  '& .MuiChip-label': { px: 0.75 },
                                }}
                              />
                            )
                          }
                          if (status === 'online') {
                            return (
                              <Chip
                                label="Online"
                                size="small"
                                sx={{
                                  bgcolor: 'rgba(16, 185, 129, 0.2)',
                                  color: '#10b981',
                                  border: '1px solid rgba(16, 185, 129, 0.3)',
                                  fontWeight: 500,
                                  height: 18,
                                  fontSize: '0.65rem',
                                  '& .MuiChip-label': { px: 0.75 },
                                }}
                              />
                            )
                          }
                          return (
                            <Chip
                              label="Offline"
                              size="small"
                              sx={{
                                bgcolor: 'rgba(239, 68, 68, 0.2)',
                                color: '#ef4444',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                fontWeight: 500,
                                height: 18,
                                fontSize: '0.65rem',
                                '& .MuiChip-label': { px: 0.75 },
                              }}
                            />
                          )
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
