import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Box, Container, Paper, Typography, Chip, TextField, MenuItem, Select,
  CircularProgress, Alert, Switch, IconButton, Button, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogActions, Snackbar, Tabs, Tab,
} from '@mui/material'
import { Add, Autorenew, Block, Edit, Refresh, Rule, Save } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import { auditApi } from '../services/api'
import { sessionManager } from '../services/auth'
import type { AuditException, AuditExceptionsResponse, AuditRule, AuditRuleset } from '../types'
import { useI18n } from '../i18n'
import AuditExceptionDialog, { httpDetail } from '../components/AuditExceptionDialog'

/** 档位 → 配色，与查看器审计模式保持一致（刻意不用红色系：这是建议强度不是违规等级） */
const LEVEL_COLORS: Record<string, { bg: string; text: string }> = {
  '强烈建议': { bg: 'rgba(245,158,11,0.14)', text: '#FBBF24' },
  '风险提示': { bg: 'rgba(168,85,247,0.14)', text: '#C084FC' },
  '改进建议': { bg: 'rgba(59,130,246,0.12)', text: '#60A5FA' },
  '可选优化': { bg: 'rgba(148,163,184,0.12)', text: '#94A3B8' },
  '需人工判断': { bg: 'rgba(45,212,110,0.10)', text: '#5CE68C' },
}
const levelColor = (lv: string) => LEVEL_COLORS[lv] || LEVEL_COLORS['改进建议']

/** 来源 → 层级色（层优先级：公司总部 > 厂商基线 > 组织规范） */
const SOURCE_COLORS: Record<string, string> = {
  '公司总部': '#F59E0B',
  '厂商基线': '#3B82F6',
  '组织规范': '#94A3B8',
}

