import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Box, Typography, FormControl, InputLabel, Select, MenuItem,
  Button, CircularProgress, Alert, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, IconButton, Tooltip,
  Card, CardContent, Chip, Paper,
} from '@mui/material'
import {
  Folder as FolderIcon,
  Description as FileIcon,
  SmartToy as AIIcon, History as HistoryIcon,
  Settings as SettingsIcon, Refresh as RefreshIcon,
  Delete as DeleteIcon, Add as AddIcon,
} from '@mui/icons-material'
import { TreeView, TreeItem } from '@mui/x-tree-view'
import { useI18n } from '../i18n'
import { logApi, llmApi } from '../services/api'

// ==============================
// 常量
// ==============================

/** 严重级别 → 颜色 (数字→hex) */
const SEV_COLORS: Record<string, string> = {
  '0': '#b91c1c', '1': '#dc2626', '2': '#ea580c',
  '3': '#ef4444', '4': '#eab308', '5': '#3b82f6',
  '6': '#22c55e', '7': '#94a3b8',
}

/** 严重级别 → 标签 i18n key */
/** 格式化建议文本：数组→逐行拼接，字符串→在编号步骤前插入换行 */
function formatSuggestion(sug: string | string[]): string {
  if (Array.isArray(sug)) return sug.join('\n')
  // 在 "1." "2." 等编号前插入换行（汉字数字也支持）
  return String(sug).replace(/(?<=\S)\s*(?=\d+[\.\、\)）])/g, '\n')
}

const SEV_LABEL_KEY: Record<string, string> = {
  '0': 'logs.levelEmergency', '1': 'logs.levelAlert',
  '2': 'logs.levelCritical', '3': 'logs.levelError',
  '4': 'logs.levelWarning', '5': 'logs.levelNotice',
  '6': 'logs.levelInfo', '7': 'logs.levelDebug',
}

// ==============================
// 类型
// ==============================

interface SeverityGroup {
  severity: string
  label: string
  count: number
}

interface DeviceNode {
  device_name: string
  device_info: { ip: string; model: string; version: string }
  total_logs: number
  severity_groups: SeverityGroup[]
}

interface LogEntry {
  id: number
  timestamp: string
  severity: string
  facility: string
  message: string
  week: string
}

// nodeId 工具函数
const devNodeId = (name: string) => `dev::${name}`
const sevNodeId = (name: string, sev: string) => `dev::${name}::sev::${sev}`
const logNodeId = (name: string, sev: string, id: number) => `dev::${name}::sev::${sev}::log::${id}`
const loadNodeId = (name: string, sev: string) => `dev::${name}::sev::${sev}::loading`

// ==============================
// 组件
// ==============================

