import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, IconButton, InputLabel, MenuItem, Paper, Select, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TableSortLabel, TextField, Tooltip, Typography,
} from '@mui/material'
import { CloudDownload, Edit, FileUpload } from '@mui/icons-material'
import { lifecycleApi } from '../services/api'
import { ImportDialog, ModelEolDialog } from '../components/LifecycleDialogs'
import { httpDetail } from '../components/AuditExceptionDialog'
import { useI18n } from '../i18n'
import { STATUS_COLOR, STATUS_RANK } from '../shared/constants'
import type { LifecycleModelEol, PhysicalLifecycleRow } from '../types'

/**
 * 生命周期页 —— 全部物理设备（堆叠成员逐台 + 单机）一行一台。
 *
 * 数据源 = `GET /api/lifecycle/physical`（物理行 + 三色状态，判定在后端纯函数）；
 * 本页只做「状态 → 颜色」（STATUS_COLOR）与筛选/排序（约 50 行，放前端）。
 * 保修按**管理体**记账：行内编辑提交到 `row.device`（所属堆叠/单机）。
 * 编辑入口与详情页卡片**并存**（spec 第十三节第 5 条），两处写同一 API。
 */
type SortDir = 'asc' | 'desc'
interface SortState { field: string; dir: SortDir }

const STATUS_FILTERS = ['all', 'ok', 'soon', 'missing', 'expired'] as const

/** 排序取值口径（与状态严重度共用 STATUS_RANK：越严重越靠前） */
const GETTERS: Record<string, (r: PhysicalLifecycleRow) => unknown> = {
  name: r => r.display_name || r.name,
  serial: r => r.serial,
  location: r => r.location,
  model: r => r.model,
  eol_sale: r => r.eol.end_of_sale,
  eol_support: r => r.eol.end_of_support,
  warranty: r => r.warranty_end,
  status: r => STATUS_RANK[r.warranty_status] ?? 9,
  source: r => r.source,
  verified: r => r.verified_at,
}

function sortRows(rows: PhysicalLifecycleRow[], sort: SortState): PhysicalLifecycleRow[] {
  const get = GETTERS[sort.field]
  if (!get) return rows
  const dir = sort.dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const va = get(a); const vb = get(b)
    const ea = va === null || va === undefined || va === ''
    const eb = vb === null || vb === undefined || vb === ''
    if (ea || eb) return ea && eb ? 0 : ea ? 1 : -1
    const cmp = typeof va === 'number' && typeof vb === 'number'
      ? va - vb
      : String(va).localeCompare(String(vb))
    return cmp * dir
  })
}

const SortHead: React.FC<{ field: string; label: string; sort: SortState; onSort: (f: string) => void }> = ({
  field, label, sort, onSort,
}) => (
  <TableCell sortDirection={sort.field === field ? sort.dir : false} sx={{ whiteSpace: 'nowrap' }}>
    <TableSortLabel
      active={sort.field === field}
      direction={sort.field === field ? sort.dir : 'asc'}
      onClick={() => onSort(field)}
      sx={{ fontSize: '0.68rem' }}
    >
      {label}
    </TableSortLabel>
  </TableCell>
)

/** 状态圆点 + 文案（颜色唯一来源 STATUS_COLOR，与详情页卡片一致） */
const StatusDot: React.FC<{ status: string }> = ({ status }) => {
  const { t } = useI18n()
  const key = STATUS_COLOR[status] ? status : 'none'
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.6, whiteSpace: 'nowrap' }}>
      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: STATUS_COLOR[key], flexShrink: 0 }} />
      <Typography sx={{ fontSize: '0.7rem' }}>{t(`lifecycle.status.${key}`)}</Typography>
    </Box>
  )
}

