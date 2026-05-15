import React, { useState, useEffect } from 'react'
import {
  Box,
  Container,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  Card,
  CardContent,
  IconButton,
  Tooltip,
  Badge,
  LinearProgress,
  Alert,
  Avatar,
  CircularProgress,
  Checkbox,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import {
  Add,
  Delete,
  Storage,
  Refresh as RefreshIcon,
  CloudUpload,
  NetworkWifi,
  DeleteForever,
} from '@mui/icons-material'
import { deviceApi, collectorApi } from '../services/api'
import { sessionManager } from '../services/auth'
import DeviceForm from './DeviceForm'

const LOCATIONS_ROW1 = ['BJD', 'BJQ', 'DZN', 'PVG', 'SHA', 'SZX', 'ZGN']
const LOCATIONS_ROW2 = ['PEK', 'DEZ', 'UCD', 'SJY']

type BatchItemStatus = {
  status: 'pending' | 'pinging' | 'collecting' | 'success' | 'failed'
  error?: string
  result?: any
}

const DeviceList: React.FC = () => {
  const [devices, setDevices] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [openDialog, setOpenDialog] = useState(false)
  const [openConfirm, setOpenConfirm] = useState(false)
  const [openCollect, setOpenCollect] = useState(false)
  const [selectedDevice, setSelectedDevice] = useState<any>(null)
  const [collecting, setCollecting] = useState(false)
  const [collectError, setCollectError] = useState('')
  const [collectResult, setCollectResult] = useState<any>(null)
  const [collectPhase, setCollectPhase] = useState<'ping' | 'collect' | null>(null)

  // 位置筛选
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)

  // 批量选择
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set())
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchStatus, setBatchStatus] = useState<Record<string, BatchItemStatus>>({})

  // 排序
  const [sortField, setSortField] = useState<string>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  useEffect(() => {
    loadDevices()
  }, [])

  const loadDevices = async () => {
    try {
      const response = await deviceApi.list()
      setDevices(response.data)
    } catch (error: any) {
      console.error('加载设备失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenDialog = () => setOpenDialog(true)
  const handleCloseDialog = () => setOpenDialog(false)

  const handleSaveDevice = async (_data?: any) => {
    handleCloseDialog()
    await loadDevices()
  }

  const handleDelete = (device: any) => {
    setSelectedDevice(device)
    setOpenConfirm(true)
  }

  const handleConfirmDelete = async () => {
    try {
      await deviceApi.delete(selectedDevice.name)
      loadDevices()
      setOpenConfirm(false)
    } catch (error: any) {
      alert(error.message || '删除失败')
    }
  }

  // 单设备收集
  const handleCollect = async (device: any) => {
    const session = sessionManager.getSession()
    if (!session) {
      alert('请先登录')
      window.location.href = '/login'
      return
    }

    setSelectedDevice(device)
    setCollecting(true)
    setCollectPhase('ping')
    setCollectError('')

    try {
      const pingResult = await collectorApi.ping(device.name)
      if (!pingResult.reachable) {
        setCollectError(`设备不可达：${pingResult.detail}`)
        return
      }

      setCollectPhase('collect')
      const data = await collectorApi.collect(device.name, session.username, session.password)
      setCollectResult(data.result)
      setOpenCollect(true)
    } catch (error: any) {
      setCollectError(error.message || '收集失败')
    } finally {
      setCollecting(false)
      setCollectPhase(null)
    }
  }

  // 全选/取消全选
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedDevices(new Set(devices.map((d) => d.name)))
    } else {
      setSelectedDevices(new Set())
    }
  }

  // 单选
  const handleSelectOne = (name: string, checked: boolean) => {
    const next = new Set(selectedDevices)
    if (checked) {
      next.add(name)
    } else {
      next.delete(name)
    }
    setSelectedDevices(next)
  }

  // 批量收集
  const handleBatchCollect = async () => {
    const session = sessionManager.getSession()
    if (!session) { alert('请先登录'); window.location.href = '/login'; return }

    const deviceNames = Array.from(selectedDevices)
    if (deviceNames.length === 0) { alert('请先选择设备'); return }

    setBatchRunning(true)
    const initial: Record<string, BatchItemStatus> = {}
    deviceNames.forEach((n) => { initial[n] = { status: 'pending' } })
    setBatchStatus(initial)

    try {
      const data = await collectorApi.batchCollect(deviceNames, session.username, session.password)
      const updated: Record<string, BatchItemStatus> = {}
      for (const r of data.results) {
        // 确保 error 始终为字符串，避免 [object Object]
        const errStr = typeof r.error === 'string' ? r.error : (r.error ? JSON.stringify(r.error) : '')
        updated[r.device || r.name] = {
          status: r.status === 'success' ? 'success' : 'failed',
          error: errStr || r.detail || '',
          result: r,
        }
      }
      setBatchStatus((prev) => ({ ...prev, ...updated }))
    } catch (error: any) {
      const errMsg = typeof error.message === 'string' ? error.message : JSON.stringify(error)
      const failed: Record<string, BatchItemStatus> = {}
      deviceNames.forEach((n) => { failed[n] = { status: 'failed', error: errMsg } })
      setBatchStatus((prev) => ({ ...prev, ...failed }))
    } finally {
      setBatchRunning(false)
      loadDevices()
    }
  }

  const getTypeLabel = (type: string) => {
    if (type === 'cisco_ios') return 'Cisco IOS'
    if (type === 'aruba_osswitch') return 'Aruba OS'
    return type
  }

  const getDeviceColor = (type: string) => {
    if (type === 'cisco_ios') return {
      primary: '#3b82f6',
      secondary: 'rgba(59, 130, 246, 0.15)',
      border: 'rgba(59, 130, 246, 0.3)',
    }
    if (type === 'aruba_osswitch') return {
      primary: '#06b6d4',
      secondary: 'rgba(6, 182, 212, 0.15)',
      border: 'rgba(6, 182, 212, 0.3)',
    }
    return {
      primary: '#94a3b8',
      secondary: 'rgba(148, 163, 184, 0.15)',
      border: 'rgba(148, 163, 184, 0.2)',
    }
  }

  // 按位置筛选
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

  const filteredDevices = selectedLocation
    ? devices.filter((d) => (d.location || '').toUpperCase() === selectedLocation.toUpperCase())
    : devices

  const sortedDevices = [...filteredDevices].sort((a: any, b: any) => {
    const va = (a[sortField] || '').toString().toLowerCase()
    const vb = (b[sortField] || '').toString().toLowerCase()
    return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
  })

  const allSelected = devices.length > 0 && selectedDevices.size === devices.length
  const someSelected = selectedDevices.size > 0 && selectedDevices.size < devices.length

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ textAlign: 'center' }}>
          <LinearProgress sx={{ bgcolor: 'rgba(0, 0, 0, 0.3)', height: 2 }} />
        </Box>
      </Container>
    )
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 顶部标题栏 + 位置筛选按钮 */}
      <Paper
        sx={{
          p: 3,
          bgcolor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          mb: 3,
          borderRadius: 2,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '100%',
            opacity: 0.03,
            backgroundImage: `
              linear-gradient(90deg, transparent 50%, rgba(52, 211, 153, 0.3) 50%),
              linear-gradient(rgba(52, 211, 153, 0.3) 1px, transparent 1px)
            `,
            backgroundSize: '300% 100%, 50px 50px',
            maskImage: 'linear-gradient(to bottom, transparent, 10%, black, transparent)',
          }}
        />

        <Box sx={{ position: 'relative', zIndex: 1 }}>
          {/* 标题行 */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Box>
              <Typography variant="h4" sx={{ color: '#fff', fontWeight: 700, mb: 1 }}>
                <span style={{ color: '#2563eb' }}>Network</span>
                <span style={{ color: '#06b6d4' }}>Engineer</span>
                <span style={{ color: '#34d399' }}>Pro</span>
              </Typography>
              <Typography variant="subtitle2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' }}>
                Device Inventory Management
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={handleOpenDialog}
              sx={{
                px: 3, py: 1, fontSize: '0.875rem', fontWeight: 700,
                letterSpacing: '0.025em', textTransform: 'uppercase',
                bgcolor: '#2563eb', color: '#fff',
                '&:hover': { bgcolor: '#3b82f6', boxShadow: '0 0 20px rgba(37, 99, 235, 0.4)' },
              }}
            >
              Add Device
            </Button>
          </Box>

          {/* 位置筛选按钮 */}
          <Box>
            <Typography variant="caption" sx={{ color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', mb: 1 }}>
              Filter by Location
            </Typography>

            {/* 第一排 */}
            <ToggleButtonGroup
              value={selectedLocation}
              exclusive
              onChange={(_, v) => setSelectedLocation(v)}
              size="small"
              sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5,
                '& .MuiToggleButton-root': {
                  color: '#94a3b8', borderColor: 'rgba(148, 163, 184, 0.25)',
                  px: 2, py: 0.25, fontSize: '0.75rem', fontWeight: 600,
                  textTransform: 'none', borderRadius: '6px !important',
                  '&.Mui-selected': {
                    color: '#34d399', bgcolor: 'rgba(52, 211, 153, 0.15)',
                    borderColor: 'rgba(52, 211, 153, 0.4)',
                  },
                  '&:hover': { bgcolor: 'rgba(52, 211, 153, 0.08)' },
                },
              }}
            >
              {LOCATIONS_ROW1.map((loc) => (
                <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>
              ))}
            </ToggleButtonGroup>

            {/* 第二排 */}
            <ToggleButtonGroup
              value={selectedLocation}
              exclusive
              onChange={(_, v) => setSelectedLocation(v)}
              size="small"
              sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5,
                '& .MuiToggleButton-root': {
                  color: '#94a3b8', borderColor: 'rgba(148, 163, 184, 0.25)',
                  px: 2, py: 0.25, fontSize: '0.75rem', fontWeight: 600,
                  textTransform: 'none', borderRadius: '6px !important',
                  '&.Mui-selected': {
                    color: '#34d399', bgcolor: 'rgba(52, 211, 153, 0.15)',
                    borderColor: 'rgba(52, 211, 153, 0.4)',
                  },
                  '&:hover': { bgcolor: 'rgba(52, 211, 153, 0.08)' },
                },
              }}
            >
              {LOCATIONS_ROW2.map((loc) => (
                <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>
        </Box>
      </Paper>

      {/* 单设备收集进度 */}
      {collecting && selectedDevice && (
        <Paper
          sx={{
            p: 2, mb: 3, bgcolor: '#0d121f',
            border: `1px solid ${collectPhase === 'ping' ? 'rgba(250, 204, 21, 0.4)' : 'rgba(34, 211, 238, 0.3)'}`,
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={24} sx={{ color: collectPhase === 'ping' ? '#facc15' : '#22d3ee' }} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ color: collectPhase === 'ping' ? '#facc15' : '#22d3ee', fontWeight: 600 }}>
                {collectPhase === 'ping'
                  ? `正在 Ping ${selectedDevice.ip} ...`
                  : `正在收集 ${selectedDevice.name} (${selectedDevice.ip}) ...`}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {collectPhase === 'ping' ? '检测设备在线状态' : 'SSH 连接交换机，下载配置（10-30 秒）'}
              </Typography>
            </Box>
          </Box>
          <LinearProgress
            sx={{
              mt: 1.5,
              bgcolor: collectPhase === 'ping' ? 'rgba(250, 204, 21, 0.1)' : 'rgba(34, 211, 238, 0.1)',
              '& .MuiLinearProgress-bar': { bgcolor: collectPhase === 'ping' ? '#facc15' : '#22d3ee' },
            }}
          />
        </Paper>
      )}

      {/* 收集错误提示 — 独立于进度条显示 */}
      {collectError && !collecting && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setCollectError('')}>
          {collectError}
        </Alert>
      )}

      {/* 批量收集进度 */}
      {batchRunning && (
        <Paper
          sx={{
            p: 2, mb: 3, bgcolor: '#0d121f',
            border: '1px solid rgba(34, 211, 238, 0.3)', borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
            <CircularProgress size={24} sx={{ color: '#22d3ee' }} />
            <Typography variant="body2" sx={{ color: '#22d3ee', fontWeight: 600 }}>
              批量收集进行中...
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {Object.values(batchStatus).filter((s) => s.status === 'success').length} / {Object.keys(batchStatus).length} 完成
            </Typography>
          </Box>
          <LinearProgress sx={{ bgcolor: 'rgba(34, 211, 238, 0.1)', '& .MuiLinearProgress-bar': { bgcolor: '#22d3ee' } }} />
        </Paper>
      )}

      {/* 批量结果摘要（收集完成后） */}
      {!batchRunning && Object.keys(batchStatus).length > 0 && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: '#0d121f', border: '1px solid rgba(52, 211, 153, 0.1)', borderRadius: 2 }}>
          <Typography variant="subtitle2" sx={{ color: '#fff', mb: 1, fontWeight: 600 }}>
            批量收集结果
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {Object.entries(batchStatus).map(([name, s]) => (
              <Chip
                key={name}
                label={`${name}: ${s.status === 'success' ? 'OK' : s.error || '失败'}`}
                size="small"
                sx={{
                  bgcolor: s.status === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                  color: s.status === 'success' ? '#10b981' : '#ef4444',
                  border: `1px solid ${s.status === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                  fontSize: '0.7rem',
                }}
              />
            ))}
          </Box>
        </Paper>
      )}

      {/* 设备卡片网格 — 仅在选择 location 后显示 */}
      {selectedLocation && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {sortedDevices.length === 0 ? (
            <Grid item xs={12}>
              <Paper sx={{ p: 3, textAlign: 'center', bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
                <Typography color="text.secondary">该位置 ({selectedLocation}) 下没有设备</Typography>
              </Paper>
            </Grid>
          ) : (
            sortedDevices.map((device) => {
              const colors = getDeviceColor(device.type)
              return (
                <Grid item xs={12} sm={6} md={4} lg={3} key={device.name}>
                  <Card
                    sx={{
                      height: '100%', position: 'relative', bgcolor: '#0d121f',
                      border: `1px solid ${colors.border}`, transition: 'all 300ms ease', overflow: 'hidden',
                      '&::before': {
                        content: '""', position: 'absolute', inset: 0,
                        background: `linear-gradient(135deg, ${colors.secondary}, transparent)`, pointerEvents: 'none',
                      },
                      '&::after': {
                        content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                        background: `linear-gradient(90deg, transparent, ${colors.primary}, transparent)`,
                      },
                      '&:hover': {
                        boxShadow: `0 8px 24px rgba(${colors.primary}, 0.2), 0 0 0 1px ${colors.primary}`,
                        transform: 'translateY(-4px)',
                      },
                    }}
                  >
                    <Box sx={{ position: 'absolute', top: 8, left: 8, right: 8, bottom: 8, border: `1px solid ${colors.border}` }} />
                    <CardContent sx={{ position: 'relative', zIndex: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <Badge
                          overlap="circular" anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} variant="dot"
                          color={collecting ? 'error' : 'success'}
                          sx={{ mr: 1.5, mt: 0.5, '& .MuiBadge-badge': { color: colors.primary, bgcolor: colors.primary } }}
                        >
                          <Storage sx={{ color: colors.primary, fontSize: 20 }} />
                        </Badge>
                        <Box>
                          <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600, mb: 0.5 }}>{device.name}</Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <NetworkWifi sx={{ fontSize: 14 }} />{device.ip}
                          </Typography>
                        </Box>
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Chip label={getTypeLabel(device.type)} sx={{ bgcolor: colors.secondary, color: colors.primary, border: `1px solid ${colors.border}`, fontWeight: 500, fontSize: '0.75rem', mr: 0.5, mb: 0.5 }} />
                        {device.location && (
                          <Chip label={device.location} sx={{ bgcolor: 'rgba(148,163,184,0.1)', color: '#94a3b8', border: '1px solid rgba(148,163,184,0.2)', fontWeight: 500, fontSize: '0.75rem', ml: 0.5, mb: 0.5 }} />
                        )}
                      </Box>

                      {device.notes && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontSize: '0.75rem' }}>
                          {device.notes}
                        </Typography>
                      )}

                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          <Storage sx={{ fontSize: 12, color: 'rgba(148,163,184,0.5)' }} />
                          {device.platform || 'Unknown'}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Tooltip title={collecting && selectedDevice?.name === device.name ? '正在收集...' : 'Collect Configuration'}>
                            <IconButton size="small" onClick={() => handleCollect(device)} disabled={collecting}
                              sx={{ color: colors.primary, bgcolor: 'rgba(52,211,153,0.05)', '&:hover': { bgcolor: 'rgba(52,211,153,0.15)' } }}>
                              <CloudUpload fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="View Details">
                            <IconButton size="small" component="a" href={`/devices/${device.name}`}
                              sx={{ color: '#34d399', bgcolor: 'rgba(52,211,153,0.05)', '&:hover': { bgcolor: 'rgba(52,211,153,0.15)' } }}>
                              <RefreshIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete">
                            <IconButton size="small" onClick={() => handleDelete(device)}
                              sx={{ color: '#ef4444', bgcolor: 'rgba(239,68,68,0.05)', '&:hover': { bgcolor: 'rgba(239,68,68,0.15)' } }}>
                              <Delete fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              )
            })
          )}
        </Grid>
      )}

      {/* 空状态 — 未选择 location 时显示提示 */}
      {!selectedLocation && devices.length > 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', mb: 4, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
          <NetworkWifi sx={{ fontSize: 48, color: 'rgba(148,163,184,0.2)', mb: 2 }} />
          <Typography variant="body1" color="text.secondary" sx={{ mb: 0.5 }}>
            点击上方位置按钮筛选设备
          </Typography>
          <Typography variant="caption" color="text.secondary">
            选择 Office Location 后，对应位置的设备卡片将在此处显示
          </Typography>
        </Paper>
      )}

      {/* 空状态 — 没有任何设备 */}
      {devices.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', mb: 4, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
          <Box sx={{ width: 100, height: 100, mx: 'auto', mb: 3, borderRadius: '50%', border: '3px solid rgba(52,211,153,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
            <Box sx={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'conic-gradient(from 0deg, rgba(52,211,153,0.1), rgba(52,211,153,0.3), rgba(52,211,153,0.1))', animation: 'spin 3s linear infinite' }} />
            <Storage sx={{ fontSize: 56, color: '#34d399', position: 'relative', zIndex: 1 }} />
          </Box>
          <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 500, mb: 1 }}>No Devices Configured</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>添加设备以开始管理网络交换机配置</Typography>
          <Button variant="contained" startIcon={<Add />} onClick={handleOpenDialog}
            sx={{ px: 3, py: 1, fontWeight: 700, letterSpacing: '0.025em', textTransform: 'uppercase', bgcolor: '#2563eb', '&:hover': { bgcolor: '#3b82f6', boxShadow: '0 0 20px rgba(37,99,235,0.4)' } }}>
            Add Device
          </Button>
        </Paper>
      )}

      {/* 设备表格 — 多选 + 批量操作 */}
      <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
            Device Inventory
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {selectedDevices.size > 0 && (
              <Button
                variant="contained" size="small" disabled={batchRunning}
                onClick={handleBatchCollect}
                sx={{
                  textTransform: 'none', fontWeight: 600, fontSize: '0.75rem',
                  bgcolor: '#22d3ee', color: '#000', '&:hover': { bgcolor: '#67e8f9' },
                }}
              >
                批量收集 ({selectedDevices.size})
              </Button>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.75rem' }}>
              Total: {devices.length}
            </Typography>
          </Box>
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={allSelected}
                    indeterminate={someSelected}
                    onChange={(_, checked) => handleSelectAll(checked)}
                    sx={{ color: '#94a3b8', '&.Mui-checked': { color: '#34d399' }, '&.MuiCheckbox-indeterminate': { color: '#34d399' } }}
                  />
                </TableCell>
                <TableCell onClick={() => handleSort('name')} sx={{ ...sortStyle('name'), fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>
                  Device {sortField === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </TableCell>
                <TableCell onClick={() => handleSort('type')} sx={{ ...sortStyle('type'), fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>
                  Type {sortField === 'type' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </TableCell>
                <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>IP Address</TableCell>
                <TableCell onClick={() => handleSort('location')} sx={{ ...sortStyle('location'), fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>
                  Location {sortField === 'location' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </TableCell>
                <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>Platform</TableCell>
                <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>Last Sync</TableCell>
                <TableCell sx={{ color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedDevices.map((device) => {
                const colors = getDeviceColor(device.type)
                const isSelected = selectedDevices.has(device.name)
                const bs = batchStatus[device.name]
                return (
                  <TableRow
                    key={device.name}
                    hover
                    selected={isSelected}
                    sx={{
                      '&:hover': { bgcolor: 'rgba(52,211,153,0.05)' },
                      '&.Mui-selected': { bgcolor: 'rgba(52,211,153,0.08)' },
                    }}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={isSelected}
                        onChange={(_, checked) => handleSelectOne(device.name, checked)}
                        sx={{ color: '#94a3b8', '&.Mui-checked': { color: '#34d399' } }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Avatar sx={{ bgcolor: colors.secondary, color: colors.primary, mr: 1.5, width: 32, height: 32, border: `1px solid ${colors.primary}` }}>
                          <Storage fontSize="small" />
                        </Avatar>
                        <Box>
                          <Typography variant="body2" sx={{ color: '#e2e8f0', fontWeight: 500 }}>{device.name}</Typography>
                          {bs && (
                            <Chip
                              label={bs.status === 'success' ? 'OK' : bs.status === 'failed' ? '失败' : bs.status}
                              size="small"
                              sx={{
                                height: 16, fontSize: '0.6rem', mt: 0.25,
                                bgcolor: bs.status === 'success' ? 'rgba(16,185,129,0.15)' : bs.status === 'failed' ? 'rgba(239,68,68,0.15)' : 'rgba(148,163,184,0.1)',
                                color: bs.status === 'success' ? '#10b981' : bs.status === 'failed' ? '#ef4444' : '#94a3b8',
                              }}
                            />
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip label={getTypeLabel(device.type)} size="small"
                        sx={{ bgcolor: colors.secondary, color: colors.primary, border: `1px solid ${colors.primary}`, fontWeight: 500, height: 20, fontSize: '0.65rem' }} />
                    </TableCell>
                    <TableCell sx={{ color: '#e2e8f0', fontSize: '0.8rem' }}>{device.ip}</TableCell>
                    <TableCell sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>{device.location || '-'}</TableCell>
                    <TableCell sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>{device.platform || '-'}</TableCell>
                    <TableCell sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                      {device.last_synced
                        ? (() => { const [d, t] = device.last_synced.split(' '); return `${d} ${t || ''}`; })()
                        : '-'}
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Tooltip title="Collect">
                          <IconButton size="small" onClick={() => handleCollect(device)} disabled={collecting}
                            sx={{ color: colors.primary, bgcolor: 'rgba(52,211,153,0.05)', '&:hover': { bgcolor: 'rgba(52,211,153,0.15)' } }}>
                            <CloudUpload fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Details">
                          <IconButton size="small" component="a" href={`/devices/${device.name}`}
                            sx={{ color: '#34d399', bgcolor: 'rgba(52,211,153,0.05)', '&:hover': { bgcolor: 'rgba(52,211,153,0.15)' } }}>
                            <RefreshIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton size="small" onClick={() => handleDelete(device)}
                            sx={{ color: '#ef4444', bgcolor: 'rgba(239,68,68,0.05)', '&:hover': { bgcolor: 'rgba(239,68,68,0.15)' } }}>
                            <Delete fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* 添加/编辑设备对话框 */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DeviceForm deviceName={null} onSubmit={handleSaveDevice} onCancel={handleCloseDialog} loading={collecting} />
      </Dialog>

      {/* 单设备收集结果对话框 */}
      <Dialog open={openCollect} onClose={() => setOpenCollect(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {collectResult?.status === 'success'
              ? <CloudUpload color="success" sx={{ fontSize: 40, filter: 'drop-shadow(0 0 12px rgba(16,185,129,0.6))' }} />
              : <CloudUpload color="error" sx={{ fontSize: 40 }} />}
            <Box>
              <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600 }}>Configuration Collection</Typography>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {collectResult?.status === 'success' ? 'Success' : 'Failed'}
              </Typography>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {collectError && <Alert severity="error" sx={{ mb: 2 }}>{collectError}</Alert>}
          {collectResult?.status === 'success' && (
            <Box sx={{ p: 2 }}>
              <Box sx={{ p: 2, bgcolor: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 1, mb: 2 }}>
                <Typography variant="body1" gutterBottom>
                  <strong style={{ color: '#34d399' }}>Device:</strong>{' '}
                  <span style={{ color: '#e2e8f0' }}>{collectResult.name}</span>
                </Typography>
                <Typography variant="body1">
                  <strong style={{ color: '#34d399' }}>IP:</strong>{' '}
                  <span style={{ color: '#e2e8f0' }}>{collectResult.ip}</span>
                </Typography>
                <Typography variant="body1">
                  <strong style={{ color: '#34d399' }}>Software Version:</strong>{' '}
                  <span style={{ color: '#e2e8f0' }}>{collectResult.software_version}</span>
                </Typography>
                <Typography variant="body1">
                  <strong style={{ color: '#34d399' }}>Serial Number:</strong>{' '}
                  <span style={{ color: '#e2e8f0' }}>{collectResult.serial_number || 'Unknown'}</span>
                </Typography>
                <Typography variant="body1" sx={{ mt: 1, fontWeight: 500 }}>
                  <strong style={{ color: '#34d399' }}>Running Config Lines:</strong>{' '}
                  <span style={{ color: '#10b981' }}>{collectResult.running_lines}</span>
                </Typography>
              </Box>
              {collectResult.type_mismatch && (
                <Alert severity="warning" sx={{ mb: 2, fontSize: '0.8rem' }}>
                  设备类型已自动修正：{collectResult.configured_type} → {collectResult.device_type}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenCollect(false)} sx={{ fontWeight: 600, letterSpacing: '0.025em', textTransform: 'uppercase' }}>Close</Button>
          {collectResult?.status === 'success' && (
            <Button variant="contained" onClick={() => { setOpenCollect(false); window.location.href = `/viewer?device=${selectedDevice?.name}` }}
              sx={{ fontWeight: 700, letterSpacing: '0.025em', textTransform: 'uppercase', bgcolor: '#2563eb', '&:hover': { bgcolor: '#3b82f6', boxShadow: '0 0 20px rgba(37,99,235,0.4)' } }}>
              View Data
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={openConfirm} onClose={() => setOpenConfirm(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <DeleteForever color="error" sx={{ fontSize: 40 }} />
            <Box>
              <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600 }}>Delete Device</Typography>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Confirm Deletion</Typography>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            Are you sure you want to delete device <strong style={{ color: '#ef4444' }}>{selectedDevice?.name}</strong>? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenConfirm(false)} sx={{ textTransform: 'none', fontWeight: 600 }}>Cancel</Button>
          <Button onClick={handleConfirmDelete} variant="contained" color="error" sx={{ textTransform: 'none', fontWeight: 700, letterSpacing: '0.025em' }}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Container>
  )
}

export default DeviceList
