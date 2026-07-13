import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Box, Paper, Typography, Chip, LinearProgress } from '@mui/material'
import type { BatchItemStatus, Device } from '../../types'
import { useI18n } from '../../i18n'

interface BatchCollectionPanelProps {
  running: boolean
  statuses: Record<string, BatchItemStatus>
  devices: Device[]
  /** 由父组件更新设备的实时进度（0-100）+ 步骤信息 */
  onDeviceProgress?: (name: string, pct: number, cmdDone: number, totalCmds: number) => void
}

/** 单个活跃设备的进度行 —— 通过轮询获取后端实时步骤 */
function ActiveDeviceRow({
  name,
  ip,
  polling,
  onProgress,
}: {
  name: string
  ip: string
  polling: boolean
  onProgress?: (pct: number, cmdDone: number, totalCmds: number) => void
}) {
  const { t } = useI18n()
  const [step, setStep] = useState('')
  const [progressPct, setProgressPct] = useState(0)
  const seenActiveRef = useRef(false)
  const completedRef = useRef(false)
  const onProgressRef = useRef(onProgress)
  onProgressRef.current = onProgress

  useEffect(() => {
    if (!polling) return

    seenActiveRef.current = false
    completedRef.current = false

    const poll = async () => {
      if (completedRef.current) return
      try {
        const res = await fetch(`/api/collect/progress/${name}`)
        const data = await res.json()
        const s: string = data.step || ''
        const pct: number = data.progress ?? 0
        const cd: number = data.cmd_done ?? 0
        const tc: number = data.total_cmds ?? 0

        if (s === 'complete') {
          completedRef.current = true
          setProgressPct(100)
          onProgressRef.current?.(100, cd || tc, tc) // 完成后全部计满
        } else if (s === 'failed') {
          completedRef.current = true
          setProgressPct(100)
          onProgressRef.current?.(100, cd, tc)
        } else if (s && s !== 'idle') {
          seenActiveRef.current = true
          setStep(s)
          setProgressPct(pct)
          onProgressRef.current?.(pct, cd, tc)
        }
      } catch { /* 网络抖动忽略 */ }
    }

    poll() // 立即查一次
    const id = setInterval(poll, 800)

    return () => {
      clearInterval(id)
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

    // 总进度 = 按所有设备的步骤数加权计算
    // success/failed → 该设备 totalCmds 步全部完成
    // pending → 只计入总步骤数，完成 0 步
    // pinging/collecting → cmdDone 步完成，totalCmds 步总计
    const overallPct = useMemo(() => {
      if (totalCount === 0) return 0
      let totalStepsDone = 0
      let totalStepsAll = 0
      for (const s of Object.values(statuses)) {
        const tc = s.totalCmds || 0
        const cd = s.cmdDone || 0
        if (s.status === 'success' || s.status === 'failed') {
          totalStepsDone += tc || 8
          totalStepsAll += tc || 8
        } else if (s.status === 'pending') {
          totalStepsAll += tc || 8
        } else {
          totalStepsDone += cd
          totalStepsAll += tc || 8
        }
      }
      return totalStepsAll > 0 ? (totalStepsDone / totalStepsAll) * 100 : 0
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
                    onProgress={(pct, cd, tc) => onDeviceProgress?.(name, pct, cd, tc)}
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
