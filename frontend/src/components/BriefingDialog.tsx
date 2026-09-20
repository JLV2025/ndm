import React from 'react'
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Typography,
} from '@mui/material'
import { ContentCopy } from '@mui/icons-material'
import { useI18n } from '../i18n'
import type { AuditBriefing } from '../types'

/** 极简 Markdown 渲染：标题行加粗、`- ` 列表、**加粗** —— 不引第三方依赖 */
const renderInline = (text: string): React.ReactNode[] =>
  text.split(/(\*\*[^*]+\*\*)/g).map((seg, i) =>
    seg.startsWith('**') && seg.endsWith('**')
      ? <b key={i}>{seg.slice(2, -2)}</b>
      : <React.Fragment key={i}>{seg}</React.Fragment>)

const BriefingBody: React.FC<{ text: string }> = ({ text }) => (
  <Box sx={{ fontSize: '0.82rem', lineHeight: 1.75, color: 'text.primary' }}>
    {text.split('\n').map((line, i) => {
      const trimmed = line.trim()
      if (!trimmed) return <Box key={i} sx={{ height: 8 }} />
      if (trimmed.startsWith('#')) {
        return (
          <Typography key={i} variant="subtitle2" sx={{ fontWeight: 700, mt: 1.5, mb: 0.5, fontSize: '0.85rem' }}>
            {renderInline(trimmed.replace(/^#+\s*/, ''))}
          </Typography>
        )
      }
      const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ') || /^\d+[.、]/.test(trimmed)
      return (
        <Box key={i} sx={{ display: 'flex', gap: 0.75, pl: isBullet ? 1 : 0, mb: 0.25 }}>
          {isBullet && <Box sx={{ color: 'text.disabled' }}>·</Box>}
          <Box sx={{ flex: 1 }}>{renderInline(trimmed.replace(/^[-*]\s+/, ''))}</Box>
        </Box>
      )
    })}
  </Box>
)

/**
 * AI 专家简报对话框（单台 / 全网共用）。
 *
 * 内容是**确定性引擎结论的讲解**（prompt 里硬约束 AI 不得新增未列出的问题）——
 * 所以底部要写清楚这是"讲人话"而不是新的判定，并展示 provider 便于排查。
 */
const BriefingDialog: React.FC<{
  open: boolean
  onClose: () => void
  loading: boolean
  error: string
  briefing: AuditBriefing | null
  title?: string
}> = ({ open, onClose, loading, error, briefing, title }) => {
  const { t } = useI18n()
  const copy = () => {
    if (briefing?.briefing) navigator.clipboard?.writeText(briefing.briefing)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontSize: '0.95rem' }}>{title || t('briefing.title')}</DialogTitle>
      <DialogContent>
        {loading && (
          <Box sx={{ textAlign: 'center', py: 5 }}>
            <CircularProgress size={26} />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              {t('briefing.generating')}
            </Typography>
          </Box>
        )}
        {error && <Alert severity="warning" sx={{ fontSize: '0.78rem' }}>{error}</Alert>}
        {!loading && briefing && (
          <>
            <BriefingBody text={briefing.briefing} />
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 2, fontSize: '0.62rem' }}>
              {t('briefing.footerNote')}
              {briefing.provider && ` · ${briefing.provider}`}
              {briefing.generated_at && ` · ${briefing.generated_at.replace('T', ' ')}`}
            </Typography>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button startIcon={<ContentCopy sx={{ fontSize: 15 }} />} onClick={copy} disabled={!briefing}>
          {t('briefing.copy')}
        </Button>
        <Button onClick={onClose}>{t('auditRules.cancel')}</Button>
      </DialogActions>
    </Dialog>
  )
}

export default BriefingDialog
