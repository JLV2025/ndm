import { useState, useEffect, useMemo } from 'react'
import {
  Box, Typography, Select, MenuItem, FormControl, InputLabel,
  Button, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Checkbox, Chip, Paper, CircularProgress, Alert,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  IconButton, Tooltip, Card, CardContent,
} from '@mui/material'
import {
  BugReport as BugIcon, History as HistoryIcon, Settings as SettingsIcon,
  Refresh as RefreshIcon, Delete as DeleteIcon, Add as AddIcon,
  SmartToy as AIIcon,
} from '@mui/icons-material'
import { useI18n } from '../i18n'
import { deviceApi, logApi, llmApi } from '../services/api'
import type { Device } from '../types'

// 严重级别颜色
const SEV_COLORS: Record<string, string> = {
  '0': '#ef4444', '1': '#f97316', '2': '#eab308',
  '3': '#22c55e', '4': '#3b82f6', '5': '#6366f1',
  '6': '#94a3b8', '7': '#64748b',
  'emergency': '#ef4444', 'alert': '#f97316', 'critical': '#f97316',
  'error': '#ef4444', 'err': '#ef4444',
  'warning': '#eab308', 'warn': '#eab308',
  'notice': '#3b82f6', 'info': '#6366f1', 'debug': '#94a3b8',
}

function SevChip({ sev }: { sev: string }) {
  const s = sev.toLowerCase()
  const label = sev || '?'
  const color = SEV_COLORS[s] || '#94a3b8'
  return (
    <Chip label={label} size="small"
      sx={{ bgcolor: color, color: '#fff', fontWeight: 600, minWidth: 36, fontSize: '0.7rem' }} />
  )
}

