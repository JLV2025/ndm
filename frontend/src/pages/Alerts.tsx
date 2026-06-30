import { useState, useEffect, useCallback } from 'react'
import {
  Box, Container, Typography, Card, CardContent, Chip, Button, Alert as MuiAlert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, IconButton, Tooltip, CircularProgress, Select, MenuItem,
  FormControl, InputLabel, Collapse, Divider,
} from '@mui/material'
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  CheckCircle,
  ExpandMore,
  ExpandLess,
  DoneAll,
} from '@mui/icons-material'
import { alertsApi, phase2Api } from '../services/api'
import { useI18n } from '../i18n'

const SEVERITY_CONFIG: Record<string, { color: 'error' | 'warning' | 'info' | 'success'; icon: typeof WarningIcon; label: string }> = {
  CRITICAL: { color: 'error', icon: ErrorIcon, label: '严重' },
  HIGH: { color: 'error', icon: WarningIcon, label: '高' },
  WARNING: { color: 'warning', icon: WarningIcon, label: '警告' },
  INFO: { color: 'info', icon: InfoIcon, label: '信息' },
}

interface AlertItem {
  id: number
  device_id: number
  device_name: string
  alert_type: string
  severity: string
  title: string
  detail: Record<string, any>
  suggestion: string
  is_read: boolean
  resolved_at: string | null
  created_at: string
}

