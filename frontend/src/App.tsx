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
          bgcolor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
        },
      }}
    >
      <MenuItem onClick={handleProfileMenuClose}>
        <AccountIcon sx={{ mr: 1, color: 'primary.main' }} />
        Profile
      </MenuItem>
      <Divider sx={{ my: 0.5 }} />
      <MenuItem onClick={handleLogout} sx={{ color: 'error.main' }}>
        <LogoutIcon sx={{ mr: 1 }} />
        Logout
      </MenuItem>
    </Menu>
  )

  const drawerContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Toolbar sx={{ px: 2, minHeight: '64px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              bgcolor: 'rgba(34, 197, 94, 0.12)',
              border: '1px solid',
              borderColor: 'rgba(34, 197, 94, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Storage sx={{ color: 'primary.main', fontSize: 20 }} />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ color: 'text.primary', fontWeight: 700, fontSize: '0.8rem', lineHeight: 1.2 }}>
              Network
            </Typography>
            <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.65rem', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Engineer Pro
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
                component="a"
                href={item.path}
                sx={{
                  borderRadius: 1.5,
                  py: 1.3,
                  px: 2,
                  bgcolor: isActive ? 'rgba(34, 197, 94, 0.08)' : 'transparent',
                  border: '1px solid',
                  borderColor: isActive ? 'rgba(34, 197, 94, 0.2)' : 'transparent',
                  transition: 'all 150ms ease',
                  '&:hover': {
                    bgcolor: 'rgba(34, 197, 94, 0.06)',
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
        <Divider sx={{ mb: 2 }} />
        <Box
          sx={{
            p: 2,
            bgcolor: 'rgba(34, 197, 94, 0.04)',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1.5,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                bgcolor: 'success.main',
              }}
            />
            <Typography variant="caption" sx={{ color: 'success.main', fontWeight: 600, fontSize: '0.65rem', letterSpacing: '0.05em' }}>
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
    <Box sx={{ display: 'flex', bgcolor: 'background.default', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { sm: `${DRAWER_WIDTH}px` },
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
          boxShadow: 'none',
        }}
      >
        <Toolbar sx={{ minHeight: '64px !important' }}>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' }, color: 'primary.main' }}
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
              color: 'text.primary',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
          >
            Network Engineer Pro
          </Typography>

          <Box sx={{ flexGrow: 1 }} />

          <Tooltip title="Notifications">
            <IconButton sx={{ color: 'text.disabled' }}>
              <Badge
                variant="dot"
                color="error"
                sx={{
                  '& .MuiBadge-badge': {
                    bgcolor: 'error.main',
                  },
                }}
              >
                <NotificationsIcon />
              </Badge>
            </IconButton>
          </Tooltip>

          <Tooltip title="Account">
            <IconButton size="large" edge="end" onClick={handleProfileMenuOpen}>
              <Avatar
                sx={{
                  width: 32,
                  height: 32,
                  fontSize: '0.8rem',
                  fontWeight: 600,
                }}
              >
                {user?.username?.charAt(0).toUpperCase() || <AccountIcon />}
              </Avatar>
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

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
          mt: '64px',
          bgcolor: 'background.default',
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
