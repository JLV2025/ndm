import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { Routes, Route, Navigate, useLocation, Link, Outlet } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import {
  Box,
  CssBaseline,
  Collapse,
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
  Snackbar,
} from '@mui/material'
import {
  AccountCircle as AccountIcon,
  Dashboard as DashboardIcon,
  Storage,
  Terminal,
  Hub as HubIcon,
  AccountTree as TreeIcon,
  Warning as AlertIcon,
  Assessment as ReportsIcon,
  BugReport as BugIcon,
  FactCheck as AuditIcon,
  Bolt as BoltIcon,
  VerifiedUser as LifecycleIcon,
  ExpandLess,
  ExpandMore,
} from '@mui/icons-material'
import Login from './pages/Login'
import DeviceList from './pages/DeviceList'
import DeviceDetail from './pages/DeviceDetail'
import Dashboard from './pages/Dashboard'
import Viewer from './pages/Viewer'
import Topology from './pages/PortTopology'
import NetworkTopology from './pages/NetworkTopology'
import StpTopology from './pages/StpTopology'
import Alerts from './pages/Alerts'
import Reports from './pages/Reports'
import LogAnalyzer from './pages/LogAnalyzer'
import ComplianceStandard from './pages/ComplianceStandard'
import ComplianceAudit from './pages/ComplianceAudit'
import BatchExec from './pages/BatchExec'
import Lifecycle from './pages/Lifecycle'
import MatrixRain from './components/MatrixRain'
import { sessionManager } from './services/auth'
import { useI18n } from './i18n'

const DRAWER_WIDTH = 260

/** 侧栏分组展开态的 localStorage 键 */
const NAV_GROUP_STORAGE = 'ndm_nav_groups'

type NavEntry = { label: string; icon: ReactNode; path: string }

