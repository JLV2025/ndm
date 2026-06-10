import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Box, Paper, Typography, CircularProgress, LinearProgress } from '@mui/material'
import { useI18n } from '../../i18n'

interface CollectionProgressProps {
  deviceName: string
  deviceIp: string
  onComplete: () => void
  onError: (msg: string) => void
}

const STEP_KEYS = [
  'connecting',
  'collecting_config',
  'collecting_logs',
  'collecting_interface',
  'analyzing',
  'saving',
] as const

const STEP_I18N: Record<string, string> = {
  idle: 'collect.stepIdle',
  connecting: 'collect.stepConnecting',
  collecting_config: 'collect.stepCollectingConfig',
  collecting_logs: 'collect.stepCollectingLogs',
  collecting_interface: 'collect.stepCollectingInterface',
  analyzing: 'collect.stepAnalyzing',
  saving: 'collect.stepSaving',
  failed: 'collect.stepFailed',
}

function stepIndex(step: string): number {
  const idx = STEP_KEYS.indexOf(step as typeof STEP_KEYS[number])
  return idx >= 0 ? idx : 0
}

const CollectionProgress: React.FC<CollectionProgressProps> = React.memo(({ deviceName, deviceIp, onComplete, onError }) => {
  const { t } = useI18n()
  const [step, setStep] = useState<string | null>(null)
  const [stepError, setStepError] = useState('')
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const completedRef = useRef(false)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  onCompleteRef.current = onComplete
  onErrorRef.current = onError

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`/api/collect/progress/${deviceName}`)
        if (!res.ok) return
        const data = await res.json()
        // 后端尚未写入任何进度时 step 为 null/undefined/空字符串 → 继续轮询
        const s: string | undefined = data.step
        if (s === 'idle' || s === 'failed') {
          if (pollTimer.current) clearInterval(pollTimer.current)
          if (!completedRef.current) {
            completedRef.current = true
            if (s === 'failed' || data.error) {
              onErrorRef.current(data.error || t('collect.stepFailed'))
            } else {
              onCompleteRef.current()
            }
          }
          return
        }
        if (s) {
          setStep(s)
          if (data.error) setStepError(data.error)
        }
        // s 为 undefined/null → 继续轮询
      } catch {
        // 网络错误忽略，继续轮询
      }
    }

    poll()
    pollTimer.current = setInterval(poll, 2000)

    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceName, deviceIp, t])

  const stepLabel = step === 'failed'
    ? `${t(STEP_I18N[step] || 'collect.stepFailed')}: ${stepError}`
    : step
      ? t(STEP_I18N[step] || 'collect.stepIdle')
      : t('collect.stepConnecting')

  const progressValue = step === 'failed' ? 100
    : step && step !== 'idle'
      ? ((stepIndex(step) + 1) / STEP_KEYS.length) * 100
      : 0

  return (
    <Paper sx={{ p: 2, mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {step === 'failed' ? (
          <CircularProgress size={24} color="error" />
        ) : (
          <CircularProgress size={24} />
        )}
        <Box sx={{ flex: 1 }}>
          <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 600 }}>
            {t('collect.singleTitle')}: {deviceName} ({deviceIp})
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {stepLabel}
          </Typography>
        </Box>
      </Box>
      <LinearProgress
        variant="determinate"
        value={progressValue}
        color={step === 'failed' ? 'error' : 'primary'}
        sx={{ mt: 1.5, bgcolor: 'rgba(255,255,255,0.06)' }}
      />
    </Paper>
  )
})

export default CollectionProgress
