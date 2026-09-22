import React, { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, Paper, Table, TableBody, TableCell, TableHead, TableRow,
  TextField, Tooltip, Typography,
} from '@mui/material'
import { CloudDownload, Edit, FileUpload, Save } from '@mui/icons-material'
import { lifecycleApi } from '../services/api'
import { ImportDialog, ModelEolDialog } from './LifecycleDialogs'
import { httpDetail } from './AuditExceptionDialog'
import { useI18n } from '../i18n'
import type { DeviceLifecycle, LifecycleModelEol } from '../types'

const SOURCE_COLORS: Record<string, string> = { api: '#3B82F6', manual: '#94A3B8' }
const EOL_COLOR = { bg: 'rgba(245,158,11,0.16)', text: '#FBBF24' }
const OK_COLOR = { bg: 'rgba(45,212,110,0.12)', text: '#5CE68C' }

/**
 * 设备生命周期卡片 —— EoL 与保修期。
 *
 * 手工登记是**主路径**（Aruba 无公开 API、Cisco 保修需 SNTC 权限、EoX 凭据未到位都靠它），
 * 所以编辑与批量导入要顺手；Cisco EoX 自动刷新是加分项，未配凭据时给可读提示而不是报错。
 * 未登记的信息会作为「待查」进审计（需人工判断档）。
 */
