import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  Chip,
  Grid,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Card,
  Avatar,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material'
import {
  Delete,
  Edit,
  Refresh,
  CloudUpload,
  CheckCircle,
  Storage,
  NetworkWifi,
  Description,
  LocationOn,
  ViewModule,
  TableChart,
  Info,
} from '@mui/icons-material'
import { deviceApi, collectorApi } from '../services/api'
import { sessionManager } from '../services/auth'
import FrontPanel from '../components/devices/FrontPanel'
import type { Device, CollectResult, FrontPanelData, PortInfo } from '../types'
import { useI18n } from '../i18n'

const DeviceDetail: React.FC = () => {
  const { t } = useI18n()
  const { name } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [device, setDevice] = useState<Device | null>(null)
  const [collecting, setCollecting] = useState(false)
  const [collectResult, setCollectResult] = useState<CollectResult | null>(null)
  const [formData, setFormData] = useState<Partial<Device>>({})
  const [showCollect, setShowCollect] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [collectError, setCollectError] = useState('')
  const [tabIndex, setTabIndex] = useState(0)
  const [frontPanelData, setFrontPanelData] = useState<FrontPanelData | null>(null)
  const [frontPanelLoading, setFrontPanelLoading] = useState(false)
  const [portSearch, setPortSearch] = useState('')
  const [portSortField, setPortSortField] = useState<string>('name')
  const [portSortDir, setPortSortDir] = useState<'asc' | 'desc'>('asc')

  useEffect(() => {
    loadDevice()
  }, [name])

  useEffect(() => {
    const session = sessionManager.getSession()
    if (!session) {
      navigate('/login')
    } else {
      setUsername(session.username)
      setPassword(session.password)
    }
  }, [navigate])

  const loadDevice = async () => {
    if (!name) return
    try {
      const response = await deviceApi.get(name)
      setDevice(response.data)
      setFormData(response.data)
    } catch (error: unknown) {
      console.error('加载设备详情失败:', error instanceof Error ? error.message : error)
    } finally {
      setLoading(false)
    }
  }

  const loadFrontPanel = async () => {
    if (!name) return
    setFrontPanelLoading(true)
    try {
      const response = await fetch(`/api/data/${encodeURIComponent(name)}/ports/latest`)
      if (response.ok) {
        setFrontPanelData(await response.json())
      }
    } catch (error: unknown) {
      console.error('加载前面板数据失败:', error)
    } finally {
      setFrontPanelLoading(false)
    }
  }

  const handleDelete = async () => {
    if (window.confirm(`确定要删除设备 "${name}" 吗？`)) {
      try {
        await deviceApi.delete(name!)
        navigate('/devices')
      } catch (error: unknown) {
        alert(error instanceof Error ? error.message : t('common.deleteFailed'))
      }
    }
  }

  const handleCollect = async () => {
    const session = sessionManager.getSession()
    if (!session) {
      setCollectError(t('common.reLoginRequired'))
      alert(t('common.pleaseLogin'))
      navigate('/login')
      return
    }

    setCollecting(true)
    setCollectError('')

    try {
      const data = await collectorApi.collect(name!, username, password)
      setCollectResult(data.result)
      setCollectError('')
      setShowCollect(true)
    } catch (error: unknown) {
      const errorMsg = error instanceof Error ? error.message : t('common.collectFailed')
      setCollectError(errorMsg)
      alert(errorMsg)
    } finally {
      setCollecting(false)
    }
  }

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTabIndex(newValue)
    if (newValue === 1 && !frontPanelData) {
      loadFrontPanel()
    }
  }

  const getDeviceTheme = (type: string) => {
    if (type === 'cisco_ios') {
      return {
        primary: '#3B82F6',
        bg: 'rgba(59, 130, 246, 0.1)',
        border: 'rgba(59, 130, 246, 0.25)',
      }
    }
    if (type === 'aruba_aoscx') {
      return {
        primary: '#06B6D4',
        bg: 'rgba(6, 182, 212, 0.1)',
        border: 'rgba(6, 182, 212, 0.25)',
      }
    }
    return {
      primary: '#94A3B8',
      bg: 'rgba(148, 163, 184, 0.08)',
      border: 'rgba(148, 163, 184, 0.15)',
    }
  }

  const getPortSortValue = (port: PortInfo, field: string): string | number => {
    switch (field) {
      case 'name': return port.name
      case 'status': return port.status
      case 'speed': return parseInt(port.speed || '0')
      case 'rx_mbps': return port.rx_mbps || 0
      case 'tx_mbps': return port.tx_mbps || 0
      case 'total_mbps': return (port.rx_mbps || 0) + (port.tx_mbps || 0)
      default: return ''
    }
  }

  if (loading) {
    return (
      <Container>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>{t('detail.loading')}</Typography>
        </Paper>
      </Container>
    )
  }

  if (!device) {
    return (
      <Container>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>{t('detail.notFound')}</Typography>
          <Button variant="contained" onClick={() => navigate('/devices')} startIcon={<Refresh />}>
            {t('detail.backToList')}
          </Button>
        </Paper>
      </Container>
    )
  }

  const colors = getDeviceTheme(device.type)

  const InfoCard = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) => (
    <Card sx={{ p: 2, bgcolor: 'rgba(148,163,184,0.04)', border: '1px solid', borderColor: 'divider', transition: 'border-color 200ms ease', '&:hover': { borderColor: 'text.secondary' } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ width: 36, height: 36, borderRadius: '50%', bgcolor: 'rgba(45,212,110,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {icon}
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
            {label}
          </Typography>
          <Typography variant="body1" sx={{ color: 'text.primary', fontWeight: 500 }}>
            {value}
          </Typography>
        </Box>
      </Box>
    </Card>
  )

  const overviewTab = (
    <Box>
      {/* 基本信息 */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
          {t('detail.deviceInfo')}
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<NetworkWifi sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.ipAddress')} value={formData.ip || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Description sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.platform')} value={formData.platform || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<LocationOn sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.location')} value={formData.location || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Storage sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.serialNumber')} value={formData.serial_number || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Description sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.softwareVersion')} value={formData.version || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Description sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.notes')} value={formData.notes || 'N/A'} />
          </Grid>
          {device.uplink_ports && device.uplink_ports.length > 0 && (
            <Grid item xs={12}>
              <InfoCard icon={<NetworkWifi sx={{ color: 'primary.main', fontSize: 18 }} />} label={t('detail.uplinkPorts')} value={device.uplink_ports.join(', ')} />
            </Grid>
          )}
        </Grid>
      </Paper>

      {/* 收集结果 */}
      {collectResult && (
        <Paper sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
              {t('detail.collectionResult')}
            </Typography>
            <Chip label={collectResult.status === 'success' ? t('detail.success') : t('detail.failed')} color={collectResult.status === 'success' ? 'success' : 'error'} sx={{ fontWeight: 600 }} />
          </Box>

          {collectResult.status === 'success' && (
            <Card sx={{ p: 2, bgcolor: 'rgba(45,212,110,0.06)', border: '1px solid rgba(45,212,110,0.2)', mb: 2 }}>
              <Typography variant="body1" color="success.main" gutterBottom>
                <CheckCircle sx={{ mr: 1, fontSize: 18, verticalAlign: 'middle' }} />
                {t('detail.runningLines')}: {collectResult.running_lines}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontSize: '0.75rem' }}>
                {t('detail.softwareVersion')}: {collectResult.software_version}
              </Typography>
            </Card>
          )}

          {collectError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {collectError}
            </Alert>
          )}
        </Paper>
      )}
    </Box>
  )

  const frontPanelTab = (
    <Box>
      {frontPanelLoading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress size={24} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{t('detail.loadPortDataHint')}</Typography>
        </Paper>
      ) : frontPanelData ? (
        <Box>
          {/* 汇总卡片 */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={6} sm={3}>
              <Card sx={{ p: 2, textAlign: 'center', bgcolor: 'rgba(59,130,246,0.06)' }}>
                <Typography variant="h5" sx={{ fontWeight: 700, color: '#3B82F6' }}>{frontPanelData.total_ports}</Typography>
                <Typography variant="caption" color="text.secondary">{t('detail.totalPorts')}</Typography>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card sx={{ p: 2, textAlign: 'center', bgcolor: 'rgba(45,212,110,0.06)' }}>
                <Typography variant="h5" sx={{ fontWeight: 700, color: '#2DD46E' }}>{frontPanelData.up_ports}</Typography>
                <Typography variant="caption" color="text.secondary">{t('detail.up')}</Typography>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card sx={{ p: 2, textAlign: 'center', bgcolor: 'rgba(148,163,184,0.06)' }}>
                <Typography variant="h5" sx={{ fontWeight: 700, color: '#94A3B8' }}>{frontPanelData.down_ports}</Typography>
                <Typography variant="caption" color="text.secondary">{t('detail.down')}</Typography>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card sx={{ p: 2, textAlign: 'center', bgcolor: 'rgba(239,68,68,0.06)' }}>
                <Typography variant="h5" sx={{ fontWeight: 700, color: frontPanelData.error_ports > 0 ? '#EF4444' : '#2DD46E' }}>{frontPanelData.error_ports}</Typography>
                <Typography variant="caption" color="text.secondary">{t('detail.error')}</Typography>
              </Card>
            </Grid>
          </Grid>
          <FrontPanel ports={frontPanelData.ports} deviceName={device.name} deviceType={device.type} devicePlatform={device.platform} />
        </Box>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">{t('detail.noPortData')}</Typography>
        </Paper>
      )}
    </Box>
  )

  const sortedPorts = frontPanelData ? [...frontPanelData.ports].sort((a, b) => {
    const va = getPortSortValue(a, portSortField)
    const vb = getPortSortValue(b, portSortField)
    if (typeof va === 'number' && typeof vb === 'number') {
      return portSortDir === 'asc' ? va - vb : vb - va
    }
    return portSortDir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va))
  }) : []

  const filteredPorts = portSearch
    ? sortedPorts.filter((p) => p.name.toLowerCase().includes(portSearch.toLowerCase()) || (p.description || '').toLowerCase().includes(portSearch.toLowerCase()))
    : sortedPorts

  const handlePortSort = (field: string) => {
    if (portSortField === field) {
      setPortSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setPortSortField(field)
      setPortSortDir('asc')
    }
  }

  const portSortStyle = (field: string) => ({
    cursor: 'pointer',
    userSelect: 'none',
    '&:hover': { color: 'primary.main' },
    color: portSortField === field ? 'primary.main' : 'text.secondary',
  } as const)

  const portListTab = (
    <Box>
      {frontPanelLoading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress size={24} />
        </Paper>
      ) : frontPanelData ? (
        <Paper sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t('detail.portCount').replace('{count}', String(frontPanelData.ports.length))}
            </Typography>
            <TextField
              size="small"
              placeholder={t('detail.searchPort')}
              value={portSearch}
              onChange={(e) => setPortSearch(e.target.value)}
              sx={{ width: 250, '& .MuiInputBase-root': { fontSize: '0.75rem' } }}
            />
          </Box>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell onClick={() => handlePortSort('name')} sx={portSortStyle('name')}>
                    {t('detail.portName')} {portSortField === 'name' ? (portSortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell onClick={() => handlePortSort('status')} sx={portSortStyle('status')}>
                    {t('detail.portStatus')} {portSortField === 'status' ? (portSortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell>{t('detail.portMode')}</TableCell>
                  <TableCell>{t('detail.portSpeed')}</TableCell>
                  <TableCell>{t('detail.portDesc')}</TableCell>
                  <TableCell onClick={() => handlePortSort('rx_mbps')} sx={portSortStyle('rx_mbps')}>
                    {t('detail.portRx')} {portSortField === 'rx_mbps' ? (portSortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell onClick={() => handlePortSort('tx_mbps')} sx={portSortStyle('tx_mbps')}>
                    {t('detail.portTx')} {portSortField === 'tx_mbps' ? (portSortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell>{t('detail.portUplink')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredPorts.map((port) => (
                  <TableRow key={port.name} hover>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem', fontWeight: 500 }}>
                      {port.name}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={port.status}
                        size="small"
                        sx={{
                          bgcolor: port.status_up ? 'rgba(45,212,110,0.12)' : 'rgba(148,163,184,0.08)',
                          color: port.status_up ? 'success.main' : 'text.secondary',
                          height: 20,
                          fontSize: '0.65rem',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{port.mode || '-'}</TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{port.speed || '-'}</TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {port.description || '-'}
                    </TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.7rem' }}>
                      {port.rx_mbps !== undefined ? port.rx_mbps.toFixed(2) : '-'}
                    </TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.7rem' }}>
                      {port.tx_mbps !== undefined ? port.tx_mbps.toFixed(2) : '-'}
                    </TableCell>
                    <TableCell>
                      {port.is_uplink ? <Chip label="Uplink" size="small" sx={{ bgcolor: 'rgba(245,158,11,0.12)', color: 'warning.main', height: 20, fontSize: '0.65rem' }} /> : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">{t('detail.loadPortData')}</Typography>
        </Paper>
      )}
    </Box>
  )

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              <Avatar sx={{ bgcolor: colors.bg, color: colors.primary, width: 48, height: 48, border: '1px solid', borderColor: colors.border }}>
                <Storage sx={{ fontSize: 28 }} />
              </Avatar>
              <Box>
                <Typography variant="h4" sx={{ fontWeight: 700 }}>{device.name}</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                  <Chip label={device.type} sx={{ bgcolor: colors.bg, color: colors.primary, border: '1px solid', borderColor: colors.border, fontWeight: 500, fontSize: '0.75rem' }} />
                  {device.location && (
                    <Chip label={device.location} sx={{ bgcolor: 'rgba(148,163,184,0.08)', color: 'text.secondary', border: '1px solid', borderColor: 'divider', fontWeight: 500, fontSize: '0.75rem' }} />
                  )}
                </Box>
                {device.last_synced && (
                  <Typography variant="caption" color="warning.main" sx={{ mt: 0.5, fontWeight: 500 }}>
                    {t('detail.dataBasedOn').replace('{date}', device.last_synced)}
                  </Typography>
                )}
              </Box>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Edit Device">
              <IconButton onClick={() => setFormData(device)} size="large" color="primary">
                <Edit />
              </IconButton>
            </Tooltip>
            <Tooltip title="Collect Configuration">
              <IconButton onClick={handleCollect} disabled={collecting} size="large" sx={{ color: 'primary.main' }}>
                <CloudUpload />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete Device">
              <IconButton onClick={handleDelete} size="large" color="error">
                <Delete />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabIndex} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider', px: 1 }}>
          <Tab icon={<Info />} iconPosition="start" label={t('detail.tabOverview')} />
          <Tab icon={<ViewModule />} iconPosition="start" label={t('detail.tabFrontPanel')} />
          <Tab icon={<TableChart />} iconPosition="start" label={t('detail.tabPortList')} />
        </Tabs>
      </Paper>

      {tabIndex === 0 && overviewTab}
      {tabIndex === 1 && frontPanelTab}
      {tabIndex === 2 && portListTab}

      {/* 收集结果弹窗 */}
      {showCollect && collectResult?.status === 'success' && (
        <Dialog open={showCollect} onClose={() => setShowCollect(false)} maxWidth="md" fullWidth>
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <CheckCircle color="success" sx={{ fontSize: 40 }} />
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Configuration Collection</Typography>
                <Typography variant="subtitle2" color="text.secondary">Success</Typography>
              </Box>
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            <Box sx={{ p: 2, bgcolor: 'rgba(45,212,110,0.06)', border: '1px solid rgba(45,212,110,0.2)', borderRadius: 1 }}>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Device Name</Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>{collectResult.name}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>IP Address</Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>{collectResult.ip}</Typography>
                </Box>
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Software Version</Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>{collectResult.software_version}</Typography>
                </Box>
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>Serial Number</Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>{collectResult.serial_number || 'Unknown'}</Typography>
                </Box>
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowCollect(false)}>Close</Button>
            <Button variant="contained" onClick={() => { setShowCollect(false); navigate('/viewer') }}>
              View Data
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Container>
  )
}

export default DeviceDetail
