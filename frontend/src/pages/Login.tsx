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

const Login = ({ onLogin }: { onLogin?: () => void }) => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError('请输入账号和密码')
      return
    }
    setLoading(true)
    setError(null)
    try {
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
        bgcolor: 'background.default',
      }}
    >
      <Paper
        sx={{
          position: 'relative',
          zIndex: 1,
          p: { xs: 4, md: 5 },
          width: { xs: '90%', md: 440 },
          bgcolor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        {/* Logo */}
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Box
            sx={{
              width: 64,
              height: 64,
              mx: 'auto',
              mb: 2,
              borderRadius: '50%',
              bgcolor: 'rgba(34, 197, 94, 0.1)',
              border: '1px solid',
              borderColor: 'rgba(34, 197, 94, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Shield sx={{ fontSize: 36, color: 'primary.main' }} />
          </Box>

          <Typography variant="h4" component="h1" gutterBottom sx={{ fontWeight: 700 }}>
            <span style={{ color: '#22C55E' }}>Network</span>
            <span style={{ color: '#F8FAFC' }}>Engineer</span>
            <span style={{ color: '#4ADE80' }}>Pro</span>
          </Typography>
          <Typography
            variant="subtitle2"
            sx={{
              display: 'inline-block',
              mt: 1,
              px: 2,
              py: 0.5,
              bgcolor: 'rgba(34, 197, 94, 0.08)',
              borderRadius: 1,
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: 'primary.main',
            }}
          >
            Cisco & Aruba Configuration Management
          </Typography>
        </Box>

        {/* 状态指示器 */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                bgcolor: 'success.main',
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
            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>Authentication Failed</AlertTitle>
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
            InputProps={{
              startAdornment: (
                <Lock sx={{ mr: 1, color: 'text.disabled', fontSize: 20 }} />
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
            InputProps={{
              startAdornment: (
                <Key sx={{ mr: 1, color: 'text.disabled', fontSize: 20 }} />
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword(!showPassword)}
                    sx={{ p: 0, color: 'text.disabled' }}
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
              fontSize: '0.9rem',
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
            }}
            disabled={loading}
          >
            {loading ? (
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <CircularProgress size={20} sx={{ mr: 1, color: 'primary.contrastText' }} />
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
            bgcolor: 'rgba(34, 197, 94, 0.04)',
            borderRadius: 1.5,
            border: '1px solid',
            borderColor: 'divider',
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
            <NetworkWifi sx={{ fontSize: 16, color: 'text.disabled' }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
              v2.0.0 | Secure SSH Access | Encrypted Transmission
            </Typography>
            <Memory sx={{ fontSize: 16, color: 'text.disabled' }} />
          </Box>
        </Box>
      </Paper>
    </Box>
  )
}

export default Login