const LifecycleCard: React.FC<{ deviceName: string }> = ({ deviceName }) => {
  const { t } = useI18n()
  const [data, setData] = useState<DeviceLifecycle | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [snack, setSnack] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [modelEdit, setModelEdit] = useState<LifecycleModelEol | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    setLoading(true); setError('')
    lifecycleApi.device(deviceName)
      .then(setData)
      .catch(() => setError(t('lifecycle.loadFailed')))
      .finally(() => setLoading(false))
  }, [deviceName, t])

  useEffect(() => { load() }, [load])

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

  const hasAny = !!data && (data.model_eol.length > 0 || data.serials.some((s) => s.warranty_end))

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
          {t('lifecycle.title')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Tooltip title={data?.refresh?.available ? t('lifecycle.refreshHint') : (data?.refresh?.reason || '')}>
            <span>
              <Button size="small" startIcon={<CloudDownload sx={{ fontSize: 15 }} />}
                onClick={handleRefresh} disabled={refreshing}
                sx={{ fontSize: '0.7rem' }}>
                {refreshing ? t('lifecycle.refreshing') : t('lifecycle.refresh')}
              </Button>
            </span>
          </Tooltip>
          <Button size="small" startIcon={<FileUpload sx={{ fontSize: 15 }} />}
            onClick={() => setImportOpen(true)} sx={{ fontSize: '0.7rem' }}>
            {t('lifecycle.import')}
          </Button>
        </Box>
      </Box>
      <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
        {t('lifecycle.hint')}
      </Typography>

      {loading && <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress size={22} /></Box>}
      {error && <Alert severity="warning" sx={{ mt: 1, py: 0.25, fontSize: '0.75rem' }}>{error}</Alert>}

      {!loading && data && (
        <>
          {/* 型号 EoL */}
          {data.model_eol.length > 0 && (
            <Table size="small" sx={{ mt: 1 }}>
              <TableHead>
                <TableRow>
                  {[t('lifecycle.model'), t('lifecycle.eolStatus'), t('lifecycle.endOfSale'),
                    t('lifecycle.endOfSupport'), t('lifecycle.bulletin'), ''].map((h, i) => (
                    <TableCell key={i} sx={{ fontSize: '0.66rem', color: 'text.secondary', py: 0.4 }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {data.model_eol.map((m) => {
                  const announced = !!(m.end_of_sale || m.end_of_support)
                  return (
                    <TableRow key={m.model}>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.4 }}>{m.model}</TableCell>
                      <TableCell sx={{ py: 0.4 }}>
                        <Chip size="small"
                          label={announced ? t('lifecycle.announced') : (m.source ? t('lifecycle.notAnnounced') : t('lifecycle.notRegistered'))}
                          sx={{ height: 18, fontSize: '0.58rem',
                                bgcolor: announced ? EOL_COLOR.bg : OK_COLOR.bg,
                                color: announced ? EOL_COLOR.text : OK_COLOR.text }} />
                        {m.source && (
                          <Chip size="small" label={m.source === 'api' ? t('lifecycle.sourceApi') : t('lifecycle.sourceManual')}
                            sx={{ height: 18, fontSize: '0.56rem', ml: 0.5, bgcolor: 'rgba(148,163,184,0.12)', color: SOURCE_COLORS[m.source] || 'text.disabled' }} />
                        )}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.4 }}>{m.end_of_sale || '—'}</TableCell>
                      <TableCell sx={{ fontSize: '0.72rem', py: 0.4 }}>{m.end_of_support || '—'}</TableCell>
                      <TableCell sx={{ fontSize: '0.68rem', py: 0.4 }}>
                        {m.bulletin_url
                          ? <a href={m.bulletin_url} target="_blank" rel="noreferrer" style={{ color: '#60A5FA' }}>{m.bulletin || m.bulletin_url}</a>
                          : (m.bulletin || '—')}
                      </TableCell>
                      <TableCell sx={{ py: 0.4, width: 40 }}>
                        <IconButton size="small" onClick={() => setModelEdit(m)} title={t('lifecycle.editModel')}>
                          <Edit sx={{ fontSize: 14 }} />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}

          {/* 序列号保修 */}
          {data.serials.length > 0 && (
            <Table size="small" sx={{ mt: 1 }}>
              <TableHead>
                <TableRow>
                  {[t('lifecycle.physicalName'), t('lifecycle.serial'), t('lifecycle.warrantyEnd'),
                    t('lifecycle.note'), t('lifecycle.verifiedAt'), ''].map((h, i) => (
                    <TableCell key={i} sx={{ fontSize: '0.66rem', color: 'text.secondary', py: 0.4 }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {data.serials.map((s) => (
                  <TableRow key={s.serial}>
                    <TableCell sx={{ fontSize: '0.72rem', py: 0.4 }}>{s.physical_name || s.serial}</TableCell>
                    <TableCell sx={{ fontSize: '0.72rem', py: 0.4 }}>{s.serial}</TableCell>
                    <TableCell sx={{ fontSize: '0.72rem', py: 0.4 }}>{s.warranty_end || t('lifecycle.notRegistered')}</TableCell>
                    <TableCell sx={{ fontSize: '0.68rem', color: 'text.secondary', py: 0.4 }}>{s.note || '—'}</TableCell>
                    <TableCell sx={{ fontSize: '0.66rem', color: 'text.disabled', py: 0.4 }}>
                      {s.verified_at ? `${s.verified_at.slice(0, 10)}${s.verified_by ? ` · ${s.verified_by}` : ''}` : '—'}
                    </TableCell>
                    <TableCell sx={{ py: 0.4, width: 40 }}>
                      <IconButton size="small" onClick={() => setEditOpen(true)} title={t('lifecycle.editWarranty')}>
                        <Edit sx={{ fontSize: 14 }} />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!hasAny && (
            <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center', fontSize: '0.8rem' }}>
              {t('lifecycle.empty')}
            </Typography>
          )}
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 1, fontSize: '0.62rem' }}>
            {t('lifecycle.auditNote')}
          </Typography>
        </>
      )}

      {editOpen && data && (
        <WarrantyDialog deviceName={deviceName} data={data}
          onClose={() => setEditOpen(false)}
          onSaved={() => { setEditOpen(false); setSnack(t('lifecycle.saved')); load() }} />
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
      {snack && (
        <Alert severity="success" sx={{ mt: 1, py: 0.25, fontSize: '0.72rem' }}
          onClose={() => setSnack('')}>{snack}</Alert>
      )}
    </Paper>
  )
}

/** 保修期编辑：逐序列号（预填当前值），整表保存 */
const WarrantyDialog: React.FC<{
  deviceName: string
  data: DeviceLifecycle
  onClose: () => void
  onSaved: () => void
}> = ({ deviceName, data, onClose, onSaved }) => {
  const { t } = useI18n()
  const [rows, setRows] = useState(data.serials.map((s) => ({
    serial: s.serial, warranty_end: s.warranty_end || '', note: s.note || '',
  })))
  const [verifiedBy, setVerifiedBy] = useState('')
  const [error, setError] = useState('')

  const save = async () => {
    if (!verifiedBy.trim()) { setError(t('lifecycle.needVerifiedBy')); return }
    try {
      await lifecycleApi.saveDevice(deviceName, rows, verifiedBy.trim())
      onSaved()
    } catch (e) {
      setError(httpDetail(e) || t('lifecycle.saveFailed'))
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontSize: '0.95rem' }}>{t('lifecycle.editWarranty')}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        <Typography variant="caption" color="text.secondary">{t('lifecycle.warrantyHint')}</Typography>
        {rows.map((row, i) => (
          <Box key={row.serial} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography sx={{ fontSize: '0.72rem', minWidth: 130 }}>
              {row.serial}
            </Typography>
            <TextField size="small" type="date" value={row.warranty_end}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, warranty_end: e.target.value } : r))}
              InputLabelProps={{ shrink: true }} sx={{ width: 160 }} />
            <TextField size="small" placeholder={t('lifecycle.note')} value={row.note}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, note: e.target.value } : r))}
              sx={{ flex: 1 }} />
          </Box>
        ))}
        <TextField size="small" label={t('lifecycle.verifiedBy')} value={verifiedBy}
          onChange={(e) => setVerifiedBy(e.target.value)} sx={{ width: 200 }} />
        {error && <Alert severity="warning" sx={{ py: 0.25, fontSize: '0.75rem' }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" startIcon={<Save sx={{ fontSize: 15 }} />} onClick={save}>
          {t('auditRules.save')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default LifecycleCard
