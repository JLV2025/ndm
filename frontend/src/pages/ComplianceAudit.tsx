import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Container, Dialog, DialogContent, DialogTitle,
  DialogActions, IconButton, MenuItem, Paper, Select, Snackbar, Table, TableBody, TableCell,
  TableHead, TableRow, ToggleButton, ToggleButtonGroup, Tooltip, Typography,
} from '@mui/material'
import { AutoAwesome, PlayArrow, Refresh, TrendingDown, TrendingUp } from '@mui/icons-material'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip as RechartsTooltip, XAxis, YAxis,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import { auditApi } from '../services/api'
import BriefingDialog from '../components/BriefingDialog'
import { sessionManager } from '../services/auth'
import { useI18n } from '../i18n'
import type { AuditBriefing, AuditRun, AuditRunDetail, AuditTrendDiff, AuditTrends } from '../types'

/** 与仪表盘一致的图表配色（深色主题） */
const GRID = '#1E293B'
const AXIS_TEXT = '#94A3B8'
/** 折线色板：按系列顺序取；不用红色（审计是建议强度，不是违规等级） */
const PALETTE = ['#2DD46E', '#3B82F6', '#FBBF24', '#C084FC', '#06B6D4', '#FB923C', '#94A3B8']
const DIFF_DOWN = '#5CE68C'   // 收敛
const DIFF_UP = '#FB923C'     // 恶化（橙，沿用"审计不用红"的纪律）

const triggerLabel = (t: (k: string, f?: string) => string, trigger: string) =>
  t(`auditPage.trigger.${trigger}`, trigger)

const fmtTime = (ts: string) => (ts || '').replace('T', ' ').slice(0, 16)

/**
 * 配置审计 —— 全网审计的触发入口与结果主页。
 *
 * 三个区块：最近一次的统计 / 趋势（每周取该周最后一次运行）/ 收敛恶化榜 + 历史运行下钻。
 * 口径：建议数 = 未豁免；已批准例外单列（与例外登记机制一致）。
 */