export default function LogAnalyzer() {
  const { t } = useI18n()

  // 树数据
  const [treeData, setTreeData] = useState<DeviceNode[]>([])
  const [treeLoading, setTreeLoading] = useState(true)

  // 按需加载的日志: key = "deviceName|severity"
  const [loadedLogs, setLoadedLogs] = useState<Record<string, LogEntry[]>>({})
  const [loadingKeys, setLoadingKeys] = useState<Set<string>>(new Set())

  // 树交互
  const [expanded, setExpanded] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  // 过滤
  const [filterWeek, setFilterWeek] = useState('')
  const [weeks, setWeeks] = useState<string[]>([])

  // 当前选中的日志
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [selectedDeviceName, setSelectedDeviceName] = useState('')
  const [selectedDeviceInfo, setSelectedDeviceInfo] = useState<{ ip: string; model: string; version: string } | null>(null)

  // AI 分析
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  // 对话框
  const [history, setHistory] = useState<any[]>([])
  const [histOpen, setHistOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // ===================== 数据加载 =====================

  const loadTree = useCallback(async () => {
    setTreeLoading(true)
    try {
      const params: any = {}
      if (filterWeek) params.week = filterWeek
      const r = await logApi.getTree(params)
      setTreeData(r.data.devices || [])
    } catch {
      setError('加载树结构失败')
    } finally {
      setTreeLoading(false)
    }
  }, [filterWeek])

  const loadHistory = async () => {
    try {
      const r = await logApi.history(20)
      setHistory(r.data.history || [])
    } catch { }
  }

  // 初始化
  useEffect(() => { loadTree() }, [loadTree])
  useEffect(() => { loadHistory() }, [])

  // 加载周列表（从已有日志中提取）
  useEffect(() => {
    // 通过已有缓存中的日志推断周次
    const ws = new Set<string>()
    Object.values(loadedLogs).forEach(logs => {
      logs.forEach(l => { if (l.week) ws.add(l.week) })
    })
    setWeeks(Array.from(ws).sort().reverse())
  }, [loadedLogs])

  // ===================== 展开处理 =====================

  const handleNodeToggle = useCallback(async (_: any, nodeIds: string[]) => {
    setExpanded(nodeIds)

    // 检测新展开的 severity 节点，按需加载日志
    for (const nodeId of nodeIds) {
      const parts = nodeId.split('::')
      // nodeId 格式: dev::{name}::sev::{severity}
      if (parts.length === 4 && parts[2] === 'sev') {
        const deviceName = parts[1]
        const severity = parts[3]
        const key = `${deviceName}|${severity}`

        if (!loadedLogs[key] && !loadingKeys.has(key)) {
          setLoadingKeys(prev => new Set(prev).add(key))
          try {
            const params: any = { severity, limit: 200 }
            if (filterWeek) params.week = filterWeek
            const r = await logApi.getLogs(deviceName, params)
            setLoadedLogs(prev => ({ ...prev, [key]: r.data.logs }))
          } catch {
            // ignore
          } finally {
            setLoadingKeys(prev => { const n = new Set(prev); n.delete(key); return n })
          }
        }
      }
    }
  }, [loadedLogs, loadingKeys, filterWeek])

  // ===================== 选中处理 =====================

  const handleNodeSelect = useCallback((_: any, nodeId: string | null) => {
    setSelected(nodeId)
    if (!nodeId) {
      setSelectedLog(null)
      setSelectedDeviceName('')
      setSelectedDeviceInfo(null)
      setResult(null)
      return
    }

    const parts = nodeId.split('::')
    // nodeId 格式: dev::{name}::sev::{severity}::log::{id}
    if (parts.length === 6 && parts[4] === 'log') {
      const deviceName = parts[1]
      const severity = parts[3]
      const logId = parseInt(parts[5], 10)
      const key = `${deviceName}|${severity}`
      const logs = loadedLogs[key] || []
      const log = logs.find(l => l.id === logId)
      if (log) {
        setSelectedLog(log)
        setSelectedDeviceName(deviceName)
        setError('')
        setResult(null)

        // 查找设备信息
        const dev = treeData.find(d => d.device_name === deviceName)
        setSelectedDeviceInfo(dev?.device_info || null)
      }
    }
  }, [loadedLogs, treeData])

  // ===================== AI 分析 =====================

  const handleAnalyze = async () => {
    if (!selectedLog || !selectedDeviceName) return
    setAnalyzing(true)
    setError('')
    setResult(null)
    try {
      const r = await logApi.analyze([selectedLog.id], selectedDeviceName)
      setResult(r.data)
      loadHistory()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  // ===================== 渲染工具 =====================

  /** 获取 severity 对应的颜色 */
  const sevColor = (sev: string) => SEV_COLORS[sev] || '#94a3b8'

  /** 获取 severity 对应的标签 */
  const sevLabel = (sev: string) => t(SEV_LABEL_KEY[sev] || 'logs.levelDebug')

  // ===================== 历史记录数据 =====================

  const histData = useMemo(() => {
    return history.map(h => {
      let sug = h.suggestion
      try { sug = typeof sug === 'string' ? JSON.parse(sug) : sug } catch { }
      return { ...h, parsed: sug }
    })
  }, [history])

  // ===================== 渲染 =====================

  return (
    <Box sx={{ p: 2, display: 'flex', gap: 2, height: 'calc(100vh - 80px)' }}>
      {/* ============ 左侧面板 (40%) ============ */}
      <Paper sx={{
        width: '40%', display: 'flex', flexDirection: 'column', overflow: 'hidden',
        minWidth: 280,
      }}>
        {/* 工具栏 */}
        <Box sx={{ p: 1.5, display: 'flex', gap: 1, alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mr: 1, whiteSpace: 'nowrap' }}>
            📋 {t('logs.title')}
          </Typography>

          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>{t('logs.filterWeek')}</InputLabel>
            <Select value={filterWeek} label={t('logs.filterWeek')}
              onChange={e => setFilterWeek(e.target.value)}>
              <MenuItem value="">{t('logs.allWeeks')}</MenuItem>
              {weeks.map(w => <MenuItem key={w} value={w}>{w}</MenuItem>)}
            </Select>
          </FormControl>

          <Box sx={{ flex: 1 }} />

          <Tooltip title={t('logs.refresh')}>
            <IconButton onClick={loadTree} size="small"><RefreshIcon fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title={t('logs.history')}>
            <IconButton onClick={() => setHistOpen(true)} size="small"><HistoryIcon fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title={t('logs.settings')}>
            <IconButton onClick={() => setSettingsOpen(true)} size="small"><SettingsIcon fontSize="small" /></IconButton>
          </Tooltip>
        </Box>

        {/* 树结构 */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
          {treeLoading ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <CircularProgress size={24} />
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                {t('logs.loadingTree')}
              </Typography>
            </Box>
          ) : treeData.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
              <Typography variant="body2">{t('logs.noLogs')}</Typography>
            </Box>
          ) : (
            <TreeView
              expanded={expanded}
              onNodeToggle={handleNodeToggle}
              selected={selected}
              onNodeSelect={handleNodeSelect}
              sx={{ flexGrow: 1 }}
            >
              {treeData.map(dev => (
                <TreeItem
                  key={devNodeId(dev.device_name)}
                  nodeId={devNodeId(dev.device_name)}
                  label={
                    <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <FolderIcon fontSize="small" sx={{ color: 'primary.main', fontSize: 18 }} />
                      <Typography variant="body2" fontWeight={600}>
                        {dev.device_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        ({dev.total_logs})
                      </Typography>
                    </Box>
                  }
                >
                  {dev.severity_groups
                    .filter(sg => sg.count > 0)
                    .map(sg => {
                      const key = `${dev.device_name}|${sg.severity}`
                      const logs = loadedLogs[key]
                      const isLoading = loadingKeys.has(key)

                      return (
                        <TreeItem
                          key={sevNodeId(dev.device_name, sg.severity)}
                          nodeId={sevNodeId(dev.device_name, sg.severity)}
                          sx={{
                            borderLeft: `2px solid ${sevColor(sg.severity)}`,
                            ml: 0.5,
                            '& > .MuiTreeItem-group': { borderLeft: `2px solid ${sevColor(sg.severity)}` },
                          }}
                          label={
                            <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <Box
                                component="span"
                                sx={{
                                  width: 12, height: 12, borderRadius: '50%',
                                  bgcolor: sevColor(sg.severity),
                                  display: 'inline-block', flexShrink: 0,
                                }}
                              />
                              <Typography variant="body2">
                                {sevLabel(sg.severity)}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                ({sg.count})
                              </Typography>
                            </Box>
                          }
                        >
                          {/* 加载中占位 */}
                          {isLoading && (
                            <TreeItem
                              nodeId={loadNodeId(dev.device_name, sg.severity)}
                              label={
                                <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                  <CircularProgress size={12} />
                                  <Typography variant="caption" color="text.secondary">{t('logs.loading')}</Typography>
                                </Box>
                              }
                              disabled
                            />
                          )}

                          {/* 已加载的日志条目 */}
                          {logs && logs.map(log => (
                            <TreeItem
                              key={logNodeId(dev.device_name, sg.severity, log.id)}
                              nodeId={logNodeId(dev.device_name, sg.severity, log.id)}
                              label={
                                <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, py: 0.25 }}>
                                  <Box component="span" sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: sevColor(sg.severity), flexShrink: 0, opacity: 0.8 }} />
                                  <Typography
                                    variant="caption"
                                    noWrap
                                    sx={{
                                      fontFamily: '"Fira Code", monospace', fontSize: '0.72rem',
                                      color: sevColor(sg.severity), fontWeight: 500,
                                    }}
                                  >
                                    {log.timestamp && <>{log.timestamp.slice(0, 19)} </>}
                                    {log.message.slice(0, 100)}
                                  </Typography>
                                </Box>
                              }
                            />
                          ))}

                          {/* 未加载且不在加载中的占位（让节点可展开） */}
                          {!logs && !isLoading && sg.count > 0 && (
                            <TreeItem
                              nodeId={loadNodeId(dev.device_name, sg.severity)}
                              label={
                                <Typography variant="caption" color="text.secondary">
                                  {t('logs.selectLogs')}...
                                </Typography>
                              }
                              disabled
                            />
                          )}
                        </TreeItem>
                      )
                    })}
                </TreeItem>
              ))}
            </TreeView>
          )}
        </Box>
      </Paper>

      {/* ============ 右侧面板 (60%) ============ */}
      <Paper sx={{
        width: '60%', p: 3, overflow: 'auto',
        display: 'flex', flexDirection: 'column', gap: 2,
      }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          📋 {t('logs.logDetail')}
        </Typography>

        {!selectedLog ? (
          <Box sx={{ textAlign: 'center', color: 'text.secondary', mt: 8, flex: 1 }}>
            <FileIcon sx={{ fontSize: 64, mb: 2, opacity: 0.2 }} />
            <Typography>{t('logs.noResult')}</Typography>
            <Typography variant="caption">{t('logs.noResultHint')}</Typography>
          </Box>
        ) : (
          <>
            {/* 日志详情卡片 */}
            <Card variant="outlined" sx={{ bgcolor: 'rgba(255,255,255,0.03)' }}>
              <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <DetailRow label={t('logs.timestamp')} value={selectedLog.timestamp || '—'} />
                <DetailRow label={t('collect.deviceLabel')} value={
                  <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" fontFamily='"Fira Code", monospace'>{selectedDeviceName}</Typography>
                    {selectedDeviceInfo && (
                      <Typography variant="caption" color="text.secondary">
                        {selectedDeviceInfo.ip}
                        {selectedDeviceInfo.model ? ` · ${selectedDeviceInfo.model}` : ''}
                      </Typography>
                    )}
                  </Box>
                } />
                <DetailRow label={t('logs.severity')} value={
                  <Chip
                    label={sevLabel(selectedLog.severity)}
                    size="small"
                    sx={{ bgcolor: sevColor(selectedLog.severity), color: '#fff', fontWeight: 600, fontSize: '0.7rem' }}
                  />
                } />
                <DetailRow label={t('logs.facility')} value={
                  <Typography variant="body2" fontFamily='"Fira Code", monospace' fontSize="0.85rem">
                    {selectedLog.facility || '—'}
                  </Typography>
                } />
                <DetailRow label={t('logs.message')} value={
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: '"Fira Code", monospace', fontSize: '0.78rem',
                      whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                      bgcolor: 'rgba(255,255,255,0.04)', p: 1.5, borderRadius: 1,
                      maxHeight: 200, overflow: 'auto',
                    }}
                  >
                    {selectedLog.message}
                  </Typography>
                } />
              </CardContent>
            </Card>

            {/* AI 分析 */}
            <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <AIIcon color="primary" />
                <Typography variant="subtitle2" fontWeight={600}>
                  {t('logs.analysisResult')}
                </Typography>
              </Box>

              {analyzing ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <CircularProgress size={32} />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {t('logs.analyzing')}
                  </Typography>
                </Box>
              ) : result ? (
                <AnalysisResult result={result} t={t} />
              ) : error ? (
                <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  {t('logs.noResultHint')}
                </Typography>
              )}

              <Button
                variant="contained"
                startIcon={<AIIcon />}
                disabled={analyzing}
                onClick={handleAnalyze}
                sx={{ mt: 2 }}
                size="small"
              >
                {analyzing ? t('logs.analyzing') : t('logs.analyzeThis')}
              </Button>
            </Box>
          </>
        )}
      </Paper>

      {/* ============ 历史记录对话框 ============ */}
      <Dialog open={histOpen} onClose={() => setHistOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('logs.historyTitle')}</DialogTitle>
        <DialogContent dividers>
          {histData.length === 0 ? (
            <Typography color="text.secondary">{t('logs.noHistory')}</Typography>
          ) : histData.map(h => (
            <Card key={h.id} variant="outlined" sx={{ mb: 1 }}>
              <CardContent>
                <Typography variant="caption" color="primary">{h.keyword}</Typography>
                {typeof h.parsed === 'object' && h.parsed ? (
                  <>
                    <Typography variant="subtitle2">{h.parsed.summary}</Typography>
                    <Typography variant="body2" color="text.secondary">{h.parsed.root_cause}</Typography>
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {typeof h.parsed === 'string' ? h.parsed : JSON.stringify(h.parsed)}
                  </Typography>
                )}
                <Typography variant="caption" sx={{ opacity: 0.5 }}>{h.created_at}</Typography>
              </CardContent>
            </Card>
          ))}
        </DialogContent>
        <DialogActions><Button onClick={() => setHistOpen(false)}>{t('common.close')}</Button></DialogActions>
      </Dialog>

      {/* ============ LLM 设置对话框 ============ */}
      <LLMSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} t={t} />
    </Box>
  )
}

