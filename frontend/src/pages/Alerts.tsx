import { useState, useEffect, useCallback } from 'react'
import {
  Box, Container, Typography, Card, CardContent, Chip, Button, Alert as MuiAlert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, IconButton, Tooltip, CircularProgress, Select, MenuItem,
  FormControl, InputLabel, Collapse, Divider, Snackbar, Alert,
  TextField,
} from '@mui/material'
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  CheckCircle,
  ExpandMore,
  ExpandLess,
  DoneAll,
  Add as AddIcon,
  Remove as RemoveIcon,
} from '@mui/icons-material'
import { alertsApi, phase2Api } from '../services/api'
import { sessionManager } from '../services/auth'
import { useI18n } from '../i18n'

/** 字段中文标签映射 */
const FIELD_LABELS: Record<string, string> = {
  port_name: '端口', description: '描述', prev_week: '上周',
  error_type: '错误类型', added_lines: '新增行', removed_lines: '删除行',
  model: '型号', current_version: '当前版本', other_versions: '其他版本',
  prev_uptime_seconds: '重启前运行', cur_uptime_seconds: '当前运行', downtime_seconds: '停机时间',
  rx_util_pct: 'RX 利用率', tx_util_pct: 'TX 利用率',
  prev_rx_util_pct: '上周 RX', prev_tx_util_pct: '上周 TX',
  port_name_cur: '当前端口', port_name_prev: '历史端口',
}

/** 将秒数格式化为可读时间 */
function formatSeconds(s: number): string {
  if (s < 60) return `${s} 秒`
  if (s < 3600) return `${Math.round(s / 60)} 分钟`
  if (s < 86400) return `${(s / 3600).toFixed(1)} 小时`
  return `${(s / 86400).toFixed(1)} 天`
}

/** 根据告警类型渲染结构化详情 */
function renderDetail(alertType: string, detail: Record<string, any>) {
  if (!detail || Object.keys(detail).length === 0) {
    return <Typography variant="body2" color="text.secondary">无额外详情</Typography>
  }

  // 拓扑变更：紧凑列表展示新增/消失邻居
  if (alertType === 'topology_changed') {
    const added = (detail.new_neighbors as any[]) || []
    const gone = (detail.gone_neighbors as any[]) || []
    return (
      <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
        {added.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="caption" color="success.main" fontWeight={700}>
              <AddIcon sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.3 }} />
              新增 {added.length} 条
            </Typography>
            {added.map((n, i) => (
              <Typography key={`add-${i}`} variant="body2" sx={{ pl: 2, fontSize: 12 }}>
                {n.port} → {n.name} {n.type ? `(${n.type})` : ''}
              </Typography>
            ))}
          </Box>
        )}
        {gone.length > 0 && (
          <Box>
            <Typography variant="caption" color="error.main" fontWeight={700}>
              <RemoveIcon sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.3 }} />
              消失 {gone.length} 条
            </Typography>
            {gone.map((n, i) => (
              <Typography key={`gone-${i}`} variant="body2" sx={{ pl: 2, fontSize: 12 }}>
                {n.port} → {n.name} {n.type ? `(${n.type})` : ''}
              </Typography>
            ))}
          </Box>
        )}
      </Box>
    )
  }

  // 通用：键值对格式
  return (
    <Box component="dl" sx={{ m: 0 }}>
      {Object.entries(detail).filter(([k]) => k !== 'new_neighbors' && k !== 'gone_neighbors').map(([k, v]) => {
        const label = FIELD_LABELS[k] || k
        let display: string
        if (typeof v === 'number' && (k.includes('uptime') || k.includes('downtime'))) {
          display = formatSeconds(v)
        } else if (typeof v === 'number' && k.endsWith('_pct')) {
          display = `${v.toFixed(0)}%`
        } else if (Array.isArray(v)) {
          display = v.join(', ')
        } else {
          display = String(v ?? '')
        }
        return (
          <Box key={k} sx={{ display: 'flex', gap: 1 }}>
            <Typography component="dt" variant="body2" color="text.secondary" sx={{ minWidth: 90, flexShrink: 0, fontWeight: 600 }}>
              {label}
            </Typography>
            <Typography component="dd" variant="body2">{display || '—'}</Typography>
          </Box>
        )
      })}
    </Box>
  )
}

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
  const [filterDevice, setFilterDevice] = useState('')
  const [filterDateFrom, setFilterDateFrom] = useState('')
  const [filterDateTo, setFilterDateTo] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(true)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [phase2Loading, setPhase2Loading] = useState<Set<number>>(new Set())
  const [phase2Msg, setPhase2Msg] = useState<{ text: string; severity: 'info' | 'success' | 'error' } | null>(null)
  const [suggestions, setSuggestions] = useState<Record<number, string>>({})

  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number | boolean> = { limit: 100 }
      if (filterType) params.alert_type = filterType
      if (filterSeverity) params.severity = filterSeverity
      if (filterDevice) params.device_name = filterDevice
      if (filterDateFrom) params.date_from = filterDateFrom
      if (filterDateTo) params.date_to = filterDateTo
      if (unreadOnly) params.unread_only = true
      const res = await alertsApi.list(params)
      setAlerts(res.data.alerts || [])
      setTotal(res.data.total || 0)
    } catch (e) {
      console.error('Failed to fetch alerts:', e)
    } finally {
      setLoading(false)
    }
  }, [filterType, filterSeverity, filterDevice, filterDateFrom, filterDateTo, unreadOnly])

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
    const session = sessionManager.getSession()
    if (!session) { alert('请先登录'); return }

    setPhase2Loading(prev => new Set(prev).add(alert.id))
    setPhase2Msg({ text: `正在对 ${alert.device_name} 执行深度诊断...`, severity: 'info' })
    try {
      await phase2Api.trigger(
        alert.device_name,
        [alert.alert_type],
        session.username,
        session.password,
        alert.detail?.port_name,
      )
      setPhase2Msg({ text: `${alert.device_name} 深度诊断完成`, severity: 'success' })
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Phase 2 执行失败'
      setPhase2Msg({ text: msg, severity: 'error' })
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
        <TextField
          size="small"
          label="设备名"
          placeholder="输入设备名筛选"
          value={filterDevice}
          onChange={e => setFilterDevice(e.target.value)}
          sx={{ minWidth: 160 }}
        />
        <TextField
          size="small"
          label="起始日期"
          type="date"
          value={filterDateFrom}
          onChange={e => setFilterDateFrom(e.target.value)}
          InputLabelProps={{ shrink: true }}
          sx={{ minWidth: 150 }}
        />
        <TextField
          size="small"
          label="结束日期"
          type="date"
          value={filterDateTo}
          onChange={e => setFilterDateTo(e.target.value)}
          InputLabelProps={{ shrink: true }}
          sx={{ minWidth: 150 }}
        />
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
          {unreadOnly ? `仅未处理 (${total})` : `显示全部 (${total})`}
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          {total} 条告警
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
                        <Box sx={{ mt: 1, p: 2, bgcolor: 'grey.50', borderRadius: 1, maxHeight: 340, overflow: 'auto' }}>
                          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{t('alerts.detail')}</Typography>
                          {renderDetail(a.alert_type, a.detail)}
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
      <Snackbar
        open={!!phase2Msg}
        autoHideDuration={4000}
        onClose={() => setPhase2Msg(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        {phase2Msg ? (
          <Alert severity={phase2Msg.severity} onClose={() => setPhase2Msg(null)} variant="filled">
            {phase2Msg.text}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Container>
  )
}
