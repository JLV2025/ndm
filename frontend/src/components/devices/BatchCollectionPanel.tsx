import React from 'react'
import { Box, Paper, Typography, Chip, CircularProgress, LinearProgress } from '@mui/material'
import type { BatchItemStatus } from '../../types'
import { useI18n } from '../../i18n'

interface BatchCollectionPanelProps {
  running: boolean
  statuses: Record<string, BatchItemStatus>
}

const BatchCollectionPanel: React.FC<BatchCollectionPanelProps> = React.memo(({ running, statuses }) => {
  const { t } = useI18n()
  const successCount = Object.values(statuses).filter((s) => s.status === 'success').length
  const totalCount = Object.keys(statuses).length

  return (
    <>
      {running && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {t('collect.title')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t('collect.progress').replace('{done}', String(successCount)).replace('{total}', String(totalCount))}
            </Typography>
          </Box>
          <LinearProgress />
        </Paper>
      )}

      {!running && totalCount > 0 && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            {t('collect.result')}
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {Object.entries(statuses).map(([name, s]) => (
              <Chip
                key={name}
                label={`${name}: ${s.status === 'success' ? t('collect.success') : s.error || t('collect.failed')}`}
                size="small"
                sx={{
                  bgcolor: s.status === 'success' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                  color: s.status === 'success' ? 'success.main' : 'error.main',
                  fontSize: '0.7rem',
                }}
              />
            ))}
          </Box>
        </Paper>
      )}
    </>
  )
})

export default BatchCollectionPanel
