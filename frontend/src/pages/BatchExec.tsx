import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Container, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControlLabel, IconButton, Paper, Snackbar, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { Bolt, Refresh, Stop } from '@mui/icons-material'
import { useLocation, useNavigate } from 'react-router-dom'
import { batchApi, deviceApi } from '../services/api'
import { sessionManager } from '../services/auth'
import LocationFilter from '../components/devices/LocationFilter'
import { useI18n } from '../i18n'
import type { BatchCheckResult, BatchHistoryDetail, BatchRun, Device } from '../types'

/** 执行队列的一项 */
interface QueueItem {
  name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'blocked'
  output: string
  error: string
}

/** 审计页「批量处理」带入的路由 state */
interface FromAudit {
  devices?: string[]
  text?: string
  mode?: 'show' | 'config'
  note?: string
  current?: string      // 设备上的现状（"当前的错误配置"），右侧参照用
}

const STATUS_COLOR: Record<QueueItem['status'], string> = {
  pending: '#94A3B8', running: '#3B82F6', success: '#2DD46E', failed: '#EF5350', blocked: '#FB923C',
}
const statusColor = (s: string) => STATUS_COLOR[s as QueueItem['status']] || '#94A3B8'

const uuid = () => (typeof crypto !== 'undefined' && crypto.randomUUID)
  ? crypto.randomUUID()
  : `b-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`

/**
 * 批量执行 —— 命令下发工具（三层保护：黑名单拦截 / 预览 / 配置模式二次确认）。
 *
 * 编排在**前端**（与采集一致）：逐台调单设备端点，进度实时、可停止；
 * 服务端每次执行前还会再查一次黑名单（绕过前端也拦得住），并逐台落库留痕。
 * 凭据来自登录会话（与采集同一模式），不落盘。
 */