const ComplianceStandard: React.FC = () => {
  const { t } = useI18n()
  const navigate = useNavigate()

  const [ruleset, setRuleset] = useState<AuditRuleset | null>(null)
  const [tab, setTab] = useState<'rules' | 'exceptions'>('rules')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterSource, setFilterSource] = useState('')
  const [filterLevel, setFilterLevel] = useState('')
  const [filterPlatform, setFilterPlatform] = useState('')
  const [keyword, setKeyword] = useState('')
  const [editing, setEditing] = useState<AuditRule | null>(null)
  const [snack, setSnack] = useState('')

  const load = useCallback(() => {
    setLoading(true); setError('')
    auditApi.ruleset()
      .then(setRuleset)
      .catch(() => setError(t('auditRules.loadFailed')))
      .finally(() => setLoading(false))
  }, [t])

  useEffect(() => {
    if (!sessionManager.getSession()) { navigate('/login'); return }
    load()
  }, [])

  const rules = ruleset?.rules || []

  const shown = useMemo(() => rules.filter((r) =>
    (!filterSource || r.source === filterSource)
    && (!filterLevel || r.level === filterLevel)
    && (!filterPlatform || r.platforms.includes(filterPlatform))
    && (!keyword || r.id.includes(keyword) || r.title.includes(keyword)
        || r.why.includes(keyword) || r.fix.includes(keyword))),
    [rules, filterSource, filterLevel, filterPlatform, keyword])

  /** 按层分组展示 —— 层优先级就是分组顺序 */
  const grouped = useMemo(() => {
    const order = Object.entries(ruleset?.layer_priority || {}).sort((a, b) => a[1] - b[1]).map(([k]) => k)
    const m = new Map<string, AuditRule[]>()
    for (const s of order) m.set(s, [])
    for (const r of shown) {
      if (!m.has(r.source)) m.set(r.source, [])
      m.get(r.source)!.push(r)
    }
    return [...m.entries()].filter(([, v]) => v.length > 0)
  }, [shown, ruleset])

  const save = useCallback(async (rule: AuditRule, patch: Record<string, unknown>) => {
    try {
      await auditApi.updateRule(rule.id, patch)
      setSnack(t('auditRules.saved'))
      setEditing(null)
      load()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSnack(detail || t('auditRules.saveFailed'))
    }
  }, [load, t])

  const handleToggle = (rule: AuditRule) => {
    if (rule.enabled) {
      // 停用必须写明原因 —— 直接打开对话框，而不是静默关掉
      setEditing({ ...rule, enabled: false })
    } else {
      save(rule, { enabled: true })
    }
  }

  const counts = useMemo(() => ({
    total: rules.length,
    off: rules.filter((r) => !r.enabled).length,
  }), [rules])

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              <span style={{ color: '#2DD46E' }}>{t('auditRules.title')}</span>
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">{t('auditRules.description')}</Typography>
            <Box sx={{ display: 'flex', gap: 0.5, mt: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <Chip size="small" label={t('auditRules.priority')}
                sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(45,212,110,0.1)', color: 'primary.main' }} />
              {ruleset && (
                <Chip size="small" label={`${t('audit.configHash').replace('配置', '规则集')}: ${ruleset.ruleset_hash}`}
                  sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(148,163,184,0.1)', color: 'text.secondary' }} />
              )}
              <Chip size="small" label={t('auditRules.totalRules').replace('{n}', String(counts.total))}
                sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(148,163,184,0.1)', color: 'text.secondary' }} />
              {counts.off > 0 && (
                <Chip size="small" label={`${t('auditRules.disabled')} ${counts.off}`}
                  sx={{ height: 20, fontSize: '0.62rem', bgcolor: 'rgba(148,163,184,0.15)', color: 'text.disabled' }} />
              )}
            </Box>
          </Box>
          <IconButton onClick={load} title={t('audit.run')}><Refresh /></IconButton>
        </Box>
      </Paper>

      <Paper sx={{ px: 2, mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ minHeight: 40 }}>
          <Tab value="rules" label={`${t('exceptions.tabRules')}（${counts.total}）`}
            sx={{ minHeight: 40, fontSize: '0.78rem' }} />
          <Tab value="exceptions" label={t('exceptions.tab')} sx={{ minHeight: 40, fontSize: '0.78rem' }} />
        </Tabs>
      </Paper>

      {tab === 'rules' && (<>
      <Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField size="small" placeholder={t('auditRules.fieldTitle')} value={keyword}
          onChange={(e) => setKeyword(e.target.value)} sx={{ minWidth: 220 }} />
        <Select size="small" displayEmpty value={filterSource} onChange={(e) => setFilterSource(e.target.value)} sx={{ minWidth: 150 }}>
          <MenuItem value="">{t('audit.filterSource')}：{t('audit.all')}</MenuItem>
          {(ruleset?.layer_priority ? Object.keys(ruleset.layer_priority) : []).map((s) => (
            <MenuItem key={s} value={s}>{s}</MenuItem>
          ))}
        </Select>
        <Select size="small" displayEmpty value={filterLevel} onChange={(e) => setFilterLevel(e.target.value)} sx={{ minWidth: 140 }}>
          <MenuItem value="">{t('audit.filterLevel')}：{t('audit.all')}</MenuItem>
          {(ruleset?.levels || []).map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
        </Select>
        <Select size="small" displayEmpty value={filterPlatform} onChange={(e) => setFilterPlatform(e.target.value)} sx={{ minWidth: 130 }}>
          <MenuItem value="">平台：{t('audit.all')}</MenuItem>
          {(ruleset?.platforms || []).map((p) => <MenuItem key={p} value={p}>{p}</MenuItem>)}
        </Select>
      </Paper>

      {loading && <Paper sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Paper>}
      {error && <Alert severity="warning">{error}</Alert>}

      {!loading && grouped.map(([source, list]) => (
        <Box key={source} sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Box sx={{ width: 3, height: 16, bgcolor: SOURCE_COLORS[source] || '#64748B', borderRadius: 1 }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{source}</Typography>
            <Typography variant="caption" color="text.secondary">{list.length}</Typography>
          </Box>

          {list.map((r) => {
            const c = levelColor(r.level)
            return (
              <Paper key={r.id} sx={{ p: 1.5, mb: 0.75, display: 'flex', gap: 1.5, alignItems: 'flex-start',
                                       opacity: r.enabled ? 1 : 0.5 }}>
                <Tooltip title={r.enabled ? t('auditRules.disabled') : t('auditRules.enabled')}>
                  <Switch size="small" checked={r.enabled} onChange={() => handleToggle(r)} sx={{ mt: -0.5 }} />
                </Tooltip>

                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap', mb: 0.25 }}>
                    <Chip size="small" label={r.level}
                      sx={{ height: 18, fontSize: '0.6rem', bgcolor: c.bg, color: c.text }} />
                    <Chip size="small" variant="outlined" label={r.platforms.join('/')}
                      sx={{ height: 18, fontSize: '0.6rem', color: 'text.secondary', borderColor: 'divider' }} />
                    {r.severity && (
                      <Chip size="small" variant="outlined" label={r.severity}
                        sx={{ height: 18, fontSize: '0.6rem', color: 'text.disabled', borderColor: 'divider' }} />
                    )}
                    <Typography variant="caption" sx={{ color: 'text.disabled', fontFamily: '"Fira Code", monospace', fontSize: '0.62rem' }}>
                      {r.id}
                    </Typography>
                    {!r.enabled && (
                      <Tooltip title={r.superseded_by || r.disabled_reason || ''}>
                        <Chip size="small" label={t('auditRules.disabled')}
                          sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'rgba(148,163,184,0.15)', color: 'text.disabled' }} />
                      </Tooltip>
                    )}
                    {r.controls.length > 0 && (
                      <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.58rem' }}>
                        {r.controls.join(', ')}
                      </Typography>
                    )}
                    <Typography variant="caption" sx={{ color: 'text.disabled', ml: 'auto', fontSize: '0.58rem' }}>
                      {r.source_file}
                    </Typography>
                  </Box>
                  <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{r.title}</Typography>
                  {r.why && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                      {r.why.length > 160 ? r.why.slice(0, 160) + '…' : r.why}
                    </Typography>
                  )}
                  {r.note && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.25, color: 'warning.main', fontSize: '0.62rem' }}>
                      {t('audit.note')}：{r.note.length > 120 ? r.note.slice(0, 120) + '…' : r.note}
                    </Typography>
                  )}
                </Box>

                <IconButton size="small" onClick={() => setEditing(r)} title={t('auditRules.edit')}>
                  <Edit sx={{ fontSize: 16 }} />
                </IconButton>
              </Paper>
            )
          })}
        </Box>
      ))}

      {!loading && shown.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Rule sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography color="text.secondary">{t('audit.noFindings')}</Typography>
        </Paper>
      )}
      </>)}

      {tab === 'exceptions' && <ExceptionsPanel />}

      {editing && (
        <RuleEditDialog rule={editing} levels={ruleset?.levels || []} t={t}
          onClose={() => setEditing(null)} onSave={(patch) => save(editing, patch)} />
      )}

      <Snackbar open={!!snack} autoHideDuration={3000} onClose={() => setSnack('')}
        message={snack} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} />
    </Container>
  )
}