function Layout() {
  const { t, lang, setLang } = useI18n()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [version, setVersion] = useState('')
  const user = sessionManager.getSession()
  const location = useLocation()
  const currentPath = location.pathname

  useEffect(() => {
    fetch('/api/version')
      .then(r => r.json())
      .then(d => setVersion(d.version || ''))
      .catch(() => setVersion(''))
  }, [])

  // 构建新鲜度检查：标签页长期开着时，后台重建（start.bat 每次启动都会重建）后
  // 内存里跑的还是旧 JS —— 界面看着是旧版、接口却是新版，数据对不上号。
  // 取当前 index.html 引用的 bundle 名与正在运行的对不上 → 提示刷新。
  const [staleBuild, setStaleBuild] = useState(false)
  useEffect(() => {
    const running = (import.meta.url.split('?')[0].split('/').pop() || '')
    if (!running.startsWith('index-')) return  // dev 模式（/src/main.tsx）不检查
    const check = async () => {
      try {
        const res = await fetch('/index.html', { cache: 'no-store' })
        if (!res.ok) return
        const match = (await res.text()).match(/assets\/(index-[\w-]+\.js)/)
        if (match && match[1] !== running) setStaleBuild(true)
      } catch { /* 离线/网络异常：静默跳过 */ }
    }
    check()
    window.addEventListener('focus', check)
    const timer = window.setInterval(check, 5 * 60 * 1000)
    return () => {
      window.removeEventListener('focus', check)
      window.clearInterval(timer)
    }
  }, [])

  // 侧栏结构（2026-09-22 用户定案）：顶层留高频三项，其余按心智模型分 4 组折叠
  const navPinned: NavEntry[] = [
    { label: t('nav.dashboard'), icon: <DashboardIcon />, path: '/' },
    { label: t('nav.devices'), icon: <Storage />, path: '/devices' },
    { label: t('nav.viewer'), icon: <Terminal />, path: '/viewer' },
  ]
  const navGroups: { key: string; label: string; items: NavEntry[] }[] = [
    { key: 'topology', label: t('nav.group.topology'), items: [
      { label: t('nav.topology'), icon: <HubIcon />, path: '/network-topology' },
      { label: t('nav.portTopology'), icon: <HubIcon />, path: '/port-topology' },
      { label: t('nav.stpTopology'), icon: <TreeIcon />, path: '/stp-topology' },
    ] },
    { key: 'audit', label: t('nav.group.audit'), items: [
      { label: t('nav.audit'), icon: <AuditIcon />, path: '/compliance-audit' },
      { label: t('auditRules.title'), icon: <AuditIcon />, path: '/compliance-standard' },
    ] },
    { key: 'monitor', label: t('nav.group.monitor'), items: [
      { label: t('alerts.title'), icon: <AlertIcon />, path: '/alerts' },
      { label: t('logs.title'), icon: <BugIcon />, path: '/log-analyzer' },
      { label: t('reports.title'), icon: <ReportsIcon />, path: '/reports' },
    ] },
    { key: 'assets', label: t('nav.group.assets'), items: [
      { label: t('nav.lifecycle'), icon: <LifecycleIcon />, path: '/lifecycle' },
      { label: t('nav.batchExec'), icon: <BoltIcon />, path: '/batch-exec' },
    ] },
  ]

  // 分组展开态：**当前路由所在组一律展开**（进站/跳转时自动打开并记忆——否则刷新或从深链进来
  // 会看不到高亮项）；其余组的开合由用户点击决定，状态存 localStorage 跨会话保留。
  // 首次进站（无存档）：展开第一组。
  const activeGroup = navGroups.find(g => g.items.some(
    it => currentPath === it.path || (it.path !== '/' && currentPath.startsWith(it.path))))?.key
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(NAV_GROUP_STORAGE) || 'null')
      if (saved && typeof saved === 'object') return saved as Record<string, boolean>
    } catch { /* 坏值当没有存档 */ }
    return { [navGroups[0].key]: true }
  })
  useEffect(() => {
    if (!activeGroup) return
    setOpenGroups(prev => {
      if (prev[activeGroup]) return prev
      const next = { ...prev, [activeGroup]: true }
      localStorage.setItem(NAV_GROUP_STORAGE, JSON.stringify(next))
      return next
    })
  }, [activeGroup])
  const toggleGroup = (key: string) => {
    setOpenGroups(prev => {
      const next = { ...prev, [key]: !(prev[key] ?? false) }
      localStorage.setItem(NAV_GROUP_STORAGE, JSON.stringify(next))
      return next
    })
  }

  /** 单个导航条目 —— 顶层与组内共用，样式与高亮逻辑保持原样 */
  const renderNavItem = (item: NavEntry) => {
    const isActive = currentPath === item.path || (item.path !== '/' && currentPath.startsWith(item.path))
    return (
      <ListItem key={item.path} disablePadding sx={{ mb: 0.25 }}>
        <ListItemButton
          component={Link}
          to={item.path}
          sx={{
            borderRadius: 1.5,
            py: 1,
            px: 1.5,
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
  }

  const handleDrawerToggle = () => setMobileOpen(!mobileOpen)

  const handleLogout = () => {
    sessionManager.logout()
    window.location.href = '/login'
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
            <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.05em' }}>
              网络设备管理
            </Typography>
          </Box>
        </Box>
      </Toolbar>

      <Divider />

      <Box sx={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <List sx={{ px: 1, pt: 2, flex: 0 }}>
        {navPinned.map(renderNavItem)}
        {navGroups.map(g => {
          const open = openGroups[g.key] ?? false
          return (
            <Box key={g.key} sx={{ mt: 0.5 }}>
              {/* 组标题：可点、带箭头（折叠态 ▸ / 展开态 ▾）与条目数 */}
              <ListItemButton onClick={() => toggleGroup(g.key)}
                sx={{
                  borderRadius: 1.5, py: 0.75, px: 1.5,
                  '&:hover': { bgcolor: 'rgba(45, 212, 110, 0.06)' },
                }}>
                <ListItemIcon sx={{ color: 'text.disabled', minWidth: 40 }}>
                  {open ? <ExpandLess sx={{ fontSize: 18 }} /> : <ExpandMore sx={{ fontSize: 18 }} />}
                </ListItemIcon>
                <ListItemText
                  primary={g.label}
                  primaryTypographyProps={{
                    sx: { color: 'text.disabled', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.06em' },
                  }}
                />
                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{g.items.length}</Typography>
              </ListItemButton>
              <Collapse in={open} timeout={150} unmountOnExit>
                <Box sx={{ mt: 0.25 }}>{g.items.map(renderNavItem)}</Box>
              </Collapse>
            </Box>
          )
        })}
      </List>

      {/* 版本号 */}
      {version && (
        <Box sx={{ px: 2, pb: 0.5 }}>
          <Typography
            sx={{
              color: 'text.disabled',
              fontSize: '0.7rem',
              fontWeight: 600,
              letterSpacing: '0.04em',
              fontFamily: '"Fira Code", monospace',
            }}
          >
            v{version}
          </Typography>
        </Box>
      )}

      <Box sx={{ p: 2, pt: version ? 1 : 2 }}>
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
      </Box> {/* scroll */}
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

      <Snackbar
        open={staleBuild}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        message={t('app.staleBuild')}
        action={
          <Button color="primary" size="small" onClick={() => window.location.reload()}>
            {t('app.reload')}
          </Button>
        }
      />
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
          <Route path="topology" element={<Topology />} />
          <Route path="port-topology" element={<Topology />} />
          <Route path="network-topology" element={<NetworkTopology />} />
          <Route path="stp-topology" element={<StpTopology />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="reports" element={<Reports />} />
          <Route path="log-analyzer" element={<LogAnalyzer />} />
          <Route path="compliance-standard" element={<ComplianceStandard />} />
          <Route path="compliance-audit" element={<ComplianceAudit />} />
          <Route path="lifecycle" element={<Lifecycle />} />
          <Route path="batch-exec" element={<BatchExec />} />
        </Route>
      </Routes>
      </ErrorBoundary>
    </>
  )
}

export default App