const BatchExec: React.FC = () => {
  const { t } = useI18n()
  const navigate = useNavigate()
  const routeState = (useLocation().state || null) as FromAudit | null

  const [devices, setDevices] = useState<Device[]>([])
  const [location, setLocation] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [text, setText] = useState('')
  const [mode, setMode] = useState<'show' | 'config'>('show')
  const [save, setSave] = useState(false)
  const [note, setNote] = useState('')
  const [check, setCheck] = useState<BatchCheckResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [running, setRunning] = useState(false)
  const [expandedOut, setExpandedOut] = useState('')
  const [history, setHistory] = useState<BatchRun[]>([])
  const [detail, setDetail] = useState<BatchHistoryDetail | null>(null)
  const [snack, setSnack] = useState('')
  const [error, setError] = useState('')
  const [fromAudit, setFromAudit] = useState(false)
  const [fromAuditCurrent, setFromAuditCurrent] = useState('')
  const stopRef = useRef(false)

  const loadHistory = useCallback(() => {
    batchApi.history(20).then((res) => setHistory(res.batches || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sessionManager.getSession()) { navigate('/login'); return }
    deviceApi.list().then((res) => setDevices(res.data || []))
      .catch(() => setError(t('batch.loadFailed')))
    loadHistory()
    // 从审计页「批量处理」带入：设备清单 + 修复命令 + 现状（供参照）
    if (routeState?.devices?.length) {
      setSelected(routeState.devices)
      if (routeState.text) setText(routeState.text)
      if (routeState.mode) setMode(routeState.mode)
      setNote(routeState.note || '')
      setFromAuditCurrent(routeState.current || '')
      setFromAudit(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 命令 / 模式变了 → 旧预检作废（必须重新预检才能执行）
  useEffect(() => { setCheck(null) }, [text, mode])

  const locations = useMemo(
    () => [...new Set(devices.map((d) => d.location || '').filter(Boolean))].sort(), [devices])

  const shown = useMemo(() => devices.filter((d) => {
    if (location && d.location !== location) return false
    if (search) {
      const q = search.toLowerCase()
      return d.name.toLowerCase().includes(q) || (d.ip || '').includes(q)
    }
    return true
  }), [devices, location, search])

  const toggleOne = (name: string) => setSelected((prev) =>
    prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name])

  const toggleAllShown = () => setSelected((prev) => {
    const names = shown.map((d) => d.name)
    const allIn = names.every((n) => prev.includes(n))
    return allIn ? prev.filter((n) => !names.includes(n)) : [...new Set([...prev, ...names])]
  })

  const doCheck = async () => {
    setChecking(true); setError('')
    try {
      const res = await batchApi.check(text)
      setCheck(res)
    } catch {
      setError(t('batch.loadFailed'))
    } finally {
      setChecking(false)
    }
  }

  const handleStartClick = () => {
    if (mode === 'config') setConfirmOpen(true)     // 配置变更必须二次确认
    else void startExec()
  }

  const startExec = async () => {
    setConfirmOpen(false)
    const session = sessionManager.getSession()
    if (!session) { navigate('/login'); return }
    const batchId = uuid()
    const targets = [...selected]
    stopRef.current = false
    setRunning(true)
    setQueue(targets.map((n) => ({ name: n, status: 'pending', output: '', error: '' })))

    for (const name of targets) {
      if (stopRef.current) break
      setQueue((q) => q.map((it) => it.name === name ? { ...it, status: 'running' } : it))
      try {
        const res = await batchApi.execute({
          device_name: name, username: session.username, password: session.password,
          text, mode, save: mode === 'config' && save, batch_id: batchId,
          total: targets.length, note,
        })
        setQueue((q) => q.map((it) => it.name === name
          ? { ...it, status: res.status, output: res.output, error: res.error } : it))
      } catch (e) {
        const msg = e instanceof Error ? e.message : t('batch.loadFailed')
        setQueue((q) => q.map((it) => it.name === name
          ? { ...it, status: 'failed', error: msg } : it))
      }
    }
    setRunning(false)
    if (stopRef.current) setSnack(t('batch.stopped'))
    loadHistory()
  }

  const openDetail = async (batchId: string) => {
    try { setDetail(await batchApi.historyDetail(batchId)) } catch { /* 已删除等 */ }
  }

  const removeBatch = async (batchId: string) => {
    if (!window.confirm(t('batch.deleteConfirm'))) return
    await batchApi.remove(batchId)
    setDetail(null)
    loadHistory()
  }

  const cmdLines = (check?.commands || []).length
  const canRun = !running && !!check && check.blocked.length === 0
    && cmdLines > 0 && selected.length > 0
  const allShownSelected = shown.length > 0 && shown.every((d) => selected.includes(d.name))

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 头部 */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          <Bolt sx={{ color: 'primary.main' }} />
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{t('batch.title')}</Typography>
          <Box sx={{ flex: 1 }} />
          <IconButton onClick={loadHistory} size="small"><Refresh fontSize="small" /></IconButton>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {t('batch.hint')}
        </Typography>
        {error && <Alert severity="error" sx={{ mt: 1.5 }} onClose={() => setError('')}>{error}</Alert>}
        {fromAudit && (
          <Alert severity="info" sx={{ mt: 1.5 }} onClose={() => setFromAudit(false)}>
            {t('batch.fromAudit').replace('{n}', String(routeState?.devices?.length || 0))}
          </Alert>
        )}
      </Paper>

      {/* 1. 选择设备 */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', mb: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{t('batch.stepDevices')}</Typography>
          <LocationFilter selectedLocation={location} onChange={setLocation} locations={locations} />
          <Box sx={{ flex: 1 }} />
          <TextField size="small" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('batch.searchPlaceholder')} sx={{ width: 220 }} />
        </Box>
        <TableContainer sx={{ maxHeight: 300 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox size="small" checked={allShownSelected} onChange={toggleAllShown} />
                </TableCell>
                {[t('batch.colDevice'), t('batch.colModel'), t('batch.colLocation'), t('batch.colIp')]
                  .map((h) => (
                    <TableCell key={h} sx={{ fontSize: '0.7rem', color: 'text.secondary', py: 0.5 }}>{h}</TableCell>
                  ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {shown.map((d) => (
                <TableRow key={d.name} hover sx={{ cursor: 'pointer' }}
                  onClick={() => toggleOne(d.name)}>
                  <TableCell padding="checkbox">
                    <Checkbox size="small" checked={selected.includes(d.name)}
                      onChange={() => toggleOne(d.name)} onClick={(e) => e.stopPropagation()} />
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.72rem' }}>{d.name}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{d.model || '—'}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{d.location || '—'}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary', fontFamily: 'monospace' }}>{d.ip}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 1 }}>
          <Chip size="small" color={selected.length ? 'primary' : 'default'} variant="outlined"
            label={t('batch.selectedN').replace('{n}', String(selected.length))} />
          <Button size="small" onClick={() => setSelected([])} disabled={!selected.length}>
            {t('batch.clear')}
          </Button>
        </Box>
      </Paper>

      {/* 2. 命令 */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>{t('batch.stepCommands')}</Typography>
        <ToggleButtonGroup exclusive size="small" value={mode}
          onChange={(_, v) => v && setMode(v)} sx={{ mb: 1.5 }}>
          <ToggleButton value="show" sx={{ fontSize: '0.72rem', textTransform: 'none', px: 2 }}>
            {t('batch.modeShow')}
          </ToggleButton>
          <ToggleButton value="config" sx={{ fontSize: '0.72rem', textTransform: 'none', px: 2 }}>
            {t('batch.modeConfig')}
          </ToggleButton>
        </ToggleButtonGroup>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: { xs: 'wrap', md: 'nowrap' }, alignItems: 'stretch' }}>
          <TextField fullWidth multiline rows={6} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={t('batch.commandPlaceholder')}
            sx={{ flex: '1 1 50%', '& textarea': { fontSize: '0.8rem' } }} />
          {/* 设备当前配置（带入的现状）—— 对着它把左侧命令里的占位符填成实际值 */}
          <Box sx={{
            flex: '1 1 50%', minWidth: 260, border: '1px solid', borderColor: 'divider',
            borderRadius: 1, p: 1.25, bgcolor: 'rgba(148,163,184,0.04)',
          }}>
            <Typography variant="caption" color="text.secondary"
              sx={{ display: 'block', mb: 0.5, fontWeight: 700 }}>
              {t('batch.currentTitle')}
            </Typography>
            {fromAuditCurrent ? (
              <Box component="pre" sx={{
                m: 0, fontSize: '0.72rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap',
                color: '#FB923C', maxHeight: 136, overflow: 'auto',
              }}>{fromAuditCurrent}</Box>
            ) : (
              <Typography variant="caption" color="text.disabled">{t('batch.currentHint')}</Typography>
            )}
          </Box>
        </Box>
        {mode === 'config' && (
          <Box sx={{ mt: 1 }}>
            <FormControlLabel control={
              <Checkbox size="small" checked={save} onChange={(e) => setSave(e.target.checked)} />
            } label={<Typography variant="body2">{t('batch.saveConfig')}</Typography>} />
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', ml: 4 }}>
              {t('batch.saveHint')}
            </Typography>
          </Box>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 1.5, flexWrap: 'wrap' }}>
          <Button variant="outlined" size="small" onClick={doCheck}
            disabled={checking || !text.trim()}>
            {checking ? <CircularProgress size={14} sx={{ mr: 1 }} /> : null}
            {t('batch.check')}
          </Button>
          <Button variant="contained" size="small" startIcon={<Bolt />}
            disabled={!canRun} onClick={handleStartClick}>
            {t('batch.start')}
          </Button>
          {running && (
            <Button size="small" color="warning" startIcon={<Stop />}
              onClick={() => { stopRef.current = true }}>
              {t('batch.stop')}
            </Button>
          )}
          {check && check.blocked.length === 0 && (
            <Typography variant="body2" sx={{ color: 'success.main', fontSize: '0.76rem' }}>
              {t('batch.willRun').replace('{n}', String(selected.length)).replace('{m}', String(cmdLines))}
            </Typography>
          )}
          {!check && text.trim() && (
            <Typography variant="caption" color="text.disabled">{t('batch.needCheck')}</Typography>
          )}
        </Box>
        {check && check.blocked.length > 0 && (
          <Alert severity="error" sx={{ mt: 1.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>{t('batch.blockedTitle')}</Typography>
            {check.blocked.map((b) => (
              <Typography key={b.cmd} variant="caption" sx={{ display: 'block', fontFamily: 'monospace' }}>
                {b.cmd} —— {b.reason}
              </Typography>
            ))}
          </Alert>
        )}
        {check && check.warnings.length > 0 && (
          <Alert severity="warning" sx={{ mt: 1.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>{t('batch.warnTitle')}</Typography>
            {check.warnings.map((w) => (
              <Typography key={w.cmd} variant="caption" sx={{ display: 'block', fontFamily: 'monospace' }}>
                {w.cmd} —— {w.reason}
              </Typography>
            ))}
          </Alert>
        )}
      </Paper>

      {/* 3. 执行队列 */}
      {queue.length > 0 && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{t('batch.stepRun')}</Typography>
            {running && <CircularProgress size={14} />}
          </Box>
          <Table size="small">
            <TableHead>
              <TableRow>
                {[t('batch.colDevice'), t('batch.colStatus'), t('batch.colResult')].map((h) => (
                  <TableCell key={h} sx={{ fontSize: '0.7rem', color: 'text.secondary', py: 0.5 }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {queue.map((it) => (
                <React.Fragment key={it.name}>
                  <TableRow hover sx={{ cursor: 'pointer' }}
                    onClick={() => setExpandedOut(expandedOut === it.name ? '' : it.name)}>
                    <TableCell sx={{ fontSize: '0.72rem' }}>{it.name}</TableCell>
                    <TableCell>
                      <Chip size="small" label={t(`batch.status.${it.status}`)}
                        sx={{
                          height: 20, fontSize: '0.64rem', fontWeight: 700,
                          bgcolor: `${STATUS_COLOR[it.status]}22`, color: STATUS_COLOR[it.status],
                        }} />
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.72rem' }}>
                      {it.error
                        ? <Typography variant="caption" sx={{ color: it.status === 'blocked' ? '#FB923C' : '#EF5350' }}>
                            {it.error}</Typography>
                        : <Typography variant="caption" color="text.disabled">
                            {it.status === 'success' ? t('batch.clickForOutput') : '—'}</Typography>}
                    </TableCell>
                  </TableRow>
                  {expandedOut === it.name && (
                    <TableRow>
                      <TableCell colSpan={3} sx={{ py: 0, border: 0 }}>
                        <Box component="pre" sx={{
                          m: 1, p: 1.5, maxHeight: 320, overflow: 'auto', fontSize: '0.72rem',
                          bgcolor: 'rgba(148,163,184,0.06)', borderRadius: 1, whiteSpace: 'pre-wrap',
                        }}>
                          {it.output || t('batch.noOutput')}
                        </Box>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}

      {/* 历史记录 */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>{t('batch.history')}</Typography>
        {history.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center', fontSize: '0.82rem' }}>
            {t('batch.historyEmpty')}
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                {[t('batch.colTime'), t('batch.colOperator'), t('batch.colMode'),
                  t('batch.colOutcome'), t('batch.colProgress'), t('batch.colNote')].map((h) => (
                  <TableCell key={h} sx={{ fontSize: '0.7rem', color: 'text.secondary', py: 0.5 }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((b) => (
                <TableRow key={b.batch_id} hover sx={{ cursor: 'pointer' }}
                  onClick={() => openDetail(b.batch_id)}>
                  <TableCell sx={{ fontSize: '0.72rem' }}>{(b.created_at || '').replace('T', ' ').slice(0, 16)}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem' }}>{b.username}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem' }}>
                    {b.mode === 'config'
                      ? <Chip size="small" label={t('batch.modeConfigShort') + (b.save_config ? ' + save' : '')}
                          sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'rgba(251,146,60,0.15)', color: '#FB923C' }} />
                      : <Chip size="small" label={t('batch.modeShowShort')}
                          sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'rgba(148,163,184,0.12)', color: 'text.secondary' }} />}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.72rem' }}>
                    {t('batch.successN').replace('{n}', String(b.success_count ?? 0))}
                    {(b.failed_count ?? 0) > 0 && (
                      <Typography component="span" variant="caption" sx={{ color: '#FB923C', ml: 0.75 }}>
                        {t('batch.failedN').replace('{n}', String(b.failed_count))}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.disabled' }}>
                    {b.done_count}/{b.device_count || b.done_count}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.68rem', color: 'text.disabled', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {b.note || '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      {/* 配置变更二次确认 */}
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 700 }}>{t('batch.confirmTitle')}</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 1.5 }}>
            {t('batch.confirmConfig').replace('{n}', String(selected.length))}
          </Alert>
          <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 700 }}>{t('batch.confirmDevices')}</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
            {selected.map((n) => <Chip key={n} size="small" label={n} sx={{ height: 20, fontSize: '0.66rem' }} />)}
          </Box>
          <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 700 }}>{t('batch.confirmCommands')}</Typography>
          <Box component="pre" sx={{
            p: 1.5, bgcolor: 'rgba(148,163,184,0.06)', borderRadius: 1, fontSize: '0.74rem',
            whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto',
          }}>{text}</Box>
          <Typography variant="caption" sx={{ display: 'block', mt: 1, color: save ? '#2DD46E' : 'text.disabled' }}>
            {save ? t('batch.confirmSaveOn') : t('batch.confirmSaveOff')}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>{t('batch.cancel')}</Button>
          <Button variant="contained" color="warning" onClick={() => void startExec()}>
            {t('batch.confirm')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 历史详情 */}
      <Dialog open={!!detail} onClose={() => setDetail(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 700 }}>
          {t('batch.detail')}
          {detail && (
            <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1.5 }}>
              {(detail.batch.created_at || '').replace('T', ' ').slice(0, 16)} · {detail.batch.username}
            </Typography>
          )}
        </DialogTitle>
        <DialogContent>
          {detail && (
            <>
              <Box component="pre" sx={{
                p: 1.5, bgcolor: 'rgba(148,163,184,0.06)', borderRadius: 1, fontSize: '0.74rem',
                whiteSpace: 'pre-wrap', maxHeight: 160, overflow: 'auto',
              }}>{detail.batch.command_text}</Box>
              <Table size="small" sx={{ mt: 1.5 }}>
                <TableBody>
                  {detail.results.map((r) => (
                    <TableRow key={r.device_name}>
                      <TableCell sx={{ fontSize: '0.72rem', verticalAlign: 'top', width: 150 }}>
                        {r.device_name}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', verticalAlign: 'top', width: 90 }}>
                        <Chip size="small" label={t(`batch.status.${r.status}`)}
                          sx={{
                            height: 18, fontSize: '0.6rem',
                            bgcolor: `${statusColor(r.status)}22`, color: statusColor(r.status),
                          }} />
                      </TableCell>
                      <TableCell>
                        {r.error && <Typography variant="caption" sx={{ color: '#EF5350', display: 'block' }}>{r.error}</Typography>}
                        {r.output && (
                          <Box component="pre" sx={{
                            m: 0, fontSize: '0.7rem', whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto',
                          }}>{r.output}</Box>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </DialogContent>
        <DialogActions>
          {detail && (
            <Button color="error" size="small" onClick={() => void removeBatch(detail.batch.batch_id)}>
              {t('batch.delete')}
            </Button>
          )}
          <Button onClick={() => setDetail(null)}>{t('batch.close')}</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!snack} autoHideDuration={4000} onClose={() => setSnack('')}
        message={snack} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} />
    </Container>
  )
}

export default BatchExec
