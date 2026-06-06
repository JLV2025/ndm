import React, { useState, useEffect, useRef } from 'react'
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
  const failedCount = Object.values(statuses).filter((s) => s.status === 'failed').length
  const totalCount = Object.keys(statuses).length
  const doneCount = successCount + failedCount

  // 找到当前正在处理的设备，轮询其进度
  const activeEntries = Object.entries(statuses).filter(([, s]) => s.status === 'pinging' || s.status === 'collecting')
  const activeEntry = activeEntries.length > 0 ? activeEntries[0] : null
  const [currentStep, setCurrentStep] = useState('')
  const activeDeviceName = activeEntry ? activeEntry[0] : null
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!activeDeviceName) {
      setCurrentStep('')
      return
    }
    // 查找设备 IP
    const poll = async () => {
      try {
        const res = await fetch(`/api/collect/progress/${activeDeviceName}`)
        if (!res.ok) return
        const data = await res.json()
        const STEP_MAP: Record<string, string> = {
          connecting: t('collect.stepConnecting'),
          collecting_config: t('collect.stepCollectingConfig'),
          collecting_logs: t('collect.stepCollectingLogs'),
          collecting_interface: t('collect.stepCollectingInterface'),
          analyzing: t('collect.stepAnalyzing'),
          saving: t('collect.stepSaving'),
        }
        setCurrentStep(STEP_MAP[data.step] || data.step || '')
      } catch { /* ignore */ }
    }
    poll()
    pollTimer.current = setInterval(poll, 2000)
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current)
    }
  }, [activeDeviceName, t])

  return (
    <>
      {running && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
            <CircularProgress size={24} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {t('collect.title')} ({doneCount}/{totalCount})
              </Typography>
              {activeDeviceName && (
                <Typography variant="caption" color="text.secondary">
                  {t('collect.batchCollecting').replace('{name}', activeDeviceName)}
                  {currentStep ? ` — ${currentStep}` : ''}
                </Typography>
              )}
            </Box>
          </Box>
          <LinearProgress
            variant="determinate"
            value={totalCount > 0 ? (doneCount / totalCount) * 100 : 0}
          />
        </Paper>
      )}

      {!running && totalCount > 0 && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            {t('collect.result')} ({t('collect.progress').replace('{done}', String(successCount)).replace('{total}', String(totalCount))})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {Object.entries(statuses).map(([name, s]) => (
              <Chip
                key={name}
                label={`${name}: ${s.status === 'success' ? t('collect.success') : s.error || t('collect.failed')}`}
                size="small"
                sx={{
                  bgcolor: s.status === 'success' ? 'rgba(45,212,110,0.1)' : 'rgba(239,68,68,0.1)',
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
