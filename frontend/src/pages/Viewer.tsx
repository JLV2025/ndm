import React, { useState, useEffect, useMemo } from 'react'
import {
  Box, Container, Paper, Typography, Grid, Tabs, Tab, Chip, Alert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Select, MenuItem, CircularProgress,
  ToggleButton, ToggleButtonGroup,
} from '@mui/material'
import {
  Description, Timeline, Terminal, Visibility, Compare, Storage,
} from '@mui/icons-material'
import { useSearchParams } from 'react-router-dom'
import { dataApi, deviceApi } from '../services/api'
import { sessionManager } from '../services/auth'

const LOCATIONS_ROW1 = ['BJD', 'BJQ', 'DZN', 'PVG', 'SHA', 'SZX', 'ZGN']
const LOCATIONS_ROW2 = ['PEK', 'DEZ', 'UCD', 'SJY']
// 简单逐行 diff
function computeDiff(oldLines: string[], newLines: string[]): { type: 'same' | 'added' | 'removed'; text: string }[] {
  const result: { type: 'same' | 'added' | 'removed'; text: string }[] = []
  const oldSet = new Set(oldLines)
  const newSet = new Set(newLines)

  // 逐行比较：标记新增和删除
  let oi = 0
  let ni = 0
  while (oi < oldLines.length || ni < newLines.length) {
    if (oi >= oldLines.length) {
      result.push({ type: 'added', text: newLines[ni] })
      ni++
    } else if (ni >= newLines.length) {
      result.push({ type: 'removed', text: oldLines[oi] })
      oi++
    } else if (oldLines[oi] === newLines[ni]) {
      result.push({ type: 'same', text: oldLines[oi] })
      oi++; ni++
    } else if (newSet.has(oldLines[oi]) && !oldSet.has(newLines[ni])) {
      result.push({ type: 'added', text: newLines[ni] })
      ni++
    } else if (!newSet.has(oldLines[oi]) && oldSet.has(newLines[ni])) {
      result.push({ type: 'removed', text: oldLines[oi] })
      oi++
    } else {
      result.push({ type: 'removed', text: oldLines[oi] })
      oi++
    }
  }
  return result
}

