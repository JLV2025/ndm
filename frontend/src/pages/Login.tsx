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
import { Lock, Key, Shield, Terminal, Visibility, VisibilityOff } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import { sessionManager } from '../services/auth'
import { useI18n } from '../i18n'

const Login = ({ onLogin }: { onLogin?: () => void }) => {
  const { t } = useI18n()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    fetch('/health', { signal: controller.signal })
      .then((r) => setBackendOnline(r.ok))
      .catch(() => setBackendOnline(false))
      .finally(() => clearTimeout(timeout))
    return () => {
      clearTimeout(timeout)
      controller.abort()
    }
  }, [])

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError(t('login.usernameRequired') + ' / ' + t('login.passwordRequired'))
      return
    }
    setLoading(true)
    setError(null)
    try {
      sessionManager.setCredentials(username, password)
      onLogin?.()
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('login.failed'))
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
              bgcolor: 'rgba(45, 212, 110, 0.1)',
              border: '1px solid',
              borderColor: 'rgba(45, 212, 110, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Shield sx={{ fontSize: 36, color: 'primary.main' }} />
          </Box>

          <Typography variant="h4" component="h1" gutterBottom sx={{ fontWeight: 700, color: 'primary.main', letterSpacing: '0.05em' }}>
            NDM
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
            Network Device Management
          </Typography>
          <Typography
            variant="subtitle2"
            sx={{
              display: 'inline-block',
              mt: 1,
              px: 2,
              py: 0.5,
              bgcolor: 'rgba(45, 212, 110, 0.08)',
              borderRadius: 1,
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: 'primary.main',
            }}
          >
            {t('app.subtitle')}
          </Typography>
        </Box>

        {/* 状态指示器 */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {backendOnline === null ? (
              <CircularProgress size={10} sx={{ color: 'warning.main' }} />
            ) : (
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  bgcolor: backendOnline ? 'success.main' : 'error.main',
                }}
              />
            )}
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
              {backendOnline === null
                ? t('app.checking')
                : backendOnline
                ? t('app.systemOnline')
                : t('app.backendOffline')}
            </Typography>
          </Box>
        </Box>

        {/* 错误提示 */}
        {error && (
          <Fade in={true}>
            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>{t('login.failed')}</AlertTitle>
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
            label={t('login.username')}
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
            label={t('login.password')}
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
                    {showPassword ? <VisibilityOff sx={{ fontSize: 18 }} /> : <Visibility sx={{ fontSize: 18 }} />}
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
                <Typography variant="body2" color="inherit">{t('login.loggingIn')}</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Terminal sx={{ fontSize: 18 }} />
                <span>{t('login.login')}</span>
              </Box>
            )}
          </Button>
        </Box>

        {/* 底部信息 */}
        <Box sx={{ mt: 2, textAlign: 'center' }}>
          <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.68rem' }}>
            v2.0.0 · Secure SSH · Encrypted Transmission
          </Typography>
        </Box>
      </Paper>
    </Box>
  )
}

export default Login
