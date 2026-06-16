import React, { useState, useEffect, useRef } from 'react'
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
  const [isPinging, setIsPinging] = useState(true) // Ping 阶段无后端进度，前端自行显示
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const completedRef = useRef(false)
  const seenActiveRef = useRef(false) // 是否见过非 idle 步骤（collect_device 已开始运行）
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
        const s: string | undefined = data.step

        // "complete" = 后端显式标记完成
        if (s === 'complete') {
          if (pollTimer.current) clearInterval(pollTimer.current)
          if (!completedRef.current) {
            completedRef.current = true
            onCompleteRef.current()
          }
          return
        }

        // "failed" = 后端报错
        if (s === 'failed') {
          if (pollTimer.current) clearInterval(pollTimer.current)
          if (!completedRef.current) {
            completedRef.current = true
            onErrorRef.current(data.error || t('collect.stepFailed'))
          }
          return
        }

        // "idle" / undefined / null / 空字符串 = 无进度记录
        // 情况 1: 后端 collect_device 还没开始（ping 阶段）→ 继续轮询
        // 情况 2: 后端已完成，进度已清除（complete 被清除后的残留）→ 仅在见过活跃步骤后才视为完成
        if (!s || s === 'idle') {
          if (seenActiveRef.current) {
            // 见过活跃步骤后又回到 idle → 后端已完成并清除
            if (pollTimer.current) clearInterval(pollTimer.current)
            if (!completedRef.current) {
              completedRef.current = true
              onCompleteRef.current()
            }
          }
          // 还没见过活跃步骤 → 后端未启动，继续轮询
          return
        }

        // 有效步骤（connecting / collecting_config / ...）→ 后端已启动
        seenActiveRef.current = true
        setIsPinging(false)
        setStep(s)
        if (data.error) setStepError(data.error)
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
      : isPinging
        ? t('devices.pinging').replace('{ip}', deviceIp) // Ping 阶段："检测设备可达性..."
        : t('collect.stepConnecting')

  const progressValue = step === 'failed' ? 100
    : step && step !== 'idle'
      ? ((stepIndex(step) + 1) / STEP_KEYS.length) * 100
      : isPinging
        ? 8 // Ping 阶段显示少量进度
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
