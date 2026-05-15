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
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set())
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchStatus, setBatchStatus] = useState<Record<string, BatchItemStatus>>({})
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

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedDevices(new Set(devices.map((d) => d.name)))
    } else {
      setSelectedDevices(new Set())
    }
  }

  const handleSelectOne = (name: string, checked: boolean) => {
    const next = new Set(selectedDevices)
    if (checked) {
      next.add(name)
    } else {
      next.delete(name)
    }
    setSelectedDevices(next)
  }

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
      primary: '#3B82F6',
      secondary: 'rgba(59, 130, 246, 0.1)',
      border: 'rgba(59, 130, 246, 0.2)',
    }
    if (type === 'aruba_osswitch') return {
      primary: '#06B6D4',
      secondary: 'rgba(6, 182, 212, 0.1)',
      border: 'rgba(6, 182, 212, 0.2)',
    }
    return {
      primary: '#94A3B8',
      secondary: 'rgba(148, 163, 184, 0.08)',
      border: 'rgba(148, 163, 184, 0.15)',
    }
  }

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
        <LinearProgress />
      </Container>
    )
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 顶部标题栏 + 位置筛选 */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Box>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                <span style={{ color: '#22C55E' }}>Network</span>
                <span style={{ color: '#F8FAFC' }}>Engineer</span>
                <span style={{ color: '#4ADE80' }}>Pro</span>
              </Typography>
              <Typography variant="subtitle2" color="text.secondary">
                Device Inventory Management
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={handleOpenDialog}
              sx={{ px: 3, py: 1, fontWeight: 700, letterSpacing: '0.02em' }}
            >
              Add Device
            </Button>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', mb: 1 }}>
              Filter by Location
            </Typography>

            <ToggleButtonGroup
              value={selectedLocation}
              exclusive
              onChange={(_, v) => setSelectedLocation(v)}
              size="small"
              sx={{
                mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5,
                '& .MuiToggleButton-root': {
                  color: 'text.secondary',
                  borderColor: 'divider',
                  px: 2, py: 0.25, fontSize: '0.75rem', fontWeight: 600,
                  textTransform: 'none', borderRadius: '6px !important',
                  '&.Mui-selected': {
                    color: 'primary.main',
                    bgcolor: 'rgba(34, 197, 94, 0.1)',
                    borderColor: 'rgba(34, 197, 94, 0.3)',
                  },
                  '&:hover': { bgcolor: 'rgba(34, 197, 94, 0.06)' },
                },
              }}
            >
              {LOCATIONS_ROW1.map((loc) => (
                <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>
              ))}
            </ToggleButtonGroup>

            <ToggleButtonGroup
              value={selectedLocation}
              exclusive
              onChange={(_, v) => setSelectedLocation(v)}
              size="small"
              sx={{
                display: 'flex', flexWrap: 'wrap', gap: 0.5,
                '& .MuiToggleButton-root': {
                  color: 'text.secondary',
                  borderColor: 'divider',
                  px: 2, py: 0.25, fontSize: '0.75rem', fontWeight: 600,
                  textTransform: 'none', borderRadius: '6px !important',
                  '&.Mui-selected': {
                    color: 'primary.main',
                    bgcolor: 'rgba(34, 197, 94, 0.1)',
                    borderColor: 'rgba(34, 197, 94, 0.3)',
                  },
                  '&:hover': { bgcolor: 'rgba(34, 197, 94, 0.06)' },
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
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={24} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 600 }}>
                {collectPhase === 'ping'
                  ? `正在 Ping ${selectedDevice.ip} ...`
                  : `正在收集 ${selectedDevice.name} (${selectedDevice.ip}) ...`}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {collectPhase === 'ping' ? '检测设备在线状态' : 'SSH 连接交换机，下载配置（10-30 秒）'}
              </Typography>
            </Box>
          </Box>
          <LinearProgress sx={{ mt: 1.5 }} />
        </Paper>
      )}

      {collectError && !collecting && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setCollectError('')}>
          {collectError}
        </Alert>
      )}

      {/* 批量收集进度 */}
      {batchRunning && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              批量收集进行中...
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {Object.values(batchStatus).filter((s) => s.status === 'success').length} / {Object.keys(batchStatus).length} 完成
            </Typography>
          </Box>
          <LinearProgress />
        </Paper>
      )}

      {!batchRunning && Object.keys(batchStatus).length > 0 && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            批量收集结果
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {Object.entries(batchStatus).map(([name, s]) => (
              <Chip
                key={name}
                label={`${name}: ${s.status === 'success' ? 'OK' : s.error || '失败'}`}
                size="small"
                sx={{
                  bgcolor: s.status === 'success' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                  color: s.status === 'success' ? 'success.main' : 'error.main',
                  fontSize: '0.7rem',
                }}
              />
            ))}
          </Box>
        </Paper>
      )}

      {/* 设备卡片网格 */}
      {selectedLocation && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {sortedDevices.length === 0 ? (
            <Grid item xs={12}>
              <Paper sx={{ p: 3, textAlign: 'center' }}>
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
                      height: '100%',
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      transition: 'box-shadow 200ms ease, transform 200ms ease',
                      '&:hover': {
                        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                        transform: 'translateY(-2px)',
                      },
                    }}
                  >
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <Badge
                          overlap="circular"
                          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                          variant="dot"
                          color="success"
                          sx={{ mr: 1.5, mt: 0.5 }}
                        >
                          <Storage sx={{ color: colors.primary, fontSize: 20 }} />
                        </Badge>
                        <Box>
                          <Typography variant="h6" sx={{ color: 'text.primary', fontWeight: 600 }}>{device.name}</Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <NetworkWifi sx={{ fontSize: 14 }} />{device.ip}
                          </Typography>
                        </Box>
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Chip
                          label={getTypeLabel(device.type)}
                          sx={{
                            bgcolor: colors.secondary, color: colors.primary,
                            border: '1px solid', borderColor: colors.border,
                            fontWeight: 500, fontSize: '0.75rem', mr: 0.5, mb: 0.5,
                          }}
                        />
                        {device.location && (
                          <Chip
                            label={device.location}
                            sx={{
                              bgcolor: 'rgba(148,163,184,0.08)', color: 'text.secondary',
                              border: '1px solid', borderColor: 'divider',
                              fontWeight: 500, fontSize: '0.75rem', ml: 0.5, mb: 0.5,
                            }}
                          />
                        )}
                      </Box>

                      {device.notes && (
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mb: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontSize: '0.75rem' }}
                        >
                          {device.notes}
                        </Typography>
                      )}

                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {device.platform || 'Unknown'}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Tooltip title={collecting ? '正在收集...' : 'Collect Configuration'}>
                            <IconButton size="small" onClick={() => handleCollect(device)} disabled={collecting}
                              sx={{ color: colors.primary, '&:hover': { bgcolor: colors.secondary } }}>
                              <CloudUpload fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="View Details">
                            <IconButton size="small" component="a" href={`/devices/${device.name}`}
                              sx={{ color: 'primary.main', '&:hover': { bgcolor: 'rgba(34,197,94,0.08)' } }}>
                              <RefreshIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete">
                            <IconButton size="small" onClick={() => handleDelete(device)}
                              sx={{ color: 'error.main', '&:hover': { bgcolor: 'rgba(239,68,68,0.08)' } }}>
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

      {/* 空状态提示 */}
      {!selectedLocation && devices.length > 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
          <NetworkWifi sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="body1" color="text.secondary" sx={{ mb: 0.5 }}>
            点击上方位置按钮筛选设备
          </Typography>
          <Typography variant="caption" color="text.secondary">
            选择 Office Location 后，对应位置的设备卡片将在此处显示
          </Typography>
        </Paper>
      )}

      {devices.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
          <Box sx={{ mb: 3 }}>
            <Storage sx={{ fontSize: 56, color: 'text.disabled' }} />
          </Box>
          <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 500, mb: 1 }}>No Devices Configured</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>添加设备以开始管理网络交换机配置</Typography>
          <Button variant="contained" startIcon={<Add />} onClick={handleOpenDialog} sx={{ px: 3, py: 1, fontWeight: 700 }}>
            Add Device
          </Button>
        </Paper>
      )}

      {/* 设备表格 */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
            Device Inventory
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {selectedDevices.size > 0 && (
              <Button
                variant="contained"
                size="small"
                disabled={batchRunning}
                onClick={handleBatchCollect}
                sx={{ fontWeight: 600, fontSize: '0.75rem' }}
              >
                批量收集 ({selectedDevices.size})
              </Button>
            )}
            <Typography variant="caption" color="text.secondary">
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
                    sx={{ color: 'text.secondary', '&.Mui-checked': { color: 'primary.main' }, '&.MuiCheckbox-indeterminate': { color: 'primary.main' } }}
                  />
                </TableCell>
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
                <TableCell>Platform</TableCell>
                <TableCell>Last Sync</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedDevices.map((device) => {
                const colors = getDeviceColor(device.type)
                const isSelected = selectedDevices.has(device.name)
                const bs = batchStatus[device.name]
                return (
                  <TableRow key={device.name} hover selected={isSelected}>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={isSelected}
                        onChange={(_, checked) => handleSelectOne(device.name, checked)}
                        sx={{ color: 'text.secondary', '&.Mui-checked': { color: 'primary.main' } }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Avatar sx={{ bgcolor: colors.secondary, color: colors.primary, mr: 1.5, width: 28, height: 28, border: '1px solid', borderColor: colors.border }}>
                          <Storage fontSize="small" />
                        </Avatar>
                        <Box>
                          <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>{device.name}</Typography>
                          {bs && (
                            <Chip
                              label={bs.status === 'success' ? 'OK' : bs.status === 'failed' ? '失败' : bs.status}
                              size="small"
                              sx={{
                                height: 16, fontSize: '0.6rem', mt: 0.25,
                                bgcolor: bs.status === 'success' ? 'rgba(34,197,94,0.1)' : bs.status === 'failed' ? 'rgba(239,68,68,0.1)' : 'rgba(148,163,184,0.06)',
                                color: bs.status === 'success' ? 'success.main' : bs.status === 'failed' ? 'error.main' : 'text.secondary',
                              }}
                            />
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getTypeLabel(device.type)}
                        size="small"
                        sx={{
                          bgcolor: colors.secondary, color: colors.primary,
                          border: '1px solid', borderColor: colors.border,
                          fontWeight: 500, height: 20, fontSize: '0.65rem',
                        }}
                      />
                    </TableCell>
                    <TableCell>{device.ip}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{device.location || '-'}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{device.platform || '-'}</TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
                      {device.last_synced
                        ? (() => { const [d, t] = device.last_synced.split(' '); return `${d} ${t || ''}`; })()
                        : '-'}
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Tooltip title="Collect">
                          <IconButton size="small" onClick={() => handleCollect(device)} disabled={collecting}
                            sx={{ color: colors.primary, '&:hover': { bgcolor: colors.secondary } }}>
                            <CloudUpload fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Details">
                          <IconButton size="small" component="a" href={`/devices/${device.name}`}
                            sx={{ color: 'primary.main', '&:hover': { bgcolor: 'rgba(34,197,94,0.08)' } }}>
                            <RefreshIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton size="small" onClick={() => handleDelete(device)}
                            sx={{ color: 'error.main', '&:hover': { bgcolor: 'rgba(239,68,68,0.08)' } }}>
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

      {/* 添加设备对话框 */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DeviceForm deviceName={null} onSubmit={handleSaveDevice} onCancel={handleCloseDialog} loading={collecting} />
      </Dialog>

      {/* 收集结果对话框 */}
      <Dialog open={openCollect} onClose={() => setOpenCollect(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {collectResult?.status === 'success'
              ? <CloudUpload color="success" sx={{ fontSize: 40 }} />
              : <CloudUpload color="error" sx={{ fontSize: 40 }} />}
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>Configuration Collection</Typography>
              <Typography variant="subtitle2" color="text.secondary">
                {collectResult?.status === 'success' ? 'Success' : 'Failed'}
              </Typography>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {collectError && <Alert severity="error" sx={{ mb: 2 }}>{collectError}</Alert>}
          {collectResult?.status === 'success' && (
            <Box sx={{ p: 2 }}>
              <Box sx={{ p: 2, bgcolor: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 1, mb: 2 }}>
                <Typography variant="body1" gutterBottom>
                  <strong style={{ color: '#22C55E' }}>Device:</strong>{' '}
                  <span>{collectResult.name}</span>
                </Typography>
                <Typography variant="body1">
                  <strong style={{ color: '#22C55E' }}>IP:</strong>{' '}
                  <span>{collectResult.ip}</span>
                </Typography>
                <Typography variant="body1">
                  <strong style={{ color: '#22C55E' }}>Software Version:</strong>{' '}
                  <span>{collectResult.software_version}</span>
                </Typography>
                <Typography variant="body1">
                  <strong style={{ color: '#22C55E' }}>Serial Number:</strong>{' '}
                  <span>{collectResult.serial_number || 'Unknown'}</span>
                </Typography>
                <Typography variant="body1" sx={{ mt: 1, fontWeight: 500 }}>
                  <strong style={{ color: '#22C55E' }}>Running Config Lines:</strong>{' '}
                  <span style={{ color: '#4ADE80' }}>{collectResult.running_lines}</span>
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
          <Button onClick={() => setOpenCollect(false)}>Close</Button>
          {collectResult?.status === 'success' && (
            <Button variant="contained" onClick={() => { setOpenCollect(false); window.location.href = `/viewer?device=${selectedDevice?.name}` }}>
              View Data
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* 删除确认 */}
      <Dialog open={openConfirm} onClose={() => setOpenConfirm(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <DeleteForever color="error" sx={{ fontSize: 40 }} />
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>Delete Device</Typography>
              <Typography variant="subtitle2" color="text.secondary">Confirm Deletion</Typography>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            Are you sure you want to delete device <strong style={{ color: '#EF4444' }}>{selectedDevice?.name}</strong>? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenConfirm(false)}>Cancel</Button>
          <Button onClick={handleConfirmDelete} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>
    </Container>
  )
}

export default DeviceList