const ComplianceAudit: React.FC = () => {
  const { t } = useI18n()
  const navigate = useNavigate()

  const [trends, setTrends] = useState<AuditTrends | null>(null)
  const [diff, setDiff] = useState<AuditTrendDiff | null>(null)
  const [runs, setRuns] = useState<AuditRun[]>([])
  const [sites, setSites] = useState<string[]>([])
  const [site, setSite] = useState('')
  const [mode, setMode] = useState<'total' | 'level' | 'source'>('total')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [snack, setSnack] = useState('')
  const [detailId, setDetailId] = useState<number | null>(null)
  const [briefingOpen, setBriefingOpen] = useState(false)
  const [briefingLoading, setBriefingLoading] = useState(false)
  const [briefing, setBriefing] = useState<AuditBriefing | null>(null)
  const [briefingError, setBriefingError] = useState('')

  const load = useCallback(() => {
    setLoading(true); setError('')
    Promise.all([
      auditApi.trends(26, site || undefined),
      auditApi.trendDiff(),
      auditApi.runs(30),
      auditApi.ruleset().catch(() => null),   // 只为拿站点清单
    ]).then(([tr, df, rs, ruleset]) => {
      setTrends(tr); setDiff(df); setRuns(rs.runs || [])
      if (ruleset?.sites) {
        const all = new Set<string>()
        Object.values(ruleset.sites as Record<string, string[]>).forEach(
          (arr) => (arr || []).forEach((s) => all.add(s)))
        setSites([...all].sort())
      }
    }).catch(() => setError(t('auditPage.loadFailed')))
      .finally(() => setLoading(false))
  }, [site, t])

  useEffect(() => {
    if (!sessionManager.getSession()) { navigate('/login'); return }
    load()
  }, [load, navigate])

  const handleRunAll = async () => {
    setRunning(true); setError('')
    try {
      const res = await auditApi.run('manual')
      setSnack(t('auditPage.runDone')
        .replace('{devices}', String(res.device_count))
        .replace('{findings}', String(res.finding_count))
        .replace('{exempt}', String(res.exempt_count)))
      load()
    } catch {
      setError(t('auditPage.runFailed'))
    } finally {
      setRunning(false)
    }
  }

  const openBriefing = async () => {
    setBriefingOpen(true); setBriefing(null); setBriefingError(''); setBriefingLoading(true)
    try {
      setBriefing(await auditApi.briefingNetwork())
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setBriefingError(detail || t('briefing.failed'))
    } finally {
      setBriefingLoading(false)
    }
  }

  const points = trends?.points || []
  const latest = runs[0] || null

  /** 图表数据：档位/来源键加前缀，避免与 total/exempt 撞名 */
  const chartData = useMemo(() => points.map((p) => {
    const row: Record<string, number | string> = { week: p.week, total: p.total, exempt: p.exempt }
    Object.entries(p.counts).forEach(([k, v]) => { row[`lv:${k}`] = v })
    Object.entries(p.by_source).forEach(([k, v]) => { row[`src:${k}`] = v })
    return row
  }), [points])

  const series = useMemo(() => {
    if (mode === 'total') {
      return [
        { key: 'total', name: t('auditPage.suggestions'), color: PALETTE[0] },
        { key: 'exempt', name: t('auditPage.exemptCount'), color: '#94A3B8' },
      ]
    }
    const keys = [...new Set(points.flatMap((p) =>
      Object.keys(mode === 'level' ? p.counts : p.by_source)))]
    return keys.map((k, i) => ({
      key: mode === 'level' ? `lv:${k}` : `src:${k}`, name: k, color: PALETTE[i % PALETTE.length],
    }))
  }, [mode, points, t])

  /** 历史列表：与**更早一次**比，标出标准/豁免是否变过 */
  const historyRows = useMemo(() => runs.map((r, i) => {
    const prev = runs[i + 1]
    return {
      ...r,
      ruleset_changed: !!prev && prev.ruleset_hash !== r.ruleset_hash,
      exceptions_changed: !!prev && (prev.exceptions_hash || '') !== (r.exceptions_hash || ''),
    }
  }), [runs])

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 头部：触发 + 最近一次统计 */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              <span style={{ color: '#2DD46E' }}>{t('auditPage.title')}</span>
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">{t('auditPage.description')}</Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Button variant="contained" size="small" startIcon={<PlayArrow sx={{ fontSize: 16 }} />}
              onClick={handleRunAll} disabled={running} sx={{ fontSize: '0.75rem' }}>
              {running ? t('auditPage.running') : t('auditPage.runAll')}
            </Button>
            <Button size="small" startIcon={<AutoAwesome sx={{ fontSize: 16 }} />}
              onClick={openBriefing} disabled={briefingLoading}
              sx={{ fontSize: '0.75rem' }}>
              {t('briefing.generate')}
            </Button>
            <IconButton onClick={load} title={t('auditPage.title')}><Refresh /></IconButton>
          </Box>
        </Box>

        {latest && (
          <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap', mt: 1.5 }}>
            <Chip size="small" label={`${t('auditPage.latest')}: ${fmtTime(latest.started_at)}`}
              sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(45,212,110,0.1)', color: 'primary.main' }} />
            <Chip size="small" label={triggerLabel(t, latest.trigger)}
              sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(148,163,184,0.1)', color: 'text.secondary' }} />
            <Chip size="small" label={`${t('auditPage.devices')} ${latest.device_count}`}
              sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(148,163,184,0.1)', color: 'text.secondary' }} />
            <Chip size="small" label={`${t('auditPage.suggestions')} ${latest.finding_count - (latest.exempt_count || 0)}`}
              sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(59,130,246,0.12)', color: '#60A5FA' }} />
            <Chip size="small" label={`${t('auditPage.exemptCount')} ${latest.exempt_count || 0}`}
              sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(148,163,184,0.12)', color: 'text.secondary' }} />
            {historyRows[0] && (historyRows[0].ruleset_changed || historyRows[0].exceptions_changed) && (
              <Chip size="small"
                label={`${historyRows[0].ruleset_changed ? '标准' : ''}${historyRows[0].ruleset_changed && historyRows[0].exceptions_changed ? ' / ' : ''}${historyRows[0].exceptions_changed ? '豁免' : ''} ${t('auditPage.changedBadge')}`}
                sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(245,158,11,0.16)', color: '#FBBF24' }} />
            )}
          </Box>
        )}
      </Paper>

      {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <Paper sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Paper>}

      {!loading && (
        <>
          {/* 趋势 */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1, mb: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{t('auditPage.trend')}</Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <ToggleButtonGroup exclusive size="small" value={mode}
                  onChange={(_, v) => { if (v) setMode(v) }}
                  sx={{ '& .MuiToggleButton-root': { px: 1.25, py: 0.25, fontSize: '0.68rem', color: 'text.secondary' } }}>
                  <ToggleButton value="total">{t('auditPage.modeTotal')}</ToggleButton>
                  <ToggleButton value="level">{t('auditPage.modeLevel')}</ToggleButton>
                  <ToggleButton value="source">{t('auditPage.modeSource')}</ToggleButton>
                </ToggleButtonGroup>
                <Select size="small" displayEmpty value={site} onChange={(e) => setSite(e.target.value)}
                  sx={{ minWidth: 130, '& .MuiSelect-select': { py: 0.5, fontSize: '0.72rem' } }}>
                  <MenuItem value="" sx={{ fontSize: '0.72rem' }}>{t('auditPage.allSites')}</MenuItem>
                  {sites.map((s) => <MenuItem key={s} value={s} sx={{ fontSize: '0.72rem' }}>{s}</MenuItem>)}
                </Select>
              </Box>
            </Box>
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 1 }}>
              {t('auditPage.trendHint')}
            </Typography>

            {points.length === 0 ? (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center', fontSize: '0.85rem' }}>
                {t('auditPage.emptyHistory')}
              </Typography>
            ) : (
              <>
                {points.length < 2 && (
                  <Alert severity="info" sx={{ py: 0.25, mb: 1, fontSize: '0.75rem' }}>
                    {t('auditPage.needsTwoWeeks')}
                  </Alert>
                )}
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                    <XAxis dataKey="week" tick={{ fill: AXIS_TEXT, fontSize: 10 }}
                      axisLine={{ stroke: GRID }} tickLine={false} />
                    <YAxis tick={{ fill: AXIS_TEXT, fontSize: 10 }} axisLine={false} tickLine={false} width={44}
                      allowDecimals={false} />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: '#0F1223', border: `1px solid ${GRID}`, borderRadius: 6, fontSize: '0.75rem', color: '#F8FAFC' }}
                      labelStyle={{ color: AXIS_TEXT }} />
                    <Legend wrapperStyle={{ fontSize: '0.65rem', color: AXIS_TEXT }} iconType="line" iconSize={10} />
                    {series.map((s) => (
                      <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color}
                        strokeWidth={2} dot={{ r: 3 }} connectNulls />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </>
            )}
          </Paper>

          {/* 收敛/恶化榜 */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{t('auditPage.diff')}</Typography>
              {diff?.to && (
                <Typography variant="caption" color="text.secondary">
                  {diff.from?.week} → {diff.to.week}
                </Typography>
              )}
              {diff && !diff.reason && (
                <>
                  <Chip size="small" label={t('auditPage.converged').replace('{n}', String(diff.converged))}
                    sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(45,212,110,0.12)', color: DIFF_DOWN }} />
                  <Chip size="small" label={t('auditPage.worsened').replace('{n}', String(diff.worsened))}
                    sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(251,146,60,0.14)', color: DIFF_UP }} />
                </>
              )}
            </Box>
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
              {t('auditPage.diffHint')}
            </Typography>

            {diff?.reason ? (
              <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center', fontSize: '0.82rem' }}>
                {diff.reason}
              </Typography>
            ) : diff && diff.rules.length === 0 ? (
              <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center', fontSize: '0.82rem' }}>
                {t('audit.noFindings')}
              </Typography>
            ) : (
              <Box sx={{ mt: 1, maxHeight: 280, overflow: 'auto' }}>
                {(diff?.rules || []).map((r) => (
                  <Box key={r.rule_id} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                    {r.delta < 0
                      ? <TrendingDown sx={{ fontSize: 16, color: DIFF_DOWN }} />
                      : <TrendingUp sx={{ fontSize: 16, color: DIFF_UP }} />}
                    <Typography variant="body2" sx={{ fontSize: '0.78rem', flex: 1, minWidth: 0 }}>
                      {r.title}
                      <Typography component="span" variant="caption" sx={{ color: 'text.disabled', fontFamily: 'monospace', fontSize: '0.6rem', ml: 0.75 }}>
                        {r.rule_id}
                      </Typography>
                    </Typography>
                    <Chip size="small" label={r.level} sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'rgba(148,163,184,0.1)', color: 'text.secondary' }} />
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.68rem', minWidth: 76, textAlign: 'right' }}>
                      {r.from_count} → {r.to_count}
                    </Typography>
                    <Typography variant="caption" sx={{ color: r.delta < 0 ? DIFF_DOWN : DIFF_UP, fontSize: '0.68rem', minWidth: 52, textAlign: 'right' }}>
                      {r.delta > 0 ? `+${r.delta}` : r.delta} {t('auditPage.devices')}
                    </Typography>
                    {r.exempt_count > 0 && (
                      <Chip size="small" label={`${t('auditPage.exemptCount')} ${r.exempt_count}`}
                        sx={{ height: 18, fontSize: '0.58rem', bgcolor: 'rgba(148,163,184,0.12)', color: 'text.disabled' }} />
                    )}
                  </Box>
                ))}
              </Box>
            )}
          </Paper>

          {/* 历史运行 */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>{t('auditPage.history')}</Typography>
            {historyRows.length === 0 ? (
              <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center', fontSize: '0.82rem' }}>
                {t('auditPage.emptyHistory')}
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {[t('auditPage.colTime'), t('auditPage.colTrigger'), t('auditPage.colDevices'),
                      t('auditPage.colFindings'), t('auditPage.colExempt'), t('auditPage.colHashes')].map((h) => (
                      <TableCell key={h} sx={{ fontSize: '0.68rem', color: 'text.secondary', py: 0.5 }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {historyRows.map((r) => (
                    <TableRow key={r.id} hover onClick={() => setDetailId(r.id)} sx={{ cursor: 'pointer' }}>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.5, fontFamily: 'monospace' }}>{fmtTime(r.started_at)}</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.5 }}>{triggerLabel(t, r.trigger)}</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.5 }}>{r.device_count}</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.5 }}>{r.finding_count - (r.exempt_count || 0)}</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.5 }}>{r.exempt_count || 0}</TableCell>
                      <TableCell sx={{ py: 0.5 }}>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Tooltip title={`ruleset: ${r.ruleset_hash}`}>
                            <Chip size="small" label={`R ${r.ruleset_changed ? t('auditPage.changedBadge') : t('auditPage.unchangedBadge')}`}
                              sx={{ height: 18, fontSize: '0.58rem', bgcolor: r.ruleset_changed ? 'rgba(245,158,11,0.16)' : 'rgba(148,163,184,0.1)', color: r.ruleset_changed ? '#FBBF24' : 'text.disabled' }} />
                          </Tooltip>
                          <Tooltip title={`exceptions: ${r.exceptions_hash || '—'}`}>
                            <Chip size="small" label={`E ${r.exceptions_changed ? t('auditPage.changedBadge') : t('auditPage.unchangedBadge')}`}
                              sx={{ height: 18, fontSize: '0.58rem', bgcolor: r.exceptions_changed ? 'rgba(245,158,11,0.16)' : 'rgba(148,163,184,0.1)', color: r.exceptions_changed ? '#FBBF24' : 'text.disabled' }} />
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Paper>
        </>
      )}

      {detailId != null && <RunDetailDialog runId={detailId} onClose={() => setDetailId(null)} />}

      <BriefingDialog open={briefingOpen} onClose={() => setBriefingOpen(false)}
        loading={briefingLoading} error={briefingError} briefing={briefing}
        title={`${t('briefing.title')} —— ${t('briefing.scopeNetwork')}`} />

      <Snackbar open={!!snack} autoHideDuration={4000} onClose={() => setSnack('')}
        message={snack} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} />
    </Container>
  )
}

