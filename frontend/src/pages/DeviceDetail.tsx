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
} from '@mui/icons-material'
import { deviceApi, collectorApi } from '../services/api'
import { sessionManager } from '../services/auth'

const DeviceDetail: React.FC = () => {
  const { name } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [device, setDevice] = useState<any>(null)
  const [collecting, setCollecting] = useState(false)
  const [collectResult, setCollectResult] = useState<any>(null)
  const [formData, setFormData] = useState<any>({})
  const [showCollect, setShowCollect] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [collectError, setCollectError] = useState('')

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
    } catch (error: any) {
      console.error('加载设备详情失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (window.confirm(`确定要删除设备 "${name}" 吗？`)) {
      try {
        await deviceApi.delete(name!)
        navigate('/devices')
      } catch (error: any) {
        alert(error.message || '删除失败')
      }
    }
  }

  const handleCollect = async () => {
    const session = sessionManager.getSession()
    if (!session) {
      setCollectError('请先登录或重新登录')
      alert('请先登录')
      window.location.href = '/login'
      return
    }

    setCollecting(true)
    setCollectError('')

    try {
      const data = await collectorApi.collect(name!, username, password)
      setCollectResult(data.result)
      setCollectError('')
      setShowCollect(true)
    } catch (error: any) {
      const errorMsg = error.message || '收集失败'
      setCollectError(errorMsg)
      alert(errorMsg)
    } finally {
      setCollecting(false)
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
    if (type === 'aruba_osswitch') {
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

  if (loading) {
    return (
      <Container>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Loading device information...</Typography>
        </Paper>
      </Container>
    )
  }

  if (!device) {
    return (
      <Container>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>Device Not Found</Typography>
          <Button variant="contained" onClick={() => navigate('/devices')} startIcon={<Refresh />}>
            Back to Device List
          </Button>
        </Paper>
      </Container>
    )
  }

  const colors = getDeviceTheme(device.type)

  const InfoCard = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) => (
    <Card sx={{ p: 2, bgcolor: 'rgba(148,163,184,0.04)', border: '1px solid', borderColor: 'divider', transition: 'border-color 200ms ease', '&:hover': { borderColor: 'text.secondary' } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ width: 36, height: 36, borderRadius: '50%', bgcolor: 'rgba(34,197,94,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
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

      {/* 基本信息 */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
          Device Information
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<NetworkWifi sx={{ color: 'primary.main', fontSize: 18 }} />} label="IP Address" value={formData.ip} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Description sx={{ color: 'primary.main', fontSize: 18 }} />} label="Platform" value={formData.platform || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<LocationOn sx={{ color: 'primary.main', fontSize: 18 }} />} label="Location" value={formData.location || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Storage sx={{ color: 'primary.main', fontSize: 18 }} />} label="Serial Number (SN)" value={formData.serial_number || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Description sx={{ color: 'primary.main', fontSize: 18 }} />} label="Software Version" value={formData.version || 'N/A'} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <InfoCard icon={<Description sx={{ color: 'primary.main', fontSize: 18 }} />} label="Notes" value={formData.notes || 'N/A'} />
          </Grid>
        </Grid>
      </Paper>

      {/* 收集结果 */}
      {collectResult && (
        <Paper sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
              Collection Result
            </Typography>
            <Chip label={collectResult.status === 'success' ? 'Success' : 'Failed'} color={collectResult.status === 'success' ? 'success' : 'error'} sx={{ fontWeight: 600 }} />
          </Box>

          {collectResult.status === 'success' && (
            <Card sx={{ p: 2, bgcolor: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', mb: 2 }}>
              <Typography variant="body1" color="success.main" gutterBottom>
                <CheckCircle sx={{ mr: 1, fontSize: 18, verticalAlign: 'middle' }} />
                Running Config Lines: {collectResult.running_lines}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontSize: '0.75rem' }}>
                Software Version: {collectResult.software_version}
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
            <Box sx={{ p: 2, bgcolor: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 1 }}>
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
