import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import {
  Box, Container, Paper, Typography, Grid, Chip, Alert,
  Select, MenuItem, CircularProgress,
  ToggleButton, ToggleButtonGroup,
  IconButton, Snackbar,
} from '@mui/material'
import {
  Visibility, Compare, Storage, ContentCopy,
} from '@mui/icons-material'
import { useSearchParams, useNavigate } from 'react-router-dom'
import type { AxiosResponse } from 'axios'
import { dataApi, deviceApi } from '../services/api'
import { sessionManager } from '../services/auth'

import type { Device } from '../types'
import LocationFilter from '../components/devices/LocationFilter'
import { useI18n } from '../i18n'

/** 语义颜色常量 — 对应 MUI OLED Dark 主题 */
const DIFF_COLORS = {
  added: { bg: 'rgba(45, 212, 110, 0.15)', text: '#5CE68C', border: '#2DD46E' },
  removed: { bg: 'rgba(239, 68, 68, 0.12)', text: '#F87171', border: '#EF4444' },
  same: { text: '#94A3B8' },
  info: { text: '#F8FAFC' },
} as const

function computeLCS(oldLines: string[], newLines: string[]): { type: 'same' | 'added' | 'removed'; text: string }[] {
  const m = oldLines.length
  const n = newLines.length
  // 构建 LCS DP 表
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  // 回溯构建 diff 序列
  const result: { type: 'same' | 'added' | 'removed'; text: string }[] = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.push({ type: 'same', text: oldLines[i - 1] })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'added', text: newLines[j - 1] })
      j--
    } else {
      result.push({ type: 'removed', text: oldLines[i - 1] })
      i--
    }
  }
  return result.reverse()
}