/** 单次运行的明细（下钻）：档位/设备筛选在**前端**做 —— 服务端筛选会让选项本身被筛掉。 */
const RunDetailDialog: React.FC<{ runId: number; onClose: () => void }> = ({ runId, onClose }) => {
  const { t } = useI18n()
  const [data, setData] = useState<AuditRunDetail | null>(null)
  const [level, setLevel] = useState('')
  const [device, setDevice] = useState('')

  useEffect(() => {
    auditApi.runDetail(runId).then(setData).catch(() => setData(null))
  }, [runId])

  const all = data?.findings || []
  const levels = useMemo(() => [...new Set(all.map((f) => f.level))], [all])
  const devices = useMemo(() => [...new Set(all.map((f) => f.device_name))].sort(), [all])
  const shown = all.filter((f) => (!level || f.level === level) && (!device || f.device_name === device))

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontSize: '0.95rem' }}>
        {t('auditPage.detail')}
        {data?.run && (
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            #{data.run.id} · {fmtTime(data.run.started_at)} · {triggerLabel(t, data.run.trigger)}
          </Typography>
        )}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
          <Select size="small" displayEmpty value={level} onChange={(e) => setLevel(e.target.value)}
            sx={{ minWidth: 130, '& .MuiSelect-select': { py: 0.5, fontSize: '0.72rem' } }}>
            <MenuItem value="" sx={{ fontSize: '0.72rem' }}>{t('audit.filterLevel')}：{t('audit.all')}</MenuItem>
            {levels.map((lv) => <MenuItem key={lv} value={lv} sx={{ fontSize: '0.72rem' }}>{lv}</MenuItem>)}
          </Select>
          <Select size="small" displayEmpty value={device} onChange={(e) => setDevice(e.target.value)}
            sx={{ minWidth: 170, '& .MuiSelect-select': { py: 0.5, fontSize: '0.72rem' } }}>
            <MenuItem value="" sx={{ fontSize: '0.72rem' }}>{t('auditPage.devices')}：{t('audit.all')}</MenuItem>
            {devices.map((d) => <MenuItem key={d} value={d} sx={{ fontSize: '0.72rem' }}>{d}</MenuItem>)}
          </Select>
          <Typography variant="caption" color="text.disabled" sx={{ alignSelf: 'center' }}>
            {shown.length} / {all.length}
          </Typography>
        </Box>

        {!data ? (
          <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress size={24} /></Box>
        ) : shown.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center', fontSize: '0.82rem' }}>
            {t('auditPage.noFindings')}
          </Typography>
        ) : (
          <Box sx={{ maxHeight: '56vh', overflow: 'auto' }}>
            {shown.map((f, i) => (
              <Box key={`${f.device_name}-${f.rule_id}-${i}`}
                sx={{ py: 0.75, borderBottom: '1px solid', borderColor: 'divider', opacity: f.exempt && f.exempt.status !== 'expired' ? 0.75 : 1 }}>
                <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.68rem', color: 'text.secondary', minWidth: 92 }}>
                    {f.device_name}
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: '0.76rem', flex: 1, minWidth: 0 }}>
                    {f.title}
                    <Typography component="span" variant="caption" sx={{ color: 'text.disabled', fontFamily: 'monospace', fontSize: '0.58rem', ml: 0.75 }}>
                      {f.rule_id}
                    </Typography>
                  </Typography>
                  <Chip size="small" label={f.level}
                    sx={{ height: 17, fontSize: '0.58rem', bgcolor: 'rgba(148,163,184,0.1)', color: 'text.secondary' }} />
                  {f.exempt?.status === 'expired' ? (
                    <Chip size="small" label={t('auditPage.expiredTag')}
                      sx={{ height: 17, fontSize: '0.58rem', bgcolor: 'rgba(245,158,11,0.28)', color: '#FB923C' }} />
                  ) : f.exempt ? (
                    <Chip size="small" label={`${t('auditPage.exemptTag')} ${f.exempt.exception_id}`}
                      sx={{ height: 17, fontSize: '0.58rem', bgcolor: 'rgba(148,163,184,0.12)', color: 'text.disabled' }} />
                  ) : null}
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
      </DialogActions>
    </Dialog>
  )
}

export default ComplianceAudit
