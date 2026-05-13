import { useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import {
  Box,
  CssBaseline,
  Drawer,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Divider,
  Badge,
  Menu,
  MenuItem,
  Avatar,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
} from '@mui/material'
import {
  Menu as MenuIcon,
  Notifications as NotificationsIcon,
  AccountCircle as AccountIcon,
  Dashboard as DashboardIcon,
  Storage,
  ExitToApp as LogoutIcon,
  Terminal,
} from '@mui/icons-material'
import Login from './pages/Login'
import DeviceList from './pages/DeviceList'
import DeviceDetail from './pages/DeviceDetail'
import Dashboard from './pages/Dashboard'
import Viewer from './pages/Viewer'
import { sessionManager } from './services/auth'

const DRAWER_WIDTH = 260

// 导航菜单项
const navItems = [
  { label: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { label: 'Devices', icon: <Storage />, path: '/devices' },
  { label: 'Viewer', icon: <Terminal />, path: '/viewer' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const user = sessionManager.getSession()
  const currentPath = window.location.pathname

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  const handleProfileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleProfileMenuClose = () => {
    setAnchorEl(null)
  }

  const handleLogout = () => {
    sessionManager.logout()
    handleProfileMenuClose()
  }

  const renderMenu = (
    <Menu
      anchorEl={anchorEl}
      anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      open={Boolean(anchorEl)}
      onClose={handleProfileMenuClose}
      PaperProps={{
        sx: {
          bgcolor: '#0d121f',
          border: '1px solid rgba(52, 211, 153, 0.2)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 24px rgba(52, 211, 153, 0.1)',
        },
      }}
    >
      <MenuItem onClick={handleProfileMenuClose} sx={{ color: '#e2e8f0' }}>
        <AccountIcon sx={{ mr: 1, color: '#34d399' }} />
        Profile
      </MenuItem>
      <Divider sx={{ my: 0.5, bgcolor: 'rgba(52, 211, 153, 0.1)' }} />
      <MenuItem onClick={handleLogout} sx={{ color: '#ef4444' }}>
        <LogoutIcon sx={{ mr: 1 }} />
        Logout
      </MenuItem>
    </Menu>
  )

  const drawerContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo 区域 */}
      <Toolbar sx={{ px: 2, minHeight: '64px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2,
              bgcolor: 'rgba(52, 211, 153, 0.2)',
              border: '1px solid rgba(52, 211, 153, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Storage sx={{ color: '#34d399', fontSize: 24 }} />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ color: '#fff', fontWeight: 700, fontSize: '0.8rem', lineHeight: 1.2 }}>
              Network
            </Typography>
            <Typography variant="caption" sx={{ color: '#34d399', fontWeight: 600, fontSize: '0.65rem', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Engineer Pro
            </Typography>
          </Box>
        </Box>
      </Toolbar>

      <Divider sx={{ bgcolor: 'rgba(52, 211, 153, 0.1)' }} />

      {/* 导航菜单 */}
      <List sx={{ px: 1, pt: 2, flex: 1 }}>
        {navItems.map((item) => {
          const isActive = currentPath === item.path || (item.path !== '/' && currentPath.startsWith(item.path))
          return (
            <ListItem key={item.path} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                component="a"
                href={item.path}
                sx={{
                  borderRadius: 2,
                  py: 1.5,
                  px: 2,
                  bgcolor: isActive ? 'rgba(52, 211, 153, 0.1)' : 'transparent',
                  border: isActive ? '1px solid rgba(52, 211, 153, 0.3)' : '1px solid transparent',
                  transition: 'all 200ms ease',
                  '&:hover': {
                    bgcolor: 'rgba(52, 211, 153, 0.08)',
                    borderColor: 'rgba(52, 211, 153, 0.2)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: isActive ? '#34d399' : '#64748b', minWidth: 40 }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    sx: {
                      color: isActive ? '#e2e8f0' : '#94a3b8',
                      fontWeight: isActive ? 600 : 500,
                      fontSize: '0.8rem',
                      letterSpacing: '0.025em',
                    },
                  }}
                />
                {isActive && (
                  <Box
                    sx={{
                      width: 4,
                      height: 4,
                      borderRadius: '50%',
                      bgcolor: '#34d399',
                      boxShadow: '0 0 8px rgba(52, 211, 153, 0.6)',
                    }}
                  />
                )}
              </ListItemButton>
            </ListItem>
          )
        })}
      </List>

      {/* 底部状态 */}
      <Box sx={{ p: 2 }}>
        <Divider sx={{ bgcolor: 'rgba(52, 211, 153, 0.1)', mb: 2 }} />
        <Box
          sx={{
            p: 2,
            bgcolor: 'rgba(52, 211, 153, 0.05)',
            border: '1px solid rgba(52, 211, 153, 0.1)',
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: '#10b981',
                boxShadow: '0 0 8px #10b981',
              }}
            />
            <Typography variant="caption" sx={{ color: '#10b981', fontWeight: 600, fontSize: '0.65rem', letterSpacing: '0.05em' }}>
              SYSTEM ONLINE
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
            {user?.username || 'Not logged in'}
          </Typography>
        </Box>
      </Box>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', bgcolor: '#0a0f1a', minHeight: '100vh' }}>
      {/* AppBar */}
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { sm: `${DRAWER_WIDTH}px` },
          bgcolor: '#0d121f',
          borderBottom: '1px solid rgba(52, 211, 153, 0.1)',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.3)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <Toolbar sx={{ minHeight: '64px !important' }}>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' }, color: '#34d399' }}
          >
            <MenuIcon />
          </IconButton>

          <Typography
            variant="h6"
            noWrap
            component="div"
            sx={{
              flexGrow: 1,
              display: { sm: 'none' },
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
          >
            Network Engineer Pro
          </Typography>

          <Box sx={{ flexGrow: 1 }} />

          {/* 通知图标 */}
          <Tooltip title="Notifications">
            <IconButton sx={{ color: '#64748b' }}>
              <Badge
                variant="dot"
                color="error"
                sx={{
                  '& .MuiBadge-badge': {
                    bgcolor: '#ef4444',
                    boxShadow: '0 0 8px rgba(239, 68, 68, 0.6)',
                  },
                }}
              >
                <NotificationsIcon />
              </Badge>
            </IconButton>
          </Tooltip>

          {/* 用户头像 */}
          <Tooltip title="Account">
            <IconButton size="large" edge="end" onClick={handleProfileMenuOpen}>
              <Avatar
                sx={{
                  width: 36,
                  height: 36,
                  bgcolor: 'rgba(52, 211, 153, 0.2)',
                  color: '#34d399',
                  border: '1px solid rgba(52, 211, 153, 0.3)',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                }}
              >
                {user?.username?.charAt(0).toUpperCase() || <AccountIcon />}
              </Avatar>
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      {/* 侧边栏 */}
      <Box
        component="nav"
        sx={{ width: { sm: DRAWER_WIDTH }, flexShrink: { sm: 0 } }}
      >
        {/* 移动端临时抽屉 */}
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
              bgcolor: '#0d121f',
              borderRight: '1px solid rgba(52, 211, 153, 0.1)',
              boxShadow: '4px 0 24px rgba(0, 0, 0, 0.3)',
            },
          }}
        >
          {drawerContent}
        </Drawer>

        {/* 桌面端固定抽屉 */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              bgcolor: '#0d121f',
              borderRight: '1px solid rgba(52, 211, 153, 0.1)',
              boxShadow: '4px 0 24px rgba(0, 0, 0, 0.2)',
            },
          }}
          open
        >
          {drawerContent}
        </Drawer>
      </Box>

      {/* 主内容区 */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: '64px',
          bgcolor: '#0a0f1a',
          minHeight: 'calc(100vh - 64px)',
        }}
      >
        {children}
      </Box>

      {renderMenu}
    </Box>
  )
}

const App: React.FC = () => {
  const [user, setUser] = useState(sessionManager.getSession())

  // 每次路由变化时重新检查登录状态
  const refreshSession = () => {
    setUser(sessionManager.getSession())
  }

  return (
    <>
      <CssBaseline />
      <Routes>
        <Route path="/login" element={<Login onLogin={refreshSession} />} />
        <Route path="/" element={user ? <Layout><Dashboard /></Layout> : <Navigate to="/login" />} />
        <Route path="/devices" element={user ? <Layout><DeviceList /></Layout> : <Navigate to="/login" />} />
        <Route path="/devices/:name" element={user ? <Layout><DeviceDetail /></Layout> : <Navigate to="/login" />} />
        <Route path="/dashboard" element={user ? <Layout><Dashboard /></Layout> : <Navigate to="/login" />} />
        <Route path="/viewer" element={user ? <Layout><Viewer /></Layout> : <Navigate to="/login" />} />
      </Routes>
    </>
  )
}

export default App