export default function AlertsPage() {
  const { t } = useI18n()
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(true)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [phase2Loading, setPhase2Loading] = useState<Set<number>>(new Set())
  const [suggestions, setSuggestions] = useState<Record<number, string>>({})

  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number | boolean> = { limit: 100 }
      if (filterType) params.alert_type = filterType
      if (filterSeverity) params.severity = filterSeverity
      if (unreadOnly) params.unread_only = true
      const res = await alertsApi.list(params)
      setAlerts(res.data.alerts || [])
      setTotal(res.data.total || 0)
    } catch (e) {
      console.error('Failed to fetch alerts:', e)
    } finally {
      setLoading(false)
    }
  }, [filterType, filterSeverity, unreadOnly])

  useEffect(() => { fetchAlerts() }, [fetchAlerts])

  const toggleExpand = (id: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleMarkRead = async (id: number) => {
    await alertsApi.markRead(id)
    fetchAlerts()
  }

  const handleResolve = async (id: number) => {
    await alertsApi.resolve(id)
    fetchAlerts()
  }

  const handlePhase2 = async (alert: AlertItem) => {
    setPhase2Loading(prev => new Set(prev).add(alert.id))
    try {
      await phase2Api.trigger(alert.device_name, [alert.alert_type], alert.detail?.port_name)
    } catch (e: any) {
      console.error('Phase 2 failed:', e)
    }
    setPhase2Loading(prev => {
      const next = new Set(prev)
      next.delete(alert.id)
      return next
    })
  }

  const loadSuggestion = async (alert: AlertItem) => {
    if (suggestions[alert.id]) return
    try {
      const res = await alertsApi.getSuggestion(alert.id)
      setSuggestions(prev => ({ ...prev, [alert.id]: res.data.suggestion }))
    } catch (e) { /* ignore */ }
  }

  const hasPhase2 = (alertType: string) =>
    ['device_reboot', 'port_sudden_down', 'port_errors', 'topology_changed', 'high_utilization'].includes(alertType)

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 8 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>{t('alerts.title')}</Typography>
        <Typography variant="body2" color="text.secondary">{t('alerts.description')}</Typography>
      </Box>

      {/* 过滤栏 */}
      <Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>{t('alerts.allTypes')}</InputLabel>
          <Select value={filterType} label={t('alerts.allTypes')} onChange={e => setFilterType(e.target.value)}>
            <MenuItem value="">{t('alerts.allTypes')}</MenuItem>
            <MenuItem value="device_reboot">{t('alerts.type_device_reboot')}</MenuItem>
            <MenuItem value="port_sudden_down">{t('alerts.type_port_sudden_down')}</MenuItem>
            <MenuItem value="port_errors">{t('alerts.type_port_errors')}</MenuItem>
            <MenuItem value="config_changed">{t('alerts.type_config_changed')}</MenuItem>
            <MenuItem value="topology_changed">{t('alerts.type_topology_changed')}</MenuItem>
            <MenuItem value="version_mismatch">{t('alerts.type_version_mismatch')}</MenuItem>
            <MenuItem value="high_utilization">{t('alerts.type_high_utilization')}</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>{t('alerts.allSeverities')}</InputLabel>
          <Select value={filterSeverity} label={t('alerts.allSeverities')} onChange={e => setFilterSeverity(e.target.value)}>
            <MenuItem value="">{t('alerts.allSeverities')}</MenuItem>
            <MenuItem value="CRITICAL">严重</MenuItem>
            <MenuItem value="HIGH">高</MenuItem>
            <MenuItem value="WARNING">警告</MenuItem>
            <MenuItem value="INFO">信息</MenuItem>
          </Select>
        </FormControl>
        <Button variant={unreadOnly ? 'contained' : 'outlined'} size="small" onClick={() => setUnreadOnly(!unreadOnly)}>
          {unreadOnly ? '仅未处理' : '显示全部'}
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          {t('alerts.summary', { total: String(total) })}
        </Typography>
      </Paper>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
      ) : alerts.length === 0 ? (
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <CheckCircle sx={{ fontSize: 48, color: 'success.main', mb: 2 }} />
          <Typography variant="h6">{t('alerts.noAlerts')}</Typography>
          <Typography variant="body2" color="text.secondary">{t('alerts.noAlertsHint')}</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>级别</TableCell>
                <TableCell>设备</TableCell>
                <TableCell>类型</TableCell>
                <TableCell>标题</TableCell>
                <TableCell>时间</TableCell>
                <TableCell align="right">操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {alerts.map(a => {
                const sev = SEVERITY_CONFIG[a.severity] || SEVERITY_CONFIG.INFO
                const SevIcon = sev.icon
                const isExpanded = expanded.has(a.id)
                return (
                  <TableRow
                    key={a.id}
                    sx={{ opacity: a.is_read || a.resolved_at ? 0.6 : 1, '&:hover': { bgcolor: 'action.hover' } }}
                  >
                    <TableCell><Chip icon={<SevIcon />} label={sev.label} color={sev.color} size="small" /></TableCell>
                    <TableCell>{a.device_name}</TableCell>
                    <TableCell>{t(`alerts.type_${a.alert_type}`)}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {a.title}
                        <IconButton size="small" onClick={() => { toggleExpand(a.id); loadSuggestion(a) }}>
                          {isExpanded ? <ExpandLess /> : <ExpandMore />}
                        </IconButton>
                      </Box>
                      <Collapse in={isExpanded}>
                        <Box sx={{ mt: 1, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                          <Typography variant="subtitle2">{t('alerts.detail')}</Typography>
                          <Box component="pre" sx={{ fontSize: 12, whiteSpace: 'pre-wrap', mb: 1 }}>
                            {JSON.stringify(a.detail, null, 2)}
                          </Box>
                          {suggestions[a.id] && (
                            <>
                              <Divider sx={{ my: 1 }} />
                              <Typography variant="subtitle2" color="primary">{t('alerts.suggestion')}</Typography>
                              <Typography variant="body2">{suggestions[a.id]}</Typography>
                            </>
                          )}
                        </Box>
                      </Collapse>
                    </TableCell>
                    <TableCell>{new Date(a.created_at).toLocaleString('zh-CN')}</TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                        {!a.is_read && (
                          <Tooltip title={t('alerts.markRead')}>
                            <IconButton size="small" onClick={() => handleMarkRead(a.id)}><DoneAll /></IconButton>
                          </Tooltip>
                        )}
                        {!a.resolved_at && (
                          <Tooltip title={t('alerts.resolve')}>
                            <IconButton size="small" color="success" onClick={() => handleResolve(a.id)}><CheckCircle /></IconButton>
                          </Tooltip>
                        )}
                        {hasPhase2(a.alert_type) && !a.resolved_at && (
                          <Button
                            size="small" variant="contained" color="primary"
                            disabled={phase2Loading.has(a.id)}
                            onClick={() => handlePhase2(a)}
                          >
                            {phase2Loading.has(a.id) ? t('alerts.phase2Running') : t('alerts.phase2')}
                          </Button>
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Container>
  )
}