const Lifecycle: React.FC = () => {
  const { t } = useI18n()
  const [rows, setRows] = useState<PhysicalLifecycleRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [snack, setSnack] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [location, setLocation] = useState('')
  const [model, setModel] = useState('')
  const [sort, setSort] = useState<SortState>({ field: 'status', dir: 'asc' })
  const [verifiedBy, setVerifiedBy] = useState('')
  const [editRow, setEditRow] = useState<PhysicalLifecycleRow | null>(null)
  const [modelEdit, setModelEdit] = useState<LifecycleModelEol | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    setLoading(true); setError('')
    lifecycleApi.listPhysical()
      .then(res => setRows(res.devices || []))
      .catch(() => setError(t('lifecycle.loadFailed')))
      .finally(() => setLoading(false))
  }, [t])

  useEffect(() => { load() }, [load])

  const locations = useMemo(
    () => [...new Set(rows.map(r => r.location).filter(Boolean))].sort(), [rows])
  const models = useMemo(
    () => [...new Set(rows.map(r => r.model).filter(Boolean))].sort(), [rows])
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: rows.length }
    rows.forEach(r => { c[r.warranty_status] = (c[r.warranty_status] || 0) + 1 })
    return c
  }, [rows])

  const filtered = useMemo(() => rows.filter(r =>
    (statusFilter === 'all' || r.warranty_status === statusFilter) &&
    (!location || r.location === location) &&
    (!model || r.model === model)), [rows, statusFilter, location, model])
  const sorted = useMemo(() => sortRows(filtered, sort), [filtered, sort])

  const handleSort = (field: string) => {
    setSort(s => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  /** 点型号 → 先取当前登记再开对话框（保存是整条覆盖，不回填会丢公告/链接/备注） */
  const openModelEdit = async (m: string) => {
    if (!m) return
    try {
      const res = await lifecycleApi.model(m)
      setModelEdit(res.model)
    } catch (e) {
      setError(httpDetail(e) || t('lifecycle.loadFailed'))
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true); setError('')
    try {
      const res = await lifecycleApi.refresh()
      setSnack(t('lifecycle.refreshDone')
        .replace('{n}', String((res.updated || []).length))
        .replace('{m}', String((res.not_announced || []).length)))
      load()
    } catch (e) {
      setError(httpDetail(e) || t('lifecycle.refreshFailed'))
    } finally {
      setRefreshing(false)
    }
  }

  const chipLabel = (s: string) => s === 'all'
    ? `${t('lifecycle.page.all')} ${counts.all || 0}`
    : `${t(`lifecycle.status.${s}`)} ${counts[s] || 0}`

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>{t('nav.lifecycle')}</Typography>
      <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 2 }}>
        {t('lifecycle.page.hint')}
      </Typography>

      {error && <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {snack && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSnack('')}>{snack}</Alert>}

      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          {STATUS_FILTERS.map(s => (
            <Chip key={s} size="small" label={chipLabel(s)}
              variant={statusFilter === s ? 'filled' : 'outlined'}
              onClick={() => setStatusFilter(s)}
              icon={s === 'all' ? undefined
                : <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: STATUS_COLOR[s], ml: 1 }} />}
              sx={{ fontSize: '0.68rem', height: 24 }} />
          ))}

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel sx={{ fontSize: '0.78rem' }}>{t('lifecycle.page.location')}</InputLabel>
            <Select label={t('lifecycle.page.location')} value={location}
              onChange={e => setLocation(e.target.value)} sx={{ fontSize: '0.78rem' }}>
              <MenuItem value="" sx={{ fontSize: '0.78rem' }}>{t('lifecycle.page.allLocations')}</MenuItem>
              {locations.map(l => <MenuItem key={l} value={l} sx={{ fontSize: '0.78rem' }}>{l}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel sx={{ fontSize: '0.78rem' }}>{t('lifecycle.model')}</InputLabel>
            <Select label={t('lifecycle.model')} value={model}
              onChange={e => setModel(e.target.value)} sx={{ fontSize: '0.78rem' }}>
              <MenuItem value="" sx={{ fontSize: '0.78rem' }}>{t('lifecycle.page.allModels')}</MenuItem>
              {models.map(m => <MenuItem key={m} value={m} sx={{ fontSize: '0.78rem' }}>{m}</MenuItem>)}
            </Select>
          </FormControl>

          <TextField size="small" label={t('lifecycle.verifiedBy')} value={verifiedBy}
            onChange={e => setVerifiedBy(e.target.value)} sx={{ width: 140 }} />

          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.disabled" sx={{ mr: 1 }}>
            {t('lifecycle.page.count').replace('{n}', String(sorted.length))}
          </Typography>
          <Tooltip title={t('lifecycle.refreshHint')}>
            <span>
              <Button size="small" startIcon={<CloudDownload sx={{ fontSize: 15 }} />}
                onClick={handleRefresh} disabled={refreshing} sx={{ fontSize: '0.7rem' }}>
                {refreshing ? t('lifecycle.refreshing') : t('lifecycle.refresh')}
              </Button>
            </span>
          </Tooltip>
          <Button size="small" startIcon={<FileUpload sx={{ fontSize: 15 }} />}
            onClick={() => setImportOpen(true)} sx={{ fontSize: '0.7rem' }}>
            {t('lifecycle.import')}
          </Button>
        </Box>

        {loading ? (
          <Box sx={{ textAlign: 'center', py: 4 }}><CircularProgress size={22} /></Box>
        ) : sorted.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center', fontSize: '0.8rem' }}>
            {rows.length === 0 ? t('lifecycle.empty') : t('lifecycle.page.filteredEmpty')}
          </Typography>
        ) : (
          <TableContainer sx={{ mt: 1 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <SortHead field="name" label={t('lifecycle.physicalName')} sort={sort} onSort={handleSort} />
                  <SortHead field="serial" label={t('lifecycle.serial')} sort={sort} onSort={handleSort} />
                  <SortHead field="location" label={t('lifecycle.page.location')} sort={sort} onSort={handleSort} />
                  <SortHead field="model" label={t('lifecycle.model')} sort={sort} onSort={handleSort} />
                  <SortHead field="eol_sale" label={t('lifecycle.endOfSale')} sort={sort} onSort={handleSort} />
                  <SortHead field="eol_support" label={t('lifecycle.endOfSupport')} sort={sort} onSort={handleSort} />
                  <SortHead field="warranty" label={t('lifecycle.warrantyEnd')} sort={sort} onSort={handleSort} />
                  <SortHead field="status" label={t('lifecycle.page.status')} sort={sort} onSort={handleSort} />
                  <SortHead field="source" label={t('lifecycle.page.source')} sort={sort} onSort={handleSort} />
                  <SortHead field="verified" label={t('lifecycle.page.verified')} sort={sort} onSort={handleSort} />
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {sorted.map(r => (
                  <TableRow key={r.name} hover>
                    <TableCell sx={{ fontSize: '0.74rem', whiteSpace: 'nowrap' }}>
                      {r.display_name || r.name}
                      {r.kind === 'member' && (
                        <Typography component="span" sx={{ fontSize: '0.6rem', color: 'text.disabled', ml: 0.75 }}>
                          {r.device}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.72rem', fontFamily: '"Fira Code", monospace' }}>
                      {r.serial || '—'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.72rem' }}>{r.location || '—'}</TableCell>
                    <TableCell>
                      <Button size="small" onClick={() => openModelEdit(r.model)} disabled={!r.model}
                        sx={{ fontSize: '0.72rem', textTransform: 'none', minWidth: 0, p: 0.25 }}>
                        {r.model || '—'}
                      </Button>
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.72rem', color: STATUS_COLOR[r.eol.status] }}>
                      {r.eol.end_of_sale || '—'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.72rem', color: STATUS_COLOR[r.eol.status] }}>
                      {r.eol.end_of_support || '—'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.72rem' }}>{r.warranty_end || '—'}</TableCell>
                    <TableCell><StatusDot status={r.warranty_status} /></TableCell>
                    <TableCell>
                      {r.source && (
                        <Chip size="small"
                          label={r.source === 'api' ? t('lifecycle.sourceApi') : t('lifecycle.sourceManual')}
                          sx={{ height: 18, fontSize: '0.56rem', bgcolor: 'rgba(148,163,184,0.12)',
                                color: r.source === 'api' ? '#3B82F6' : '#94A3B8' }} />
                      )}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.66rem', color: 'text.disabled' }}>
                      {r.verified_at ? r.verified_at.slice(0, 10) : '—'}
                    </TableCell>
                    <TableCell sx={{ width: 40 }}>
                      <IconButton size="small" onClick={() => setEditRow(r)} title={t('lifecycle.page.editRow')}>
                        <Edit sx={{ fontSize: 14 }} />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {editRow && (
        <WarrantyRowDialog row={editRow} verifiedBy={verifiedBy}
          onClose={() => setEditRow(null)}
          onSaved={() => { setEditRow(null); setSnack(t('lifecycle.page.saveOk')); load() }} />
      )}
      {modelEdit && (
        <ModelEolDialog model={modelEdit}
          onClose={() => setModelEdit(null)}
          onSaved={() => { setModelEdit(null); setSnack(t('lifecycle.saved')); load() }} />
      )}
      {importOpen && (
        <ImportDialog onClose={() => setImportOpen(false)}
          onDone={(res) => {
            setSnack(t('lifecycle.importDone')
              .replace('{matched}', String(res.matched.length))
              .replace('{unmatched}', String(res.unmatched.length + res.invalid.length)))
            load()
          }} />
      )}
    </Box>
  )
}

/** 单行维保编辑：只提交这台（所属管理体 + 序列号），不动兄弟成员 */
const WarrantyRowDialog: React.FC<{
  row: PhysicalLifecycleRow
  verifiedBy: string
  onClose: () => void
  onSaved: () => void
}> = ({ row, verifiedBy, onClose, onSaved }) => {
  const { t } = useI18n()
  const [end, setEnd] = useState(row.warranty_end || '')
  const [note, setNote] = useState(row.note || '')
  const [error, setError] = useState('')

  const save = async () => {
    if (!verifiedBy.trim()) { setError(t('lifecycle.needVerifiedBy')); return }
    try {
      await lifecycleApi.saveDevice(row.device,
        [{ serial: row.serial, warranty_end: end, note }], verifiedBy.trim())
      onSaved()
    } catch (e) {
      setError(httpDetail(e) || t('lifecycle.saveFailed'))
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.92rem' }}>{t('lifecycle.page.editRow')}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: '8px !important' }}>
        <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
          {row.display_name} · <span style={{ fontFamily: '"Fira Code", monospace' }}>{row.serial}</span>
          <br />{t('lifecycle.page.device')}：{row.device}
        </Typography>
        <TextField size="small" type="date" label={t('lifecycle.warrantyEnd')} value={end}
          onChange={e => setEnd(e.target.value)} InputLabelProps={{ shrink: true }} />
        <TextField size="small" label={t('lifecycle.note')} value={note}
          onChange={e => setNote(e.target.value)} />
        {!verifiedBy.trim() && (
          <Alert severity="info" sx={{ py: 0.25, fontSize: '0.72rem' }}>{t('lifecycle.needVerifiedBy')}</Alert>
        )}
        {error && <Alert severity="warning" sx={{ py: 0.25, fontSize: '0.75rem' }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" onClick={save}>{t('auditRules.save')}</Button>
      </DialogActions>
    </Dialog>
  )
}

export default Lifecycle
