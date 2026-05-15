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
    // 验证 session 是否有效
    const session = sessionManager.getSession()
    if (!session) {
      setCollectError('请先登录或重新登录')
      alert('请先登录')
      window.location.href = '/login'
      return
    }

    console.log('[调试] 设备收集 - 用户名:', username)
    console.log('[调试] 设备收集 - 密码长度:', password ? password.length : 0)
    console.log('[调试] 设备收集 - session 用户名:', session.username)
    console.log('[调试] 设备收集 - session 密码长度:', session.password ? session.password.length : 0)
    console.log('[调试] 设备收集 - 设备名:', name)
    console.log('[调试] 设备收集 - device.formData:', formData)

    setCollecting(true)
    setCollectError('')

    try {
      console.log('[调试] 发送收集请求...')
      const data = await collectorApi.collect(name!, username, password)
      console.log('[调试] 收集响应:', data)
      setCollectResult(data.result)
      setCollectError('')
      setShowCollect(true)
    } catch (error: any) {
      console.error('[调试] 收集错误:', error)
      const errorMsg = error.message || '收集失败'
      setCollectError(errorMsg)
      alert(errorMsg)
    } finally {
      setCollecting(false)
    }
  }

  // 获取设备颜色主题
  const getDeviceTheme = (type: string) => {
    if (type === 'cisco_ios') {
      return {
        primary: '#3b82f6',
        secondary: '#60a5fa',
        bg: 'rgba(59, 130, 246, 0.1)',
        border: 'rgba(59, 130, 246, 0.3)',
      }
    }
    if (type === 'aruba_osswitch') {
      return {
        primary: '#06b6d4',
        secondary: '#22d3ee',
        bg: 'rgba(6, 182, 212, 0.1)',
        border: 'rgba(6, 182, 212, 0.3)',
      }
    }
    return {
      primary: '#94a3b8',
      secondary: '#9ca3af',
      bg: 'rgba(148, 163, 184, 0.1)',
      border: 'rgba(148, 163, 184, 0.2)',
    }
  }

  if (loading) {
    return (
      <Container>
        <Paper sx={{ p: 4, textAlign: 'center', bgcolor: '#0d121f', border: '1px solid rgba(52, 211, 153, 0.1)' }}>
          <CircularProgress sx={{ color: '#34d399' }} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Loading device information...</Typography>
        </Paper>
      </Container>
    )
  }

  if (!device) {
    return (
      <Container>
        <Paper sx={{ p: 4, textAlign: 'center', bgcolor: '#0d121f', border: '1px solid rgba(52, 211, 153, 0.1)' }}>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>Device Not Found</Typography>
          <Button variant="contained" sx={{ mt: 2, textTransform: 'none' }} onClick={() => navigate('/devices')}>
            <Refresh sx={{ mr: 1 }} />
            Back to Device List
          </Button>
        </Paper>
      </Container>
    )
  }

  const colors = getDeviceTheme(device.type)

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 顶部标题栏 */}
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
        {/* 装饰性背景 */}
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '100%',
            opacity: 0.03,
            backgroundImage: `linear-gradient(90deg, transparent 50%, rgba(52, 211, 153, 0.3) 50%)`,
            backgroundSize: '300% 100%',
          }}
        />

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 1 }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              <Avatar
                sx={{
                  bgcolor: colors.bg,
                  color: colors.primary,
                  width: 56,
                  height: 56,
                  border: `1px solid ${colors.primary}`,
                }}
              >
                <Storage sx={{ fontSize: 32 }} />
              </Avatar>
              <Box>
                <Typography variant="h4" sx={{ color: '#fff', fontWeight: 700 }}>
                  {device.name}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                  <Chip
                    label={device.type}
                    sx={{
                      bgcolor: colors.bg,
                      color: colors.primary,
                      border: `1px solid ${colors.primary}`,
                      fontWeight: 500,
                      fontSize: '0.75rem',
                    }}
                  />
                  {device.location && (
                    <Chip
                      label={device.location}
                      sx={{
                        bgcolor: 'rgba(148, 163, 184, 0.1)',
                        color: '#94a3b8',
                        border: '1px solid rgba(148, 163, 184, 0.2)',
                        fontWeight: 500,
                        fontSize: '0.75rem',
                      }}
                    />
                  )}
                </Box>
              </Box>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Edit Device">
              <IconButton onClick={() => setFormData(device)} size="large" sx={{ color: '#34d399' }}>
                <Edit />
              </IconButton>
            </Tooltip>
            <Tooltip title="Collect Configuration">
              <IconButton onClick={handleCollect} disabled={collecting} size="large" sx={{ color: '#34d399' }}>
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

      {/* 基本信息卡片 */}
      <Paper
        sx={{
          p: 2,
          bgcolor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.1)',
          mb: 3,
          borderRadius: 2,
        }}
      >
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' }}>
          Device Information
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: 2,
                transition: 'all 300ms ease',
                '&:hover': {
                  borderColor: '#94a3b8',
                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    bgcolor: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <NetworkWifi sx={{ color: '#34d399', fontSize: 20 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    IP Address
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {formData.ip}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: 2,
                transition: 'all 300ms ease',
                '&:hover': {
                  borderColor: '#94a3b8',
                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    bgcolor: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Description sx={{ color: '#34d399', fontSize: 20 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Platform
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {formData.platform || 'N/A'}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: 2,
                transition: 'all 300ms ease',
                '&:hover': {
                  borderColor: '#94a3b8',
                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    bgcolor: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <LocationOn sx={{ color: '#34d399', fontSize: 20 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Location
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {formData.location || 'N/A'}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: 2,
                transition: 'all 300ms ease',
                '&:hover': {
                  borderColor: '#94a3b8',
                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    bgcolor: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Storage sx={{ color: '#34d399', fontSize: 20 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Serial Number (SN)
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {formData.serial_number || 'N/A'}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: 2,
                transition: 'all 300ms ease',
                '&:hover': {
                  borderColor: '#94a3b8',
                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    bgcolor: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Description sx={{ color: '#34d399', fontSize: 20 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Software Version
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {formData.version || 'N/A'}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: 2,
                transition: 'all 300ms ease',
                '&:hover': {
                  borderColor: '#94a3b8',
                  bgcolor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    bgcolor: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Description sx={{ color: '#34d399', fontSize: 20 }} />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Notes
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {formData.notes || 'N/A'}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </Grid>
        </Grid>
      </Paper>

      {/* 收集结果 */}
      {collectResult && (
        <Paper
          sx={{
            p: 2,
            bgcolor: '#0d121f',
            border: '1px solid rgba(52, 211, 153, 0.1)',
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
              Collection Result
            </Typography>
            <Chip
              label={collectResult.status === 'success' ? 'Success' : 'Failed'}
              color={collectResult.status === 'success' ? 'success' : 'error'}
              sx={{ fontWeight: 600 }}
            />
          </Box>

          {collectResult.status === 'success' && (
            <Card
              sx={{
                p: 2,
                bgcolor: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: 2,
                mb: 2,
              }}
            >
              <Typography variant="body1" color="#10b981" gutterBottom>
                <CheckCircle sx={{ mr: 1, fontSize: 18, verticalAlign: 'middle' }} />
                Running Config Lines: {collectResult.running_lines}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontSize: '0.75rem' }}>
                Software Version: {collectResult.software_version}
              </Typography>
            </Card>
          )}

          {collectError && (
            <Alert severity="error" sx={{ mt: 2, bgcolor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              {collectError}
            </Alert>
          )}
        </Paper>
      )}

      {/* 收集结果弹窗 */}
      {showCollect && collectResult?.status === 'success' && (
        <Dialog
          open={showCollect}
          onClose={() => setShowCollect(false)}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <CheckCircle sx={{ fontSize: 40, color: '#10b981', filter: 'drop-shadow(0 0 12px rgba(16, 185, 129, 0.6))' }} />
              <Box>
                <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600 }}>
                  Configuration Collection
                </Typography>
                <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Success
                </Typography>
              </Box>
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            <Box
              sx={{
                p: 2,
                bgcolor: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: 2,
              }}
            >
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Device Name
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {collectResult.name}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    IP Address
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {collectResult.ip}
                  </Typography>
                </Box>
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Software Version
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {collectResult.software_version}
                  </Typography>
                </Box>
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    Serial Number
                  </Typography>
                  <Typography variant="body1" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                    {collectResult.serial_number || 'Unknown'}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button
              onClick={() => setShowCollect(false)}
              sx={{ fontWeight: 600, letterSpacing: '0.025em', textTransform: 'uppercase' }}
            >
              Close
            </Button>
            <Button
              variant="contained"
              onClick={() => {
                setShowCollect(false)
                navigate('/viewer')
              }}
              sx={{
                fontWeight: 700,
                letterSpacing: '0.025em',
                textTransform: 'uppercase',
                bgcolor: '#2563eb',
                '&:hover': {
                  bgcolor: '#3b82f6',
                  boxShadow: '0 0 20px rgba(37, 99, 235, 0.4)',
                },
              }}
            >
              View Data
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Container>
  )
}

export default DeviceDetail