const Viewer: React.FC = () => {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialDevice = searchParams.get('device') || ''

  const [devices, setDevices] = useState<Device[]>([])
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [selectedDevice, setSelectedDevice] = useState(initialDevice)
  const [weeks, setWeeks] = useState<string[]>([])

  const [selectedWeek, setSelectedWeek] = useState('')
  const [selectedDataType, setSelectedDataType] = useState('')
  const [availableTypes, setAvailableTypes] = useState<string[]>([])
  const [collectionMeta, setCollectionMeta] = useState<Record<string, any> | null>(null)
  const [content, setContent] = useState('')
  const [copySnackOpen, setCopySnackOpen] = useState(false)

  const [compareMode, setCompareMode] = useState(false)
  const [compareWeek1, setCompareWeek1] = useState('')
  const [compareWeek2, setCompareWeek2] = useState('')
  const [compareFile, setCompareFile] = useState('')
  const [compareContent1, setCompareContent1] = useState('')
  const [compareContent2, setCompareContent2] = useState('')

  const [loading, setLoading] = useState(false)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState('')

  // Compare 模式下的文件选项（仍从文件系统读取 running-config.raw）

  useEffect(() => {
    if (!sessionManager.getSession()) { navigate('/login'); return }
    deviceApi.list().then((res: AxiosResponse<Device[]>) => setDevices(res.data)).catch(() => setError(t('common.loadDeviceListFailed')))
  }, [])

  useEffect(() => {
    if (!selectedDevice) return
    setLoading(true)
    dataApi.getDeviceWeeks(selectedDevice).then((res: AxiosResponse<{ weeks: string[] }>) => {
      setWeeks(res.data?.weeks || [])
    }).catch(() => setWeeks([])).finally(() => setLoading(false))
  }, [selectedDevice])

  // 选完周 → 拉取采集元信息和可用数据类型
  useEffect(() => {
    if (compareMode || !selectedDevice || !selectedWeek) return
    setSelectedDataType('')
    setContent('')
    setError('')
    setLoadingContent(true)
    dataApi.getCollection(selectedDevice, selectedWeek).then((res: AxiosResponse<{
      available_types: string[]; collected_at: string; metadata: Record<string, any>
    }>) => {
      const types = res.data?.available_types || []
      setAvailableTypes(types)
      setCollectionMeta(res.data?.metadata || null)
      if (types.length > 0) {
        setSelectedDataType(types[0])
      }
    }).catch(() => setError(t('common.loadFileFailed'))).finally(() => setLoadingContent(false))
  }, [compareMode, selectedDevice, selectedWeek])

  // 选完数据类型 → 拉取原始数据
  useEffect(() => {
    if (compareMode || !selectedDevice || !selectedWeek || !selectedDataType) return
    setLoadingContent(true)
    setError('')
    dataApi.getRawData(selectedDevice, selectedWeek, selectedDataType).then((res: AxiosResponse<{ content: string }>) => {
      setContent(res.data?.content || '')
    }).catch(() => setError(t('common.loadFileFailed'))).finally(() => setLoadingContent(false))
  }, [compareMode, selectedDevice, selectedWeek, selectedDataType])

  useEffect(() => {
    if (!compareMode || !selectedDevice || !compareWeek1 || !compareWeek2 || !compareFile) return
    setLoadingContent(true)
    setError('')
    Promise.all([
      dataApi.getFile(selectedDevice, compareWeek1, compareFile),
      dataApi.getFile(selectedDevice, compareWeek2, compareFile),
    ]).then(([r1, r2]) => {
      setCompareContent1(r1.data?.content || '')
      setCompareContent2(r2.data?.content || '')
    }).catch(() => setError(t('common.loadCompareFailed'))).finally(() => setLoadingContent(false))
  }, [compareMode, selectedDevice, compareWeek1, compareWeek2, compareFile])

  const uniqueLocations: string[] = useMemo(() => [...new Set(devices.map(d => d.location).filter((l): l is string => !!l))].sort(), [devices])

  const filteredDevices = selectedLocation
    ? devices.filter((d) => (d.location || '').toUpperCase() === selectedLocation.toUpperCase())
    : devices

  const handleLocationChange = (v: string | null) => {
    setSelectedLocation(v)
    if (v && selectedDevice) {
      const device = devices.find(d => d.name === selectedDevice)
      if (!device || (device.location || '').toUpperCase() !== v.toUpperCase()) {
        setSelectedDevice('')
      }
    }
  }

  useEffect(() => {
    if (initialDevice && !selectedDevice && devices.length > 0) {
      const d = devices.find((x: Device) => x.name === initialDevice)
      if (d) {
        setSelectedDevice(initialDevice)
        if (d.location) setSelectedLocation(d.location.toUpperCase())
      }
    }
  }, [initialDevice, devices])

  const diffLines = useMemo(() => {
    if (!compareContent1 || !compareContent2) return null
    return computeLCS(
      compareContent2.split('\n'),
      compareContent1.split('\n'),
    )
  }, [compareContent1, compareContent2])

  // 双面板同步滚动
  const leftPanelRef = useRef<HTMLDivElement>(null)
  const rightPanelRef = useRef<HTMLDivElement>(null)
  const syncingLeft = useRef(false)
  const syncingRight = useRef(false)

  const handleLeftScroll = useCallback(() => {
    if (syncingRight.current) return
    syncingLeft.current = true
    if (rightPanelRef.current && leftPanelRef.current) {
      rightPanelRef.current.scrollTop = leftPanelRef.current.scrollTop
    }
    requestAnimationFrame(() => { syncingLeft.current = false })
  }, [])

  const handleRightScroll = useCallback(() => {
    if (syncingLeft.current) return
    syncingRight.current = true
    if (leftPanelRef.current && rightPanelRef.current) {
      leftPanelRef.current.scrollTop = rightPanelRef.current.scrollTop
    }
    requestAnimationFrame(() => { syncingRight.current = false })
  }, [])

  const toggleGroupSx = {
    '& .MuiToggleButton-root': {
      color: 'text.secondary',
      borderColor: 'divider',
      px: 2, py: 0.25, fontSize: '0.7rem', fontWeight: 600,
      textTransform: 'none', borderRadius: '6px !important',
      '&.Mui-selected': {
        color: 'primary.main',
        bgcolor: 'rgba(45,212,110,0.1)',
        borderColor: 'rgba(45,212,110,0.3)',
      },
      '&:hover': { bgcolor: 'rgba(45,212,110,0.06)' },
    },
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopySnackOpen(true)
    } catch {
      // 降级方案
      const ta = document.createElement('textarea')
      ta.value = content
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopySnackOpen(true)
    }
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 顶部标题栏 */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              <span style={{ color: '#2DD46E' }}>{t('viewer.title')}</span>
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              {t('viewer.description')}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <ToggleButtonGroup value={compareMode ? 'compare' : 'single'} exclusive size="small"
              onChange={(_, v) => { if (v) { setCompareMode(v === 'compare'); setError(''); } }}
              sx={toggleGroupSx}>
              <ToggleButton value="single"><Visibility sx={{ fontSize: 16, mr: 0.5 }} />Single</ToggleButton>
              <ToggleButton value="compare"><Compare sx={{ fontSize: 16, mr: 0.5 }} />Compare</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>
      </Paper>

      {/* 筛选面板 */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <LocationFilter selectedLocation={selectedLocation} onChange={handleLocationChange} locations={uniqueLocations} />

        <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>{t('viewer.deviceLabel')}</Typography>
          <Select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)} displayEmpty size="small" sx={{ minWidth: 240 }}>
            <MenuItem value="" disabled><em>{t('viewer.selectDevice')}</em></MenuItem>
            {filteredDevices.map((d: Device) => (
              <MenuItem key={d.name} value={d.name}>{d.name} ({d.ip})</MenuItem>
            ))}
          </Select>
        </Box>
      </Paper>

      {/* 内容区域 */}
      {!selectedDevice && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Storage sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography color="text.secondary">{t('viewer.selectHint')}</Typography>
        </Paper>
      )}

      {loading && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress />
        </Paper>
      )}

      {selectedDevice && !loading && !compareMode && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
            {t('viewer.configHistory')} ({selectedDevice})
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={2}>
              <Select value={selectedWeek} onChange={(e) => { setSelectedWeek(e.target.value); }} displayEmpty fullWidth size="small">
                <MenuItem value="" disabled><em>{t('viewer.selectWeek')}</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>

            {/* 数据类型按钮组 — 动态显示 */}
            {availableTypes.length > 0 && (
              <Grid item>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>{t('viewer.dataTypeLabel')}:</Typography>
                  <ToggleButtonGroup value={selectedDataType} exclusive size="small"
                    onChange={(_, v) => { if (v) setSelectedDataType(v); }}
                    sx={toggleGroupSx}>
                    {availableTypes.map((dt) => (
                      <ToggleButton key={dt} value={dt}>
                        {t(`viewer.dataTypes.${dt}` as any, dt)}
                      </ToggleButton>
                    ))}
                  </ToggleButtonGroup>
                </Box>
              </Grid>
            )}
          </Grid>

          {/* 元信息 */}
          {collectionMeta && (
            <Box sx={{ mt: 1.5, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {collectionMeta.software_version && (
                <Chip label={`${t('viewer.version')}: ${collectionMeta.software_version}`} size="small"
                  sx={{ bgcolor: 'rgba(59,130,246,0.1)', color: 'info.main', height: 20, fontSize: '0.65rem' }} />
              )}
              {collectionMeta.model && (
                <Chip label={collectionMeta.model} size="small"
                  sx={{ bgcolor: 'rgba(45,212,110,0.1)', color: 'success.main', height: 20, fontSize: '0.65rem' }} />
              )}
              {collectionMeta.running_config_lines > 0 && (
                <Chip label={`${collectionMeta.running_config_lines} ${t('viewer.lines')}`} size="small"
                  sx={{ bgcolor: 'rgba(245,158,11,0.1)', color: 'warning.main', height: 20, fontSize: '0.65rem' }} />
              )}
            </Box>
          )}

          {loadingContent && <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress /></Box>}
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

          {!loadingContent && content && (
            <Box sx={{ mt: 2 }}>
              <Paper sx={{ p: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.65rem' }}>
                    {t(`viewer.dataTypes.${selectedDataType}` as any, selectedDataType)}
                  </Typography>
                  <IconButton size="small" onClick={handleCopy} title={t('viewer.copyButton')}
                    sx={{ color: 'text.secondary', '&:hover': { color: 'primary.main' } }}>
                    <ContentCopy sx={{ fontSize: 16 }} />
                  </IconButton>
                </Box>
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","Fira Code",monospace', margin: 0, fontSize: '0.75rem', color: '#F8FAFC', lineHeight: 1.6, maxHeight: '65vh', overflow: 'auto' }}>{content}</pre>
              </Paper>
            </Box>
          )}

          <Snackbar open={copySnackOpen} autoHideDuration={2000} onClose={() => setCopySnackOpen(false)}
            message={t('viewer.copied')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} />
        </Paper>
      )}

      {/* 对比模式 */}
      {selectedDevice && !loading && compareMode && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
            {t('viewer.configCompare')} ({selectedDevice})
          </Typography>
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={6} sm={3}>
              <Typography variant="caption" color="info.main" sx={{ mb: 0.5, display: 'block' }}>{t('viewer.newerVersion')} ({t('viewer.previous')})</Typography>
              <Select value={compareWeek1} onChange={(e) => setCompareWeek1(e.target.value)} displayEmpty fullWidth size="small">
                <MenuItem value="" disabled><em>{t('viewer.selectWeek')}</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Typography variant="caption" color="warning.main" sx={{ mb: 0.5, display: 'block' }}>{t('viewer.olderVersion')} ({t('viewer.next')})</Typography>
              <Select value={compareWeek2} onChange={(e) => setCompareWeek2(e.target.value)} displayEmpty fullWidth size="small">
                <MenuItem value="" disabled><em>{t('viewer.selectWeek')}</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>{t('viewer.fileLabel')}</Typography>
              <Select value={compareFile} onChange={(e) => setCompareFile(e.target.value)} displayEmpty fullWidth size="small">
                <MenuItem value="" disabled><em>{t('viewer.selectFile')}</em></MenuItem>
                <MenuItem value="running-config.raw">running-config.raw</MenuItem>
              </Select>
            </Grid>
          </Grid>

          {loadingContent && <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress /></Box>}
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

          {!loadingContent && compareContent1 && compareContent2 && (
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Paper sx={{ p: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'rgba(59,130,246,0.3)', borderRadius: 1, height: '70vh', overflow: 'auto' }} ref={leftPanelRef} onScroll={handleLeftScroll}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Chip label={`${compareWeek1}`} size="small" sx={{ bgcolor: 'rgba(59,130,246,0.1)', color: 'info.main', height: 18, fontSize: '0.65rem' }} />
                    <Typography variant="caption" color="text.secondary">{t('viewer.newerVersion')}</Typography>
                  </Box>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","Fira Code",monospace', margin: 0, fontSize: '0.7rem', lineHeight: 1.6 }}>
                    {diffLines
                      ? diffLines.map((item, i) => (
                          <div
                            key={i}
                            style={{
                              backgroundColor: item.type === 'added' ? DIFF_COLORS.added.bg : item.type === 'removed' ? 'transparent' : 'transparent',
                              color: item.type === 'added' ? DIFF_COLORS.added.text : item.type === 'removed' ? DIFF_COLORS.removed.text : DIFF_COLORS.info.text,
                              opacity: item.type === 'removed' ? 0.4 : 1,
                              paddingLeft: 16,
                              borderLeft: item.type === 'added' ? `3px solid ${DIFF_COLORS.added.border}` : item.type === 'removed' ? `3px solid ${DIFF_COLORS.removed.border}` : '3px solid transparent',
                              minHeight: '1.6em',
                            }}
                          >
                            {item.type === 'added' && '+ '}{item.type === 'removed' && '- '}{item.text}
                          </div>
                        ))
                      : compareContent1.split('\n').map((line, i) => <div key={i} style={{ color: DIFF_COLORS.info.text }}>{line}</div>)
                    }
                  </pre>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper sx={{ p: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'rgba(245,158,11,0.2)', borderRadius: 1, height: '70vh', overflow: 'auto' }} ref={rightPanelRef} onScroll={handleRightScroll}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Chip label={`${compareWeek2}`} size="small" sx={{ bgcolor: 'rgba(245,158,11,0.1)', color: 'warning.main', height: 18, fontSize: '0.65rem' }} />
                    <Typography variant="caption" color="text.secondary">{t('viewer.olderVersion')}</Typography>
                  </Box>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","Fira Code",monospace', margin: 0, fontSize: '0.7rem', lineHeight: 1.6 }}>
                    {diffLines
                      ? diffLines.map((item, i) => (
                          <div
                            key={i}
                            style={{
                              backgroundColor: item.type === 'removed' ? DIFF_COLORS.removed.bg : item.type === 'added' ? 'transparent' : 'transparent',
                              color: item.type === 'removed' ? DIFF_COLORS.removed.text : item.type === 'added' ? DIFF_COLORS.added.text : DIFF_COLORS.same.text,
                              opacity: item.type === 'added' ? 0.4 : 1,
                              paddingLeft: 16,
                              borderLeft: item.type === 'removed' ? `3px solid ${DIFF_COLORS.removed.border}` : item.type === 'added' ? `3px solid ${DIFF_COLORS.added.border}` : '3px solid transparent',
                              minHeight: '1.6em',
                            }}
                          >
                            {item.type === 'added' && '+ '}{item.type === 'removed' && '- '}{item.text}
                          </div>
                        ))
                      : compareContent2.split('\n').map((line, i) => <div key={i} style={{ color: DIFF_COLORS.same.text }}>{line}</div>)
                    }
                  </pre>
                </Paper>
              </Grid>
            </Grid>
          )}
        </Paper>
      )}
    </Container>
  )
}

export default Viewer