// ==============================
// 辅助组件
// ==============================

/** 详情行 */
function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 80, flexShrink: 0, pt: 0.3 }}>
        {label}
      </Typography>
      <Box>{value}</Box>
    </Box>
  )
}

/** AI 分析结果 */
function AnalysisResult({ result, t }: { result: any; t: any }) {
  const sug = typeof result.suggestion === 'string'
    ? (() => { try { return JSON.parse(result.suggestion) } catch { return null } })()
    : result.suggestion

  if (!sug || typeof sug !== 'object') {
    return <Alert severity="info">{result.suggestion || '—'}</Alert>
  }

  const sourceLabel = result.from_cache ? t('logs.sourceCache') : t('logs.sourceLLM')

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* 来源标签 */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Chip
          label={sourceLabel}
          size="small"
          color={result.from_cache ? 'success' : 'primary'}
          icon={result.from_cache ? <HistoryIcon /> : <AIIcon />}
        />
        {result.provider && (
          <Chip label={`${t('logs.provider')}: ${result.provider}`} size="small" variant="outlined" />
        )}
        {result.keyword && (
          <Chip label={result.keyword} size="small" variant="outlined" color="secondary" />
        )}
      </Box>

      {/* 概述 */}
      {sug.severity && (
        <Alert severity={
          sug.severity === 'critical' ? 'error' : sug.severity === 'warning' ? 'warning' : 'info'
        }>
          <Typography variant="subtitle2" fontWeight={700}>{t('logs.summary')}</Typography>
          <Typography variant="body2">{sug.summary}</Typography>
        </Alert>
      )}

      {/* 根因分析 */}
      <Card variant="outlined">
        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            {t('logs.rootCause')}
          </Typography>
          <Typography variant="body2">{sug.root_cause}</Typography>
        </CardContent>
      </Card>

      {/* 建议操作 — 每步换行 */}
      <Card variant="outlined" sx={{ borderColor: 'primary.main', borderWidth: 1 }}>
        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Typography variant="subtitle2" color="primary" gutterBottom>
            {t('logs.suggestion')}
          </Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
            {formatSuggestion(sug.suggestion)}
          </Typography>
        </CardContent>
      </Card>

      {/* 关联错误 */}
      {sug.related_errors?.length > 0 && (
        <Box>
          <Typography variant="caption" color="text.secondary">{t('logs.relatedErrors')}</Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
            {sug.related_errors.map((e: string) => (
              <Chip key={e} label={e} size="small" variant="outlined" />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  )
}

// ==============================
// LLM 设置对话框（保留）
// ==============================

function LLMSettingsDialog({ open, onClose, t }: { open: boolean; onClose: () => void; t: any }) {
  const [timeout, setTimeout_] = useState(30)
  const [providers, setProviders] = useState<any[]>([])
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (open) {
      llmApi.getSettings().then(r => {
        setTimeout_(r.data.timeout || 30)
        setProviders(r.data.providers || [])
      }).catch(() => {})
      setMsg('')
    }
  }, [open])

  const handleSave = async () => {
    setSaving(true)
    setMsg('')
    try {
      await llmApi.saveSettings({ timeout, providers })
      setMsg(t('logs.llmSaveSuccess'))
    } catch {
      setMsg(t('logs.llmSaveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const addProvider = () => {
    setProviders([...providers, { name: '', base_url: '', api_key: '', model: '' }])
  }

  const updateProvider = (i: number, field: string, val: string) => {
    const next = [...providers]
    next[i] = { ...next[i], [field]: val }
    setProviders(next)
  }

  const removeProvider = (i: number) => {
    setProviders(providers.filter((_, idx) => idx !== i))
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t('logs.llmConfig')}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label={t('logs.llmTimeout')} type="number" size="small"
            value={timeout} onChange={e => setTimeout_(Number(e.target.value))}
            sx={{ width: 120 }} />

          {providers.map((p, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <TextField label={t('logs.llmProviderName')} size="small" value={p.name}
                onChange={e => updateProvider(i, 'name', e.target.value)} sx={{ width: 120 }} />
              <TextField label={t('logs.llmBaseUrl')} size="small" value={p.base_url}
                onChange={e => updateProvider(i, 'base_url', e.target.value)} sx={{ flex: 1 }} />
              <TextField label={t('logs.llmApiKey')} size="small" type="password" value={p.api_key}
                onChange={e => updateProvider(i, 'api_key', e.target.value)} sx={{ width: 200 }} />
              <TextField label={t('logs.llmModel')} size="small" value={p.model}
                onChange={e => updateProvider(i, 'model', e.target.value)} sx={{ width: 160 }} />
              <IconButton onClick={() => removeProvider(i)} color="error" size="small"><DeleteIcon /></IconButton>
            </Box>
          ))}

          <Button startIcon={<AddIcon />} variant="outlined" size="small" onClick={addProvider}>
            {t('logs.llmAddProvider')}
          </Button>

          {msg && <Alert severity={msg.includes('失败') ? 'error' : 'success'}>{msg}</Alert>}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('common.close')}</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving}>
          {saving ? <CircularProgress size={16} /> : null} {t('logs.llmSave')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
