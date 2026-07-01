import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import {
  Box, Container, Paper, Typography, Grid, Tabs, Tab, Chip, Alert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Select, MenuItem, CircularProgress,
  ToggleButton, ToggleButtonGroup,
} from '@mui/material'
import {
  Description, Timeline, Terminal, Visibility, Compare, Storage,
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
  const [files, setFiles] = useState<string[]>([])

  const [selectedWeek, setSelectedWeek] = useState('')
  const [selectedFile, setSelectedFile] = useState('')
  const [content, setContent] = useState('')
  const [activeTab, setActiveTab] = useState(0)

  const [compareMode, setCompareMode] = useState(false)
  const [compareWeek1, setCompareWeek1] = useState('')
  const [compareWeek2, setCompareWeek2] = useState('')
  const [compareFile, setCompareFile] = useState('')
  const [compareContent1, setCompareContent1] = useState('')
  const [compareContent2, setCompareContent2] = useState('')

  const [loading, setLoading] = useState(false)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState('')

  // 根据选中设备类型和平台动态计算可用文件列表
  const selectedDeviceObj = devices.find((d: Device) => d.name === selectedDevice) || {} as Partial<Device>
  const selectedDeviceType = selectedDeviceObj.type || ''
  const selectedDevicePlatform = selectedDeviceObj.platform || ''
  const allFileOptions = ['running-config.raw', 'interface-status.raw', 'version.raw', 'interface-utilization.raw', 'validation.json', 'performance.json', 'change.json', 'summary.txt']
  const availableFiles = useMemo(() => {
    if (files.length > 0) return files
    if (!selectedDeviceType) return allFileOptions
    if (selectedDeviceType === 'cisco_ios') {
      if (selectedDevicePlatform === 'cisco_ios_xe') {
        // Cisco IOS XE：支持日志收集（show logging | tail 100）
        return [...allFileOptions, 'logs.raw', 'switch-detail.raw']
      }
      // Cisco IOS：日志不收集，只加堆叠
      return [...allFileOptions.filter((f) => !['logs.raw'].includes(f)), 'switch-detail.raw']
    }
    if (selectedDeviceType === 'aruba_aoscx') {
      return [...allFileOptions, 'system.raw', 'vsf.raw']
    }
    return allFileOptions
  }, [files, selectedDeviceType, selectedDevicePlatform])

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

  useEffect(() => {
    if (compareMode || !selectedDevice || !selectedWeek || !selectedFile) return
    setLoadingContent(true)
    setError('')
    dataApi.getFile(selectedDevice, selectedWeek, selectedFile).then((res: AxiosResponse<{ content: string }>) => {
      setContent(res.data?.content || '')
    }).catch(() => setError(t('common.loadFileFailed'))).finally(() => setLoadingContent(false))
  }, [selectedDevice, selectedWeek, selectedFile, compareMode])

  useEffect(() => {
    if (!selectedDevice || !selectedWeek) return
    dataApi.getFilesList(selectedDevice, selectedWeek).then((res: AxiosResponse<{ files: string[] }>) => {
      setFiles(res.data?.files || [])
    }).catch(() => setFiles([]))
  }, [selectedDevice, selectedWeek])

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

  const renderContentTabs = (text: string) => {
    if (!text) return null
    return (
      <>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 2 }}>
          <Tab icon={<Terminal />} label="Raw" sx={{ fontSize: '0.7rem' }} />
          <Tab icon={<Description />} label="Formatted" sx={{ fontSize: '0.7rem' }} />
          <Tab icon={<Timeline />} label="Analysis" sx={{ fontSize: '0.7rem' }} />
        </Tabs>
        {renderTabContent(text, activeTab)}
      </>
    )
  }

  const renderTabContent = (text: string, tab: number) => {
    if (tab === 0) {
      return (
        <Paper sx={{ p: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
            <Terminal sx={{ color: 'primary.main', fontSize: 16 }} />
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.65rem' }}>Raw Content</Typography>
          </Box>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","Fira Code",monospace', margin: 0, fontSize: '0.75rem', color: '#F8FAFC', lineHeight: 1.6 }}>{text}</pre>
        </Paper>
      )
    }
    if (tab === 1) {
      try {
        const json = JSON.parse(text)
        return (
          <Paper sx={{ p: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Description sx={{ color: 'primary.main', fontSize: 16 }} />
              <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.65rem' }}>JSON Formatted</Typography>
            </Box>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","Fira Code",monospace', margin: 0, fontSize: '0.75rem', color: '#F8FAFC', lineHeight: 1.6 }}>{JSON.stringify(json, null, 2)}</pre>
          </Paper>
        )
      } catch { return null }
    }
    if (tab === 2) {
      try {
        const json = JSON.parse(text)

        // 性能分析（必须最先检查，避免 performance.json 的 errors dict 误入 validation 分支）
        if (json.interface_summary) {
          return (
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Performance Analysis</Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[{ label: 'Total', value: json.interface_summary.total, color: '#3B82F6' }, { label: 'UP', value: json.interface_summary.up, color: '#2DD46E' }, { label: 'DOWN', value: json.interface_summary.down, color: '#EF4444' }].map((item) => (
                  <Grid item xs={4} key={item.label}>
                    <Box sx={{ p: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>{item.label}</Typography>
                      <Typography variant="h4" sx={{ color: item.color, fontWeight: 700 }}>{item.value}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Interface</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {json.interface_summary.details?.slice(0, 10).map((d: { name: string; status: string; status_up: boolean }, idx: number) => (
                      <TableRow key={idx} hover>
                        <TableCell sx={{ fontSize: '0.75rem' }}>{d.name}</TableCell>
                        <TableCell>
                          <Chip label={d.status} size="small" sx={{
                            bgcolor: d.status_up ? 'rgba(45,212,110,0.1)' : 'rgba(239,68,68,0.1)',
                            color: d.status_up ? 'success.main' : 'error.main',
                            height: 18, fontSize: '0.65rem',
                          }} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )
        }

        // 配置验证（errors 必须是数组类型，避免与 performance.json 的 errors dict 冲突）
        if (Array.isArray(json.errors)) {
          return (
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Config Validation</Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[{ label: 'Errors', value: json.summary?.errors ?? 0, color: '#EF4444' }, { label: 'Warnings', value: json.summary?.warnings ?? 0, color: '#F59E0B' }, { label: 'Info', value: json.summary?.info ?? 0, color: '#3B82F6' }].map((item) => (
                  <Grid item xs={4} key={item.label}>
                    <Box sx={{ p: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>{item.label}</Typography>
                      <Typography variant="h4" sx={{ color: item.color, fontWeight: 700 }}>{item.value}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Type</TableCell>
                      <TableCell>Message</TableCell>
                      <TableCell align="right">Level</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {json.errors.map((err: { type: string; message: string; severity: string }, idx: number) => (
                      <TableRow key={idx} hover>
                        <TableCell sx={{ fontSize: '0.75rem' }}>{err.type}</TableCell>
                        <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>{err.message}</TableCell>
                        <TableCell align="right">
                          <Chip label={err.severity} size="small" sx={{
                            bgcolor: err.severity === 'error' ? 'rgba(239,68,68,0.1)' : err.severity === 'warning' ? 'rgba(245,158,11,0.1)' : 'rgba(59,130,246,0.1)',
                            color: err.severity === 'error' ? 'error.main' : err.severity === 'warning' ? 'warning.main' : 'info.main',
                            fontWeight: 500, height: 18, fontSize: '0.65rem',
                          }} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )
        }

        // 变更检测
        if (json.summary) {
          return (
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Change Detection</Typography>
              <Grid container spacing={2}>
                {[{ label: 'Added', value: json.summary.added, color: '#2DD46E' }, { label: 'Removed', value: json.summary.removed, color: '#EF4444' }, { label: 'Has Changes', value: json.has_changes ? 'Yes' : 'No', color: json.has_changes ? '#F59E0B' : '#3B82F6' }].map((item) => (
                  <Grid item xs={4} key={item.label}>
                    <Box sx={{ p: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 1, textAlign: 'center' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>{item.label}</Typography>
                      <Typography variant="h4" sx={{ color: item.color, fontWeight: 700 }}>{item.value}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          )
        }
      } catch { return null }
    }
    return null
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
          <Select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)} displayEmpty fullWidth size="small">
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
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <Select value={selectedWeek} onChange={(e) => { setSelectedWeek(e.target.value); setSelectedFile(''); }} displayEmpty fullWidth size="small">
                <MenuItem value="" disabled><em>{t('viewer.selectWeek')}</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Select value={selectedFile} onChange={(e) => setSelectedFile(e.target.value)} displayEmpty fullWidth size="small" disabled={!selectedWeek}>
                <MenuItem value="" disabled><em>{t('viewer.selectFile')}</em></MenuItem>
                {files.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
              </Select>
            </Grid>
          </Grid>

          {loadingContent && <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress /></Box>}
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

          {!loadingContent && content && (
            <Box sx={{ mt: 2 }}>
              {renderContentTabs(content)}
            </Box>
          )}
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
                {availableFiles.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
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
