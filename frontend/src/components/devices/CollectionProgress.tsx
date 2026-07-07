import React, { useState, useEffect, useRef } from 'react'
import { Box, Paper, Typography, CircularProgress, LinearProgress } from '@mui/material'
import { useI18n } from '../../i18n'

interface CollectionProgressProps {
  deviceName: string
  deviceIp: string
  onComplete: () => void
  onError: (msg: string) => void
}

const CollectionProgress: React.FC<CollectionProgressProps> = React.memo(({ deviceName, deviceIp, onComplete, onError }) => {
  const { t } = useI18n()
  const [step, setStep] = useState<string | null>(null)
  const [progressPct, setProgressPct] = useState(0)
  const [stepError, setStepError] = useState('')
  const completedRef = useRef(false)
  const seenActiveRef = useRef(false)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  onCompleteRef.current = onComplete
  onErrorRef.current = onError

  useEffect(() => {
    const es = new EventSource(`/api/collect/progress/stream/${deviceName}`)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const s: string = data.step || ''
        const err: string = data.error || ''
        const pct: number = data.progress ?? 0

        if (s === 'complete') {
          es.close()
          if (!completedRef.current) {
            completedRef.current = true
            onCompleteRef.current()
          }
          return
        }

        if (s === 'failed') {
          es.close()
          if (!completedRef.current) {
            completedRef.current = true
            onErrorRef.current(err || t('collect.stepFailed'))
          }
          return
        }

        if (!s || s === 'idle') {
          return
        }

        seenActiveRef.current = true
        setStep(s)
        setProgressPct(pct)
        if (err) setStepError(err)
      } catch { /* ignore */ }
    }

    es.onerror = () => {
      if (seenActiveRef.current) {
        es.close()
        if (!completedRef.current) {
          completedRef.current = true
          onErrorRef.current(t('collect.connectionLost'))
        }
        return
      }
    }

    return () => { es.close() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceName, deviceIp, t])

  const stepLabel = step === 'failed'
    ? `${t('collect.stepFailed')}: ${stepError}`
    : step === 'ping' || step === 'connecting'
      ? t('devices.pinging').replace('{ip}', deviceIp)
      : `${Math.round(progressPct)}%`

  const progressValue = step === 'failed' ? 100 : progressPct

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
