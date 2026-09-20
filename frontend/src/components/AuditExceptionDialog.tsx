import React, { useState, useEffect } from 'react'
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField,
  MenuItem, Select, Alert, Typography, Box,
} from '@mui/material'
import { auditApi } from '../services/api'
import type { AuditRule } from '../types'
import { useI18n } from '../i18n'

/** 今天 + 180 天 —— 例外的默认到期日（不允许永久例外） */
export const defaultExpiry = (): string => {
  const d = new Date()
  d.setDate(d.getDate() + 180)
  return d.toISOString().slice(0, 10)
}

export const httpDetail = (e: unknown): string =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || ''

/**
 * 登记例外对话框 —— 查看器（从某条 finding 出发）与标准页（新增按钮）共用。
 *
 * 必填：规则、范围（all 除外需值）、理由、批准人、到期日。
 * 保存时带 base_hash 做乐观锁（并发编辑时后端 409 拦截）。
 */
const AuditExceptionDialog: React.FC<{
  open: boolean
  onClose: () => void
  onSaved: (created: { id: string }) => void
  defaultRuleId?: string
  defaultScopeType?: 'device' | 'site' | 'all'
  defaultScopeValue?: string
  baseHash?: string
}> = ({ open, onClose, onSaved, defaultRuleId = '', defaultScopeType = 'device',
       defaultScopeValue = '', baseHash }) => {
  const { t } = useI18n()
  const [rules, setRules] = useState<AuditRule[]>([])
  const [ruleId, setRuleId] = useState(defaultRuleId)
  const [scopeType, setScopeType] = useState<'device' | 'site' | 'all'>(defaultScopeType)
  const [scopeValue, setScopeValue] = useState(defaultScopeValue)
  const [reason, setReason] = useState('')
  const [compensating, setCompensating] = useState('')
  const [approvedBy, setApprovedBy] = useState('')
  const [expiresAt, setExpiresAt] = useState(defaultExpiry())
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  // 每次打开重置（含调用方传来的预填值）——对话框被复用时不残留上一次的输入
  useEffect(() => {
    if (!open) return
    setRuleId(defaultRuleId)
    setScopeType(defaultScopeType)
    setScopeValue(defaultScopeValue)
    setReason(''); setCompensating(''); setApprovedBy('')
    setExpiresAt(defaultExpiry()); setError('')
    auditApi.ruleset()
      .then((rs) => setRules(rs.rules.filter((r) => r.enabled)))
      .catch(() => {})
  }, [open, defaultRuleId, defaultScopeType, defaultScopeValue])

  const submit = async () => {
    if (!ruleId || !reason.trim() || !approvedBy.trim() || !expiresAt) {
      setError(t('exceptions.needReason')); return
    }
    if (scopeType !== 'all' && !scopeValue.trim()) {
      setError(t('exceptions.needReason')); return
    }
    setSaving(true); setError('')
    try {
      const res = await auditApi.createException({
        rule_id: ruleId, scope_type: scopeType, scope_value: scopeValue.trim(),
        reason, compensating_control: compensating, approved_by: approvedBy,
        expires_at: expiresAt, base_hash: baseHash || undefined,
      })
      onSaved(res.exception)
    } catch (e) {
      setError(httpDetail(e) || t('exceptions.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontSize: '0.95rem' }}>{t('exceptions.add')}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        <Typography variant="caption" color="text.secondary">{t('exceptions.note')}</Typography>

        <Select size="small" displayEmpty value={ruleId} onChange={(e) => setRuleId(e.target.value)}
          sx={{ fontSize: '0.8rem' }}>
          <MenuItem value="" sx={{ fontSize: '0.8rem' }}>{t('exceptions.rulePlaceholder')}</MenuItem>
          {rules.map((r) => (
            <MenuItem key={r.id} value={r.id} sx={{ fontSize: '0.8rem' }}>
              {r.title}（{r.id}）
            </MenuItem>
          ))}
        </Select>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Select size="small" value={scopeType}
            onChange={(e) => setScopeType(e.target.value as 'device' | 'site' | 'all')}
            sx={{ minWidth: 110, fontSize: '0.8rem' }}>
            <MenuItem value="device" sx={{ fontSize: '0.8rem' }}>{t('exceptions.scope.device')}</MenuItem>
            <MenuItem value="site" sx={{ fontSize: '0.8rem' }}>{t('exceptions.scope.site')}</MenuItem>
            <MenuItem value="all" sx={{ fontSize: '0.8rem' }}>{t('exceptions.scope.all')}</MenuItem>
          </Select>
          {scopeType !== 'all' && (
            <TextField size="small" fullWidth value={scopeValue} onChange={(e) => setScopeValue(e.target.value)}
              placeholder={scopeType === 'device' ? t('exceptions.devicePlaceholder') : t('exceptions.sitePlaceholder')} />
          )}
        </Box>

        <TextField size="small" label={t('exceptions.reason')} value={reason} multiline minRows={2}
          onChange={(e) => setReason(e.target.value)} fullWidth />
        <TextField size="small" label={t('exceptions.compensating')} value={compensating}
          onChange={(e) => setCompensating(e.target.value)} fullWidth />

        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField size="small" label={t('exceptions.approvedBy')} value={approvedBy}
            onChange={(e) => setApprovedBy(e.target.value)} sx={{ flex: 1 }} />
          <TextField size="small" type="date" label={t('exceptions.expiresAt')} value={expiresAt}
            onChange={(e) => setExpiresAt(e.target.value)} sx={{ flex: 1 }}
            InputLabelProps={{ shrink: true }} />
        </Box>

        {error && <Alert severity="warning" sx={{ py: 0.25 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
        <Button variant="contained" onClick={submit} disabled={saving}>{t('auditRules.save')}</Button>
      </DialogActions>
    </Dialog>
  )
}

export default AuditExceptionDialog
