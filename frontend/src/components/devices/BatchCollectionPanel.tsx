import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Box, Paper, Typography, Chip, LinearProgress } from '@mui/material'
import type { BatchItemStatus, Device } from '../../types'
import { useI18n } from '../../i18n'

interface BatchCollectionPanelProps {
  running: boolean
  statuses: Record<string, BatchItemStatus>
  devices: Device[]
  /** 由父组件更新设备的实时进度（0-100） */
  onDeviceProgress?: (name: string, pct: number) => void
}

/** 单个活跃设备的进度行 —— 通过 SSE 实时获取后端推送的步骤 */
function ActiveDeviceRow({
  name,
  ip,
  polling,
  onProgress,
}: {
  name: string
  ip: string
  polling: boolean
  onProgress?: (pct: number) => void
}) {
  const { t } = useI18n()
  const [step, setStep] = useState('')
  const [progressPct, setProgressPct] = useState(0)
  const seenActiveRef = useRef(false)
  const onProgressRef = useRef(onProgress)
  onProgressRef.current = onProgress

  useEffect(() => {
    if (!polling) return

    const es = new EventSource(`/api/collect/progress/stream/${name}`)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const s: string = data.step || ''
        const pct: number = data.progress ?? 0
        if (s === 'complete') {
          onProgressRef.current?.(100)
          es.close()
        } else if (s === 'failed') {
          onProgressRef.current?.(100)
          es.close()
        } else if (s && s !== 'idle') {
          seenActiveRef.current = true
          setStep(s)
          setProgressPct(pct)
          onProgressRef.current?.(pct)
        }
      } catch { /* ignore */ }
    }

    es.onerror = () => {
      if (seenActiveRef.current) {
        es.close()
      }
    }

    return () => {
      es.close()
    }
  }, [name, polling])

  const stepLabel = !step
    ? t('devices.pinging').replace('{ip}', ip)
    : t(`collect.stepCollectingConfig`)

  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {name}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {step ? `${Math.round(progressPct)}%` : stepLabel}
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={progressPct}
        sx={{ bgcolor: 'rgba(255,255,255,0.06)', height: 6, borderRadius: 1 }}
      />
    </Box>
  )
}

const BatchCollectionPanel: React.FC<BatchCollectionPanelProps> = React.memo(
  ({ running, statuses, devices, onDeviceProgress }) => {
    const { t } = useI18n()

    const deviceMap = new Map<string, Device>()
    devices.forEach((d) => deviceMap.set(d.name, d))

    const successCount = Object.values(statuses).filter((s) => s.status === 'success').length
    const failedCount = Object.values(statuses).filter((s) => s.status === 'failed').length
    const totalCount = Object.keys(statuses).length
    const doneCount = successCount + failedCount

    // 活跃设备
    const activeNames = Object.entries(statuses)
      .filter(([, s]) => s.status === 'pinging' || s.status === 'collecting')
      .map(([name]) => name)

    const doneEntries = Object.entries(statuses).filter(
      ([, s]) => s.status === 'success' || s.status === 'failed'
    )

    // 总进度 = 所有设备进度的平均值
    // success/failed → 100%, pending → 0%, pinging/collecting → SSE 推送的实时值
    const overallPct = useMemo(() => {
      if (totalCount === 0) return 0
      let sum = 0
      for (const s of Object.values(statuses)) {
        if (s.status === 'success' || s.status === 'failed') {
          sum += 100
        } else if (s.status === 'pending') {
          sum += 0
        } else {
          sum += s.progress ?? 0
        }
      }
      return sum / totalCount
    }, [statuses, totalCount])

    return (
      <>
        {running && totalCount > 0 && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
              {t('collect.title')} — {t('collect.progress')
                .replace('{done}', String(doneCount))
                .replace('{total}', String(totalCount))}
            </Typography>

            {activeNames.length > 0 ? (
              activeNames.map((name) => {
                const dev = deviceMap.get(name)
                return (
                  <ActiveDeviceRow
                    key={name}
                    name={name}
                    ip={dev?.ip || ''}
                    polling={running}
                    onProgress={(pct) => onDeviceProgress?.(name, pct)}
                  />
                )
              })
            ) : (
              <Typography variant="caption" color="text.secondary">
                {t('devices.batchRunning')}
              </Typography>
            )}

            {/* 总进度条 —— 按所有设备的步骤数累计 */}
            <LinearProgress
              variant="determinate"
              value={overallPct}
              sx={{ mt: 1.5, height: 10, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.06)' }}
            />
          </Paper>
        )}

        {!running && totalCount > 0 && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
              {t('devices.batchResult')} ({successCount}/{totalCount})
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {doneEntries.map(([name, s]) => (
                <Chip
                  key={name}
                  label={`${name}: ${
                    s.status === 'success'
                      ? t('collect.success')
                      : s.error || t('collect.failed')
                  }`}
                  size="small"
                  sx={{
                    bgcolor:
                      s.status === 'success'
                        ? 'rgba(45,212,110,0.1)'
                        : 'rgba(239,68,68,0.1)',
                    color:
                      s.status === 'success' ? 'success.main' : 'error.main',
                    fontSize: '0.7rem',
                  }}
                />
              ))}
            </Box>
          </Paper>
        )}
      </>
    )
  }
)

export default BatchCollectionPanel
