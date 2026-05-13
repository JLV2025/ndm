import { useState, useEffect, type FormEvent } from 'react'
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  Alert,
  AlertTitle,
  CircularProgress,
  InputAdornment,
  IconButton,
  Fade,
} from '@mui/material'
import { Lock, Key, Shield, Terminal, Memory, NetworkWifi } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import { sessionManager } from '../services/auth'

// 网络工程师风格 - 深色科技主题
const Login = ({ onLogin }: { onLogin?: () => void }) => {
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setPosition({
        x: (e.clientX / window.innerWidth) * 20,
        y: (e.clientY / window.innerHeight) * 20,
      })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError('请输入账号和密码')
      return
    }
    setLoading(true)
    setError(null)
    try {
      // 本地保存凭据，供后续 SSH 连接交换机使用，无需服务器校验
      sessionManager.setCredentials(username, password)
      onLogin?.()
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存凭据失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#0a0f1a',
        position: 'relative',
        // 网格图案
        '&::before': {
          content: '""',
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundImage: `
            linear-gradient(rgba(37, 99, 235, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37, 99, 235, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
          transform: `translate(${position.x}px, ${position.y}px)`,
        },
        // 蓝色发光光晕
        '&::after': {
          content: '""',
          position: 'fixed',
          top: '10%',
          left: '10%',
          width: '30%',
          height: '30%',
          borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(37, 99, 235, 0.15), transparent 70%)',
          filter: 'blur(60px)',
        },
      }}
    >
      {/* 装饰性数据流动效果 */}
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'none',
          overflow: 'hidden',
          zIndex: 0,
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            width: '200%',
            height: '200%',
            backgroundImage: `
              repeating-linear-gradient(
                45deg,
                transparent,
                transparent 20px,
                rgba(37, 99, 235, 0.02) 20px,
                rgba(37, 99, 235, 0.02) 40px
              ),
              repeating-linear-gradient(
                -45deg,
                transparent,
                transparent 20px,
                rgba(37, 99, 235, 0.02) 20px,
                rgba(37, 99, 235, 0.02) 40px
              )
            `,
            animation: 'pulse 8s ease-in-out infinite',
          }}
        />
      </Box>

      {/* 登录卡片 */}
      <Paper
        sx={{
          position: 'relative',
          zIndex: 1,
          p: { xs: 4, md: 5 },
          width: { xs: '90%', md: 480 },
          bgcolor: '#0d121f',
          '&::before': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.15), transparent)',
            pointerEvents: 'none',
          },
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 60px rgba(37, 99, 235, 0.2)',
          borderRadius: 3,
          overflow: 'hidden',
          border: '1px solid rgba(37, 99, 235, 0.2)',
        }}
      >
        {/* 顶部发光条 */}
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background: 'linear-gradient(90deg, #2563eb, #60a5fa, #3b82f6, #2563eb)',
            backgroundSize: '200% 100%',
            animation: 'gradient 3s ease infinite',
          }}
        />

        {/* 装饰性边角 */}
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            left: 8,
            right: 8,
            bottom: 8,
            border: '1px solid rgba(37, 99, 235, 0.3)',
            pointerEvents: 'none',
          }}
        />

        {/* Logo 区域 */}
        <Box
          sx={{
            textAlign: 'center',
            mb: 4,
            position: 'relative',
          }}
        >
          {/* 装饰性光环 */}
          <Box
            sx={{
              width: 80,
              height: 80,
              mx: 'auto',
              mb: 2,
              position: 'relative',
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                inset: 0,
                borderRadius: '50%',
                background: 'conic-gradient(from 0deg, #2563eb, #60a5fa, #3b82f6, #06b6d4, #2563eb)',
                animation: 'spin 4s linear infinite',
                opacity: 0.3,
              }}
            />
            <Box
              sx={{
                position: 'absolute',
                inset: 2,
                borderRadius: '50%',
                background: '#0d121f',
              }}
            />
            <Shield
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                fontSize: 56,
                color: '#2563eb',
                filter: 'drop-shadow(0 0 12px rgba(37, 99, 235, 0.6))',
              }}
            />
          </Box>

          <Typography variant="h4" component="h1" gutterBottom>
            <span style={{ color: '#2563eb' }}>Network</span>
            <span style={{ color: '#fff' }}>Engineer</span>
            <span style={{ color: '#06b6d4' }}>Pro</span>
          </Typography>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{
              display: 'inline-block',
              mt: 1,
              px: 2,
              py: 0.5,
              bgcolor: 'rgba(37, 99, 235, 0.15)',
              borderRadius: 1,
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: '#60a5fa',
            }}
          >
            Cisco & Aruba Configuration Management
          </Typography>
        </Box>

        {/* 状态指示器 */}
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: '#10b981',
                boxShadow: '0 0 12px #10b981',
                animation: 'pulse 2s ease-in-out infinite',
              }}
            />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
              SYSTEM ONLINE
            </Typography>
          </Box>
        </Box>

        {/* 错误提示 */}
        {error && (
          <Fade in={true}>
            <Alert severity="error" sx={{ mb: 2, bgcolor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              <AlertTitle sx={{ color: '#ef4444' }}>Authentication Failed</AlertTitle>
              {error}
            </Alert>
          </Fade>
        )}

        {/* 登录表单 */}
        <Box component="form" onSubmit={handleLogin} noValidate sx={{ mt: 1 }}>
          <TextField
            margin="normal"
            required
            fullWidth
            id="username"
            label="管理员账号"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            sx={{
              bgcolor: '#0d121f',
              '& .MuiOutlinedInput-input': { color: '#e2e8f0' },
              '& .MuiOutlinedInput-root': {
                '& fieldset': { borderColor: 'rgba(37, 99, 235, 0.2)' },
                '&:hover fieldset': { borderColor: 'rgba(37, 99, 235, 0.4)' },
                '&.Mui-focused fieldset': {
                  borderColor: '#2563eb',
                  borderWidth: 2,
                  boxShadow: '0 0 0 3px rgba(37, 99, 235, 0.15)',
                },
              },
              '& .MuiInputLabel-root': {
                color: 'rgba(96, 165, 250, 0.5)',
                '&.Mui-focused': { color: '#60a5fa' },
              },
              '& .MuiInputLabel-shrink': { color: '#60a5fa' },
            }}
            InputProps={{
              startAdornment: (
                <Lock sx={{ mr: 1, color: 'rgba(96, 165, 250, 0.5)', fontSize: 20 }} />
              ),
            }}
          />

          <TextField
            margin="normal"
            required
            fullWidth
            name="password"
            label="密码"
            type={showPassword ? 'text' : 'password'}
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{
              bgcolor: '#0d121f',
              '& .MuiOutlinedInput-input': { color: '#e2e8f0' },
              '& .MuiOutlinedInput-root': {
                '& fieldset': { borderColor: 'rgba(37, 99, 235, 0.2)' },
                '&:hover fieldset': { borderColor: 'rgba(37, 99, 235, 0.4)' },
                '&.Mui-focused fieldset': {
                  borderColor: '#2563eb',
                  borderWidth: 2,
                  boxShadow: '0 0 0 3px rgba(37, 99, 235, 0.15)',
                },
              },
              '& .MuiInputLabel-root': {
                color: 'rgba(96, 165, 250, 0.5)',
                '&.Mui-focused': { color: '#60a5fa' },
              },
              '& .MuiInputLabel-shrink': { color: '#60a5fa' },
            }}
            InputProps={{
              startAdornment: (
                <Key sx={{ mr: 1, color: 'rgba(96, 165, 250, 0.5)', fontSize: 20 }} />
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword(!showPassword)}
                    sx={{ p: 0, color: 'rgba(96, 165, 250, 0.5)' }}
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{
              mt: 3,
              mb: 2,
              py: 1.5,
              fontWeight: 700,
              fontSize: '1rem',
              letterSpacing: '0.025em',
              textTransform: 'uppercase',
              bgcolor: '#2563eb',
              color: '#fff',
              '&:hover': {
                bgcolor: '#3b82f6',
                boxShadow: '0 0 24px rgba(37, 99, 235, 0.4)',
              },
              '&:disabled': {
                bgcolor: '#1e40af',
              },
            }}
            disabled={loading}
          >
            {loading ? (
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <CircularProgress size={20} sx={{ mr: 1, color: '#fff' }} />
                <Typography variant="body2" color="inherit">Authenticating...</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Terminal sx={{ fontSize: 18 }} />
                <span>Connect to Network</span>
              </Box>
            )}
          </Button>
        </Box>

        {/* 底部信息 */}
        <Box
          sx={{
            mt: 2,
            p: 2,
            bgcolor: 'rgba(37, 99, 235, 0.05)',
            borderRadius: 2,
            border: '1px solid rgba(37, 99, 235, 0.1)',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <NetworkWifi sx={{ fontSize: 16, color: 'rgba(37, 99, 235, 0.6)' }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
              v2.0.0 | Secure SSH Access | Encrypted Transmission
            </Typography>
            <Memory sx={{ fontSize: 16, color: 'rgba(37, 99, 235, 0.6)' }} />
          </Box>
        </Box>

        {/* 底部装饰线 */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 2,
            background: 'linear-gradient(90deg, transparent, rgba(37, 99, 235, 0.3), transparent)',
          }}
        />
      </Paper>
    </Box>
  )
}

export default Login
