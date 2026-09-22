import React, { useState } from 'react'
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography,
} from '@mui/material'
import { lifecycleApi } from '../services/api'
import { httpDetail } from './AuditExceptionDialog'
import { useI18n } from '../i18n'
import type { LifecycleImportResult, LifecycleModelEol } from '../types'

/**
 * 生命周期对话框 —— 详情页卡片与生命周期页**共用**（两处写同一 API）。
 *
 * 放共享文件而不是各写一份：交互逻辑（校验、错误提示、结果回显）复制成两份，
 * 改一处漏一处是必然。单行维保编辑在页面里另有更轻的对话框。
 */

/** 型号 EoL 手工登记（Aruba 与凭据到位前的 Cisco 都用它） */
export const ModelEolDialog: React.FC<{
  model: LifecycleModelEol
  onClose: () => void
  onSaved: () => void
}> = ({ model, onClose, onSaved }) => {
  const { t } = useI18n()
  const [endOfSale, setEndOfSale] = useState(model.end_of_sale || '')
  const [endOfSupport, setEndOfSupport] = useState(model.end_of_support || '')
  const [bulletin, setBulletin] = useState(model.bulletin || '')
  const [bulletinUrl, setBulletinUrl] = useState(model.bulletin_url || '')
  const [note, setNote] = useState(model.note || '')
  const [error, setError] = useState('')

  const save = async () => {
    try {
      await lifecycleApi.saveModel(model.model, {
        description: model.description || '', end_of_sale: endOfSale,
        end_of_support: endOfSupport, announcement: model.announcement || '',
        bulletin, bulletin_url: bulletinUrl, note,
      })
      onSaved()
    } catch (e) {
      setError(httpDetail(e) || t('lifecycle.saveFailed'))
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.92rem' }}>{model.model}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: '8px !important' }}>
        <Typography variant="caption" color="text.secondary">{t('lifecycle.modelHint')}</Typography>
        <TextField size="small" type="date" label={t('lifecycle.endOfSale')} value={endOfSale}
          onChange={(e) => setEndOfSale(e.target.value)} InputLabelProps={{ shrink: true }} />
        <TextField size="small" type="date" label={t('lifecycle.endOfSupport')} value={endOfSupport}
          onChange={(e) => setEndOfSupport(e.target.value)} InputLabelProps={{ shrink: true }} />
        <TextField size="small" label={t('lifecycle.bulletin')} value={bulletin}
          onChange={(e) => setBulletin(e.target.value)} />
        <TextField size="small" label={t('lifecycle.bulletinUrl')} value={bulletinUrl}
          onChange={(e) => setBulletinUrl(e.target.value)} />
        <TextField size="small" label={t('lifecycle.note')} value={note}
          onChange={(e) => setNote(e.target.value)} />
        {error && <Alert severity="warning" sx={{ py: 0.25, fontSize: '0.75rem' }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" onClick={save}>{t('auditRules.save')}</Button>
      </DialogActions>
    </Dialog>
  )
}

/** 批量粘贴导入：从 Cisco/HPE 保修查询页抄下来整段贴进来 */
export const ImportDialog: React.FC<{
  onClose: () => void
  onDone: (res: LifecycleImportResult) => void
}> = ({ onClose, onDone }) => {
  const { t } = useI18n()
  const [text, setText] = useState('')
  const [verifiedBy, setVerifiedBy] = useState('')
  const [result, setResult] = useState<LifecycleImportResult | null>(null)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!verifiedBy.trim()) { setError(t('lifecycle.needVerifiedBy')); return }
    try {
      const res = await lifecycleApi.importText(text, verifiedBy.trim())
      setResult(res)
      setError('')
      onDone(res)
    } catch (e) {
      setError(httpDetail(e) || t('lifecycle.saveFailed'))
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontSize: '0.95rem' }}>{t('lifecycle.import')}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: '8px !important' }}>
        <Typography variant="caption" color="text.secondary">{t('lifecycle.importHint')}</Typography>
        <TextField multiline minRows={6} placeholder={'FOC1234X5AB,2028-05-01,Smart Net\nCN41LM90H4,2027-12-31'}
          value={text} onChange={(e) => setText(e.target.value)} fullWidth
          sx={{ '& textarea': { fontFamily: '"Fira Code", monospace', fontSize: '0.75rem' } }} />
        <TextField size="small" label={t('lifecycle.verifiedBy')} value={verifiedBy}
          onChange={(e) => setVerifiedBy(e.target.value)} sx={{ width: 200 }} />
        {error && <Alert severity="warning" sx={{ py: 0.25, fontSize: '0.75rem' }}>{error}</Alert>}
        {result && (
          <Box sx={{ fontSize: '0.72rem' }}>
            <Typography variant="caption" sx={{ display: 'block', color: 'success.main' }}>
              {t('lifecycle.matched').replace('{n}', String(result.matched.length))}
            </Typography>
            {result.unmatched.length > 0 && (
              <Typography variant="caption" sx={{ display: 'block', color: 'warning.main' }}>
                {t('lifecycle.unmatched')}：{result.unmatched.join(', ')}
              </Typography>
            )}
            {result.ambiguous.length > 0 && (
              <Typography variant="caption" sx={{ display: 'block', color: 'warning.main' }}>
                {t('lifecycle.ambiguous')}：{result.ambiguous.map((a) => a.serial).join(', ')}
              </Typography>
            )}
            {result.invalid.length > 0 && (
              <Typography variant="caption" sx={{ display: 'block', color: 'text.disabled' }}>
                {t('lifecycle.invalid')}：{result.invalid.slice(0, 5).join(' / ')}
              </Typography>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" onClick={submit} disabled={!text.trim()}>
          {t('lifecycle.importSubmit')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