/** 规则编辑对话框 —— 停用规则时强制填写原因（后端也会校验，这里提前拦） */
const RuleEditDialog: React.FC<{
  rule: AuditRule
  levels: string[]
  t: (key: string, fallback?: string) => string
  onClose: () => void
  onSave: (patch: Record<string, unknown>) => void
}> = ({ rule, levels, t, onClose, onSave }) => {
  const [enabled, setEnabled] = useState(rule.enabled)
  const [level, setLevel] = useState(rule.level)
  const [title, setTitle] = useState(rule.title)
  const [fix, setFix] = useState(rule.fix)
  const [why, setWhy] = useState(rule.why)
  const [note, setNote] = useState(rule.note)
  const [supersededBy, setSupersededBy] = useState(rule.superseded_by || '')
  const [disabledReason, setDisabledReason] = useState(rule.disabled_reason || '')

  const needReason = !enabled && !supersededBy.trim() && !disabledReason.trim()
  const [touched, setTouched] = useState(false)

  const submit = () => {
    setTouched(true)
    if (needReason) return
    const patch: Record<string, unknown> = {}
    if (enabled !== rule.enabled) patch.enabled = enabled
    if (level !== rule.level) patch.level = level
    if (title !== rule.title) patch.title = title
    if (fix !== rule.fix) patch.fix = fix
    if (why !== rule.why) patch.why = why
    if (note !== rule.note) patch.note = note
    if (supersededBy !== (rule.superseded_by || '')) patch.superseded_by = supersededBy
    if (disabledReason !== (rule.disabled_reason || '')) patch.disabled_reason = disabledReason
    if (Object.keys(patch).length === 0) { onClose(); return }
    onSave(patch)
  }

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontSize: '1rem', fontFamily: '"Fira Code", monospace' }}>{rule.id}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2">{t('auditRules.enabled')}</Typography>
          <Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        </Box>

        {!enabled && (
          <Alert severity="warning" sx={{ py: 0.5 }}>{t('auditRules.disableNeedsReason')}</Alert>
        )}

        <TextField size="small" label={t('auditRules.fieldTitle')} value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
        <Select size="small" value={level} onChange={(e) => setLevel(e.target.value)}>
          {levels.map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
        </Select>

        {!enabled && (
          <>
            <TextField size="small" value={supersededBy} onChange={(e) => setSupersededBy(e.target.value)}
              label={t('auditRules.supersededBy')} fullWidth
              error={touched && needReason} />
            <TextField size="small" value={disabledReason} onChange={(e) => setDisabledReason(e.target.value)}
              label={t('auditRules.disabledReason')} fullWidth multiline minRows={2}
              error={touched && needReason} />
          </>
        )}

        <TextField size="small" label={t('auditRules.fieldFix')} value={fix} onChange={(e) => setFix(e.target.value)} fullWidth multiline minRows={3} />
        <TextField size="small" label={t('auditRules.fieldWhy')} value={why} onChange={(e) => setWhy(e.target.value)} fullWidth multiline minRows={3} />
        <TextField size="small" label={t('auditRules.fieldNote')} value={note} onChange={(e) => setNote(e.target.value)} fullWidth multiline minRows={2} />

        <Typography variant="caption" color="text.disabled">
          {rule.severity && <>severity: {rule.severity}　</>}
          {rule.controls.length > 0 && <>{t('audit.controls')}: {rule.controls.join(', ')}　</>}
          文件: {rule.source_file}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" startIcon={<Save sx={{ fontSize: 16 }} />} onClick={submit}
          disabled={touched && needReason}>
          {t('auditRules.save')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

/** 例外状态 → 配色。延续"审计不用红色系"的纪律：已过期用橙色（是提醒，不是违规） */
const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  active: { bg: 'rgba(45,212,110,0.12)', text: '#5CE68C' },
  expiring: { bg: 'rgba(245,158,11,0.16)', text: '#FBBF24' },
  expired: { bg: 'rgba(245,158,11,0.28)', text: '#FB923C' },
  revoked: { bg: 'rgba(148,163,184,0.15)', text: '#94A3B8' },
}

/**
 * 例外登记面板 —— 列表 + 新增/续期/撤销。
 *
 * 默认只显示「生效中（含即将到期）」：这页是给复核用的，
 * 已过期/已撤销属于历史，切筛选才看（但它们不会消失，历史审计要能追溯）。
 */
const ExceptionsPanel: React.FC = () => {
  const { t } = useI18n()
  const [data, setData] = useState<AuditExceptionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('open')
  const [creating, setCreating] = useState(false)
  const [renewing, setRenewing] = useState<AuditException | null>(null)
  const [revoking, setRevoking] = useState<AuditException | null>(null)
  const [snack, setSnack] = useState('')

  const load = useCallback(() => {
    setLoading(true); setError('')
    auditApi.exceptions()
      .then(setData)
      .catch(() => setError(t('exceptions.loadFailed')))
      .finally(() => setLoading(false))
  }, [t])

  useEffect(() => { load() }, [load])

  const all = data?.exceptions || []
  const shown = all.filter((e) => {
    if (filter === 'all') return true
    if (filter === 'open') return e.status === 'active' || e.status === 'expiring'
    return e.status === filter
  })

  const statusLabel = (s: string) => t(`exceptions.status.${s}`)
  const expiryText = (e: AuditException) => {
    if (e.days_left === null || e.status === 'revoked') return ''
    return e.days_left < 0
      ? t('exceptions.expiredAgo').replace('{n}', String(-e.days_left))
      : t('exceptions.daysLeft').replace('{n}', String(e.days_left))
  }

  return (
    <>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <Button size="small" variant="contained" startIcon={<Add sx={{ fontSize: 16 }} />}
          onClick={() => setCreating(true)} sx={{ fontSize: '0.72rem' }}>
          {t('exceptions.add')}
        </Button>
        <Select size="small" value={filter} onChange={(e) => setFilter(e.target.value)}
          sx={{ minWidth: 190, '& .MuiSelect-select': { py: 0.5, fontSize: '0.72rem' } }}>
          <MenuItem value="open" sx={{ fontSize: '0.72rem' }}>{t('exceptions.filter.open')}</MenuItem>
          <MenuItem value="all" sx={{ fontSize: '0.72rem' }}>{t('exceptions.filter.all')}</MenuItem>
          {['active', 'expiring', 'expired', 'revoked'].map((s) => (
            <MenuItem key={s} value={s} sx={{ fontSize: '0.72rem' }}>{statusLabel(s)}</MenuItem>
          ))}
        </Select>
        <Typography variant="caption" color="text.secondary" sx={{ flex: 1, minWidth: 260 }}>
          {t('exceptions.note')}
        </Typography>
      </Box>

      {loading && <Paper sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Paper>}
      {error && <Alert severity="warning">{error}</Alert>}

      {!loading && shown.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">{t('exceptions.empty')}</Typography>
        </Paper>
      )}

      {!loading && shown.map((e) => {
        const c = STATUS_COLORS[e.status] || STATUS_COLORS.revoked
        const scopeText = e.scope.type === 'all'
          ? t('exceptions.scope.all')
          : `${t(`exceptions.scope.${e.scope.type}`)}: ${e.scope.value}`
        return (
          <Paper key={e.id} sx={{ p: 1.5, mb: 0.75, display: 'flex', gap: 1.5, alignItems: 'flex-start',
                                   opacity: e.status === 'revoked' ? 0.6 : 1 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap', mb: 0.25 }}>
                <Chip size="small" label={statusLabel(e.status)}
                  sx={{ height: 18, fontSize: '0.6rem', bgcolor: c.bg, color: c.text }} />
                <Chip size="small" variant="outlined" label={scopeText}
                  sx={{ height: 18, fontSize: '0.6rem', color: 'text.secondary', borderColor: 'divider' }} />
                <Typography variant="caption" sx={{ color: 'text.disabled', fontFamily: '"Fira Code", monospace', fontSize: '0.62rem' }}>
                  {e.id}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.disabled', ml: 'auto', fontSize: '0.62rem' }}>
                  {t('exceptions.approvedBy')}: {e.approved_by} · {e.approved_at} → {e.expires_at}
                  {expiryText(e) && `（${expiryText(e)}）`}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.78rem' }}>
                {e.rule_title || e.rule_id}
                <Typography component="span" variant="caption"
                  sx={{ color: 'text.disabled', fontFamily: '"Fira Code", monospace', fontSize: '0.62rem', ml: 0.75 }}>
                  {e.rule_id}
                </Typography>
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                {e.reason}
              </Typography>
              {e.compensating_control && (
                <Typography variant="caption" sx={{ display: 'block', color: 'text.disabled', mt: 0.25 }}>
                  {t('exceptions.compensating')}：{e.compensating_control}
                </Typography>
              )}
              {e.revoked && (
                <Typography variant="caption" sx={{ display: 'block', color: 'text.disabled', mt: 0.25 }}>
                  {statusLabel('revoked')}：{e.revoked.by} · {e.revoked.at} —— {e.revoked.reason}
                </Typography>
              )}
            </Box>
            {e.status !== 'revoked' && (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Tooltip title={t('exceptions.renew')}>
                  <IconButton size="small" onClick={() => setRenewing(e)}>
                    <Autorenew sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
                <Tooltip title={t('exceptions.revoke')}>
                  <IconButton size="small" onClick={() => setRevoking(e)}>
                    <Block sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
          </Paper>
        )
      })}

      <AuditExceptionDialog open={creating} onClose={() => setCreating(false)}
        baseHash={data?.base_hash}
        onSaved={(created) => {
          setCreating(false)
          setSnack(t('exceptions.created').replace('{id}', created.id))
          load()
        }} />

      {renewing && (
        <RenewExceptionDialog exc={renewing} t={t} baseHash={data?.base_hash}
          onClose={() => setRenewing(null)}
          onDone={() => { setRenewing(null); setSnack(t('exceptions.renewed')); load() }} />
      )}
      {revoking && (
        <RevokeExceptionDialog exc={revoking} t={t} baseHash={data?.base_hash}
          onClose={() => setRevoking(null)}
          onDone={() => { setRevoking(null); setSnack(t('exceptions.revoked')); load() }} />
      )}

      <Snackbar open={!!snack} autoHideDuration={3000} onClose={() => setSnack('')}
        message={snack} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} />
    </>
  )
}

/** 续期对话框 —— 顺带允许修正理由与批准人（都写回同一条例外） */
const RenewExceptionDialog: React.FC<{
  exc: AuditException
  t: (key: string, fallback?: string) => string
  baseHash?: string
  onClose: () => void
  onDone: () => void
}> = ({ exc, t, baseHash, onClose, onDone }) => {
  const [expiresAt, setExpiresAt] = useState(exc.expires_at)
  const [reason, setReason] = useState(exc.reason)
  const [approvedBy, setApprovedBy] = useState(exc.approved_by)
  const [error, setError] = useState('')

  const submit = async () => {
    try {
      await auditApi.updateException(exc.id, {
        expires_at: expiresAt, reason, approved_by: approvedBy, base_hash: baseHash,
      })
      onDone()
    } catch (e) {
      setError(httpDetail(e) || t('exceptions.saveFailed'))
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.9rem', fontFamily: '"Fira Code", monospace' }}>{exc.id}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        <TextField size="small" type="date" label={t('exceptions.expiresAt')} value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)} InputLabelProps={{ shrink: true }} />
        <TextField size="small" label={t('exceptions.reason')} value={reason} multiline minRows={2}
          onChange={(e) => setReason(e.target.value)} />
        <TextField size="small" label={t('exceptions.approvedBy')} value={approvedBy}
          onChange={(e) => setApprovedBy(e.target.value)} />
        {error && <Alert severity="warning" sx={{ py: 0.25 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" onClick={submit}>{t('auditRules.save')}</Button>
      </DialogActions>
    </Dialog>
  )
}

/** 撤销对话框 —— 软删除：必须写明谁撤的、为什么（条目保留供历史审计追溯） */
const RevokeExceptionDialog: React.FC<{
  exc: AuditException
  t: (key: string, fallback?: string) => string
  baseHash?: string
  onClose: () => void
  onDone: () => void
}> = ({ exc, t, baseHash, onClose, onDone }) => {
  const [by, setBy] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')

  const submit = async () => {
    if (!by.trim() || !reason.trim()) { setError(t('exceptions.needRevoke')); return }
    try {
      await auditApi.revokeException(exc.id, { by, reason, base_hash: baseHash })
      onDone()
    } catch (e) {
      setError(httpDetail(e) || t('exceptions.saveFailed'))
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.9rem', fontFamily: '"Fira Code", monospace' }}>{exc.id}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        <Typography variant="caption" color="text.secondary">{t('exceptions.revokeConfirm')}</Typography>
        <TextField size="small" label={t('exceptions.revokeBy')} value={by}
          onChange={(e) => setBy(e.target.value)} />
        <TextField size="small" label={t('exceptions.revokeReason')} value={reason} multiline minRows={2}
          onChange={(e) => setReason(e.target.value)} />
        {error && <Alert severity="warning" sx={{ py: 0.25 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" color="warning" onClick={submit}>{t('exceptions.revoke')}</Button>
      </DialogActions>
    </Dialog>
  )
}

export default ComplianceStandard