export default function LogAnalyzer() {
  const { t } = useI18n()
  const [devices, setDevices] = useState<Device[]>([])
  const [selectedDevice, setSelectedDevice] = useState('')
  const [logs, setLogs] = useState<any[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [filterWeek, setFilterWeek] = useState('')
  const [filterSev, setFilterSev] = useState('')
  const [weeks, setWeeks] = useState<string[]>([])
  const [history, setHistory] = useState<any[]>([])
  const [histOpen, setHistOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // 加载设备列表
  useEffect(() => {
    deviceApi.list().then(r => setDevices(r.data)).catch(() => {})
    loadHistory()
  }, [])

  // 加载日志
  const loadLogs = async () => {
    if (!selectedDevice) return
    setLoading(true)
    setError('')
    try {
      const params: any = { limit: 200 }
      if (filterWeek) params.week = filterWeek
      if (filterSev) params.severity = filterSev
      const r = await logApi.getLogs(selectedDevice, params)
      setLogs(r.data.logs || [])
      // 收集可用周列表（去重）
      const ws = Array.from(new Set((r.data.logs || []).map((l: any) => l.week))) as string[]
      setWeeks(ws)
      setSelectedIds(new Set())
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadLogs() }, [selectedDevice, filterWeek, filterSev])

  const loadHistory = async () => {
    try {
      const r = await logApi.history(20)
      setHistory(r.data.history || [])
    } catch { }
  }

  // 选择/取消
  const toggleSelect = (id: number) => {
    const next = new Set(selectedIds)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelectedIds(next)
  }

  const selectAll = () => {
    if (selectedIds.size === logs.length) setSelectedIds(new Set())
    else setSelectedIds(new Set(logs.map((l: any) => l.id)))
  }

  // 开始分析
  const handleAnalyze = async () => {
    if (selectedIds.size === 0 || !selectedDevice) return
    setAnalyzing(true)
    setError('')
    setResult(null)
    try {
      const r = await logApi.analyze(Array.from(selectedIds), selectedDevice)
      setResult(r.data)
      loadHistory()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  // 历史记录
  const histData = useMemo(() => {
    return history.map(h => {
      let sug = h.suggestion
      try { sug = typeof sug === 'string' ? JSON.parse(sug) : sug } catch { }
      return { ...h, parsed: sug }
    })
  }, [history])

  return (
    <Box sx={{ p: 3, display: 'flex', gap: 2, height: 'calc(100vh - 80px)' }}>
      {/* 左侧: 日志表 */}
      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* 工具栏 */}
        <Box sx={{ p: 2, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ mr: 2 }}>📋 {t('logs.title')}</Typography>

          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>{t('logs.selectDevice')}</InputLabel>
            <Select value={selectedDevice} label={t('logs.selectDevice')}
              onChange={e => setSelectedDevice(e.target.value)}>
              {devices.map(d => (
                <MenuItem key={d.name} value={d.name}>{d.name}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>{t('logs.filterWeek')}</InputLabel>
            <Select value={filterWeek} label={t('logs.filterWeek')}
              onChange={e => setFilterWeek(e.target.value)}>
              <MenuItem value="">{t('logs.allWeeks')}</MenuItem>
              {weeks.map(w => <MenuItem key={w} value={w}>{w}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>{t('logs.filterSeverity')}</InputLabel>
            <Select value={filterSev} label={t('logs.filterSeverity')}
              onChange={e => setFilterSev(e.target.value)}>
              <MenuItem value="">{t('logs.allSeverities')}</MenuItem>
              {['0', '1', '2', '3', '4', '5', '6', '7'].map(s => (
                <MenuItem key={s} value={s}>{s}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <Tooltip title={t('logs.refresh')}><IconButton onClick={loadLogs}><RefreshIcon /></IconButton></Tooltip>
          <Tooltip title={t('logs.history')}><IconButton onClick={() => setHistOpen(true)}><HistoryIcon /></IconButton></Tooltip>
          <Tooltip title={t('logs.settings')}><IconButton onClick={() => setSettingsOpen(true)}><SettingsIcon /></IconButton></Tooltip>
        </Box>

        {/* 日志表 */}
        <TableContainer sx={{ flex: 1 }}>
          {!selectedDevice ? (
            <Box sx={{ p: 8, textAlign: 'center', color: 'text.secondary' }}>
              <BugIcon sx={{ fontSize: 48, mb: 2, opacity: 0.3 }} />
              <Typography>{t('logs.selectDeviceHint')}</Typography>
            </Box>
          ) : loading ? (
            <Box sx={{ p: 8, textAlign: 'center' }}><CircularProgress /></Box>
          ) : (
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox indeterminate={selectedIds.size > 0 && selectedIds.size < logs.length}
                      checked={selectedIds.size === logs.length && logs.length > 0}
                      onChange={selectAll} />
                  </TableCell>
                  <TableCell>{t('logs.timestamp')}</TableCell>
                  <TableCell>{t('logs.severity')}</TableCell>
                  <TableCell>{t('logs.facility')}</TableCell>
                  <TableCell>{t('logs.message')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.length === 0 ? (
                  <TableRow><TableCell colSpan={5} align="center">{t('logs.noLogs')}</TableCell></TableRow>
                ) : logs.map((l: any) => (
                  <TableRow key={l.id} hover selected={selectedIds.has(l.id)}
                    onClick={() => toggleSelect(l.id)} sx={{ cursor: 'pointer' }}>
                    <TableCell padding="checkbox">
                      <Checkbox checked={selectedIds.has(l.id)} size="small" />
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: '0.78rem' }}>
                      {l.timestamp}
                    </TableCell>
                    <TableCell><SevChip sev={l.severity} /></TableCell>
                    <TableCell sx={{ fontSize: '0.8rem' }}>{l.facility}</TableCell>
                    <TableCell sx={{ fontSize: '0.8rem', maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {l.message}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TableContainer>

        {/* 底部操作栏 */}
        <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip label={t('logs.selectedCount').replace('{n}', String(selectedIds.size))} color="primary"
            variant={selectedIds.size > 0 ? 'filled' : 'outlined'} />
          <Button variant="contained" startIcon={analyzing ? <CircularProgress size={16} /> : <AIIcon />}
            disabled={selectedIds.size === 0 || analyzing}
            onClick={handleAnalyze}>
            {analyzing ? t('logs.analyzing') : t('logs.analyze')}
          </Button>
          {error && <Alert severity="error" sx={{ flex: 1 }}>{error}</Alert>}
        </Box>
      </Paper>

      {/* 右侧: 分析结果 */}
      <Paper sx={{ width: 420, p: 3, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Typography variant="h6">🤖 {t('logs.analysisResult')}</Typography>
        {result ? (
          <ResultCard result={result} t={t} />
        ) : (
          <Box sx={{ textAlign: 'center', color: 'text.secondary', mt: 8 }}>
            <AIIcon sx={{ fontSize: 64, mb: 2, opacity: 0.2 }} />
            <Typography>{t('logs.noResult')}</Typography>
            <Typography variant="caption">{t('logs.noResultHint')}</Typography>
          </Box>
        )}
      </Paper>

      {/* 历史记录对话框 */}
      <Dialog open={histOpen} onClose={() => setHistOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('logs.historyTitle')}</DialogTitle>
        <DialogContent dividers>
          {histData.length === 0 ? (
            <Typography color="text.secondary">{t('logs.noHistory')}</Typography>
          ) : histData.map(h => (
            <Card key={h.id} variant="outlined" sx={{ mb: 1 }}>
              <CardContent>
                <Typography variant="caption" color="primary">{h.keyword}</Typography>
                {typeof h.parsed === 'object' && h.parsed ? (
                  <>
                    <Typography variant="subtitle2">{h.parsed.summary}</Typography>
                    <Typography variant="body2" color="text.secondary">{h.parsed.root_cause}</Typography>
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {typeof h.parsed === 'string' ? h.parsed : JSON.stringify(h.parsed)}
                  </Typography>
                )}
                <Typography variant="caption" sx={{ opacity: 0.5 }}>{h.created_at}</Typography>
              </CardContent>
            </Card>
          ))}
        </DialogContent>
        <DialogActions><Button onClick={() => setHistOpen(false)}>{t('common.close')}</Button></DialogActions>
      </Dialog>

      {/* LLM 设置对话框 */}
      <LLMSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} t={t} />
    </Box>
  )
}

/** 分析结果展示 */
function ResultCard({ result, t }: { result: any; t: any }) {
  const sug = typeof result.suggestion === 'string'
    ? (() => { try { return JSON.parse(result.suggestion) } catch { return null } })()
    : result.suggestion

  if (!sug || typeof sug !== 'object') {
    return <Alert severity="info">{result.suggestion || '—'}</Alert>
  }

  const sourceLabel = result.from_cache ? t('logs.sourceCache') : t('logs.sourceLLM')

  return (
    <>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Chip label={sourceLabel} size="small"
          color={result.from_cache ? 'success' : 'primary'}
          icon={result.from_cache ? <HistoryIcon /> : <AIIcon />} />
        {result.provider && (
          <Chip label={`${t('logs.provider')}: ${result.provider}`} size="small" variant="outlined" />
        )}
        {result.keyword && (
          <Chip label={result.keyword} size="small" variant="outlined" color="secondary" />
        )}
      </Box>

      {sug.severity && (
        <Alert severity={sug.severity === 'critical' ? 'error' : sug.severity === 'warning' ? 'warning' : 'info'}
          sx={{ mt: 1 }}>
          <Typography variant="subtitle2" fontWeight={700}>{t('logs.summary')}</Typography>
          <Typography variant="body2">{sug.summary}</Typography>
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>{t('logs.rootCause')}</Typography>
          <Typography variant="body2">{sug.root_cause}</Typography>
        </CardContent>
      </Card>

      <Card variant="outlined" sx={{ borderColor: 'primary.main', borderWidth: 1 }}>
        <CardContent>
          <Typography variant="subtitle2" color="primary" gutterBottom>{t('logs.suggestion')}</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{sug.suggestion}</Typography>
        </CardContent>
      </Card>

      {sug.related_errors?.length > 0 && (
        <Box>
          <Typography variant="caption" color="text.secondary">{t('logs.relatedErrors')}</Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
            {sug.related_errors.map((e: string) => (
              <Chip key={e} label={e} size="small" variant="outlined" />
            ))}
          </Box>
        </Box>
      )}
    </>
  )
}

/** LLM 设置对话框 */
function LLMSettingsDialog({ open, onClose, t }: { open: boolean; onClose: () => void; t: any }) {
  const [timeout, setTimeout_] = useState(30)
  const [providers, setProviders] = useState<any[]>([])
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (open) {
      llmApi.getSettings().then(r => {
        setTimeout_(r.data.timeout || 30)
        setProviders(r.data.providers || [])
      }).catch(() => {})
      setMsg('')
    }
  }, [open])

  const handleSave = async () => {
    setSaving(true)
    setMsg('')
    try {
      await llmApi.saveSettings({ timeout, providers })
      setMsg(t('logs.llmSaveSuccess'))
    } catch {
      setMsg(t('logs.llmSaveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const addProvider = () => {
    setProviders([...providers, { name: '', base_url: '', api_key: '', model: '' }])
  }

  const updateProvider = (i: number, field: string, val: string) => {
    const next = [...providers]
    next[i] = { ...next[i], [field]: val }
    setProviders(next)
  }

  const removeProvider = (i: number) => {
    setProviders(providers.filter((_, idx) => idx !== i))
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t('logs.llmConfig')}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label={t('logs.llmTimeout')} type="number" size="small"
            value={timeout} onChange={e => setTimeout_(Number(e.target.value))}
            sx={{ width: 120 }} />

          {providers.map((p, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <TextField label={t('logs.llmProviderName')} size="small" value={p.name}
                onChange={e => updateProvider(i, 'name', e.target.value)} sx={{ width: 120 }} />
              <TextField label={t('logs.llmBaseUrl')} size="small" value={p.base_url}
                onChange={e => updateProvider(i, 'base_url', e.target.value)} sx={{ flex: 1 }} />
              <TextField label={t('logs.llmApiKey')} size="small" type="password" value={p.api_key}
                onChange={e => updateProvider(i, 'api_key', e.target.value)} sx={{ width: 200 }} />
              <TextField label={t('logs.llmModel')} size="small" value={p.model}
                onChange={e => updateProvider(i, 'model', e.target.value)} sx={{ width: 160 }} />
              <IconButton onClick={() => removeProvider(i)} color="error" size="small"><DeleteIcon /></IconButton>
            </Box>
          ))}

          <Button startIcon={<AddIcon />} variant="outlined" size="small" onClick={addProvider}>
            {t('logs.llmAddProvider')}
          </Button>

          {msg && <Alert severity={msg.includes('失败') ? 'error' : 'success'}>{msg}</Alert>}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('common.cancel')}</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving}>
          {saving ? <CircularProgress size={16} /> : null} {t('logs.llmSave')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
