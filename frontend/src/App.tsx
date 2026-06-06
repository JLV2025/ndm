import { useState } from 'react'
import { Routes, Route, Navigate, useLocation, Link, Outlet } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import {
  Box,
  CssBaseline,
  Drawer,
  Toolbar,
  Typography,
  Divider,
  Avatar,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Button,
} from '@mui/material'
import {
  AccountCircle as AccountIcon,
  Dashboard as DashboardIcon,
  Storage,
  Terminal,
} from '@mui/icons-material'
import Login from './pages/Login'
import DeviceList from './pages/DeviceList'
import DeviceDetail from './pages/DeviceDetail'
import Dashboard from './pages/Dashboard'
import Viewer from './pages/Viewer'
import MatrixRain from './components/MatrixRain'
import { sessionManager } from './services/auth'
import { useI18n } from './i18n'

const DRAWER_WIDTH = 260

function Layout() {
  const { t, lang, setLang } = useI18n()
  const [mobileOpen, setMobileOpen] = useState(false)
  const user = sessionManager.getSession()
  const location = useLocation()
  const currentPath = location.pathname

  const navItems = [
    { label: t('nav.dashboard'), icon: <DashboardIcon />, path: '/' },
    { label: t('nav.devices'), icon: <Storage />, path: '/devices' },
    { label: t('nav.viewer'), icon: <Terminal />, path: '/viewer' },
  ]

  const handleDrawerToggle = () => setMobileOpen(!mobileOpen)

  const handleLogout = () => {
    sessionManager.logout()
  }

  const toggleLang = () => setLang(lang === 'zh' ? 'en' : 'zh')

  const drawerContent = (
    <Box sx={{ position: 'relative', overflow: 'hidden', height: '100%' }}>
      <MatrixRain />
      <Box sx={{ position: 'relative', zIndex: 1, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Toolbar sx={{ px: 2, minHeight: '64px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              bgcolor: 'rgba(45, 212, 110, 0.12)',
              border: '1px solid',
              borderColor: 'rgba(45, 212, 110, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Storage sx={{ color: 'primary.main', fontSize: 20 }} />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ color: 'text.primary', fontWeight: 700, fontSize: '0.8rem', lineHeight: 1.2 }}>
              NDM
            </Typography>
            <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.65rem', letterSpacing: '0.05em' }}>
              网络设备管理
            </Typography>
          </Box>
        </Box>
      </Toolbar>

      <Divider />

      <List sx={{ px: 1, pt: 2, flex: 1 }}>
        {navItems.map((item) => {
          const isActive = currentPath === item.path || (item.path !== '/' && currentPath.startsWith(item.path))
          return (
            <ListItem key={item.path} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                component={Link}
                to={item.path}
                sx={{
                  borderRadius: 1.5,
                  py: 1.3,
                  px: 2,
                  bgcolor: isActive ? 'rgba(45, 212, 110, 0.08)' : 'transparent',
                  border: '1px solid',
                  borderColor: isActive ? 'rgba(45, 212, 110, 0.2)' : 'transparent',
                  transition: 'all 150ms ease',
                  '&:hover': {
                    bgcolor: 'rgba(45, 212, 110, 0.06)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: isActive ? 'primary.main' : 'text.disabled', minWidth: 40 }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    sx: {
                      color: isActive ? 'text.primary' : 'text.secondary',
                      fontWeight: isActive ? 600 : 400,
                      fontSize: '0.8rem',
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
          )
        })}
      </List>

      <Box sx={{ p: 2 }}>
        {/* 语言切换 */}
        <Button
          onClick={toggleLang}
          size="small"
          sx={{
            mb: 1.5,
            width: '100%',
            borderRadius: 1.5,
            border: '1px solid',
            borderColor: 'divider',
            color: 'text.secondary',
            fontSize: '0.7rem',
            fontWeight: 600,
            letterSpacing: '0.03em',
            textTransform: 'none',
            '&:hover': {
              borderColor: 'primary.main',
              color: 'primary.main',
              bgcolor: 'rgba(45, 212, 110, 0.04)',
            },
          }}
        >
          {t('lang.switch')}
        </Button>

        <Divider sx={{ mb: 2 }} />
        <Box
          sx={{
            p: 1.5,
            bgcolor: 'rgba(45, 212, 110, 0.04)',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1.5,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <Avatar
            sx={{
              width: 32,
              height: 32,
              fontSize: '0.75rem',
              fontWeight: 600,
              bgcolor: 'primary.main',
            }}
          >
            {user?.username?.charAt(0).toUpperCase() || <AccountIcon />}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 600, fontSize: '0.75rem', display: 'block' }}>
              {user?.username || 'User'}
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', fontSize: '0.65rem', cursor: 'pointer', '&:hover': { color: 'error.main' } }}
              onClick={handleLogout}
            >
              {t('login.logout')}
            </Typography>
          </Box>
        </Box>
      </Box>
      </Box>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', bgcolor: 'background.default', minHeight: '100vh' }}>
      <Box
        component="nav"
        sx={{ width: { sm: DRAWER_WIDTH }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              overflow: 'hidden',
            },
          }}
        >
          {drawerContent}
        </Drawer>

        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              overflow: 'hidden',
            },
          }}
          open
        >
          {drawerContent}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          bgcolor: 'background.default',
          minHeight: '100vh',
        }}
      >
        <Outlet />
      </Box>

    </Box>
  )
}

const App: React.FC = () => {
  const [user, setUser] = useState(sessionManager.getSession())

  const refreshSession = () => {
    setUser(sessionManager.getSession())
  }

  return (
    <>
      <CssBaseline />
      <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login onLogin={refreshSession} />} />
        <Route element={user ? <Layout /> : <Navigate to="/login" replace />}>
          <Route index element={<Dashboard />} />
          <Route path="devices" element={<DeviceList />} />
          <Route path="devices/:name" element={<DeviceDetail />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="viewer" element={<Viewer />} />
        </Route>
      </Routes>
      </ErrorBoundary>
    </>
  )
}

export default App