const Viewer: React.FC = () => {
  const [searchParams] = useSearchParams()
  const initialDevice = searchParams.get('device') || ''

  const [devices, setDevices] = useState<any[]>([])
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [selectedDevice, setSelectedDevice] = useState(initialDevice)
  const [weeks, setWeeks] = useState<string[]>([])
  const [files, setFiles] = useState<string[]>([])

  // 单次查看
  const [selectedWeek, setSelectedWeek] = useState('')
  const [selectedFile, setSelectedFile] = useState('')
  const [content, setContent] = useState('')
  const [activeTab, setActiveTab] = useState(0)

  // 对比模式
  const [compareMode, setCompareMode] = useState(false)
  const [compareWeek1, setCompareWeek1] = useState('')
  const [compareWeek2, setCompareWeek2] = useState('')
  const [compareFile, setCompareFile] = useState('')
  const [compareContent1, setCompareContent1] = useState('')
  const [compareContent2, setCompareContent2] = useState('')

  const [loading, setLoading] = useState(false)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionManager.getSession()) { window.location.href = '/login'; return }
    deviceApi.list().then((res: any) => setDevices(res.data)).catch(() => {})
  }, [])

  // 切换设备时加载周列表
  useEffect(() => {
    if (!selectedDevice) return
    setLoading(true)
    dataApi.getDeviceWeeks(selectedDevice).then((res: any) => {
      setWeeks(res.weeks || [])
    }).catch(() => setWeeks([])).finally(() => setLoading(false))
  }, [selectedDevice])

  // 单次模式：选好 week + file 后加载内容
  useEffect(() => {
    if (compareMode || !selectedDevice || !selectedWeek || !selectedFile) return
    setLoadingContent(true)
    setError('')
    dataApi.getFile(selectedDevice, selectedWeek, selectedFile).then((res: any) => {
      setContent(res.data?.content || '')
    }).catch(() => setError('加载文件失败')).finally(() => setLoadingContent(false))
  }, [selectedDevice, selectedWeek, selectedFile, compareMode])

  // 切换 week 时加载文件列表
  useEffect(() => {
    if (!selectedDevice || !selectedWeek) return
    dataApi.getFilesList(selectedDevice, selectedWeek).then((res: any) => {
      setFiles(res.data?.files || [])
    }).catch(() => setFiles([]))
  }, [selectedDevice, selectedWeek])

  // 对比模式：加载两份内容
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
    }).catch(() => setError('加载对比文件失败')).finally(() => setLoadingContent(false))
  }, [compareMode, selectedDevice, compareWeek1, compareWeek2, compareFile])

  // 按 location 筛选设备
  const filteredDevices = selectedLocation
    ? devices.filter((d) => (d.location || '').toUpperCase() === selectedLocation.toUpperCase())
    : devices

  // 如果 URL 带了 device 参数且未选择设备，自动选择
  useEffect(() => {
    if (initialDevice && !selectedDevice && devices.length > 0) {
      const d = devices.find((x: any) => x.name === initialDevice)
      if (d) {
        setSelectedDevice(initialDevice)
        if (d.location) setSelectedLocation(d.location.toUpperCase())
      }
    }
  }, [initialDevice, devices])

  const diffLines = useMemo(() => {
    if (!compareContent1 || !compareContent2) return null
    return computeDiff(
      compareContent2.split('\n'),  // old (右侧)
      compareContent1.split('\n'),  // new (左侧)
    )
  }, [compareContent1, compareContent2])

  const renderContentTabs = (text: string) => {
    if (!text) return null
    return (
      <>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}
          sx={{ mb: 2, borderBottom: '1px solid rgba(52,211,153,0.2)', '& .MuiTabs-indicator': { backgroundColor: '#34d399' } }}>
          <Tab icon={<Terminal />} label="Raw" sx={{ color: '#94a3b8', '&.Mui-selected': { color: '#34d399' }, textTransform: 'uppercase', fontSize: '0.7rem' }} />
          <Tab icon={<Description />} label="Formatted" sx={{ color: '#94a3b8', '&.Mui-selected': { color: '#34d399' }, textTransform: 'uppercase', fontSize: '0.7rem' }} />
          <Tab icon={<Timeline />} label="Analysis" sx={{ color: '#94a3b8', '&.Mui-selected': { color: '#34d399' }, textTransform: 'uppercase', fontSize: '0.7rem' }} />
        </Tabs>
        {renderTabContent(text, activeTab)}
      </>
    )
  }

  const renderTabContent = (text: string, tab: number) => {
    if (tab === 0) {
      return (
        <Paper sx={{ p: 2, bgcolor: '#0a0f1a', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, pb: 1, borderBottom: '1px solid rgba(52,211,153,0.2)' }}>
            <Terminal sx={{ color: '#34d399', fontSize: 16 }} />
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.65rem' }}>Raw Content</Typography>
          </Box>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","JetBrains Mono",monospace', margin: 0, fontSize: '0.75rem', color: '#e2e8f0', lineHeight: 1.6 }}>{text}</pre>
        </Paper>
      )
    }
    if (tab === 1) {
      try {
        const json = JSON.parse(text)
        return (
          <Paper sx={{ p: 2, bgcolor: '#0a0f1a', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, pb: 1, borderBottom: '1px solid rgba(52,211,153,0.2)' }}>
              <Description sx={{ color: '#34d399', fontSize: 16 }} />
              <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.65rem' }}>JSON Formatted</Typography>
            </Box>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","JetBrains Mono",monospace', margin: 0, fontSize: '0.75rem', color: '#e2e8f0', lineHeight: 1.6 }}>{JSON.stringify(json, null, 2)}</pre>
          </Paper>
        )
      } catch { return null }
    }
    if (tab === 2) {
      try {
        const json = JSON.parse(text)
        if (json.errors) {
          return (
            <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Config Validation</Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[{ label: 'Errors', value: json.summary?.errors ?? 0, color: '#ef4444' }, { label: 'Warnings', value: json.summary?.warnings ?? 0, color: '#f59e0b' }, { label: 'Info', value: json.summary?.info ?? 0, color: '#3b82f6' }].map((item) => (
                  <Grid item xs={4} key={item.label}>
                    <Box sx={{ p: 2, bgcolor: 'rgba(148,163,184,0.05)', border: `1px solid ${item.color}33`, borderRadius: 2, textAlign: 'center' }}>
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
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.65rem' }}>Type</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.65rem' }}>Message</TableCell>
                      <TableCell align="right" sx={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.65rem' }}>Level</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {json.errors?.map((err: any, idx: number) => (
                      <TableRow key={idx} hover sx={{ '&:hover': { bgcolor: 'rgba(52,211,153,0.05)' } }}>
                        <TableCell sx={{ color: '#e2e8f0', fontSize: '0.75rem' }}>{err.type}</TableCell>
                        <TableCell sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>{err.message}</TableCell>
                        <TableCell align="right">
                          <Chip label={err.severity} size="small" sx={{ bgcolor: err.severity === 'error' ? 'rgba(239,68,68,0.15)' : err.severity === 'warning' ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.15)', color: err.severity === 'error' ? '#ef4444' : err.severity === 'warning' ? '#f59e0b' : '#3b82f6', fontWeight: 500, height: 18, fontSize: '0.6rem' }} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )
        }
        if (json.interface_summary) {
          return (
            <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Performance Analysis</Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[{ label: 'Total', value: json.interface_summary.total, color: '#3b82f6' }, { label: 'UP', value: json.interface_summary.up, color: '#10b981' }, { label: 'DOWN', value: json.interface_summary.down, color: '#ef4444' }].map((item) => (
                  <Grid item xs={4} key={item.label}>
                    <Box sx={{ p: 2, bgcolor: 'rgba(148,163,184,0.05)', border: `1px solid ${item.color}33`, borderRadius: 2, textAlign: 'center' }}>
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
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.65rem' }}>Interface</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.65rem' }}>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {json.interface_summary.details?.slice(0, 10).map((d: any, idx: number) => (
                      <TableRow key={idx} hover>
                        <TableCell sx={{ color: '#e2e8f0', fontSize: '0.75rem' }}>{d.name}</TableCell>
                        <TableCell><Chip label={d.status} size="small" sx={{ bgcolor: d.status_up ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)', color: d.status_up ? '#10b981' : '#ef4444', height: 18, fontSize: '0.6rem' }} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )
        }
        if (json.summary) {
          return (
            <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Change Detection</Typography>
              <Grid container spacing={2}>
                {[{ label: 'Added', value: json.summary.added, color: '#10b981' }, { label: 'Removed', value: json.summary.removed, color: '#ef4444' }, { label: 'Has Changes', value: json.has_changes ? 'Yes' : 'No', color: json.has_changes ? '#f59e0b' : '#3b82f6' }].map((item) => (
                  <Grid item xs={4} key={item.label}>
                    <Box sx={{ p: 2, bgcolor: 'rgba(148,163,184,0.05)', border: `1px solid ${item.color}33`, borderRadius: 2, textAlign: 'center' }}>
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

  const selectSx = {
    bgcolor: '#0a0f1a', border: '1px solid rgba(52,211,153,0.2)',
    '&:hover': { borderColor: 'rgba(52,211,153,0.4)' },
    '&.Mui-focused': { borderColor: '#34d399' },
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 顶部标题栏 */}
      <Paper sx={{ p: 3, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', mb: 3, borderRadius: 2, position: 'relative', overflow: 'hidden' }}>
        <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, height: '100%', opacity: 0.03, backgroundImage: 'linear-gradient(90deg, transparent 50%, rgba(52,211,153,0.3) 50%), linear-gradient(rgba(52,211,153,0.3) 1px, transparent 1px)', backgroundSize: '300% 100%, 50px 50px' }} />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 1 }}>
          <Box>
            <Typography variant="h4" sx={{ color: '#fff', fontWeight: 700 }}>
              <span style={{ color: '#2563eb' }}>Data</span>
              <span style={{ color: '#34d399' }}> Viewer</span>
            </Typography>
            <Typography variant="subtitle2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' }}>
              Configuration & Analysis Viewer
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <ToggleButtonGroup value={compareMode ? 'compare' : 'single'} exclusive size="small"
              onChange={(_, v) => { if (v) { setCompareMode(v === 'compare'); setError(''); } }}
              sx={{ '& .MuiToggleButton-root': { color: '#94a3b8', borderColor: 'rgba(148,163,184,0.25)', px: 2, py: 0.25, fontSize: '0.7rem', fontWeight: 600, textTransform: 'none', borderRadius: '6px !important', '&.Mui-selected': { color: '#34d399', bgcolor: 'rgba(52,211,153,0.15)', borderColor: 'rgba(52,211,153,0.4)' }, '&:hover': { bgcolor: 'rgba(52,211,153,0.08)' } } }}>
              <ToggleButton value="single"><Visibility sx={{ fontSize: 16, mr: 0.5 }} />Single</ToggleButton>
              <ToggleButton value="compare"><Compare sx={{ fontSize: 16, mr: 0.5 }} />Compare</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>
      </Paper>

      {/* 筛选面板 */}
      <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', mb: 3, borderRadius: 2 }}>
        {/* Location 按钮 */}
        <Typography variant="caption" sx={{ color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', mb: 1 }}>Filter by Location</Typography>
        <ToggleButtonGroup value={selectedLocation} exclusive onChange={(_, v) => { setSelectedLocation(v); setSelectedDevice(''); }} size="small"
          sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5, '& .MuiToggleButton-root': { color: '#94a3b8', borderColor: 'rgba(148,163,184,0.25)', px: 2, py: 0.25, fontSize: '0.7rem', fontWeight: 600, textTransform: 'none', borderRadius: '6px !important', '&.Mui-selected': { color: '#34d399', bgcolor: 'rgba(52,211,153,0.15)', borderColor: 'rgba(52,211,153,0.4)' }, '&:hover': { bgcolor: 'rgba(52,211,153,0.08)' } } }}>
          {LOCATIONS_ROW1.map((loc) => <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>)}
        </ToggleButtonGroup>
        <ToggleButtonGroup value={selectedLocation} exclusive onChange={(_, v) => { setSelectedLocation(v); setSelectedDevice(''); }} size="small"
          sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, '& .MuiToggleButton-root': { color: '#94a3b8', borderColor: 'rgba(148,163,184,0.25)', px: 2, py: 0.25, fontSize: '0.7rem', fontWeight: 600, textTransform: 'none', borderRadius: '6px !important', '&.Mui-selected': { color: '#34d399', bgcolor: 'rgba(52,211,153,0.15)', borderColor: 'rgba(52,211,153,0.4)' }, '&:hover': { bgcolor: 'rgba(52,211,153,0.08)' } } }}>
          {LOCATIONS_ROW2.map((loc) => <ToggleButton key={loc} value={loc}>{loc}</ToggleButton>)}
        </ToggleButtonGroup>

        {/* 设备选择 */}
        <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <Typography variant="caption" sx={{ color: '#94a3b8', whiteSpace: 'nowrap' }}>设备:</Typography>
          <Select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)} displayEmpty fullWidth size="small" sx={selectSx}>
            <MenuItem value="" disabled><em>选择设备</em></MenuItem>
            {filteredDevices.map((d: any) => (
              <MenuItem key={d.name} value={d.name}>{d.name} ({d.ip})</MenuItem>
            ))}
          </Select>
        </Box>
      </Paper>

      {/* 内容区域 */}
      {!selectedDevice && (
        <Paper sx={{ p: 4, textAlign: 'center', bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2 }}>
          <Storage sx={{ fontSize: 48, color: 'rgba(148,163,184,0.2)', mb: 2 }} />
          <Typography color="text.secondary">选择 Location 和设备后查看配置历史</Typography>
        </Paper>
      )}

      {loading && (
        <Paper sx={{ p: 4, textAlign: 'center', bgcolor: '#0d121f', borderRadius: 2 }}>
          <CircularProgress sx={{ color: '#34d399' }} />
        </Paper>
      )}

      {selectedDevice && !loading && !compareMode && (
        <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2, mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
            历史配置版本 ({selectedDevice})
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <Select value={selectedWeek} onChange={(e) => { setSelectedWeek(e.target.value); setSelectedFile(''); }} displayEmpty fullWidth size="small" sx={selectSx}>
                <MenuItem value="" disabled><em>选择周</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Select value={selectedFile} onChange={(e) => setSelectedFile(e.target.value)} displayEmpty fullWidth size="small" sx={selectSx} disabled={!selectedWeek}>
                <MenuItem value="" disabled><em>选择文件</em></MenuItem>
                {files.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
              </Select>
            </Grid>
          </Grid>

          {loadingContent && <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress sx={{ color: '#34d399' }} /></Box>}
          {error && <Alert severity="error" sx={{ mt: 2, bgcolor: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)' }}>{error}</Alert>}

          {!loadingContent && content && (
            <Box sx={{ mt: 2 }}>
              {renderContentTabs(content)}
            </Box>
          )}
        </Paper>
      )}

      {/* 对比模式 */}
      {selectedDevice && !loading && compareMode && (
        <Paper sx={{ p: 2, bgcolor: '#0d121f', border: '1px solid rgba(52,211,153,0.1)', borderRadius: 2, mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
            配置对比 ({selectedDevice})
          </Typography>
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={6} sm={3}>
              <Typography variant="caption" color="#22d3ee" sx={{ mb: 0.5, display: 'block' }}>较新版本 (左)</Typography>
              <Select value={compareWeek1} onChange={(e) => setCompareWeek1(e.target.value)} displayEmpty fullWidth size="small" sx={selectSx}>
                <MenuItem value="" disabled><em>选择周</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Typography variant="caption" color="#f59e0b" sx={{ mb: 0.5, display: 'block' }}>较旧版本 (右)</Typography>
              <Select value={compareWeek2} onChange={(e) => setCompareWeek2(e.target.value)} displayEmpty fullWidth size="small" sx={selectSx}>
                <MenuItem value="" disabled><em>选择周</em></MenuItem>
                {weeks.map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </Select>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="caption" sx={{ color: '#94a3b8', mb: 0.5, display: 'block' }}>文件</Typography>
              <Select value={compareFile} onChange={(e) => setCompareFile(e.target.value)} displayEmpty fullWidth size="small" sx={selectSx}>
                <MenuItem value="" disabled><em>选择文件</em></MenuItem>
                {(files.length > 0 ? files : ['running-config.raw', 'startup-config.raw', 'logs.raw', 'interface-status.raw', 'version.raw', 'interface-utilization.raw', 'validation.json', 'performance.json', 'change.json', 'summary.txt']).map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
              </Select>
            </Grid>
          </Grid>

          {loadingContent && <Box sx={{ textAlign: 'center', py: 3 }}><CircularProgress sx={{ color: '#34d399' }} /></Box>}
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

          {!loadingContent && compareContent1 && compareContent2 && (
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Paper sx={{ p: 2, bgcolor: '#0a0f1a', border: '1px solid rgba(34,211,238,0.4)', borderRadius: 2, height: '70vh', overflow: 'auto' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, pb: 1, borderBottom: '1px solid rgba(34,211,238,0.2)' }}>
                    <Chip label={`${compareWeek1}`} size="small" sx={{ bgcolor: 'rgba(34,211,238,0.15)', color: '#22d3ee', height: 18, fontSize: '0.6rem' }} />
                    <Typography variant="caption" color="text.secondary">较新版本</Typography>
                  </Box>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","JetBrains Mono",monospace', margin: 0, fontSize: '0.7rem', lineHeight: 1.6 }}>
                    {diffLines
                      ? diffLines.map((item, i) => (
                          <div
                            key={i}
                            style={{
                              backgroundColor: item.type === 'added' ? 'rgba(16, 185, 129, 0.25)' : item.type === 'removed' ? 'rgba(239, 68, 68, 0.15)' : 'transparent',
                              color: item.type === 'added' ? '#10b981' : item.type === 'removed' ? '#ef4444' : '#e2e8f0',
                              paddingLeft: 4,
                              borderLeft: item.type === 'added' ? '3px solid #10b981' : item.type === 'removed' ? '3px solid #ef4444' : '3px solid transparent',
                            }}
                          >
                            {item.text}
                          </div>
                        ))
                      : compareContent1.split('\n').map((line, i) => <div key={i} style={{ color: '#e2e8f0' }}>{line}</div>)
                    }
                  </pre>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper sx={{ p: 2, bgcolor: '#0a0f1a', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 2, height: '70vh', overflow: 'auto' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, pb: 1, borderBottom: '1px solid rgba(245,158,11,0.2)' }}>
                    <Chip label={`${compareWeek2}`} size="small" sx={{ bgcolor: 'rgba(245,158,11,0.15)', color: '#f59e0b', height: 18, fontSize: '0.6rem' }} />
                    <Typography variant="caption" color="text.secondary">较旧版本</Typography>
                  </Box>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: '"Fira Code","JetBrains Mono",monospace', margin: 0, fontSize: '0.7rem', color: '#94a3b8', lineHeight: 1.6 }}>
                    {compareContent2}
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
