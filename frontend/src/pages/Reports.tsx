import React, { useState, useEffect } from 'react'
import {
  Box, Container, Typography, Paper, Select, MenuItem, FormControl, InputLabel,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Chip, CircularProgress, TableSortLabel, Alert, Button,
} from '@mui/material'
import { Warning as WarningIcon, Download as DownloadIcon } from '@mui/icons-material'
import { deviceApi, reportsApi } from '../services/api'
import { useI18n } from '../i18n'
import LocationFilter from '../components/devices/LocationFilter'

type ReportType = 'device-status' | 'bandwidth-summary'
type SortDir = 'asc' | 'desc'
interface SortState { field: string; dir: SortDir }
type Row = Record<string, any>

/** 两张表的默认排序：型号字母序 / 吞吐降序 */
const DEFAULT_SORT: Record<ReportType, SortState> = {
  'device-status': { field: 'model', dir: 'asc' },
  'bandwidth-summary': { field: 'total_mbps', dir: 'desc' },
}

/** 数值列首次点击用降序（先看最大的），文本列用升序 */
const DESC_FIRST = new Set(['uptime', 'total_mbps', 'rx_mbps', 'tx_mbps', 'rx_pct', 'tx_pct'])

// 两张表的取值口径（排序与导出共用同一套，避免两处对不上）
const VERSION_GETTERS: Record<string, (r: Row) => any> = {
  name: r => r.name,
  location: r => r.location,
  model: r => r.model,
  serial: r => r.serial,
  version: r => r.version,
  rom: r => r.rom_version,
  uptime: r => r.uptime_days,
  last_synced: r => r.last_synced,
}
const BANDWIDTH_GETTERS: Record<string, (r: Row) => any> = {
  device: r => r.device_name,
  location: r => r.location,
  port: r => r.port_name,
  status: r => r.status,
  total_mbps: r => (r.rx_mbps || 0) + (r.tx_mbps || 0),
  rx_mbps: r => r.rx_mbps,
  tx_mbps: r => r.tx_mbps,
  rx_pct: r => r.rx_util_pct,
  tx_pct: r => r.tx_util_pct,
  description: r => r.description,
  collected_at: r => r.collected_at,
}

/** 导出 CSV：加 UTF-8 BOM（否则 Excel 打开中文乱码），字段按 RFC 4180 转义 */
function downloadCsv(filename: string, headers: string[], rows: Array<Array<string | number | null | undefined>>) {
  const esc = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [headers, ...rows].map(r => r.map(esc).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  // 必须先挂 DOM 再点击，且延迟释放 URL（否则文件还没写入就被回收）
  document.body.appendChild(a)
  a.click()
  setTimeout(() => { URL.revokeObjectURL(url); a.remove() }, 1000)
}

/**
 * 通用排序：空值（null / undefined / 空串）恒排最后，不随排序方向翻转
 * —— 无运行时间数据的设备不该在升序时窜到最前面。
 */
function sortRows(rows: Row[], sort: SortState, getters: Record<string, (r: Row) => any>): Row[] {
  const get = getters[sort.field]
  if (!get) return rows
  const dir = sort.dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const va = get(a)
    const vb = get(b)
    const ea = va === null || va === undefined || va === ''
    const eb = vb === null || vb === undefined || vb === ''
    if (ea || eb) return ea && eb ? 0 : ea ? 1 : -1
    const cmp = typeof va === 'number' && typeof vb === 'number'
      ? va - vb
      : String(va).localeCompare(String(vb))
    return cmp * dir
  })
}

/** 可点击排序的表头（箭头由 MUI 负责） */
const SortHead: React.FC<{ field: string; label: string; sort: SortState; onSort: (f: string) => void }> = ({
  field, label, sort, onSort,
}) => (
  <TableCell sortDirection={sort.field === field ? sort.dir : false} sx={{ whiteSpace: 'nowrap' }}>
    <TableSortLabel
      active={sort.field === field}
      direction={sort.field === field ? sort.dir : 'asc'}
      onClick={() => onSort(field)}
    >
      {label}
    </TableSortLabel>
  </TableCell>
)

/** 采集/同步时间的本地化显示（后端存 ISO 字符串） */
const fmtTime = (v?: string | null) => (v ? new Date(v).toLocaleString('zh-CN') : '—')

export default function ReportsPage() {
  const { t } = useI18n()
  const [reportType, setReportType] = useState<ReportType>('device-status')
  const [location, setLocation] = useState<string | null>(null)
  const [locations, setLocations] = useState<string[]>([])
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT['device-status'])
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)

  // 位置列表与设备管理页同源：设备清单去重排序
  useEffect(() => {
    deviceApi.list()
      .then(res => {
        const list = (res.data || []) as Array<{ location?: string }>
        setLocations([...new Set(list.map(d => d.location).filter((l): l is string => !!l))].sort())
      })
      .catch(() => setLocations([]))
  }, [])

  // 切换报告类型时回到该表的默认排序（切换位置不影响用户当前的排序选择）
  useEffect(() => { setSort(DEFAULT_SORT[reportType]) }, [reportType])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setLoading(true)
      try {
        const params = location ? { location } : undefined
        let res: any
        if (reportType === 'device-status') res = await reportsApi.softwareVersions(params)
        else res = await reportsApi.bandwidthSummary(params)
        if (!cancelled) setData(res?.data ?? null)
      } catch (e) {
        console.error('Report fetch failed:', e)
        if (!cancelled) setData(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
  }, [reportType, location])

  const handleSort = (field: string) => {
    setSort(s => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: DESC_FIRST.has(field) ? 'desc' : 'asc' })
  }

  /** 导出当前报告：位置过滤 + 当前排序都生效（所见即所得） */
  const exportCsv = () => {
    const loc = location || 'ALL'
    const stamp = new Date().toISOString().slice(0, 10)

    if (reportType === 'device-status') {
      const rows = sortRows(data?.devices || [], sort, VERSION_GETTERS)
      downloadCsv(`${t('reports.deviceStatus')}_${loc}_${stamp}.csv`,
        [t('reports.member'), t('reports.location'), t('reports.model'), t('reports.serialNumber'),
         t('reports.version'), t('reports.romVersion'), t('reports.uptimeDaysCol'), t('reports.lastSynced')],
        rows.map(r => [r.name, r.location, r.model, r.serial,
                       r.version, r.rom_version, r.uptime_days ?? '', fmtTime(r.last_synced)]))
    } else {
      const rows = sortRows(data?.ports || [], sort, BANDWIDTH_GETTERS)
      downloadCsv(`${t('reports.bandwidthSummary')}_${loc}_${stamp}.csv`,
        [t('reports.device'), t('reports.location'), t('reports.port'), t('reports.status'),
         'RX Mbps', 'TX Mbps', 'RX %', 'TX %', t('reports.portDesc'), t('reports.collectedAt')],
        rows.map(r => [r.device_name, r.location, r.port_name, r.status,
                       r.rx_mbps ?? '', r.tx_mbps ?? '', r.rx_util_pct ?? '', r.tx_util_pct ?? '',
                       r.description, fmtTime(r.collected_at)]))
    }
  }

  const renderVersions = () => {
    const rows: Row[] = data?.devices || []
    const mismatches: Array<{ device: string; versions: string[]; rom_versions: string[]; members: Row[] }> =
      data?.mismatches || []
    const mismatchDevices = new Set(mismatches.map(m => m.device))
    const sorted = sortRows(rows, sort, VERSION_GETTERS)

    /** 告警文案：点名哪台成员是什么版本（按版本分组） */
    const describeMismatch = (m: typeof mismatches[number]) => {
      const fmt = (field: 'version' | 'rom_version') => {
        const groups = new Map<string, string[]>()
        m.members.forEach(x => {
          const v = x[field] || '—'
          groups.set(v, [...(groups.get(v) || []), x.name])
        })
        return [...groups.entries()].map(([v, names]) => `${names.join('、')} 为 ${v}`).join('；')
      }
      const parts = [m.versions.length > 1 ? fmt('version') : '', m.rom_versions.length > 1 ? `ROM ${fmt('rom_version')}` : '']
      return `${m.device}：${parts.filter(Boolean).join('；')}`
    }

    return (
      <Box>
        {mismatches.length > 0 && (
          <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
            <strong>{t('reports.memberMismatch')}</strong>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {mismatches.map(m => <li key={m.device}>{describeMismatch(m)}</li>)}
            </Box>
          </Alert>
        )}
        <TableContainer component={Paper}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <SortHead field="name" label={t('reports.member')} sort={sort} onSort={handleSort} />
                <SortHead field="location" label={t('reports.location')} sort={sort} onSort={handleSort} />
                <SortHead field="model" label={t('reports.model')} sort={sort} onSort={handleSort} />
                <SortHead field="serial" label={t('reports.serialNumber')} sort={sort} onSort={handleSort} />
                <SortHead field="version" label={t('reports.version')} sort={sort} onSort={handleSort} />
                <SortHead field="rom" label={t('reports.romVersion')} sort={sort} onSort={handleSort} />
                <SortHead field="uptime" label={t('reports.uptime')} sort={sort} onSort={handleSort} />
                <SortHead field="last_synced" label={t('reports.lastSynced')} sort={sort} onSort={handleSort} />
              </TableRow>
            </TableHead>
            <TableBody>
              {sorted.map(r => (
                <TableRow
                  key={r.name}
                  hover
                  sx={mismatchDevices.has(r.device) ? { bgcolor: 'rgba(245, 158, 11, 0.08)' } : undefined}
                >
                  <TableCell>{r.name}</TableCell>
                  <TableCell>{r.location || '—'}</TableCell>
                  <TableCell>{r.model}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>
                    {r.serial || '—'}
                  </TableCell>
                  <TableCell>
                    <Chip label={r.version} size="small" color={mismatchDevices.has(r.device) ? 'warning' : 'default'} />
                  </TableCell>
                  <TableCell>
                    {r.rom_version
                      ? <Chip label={r.rom_version} size="small" variant="outlined" />
                      : <Typography variant="caption" color="text.disabled">—</Typography>}
                  </TableCell>
                  <TableCell>
                    {r.uptime_days != null
                      ? t('reports.uptimeDays').replace('{days}', String(r.uptime_days))
                      : <Typography variant="caption" color="text.disabled">—</Typography>}
                  </TableCell>
                  <TableCell>{fmtTime(r.last_synced)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    )
  }

  const renderBandwidth = () => {
    const rows: Row[] = data?.ports || []
    const sorted = sortRows(rows, sort, BANDWIDTH_GETTERS)

    return (
      <TableContainer component={Paper}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <SortHead field="device" label={t('reports.device')} sort={sort} onSort={handleSort} />
              <SortHead field="location" label={t('reports.location')} sort={sort} onSort={handleSort} />
              <SortHead field="port" label={t('reports.port')} sort={sort} onSort={handleSort} />
              <SortHead field="status" label={t('reports.status')} sort={sort} onSort={handleSort} />
              <SortHead field="rx_mbps" label="RX Mbps" sort={sort} onSort={handleSort} />
              <SortHead field="tx_mbps" label="TX Mbps" sort={sort} onSort={handleSort} />
              <SortHead field="rx_pct" label="RX %" sort={sort} onSort={handleSort} />
              <SortHead field="tx_pct" label="TX %" sort={sort} onSort={handleSort} />
              <SortHead field="description" label={t('reports.portDesc')} sort={sort} onSort={handleSort} />
              <SortHead field="collected_at" label={t('reports.collectedAt')} sort={sort} onSort={handleSort} />
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map(r => (
              <TableRow
                key={`${r.device_name}-${r.port_name}`}
                hover
                sx={{ bgcolor: Math.max(r.rx_util_pct || 0, r.tx_util_pct || 0) > 80 ? 'error.light' : 'inherit' }}
              >
                <TableCell>{r.device_name}</TableCell>
                <TableCell>{r.location || '—'}</TableCell>
                <TableCell>{r.port_name}</TableCell>
                <TableCell>{r.status}</TableCell>
                <TableCell>{r.rx_mbps?.toFixed(1) ?? '—'}</TableCell>
                <TableCell>{r.tx_mbps?.toFixed(1) ?? '—'}</TableCell>
                <TableCell>
                  <Chip
                    label={`${(r.rx_util_pct ?? 0).toFixed(0)}%`}
                    size="small"
                    color={r.rx_util_pct > 80 ? 'error' : r.rx_util_pct > 50 ? 'warning' : 'default'}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={`${(r.tx_util_pct ?? 0).toFixed(0)}%`}
                    size="small"
                    color={r.tx_util_pct > 80 ? 'error' : r.tx_util_pct > 50 ? 'warning' : 'default'}
                  />
                </TableCell>
                <TableCell>{r.description}</TableCell>
                <TableCell>{fmtTime(r.collected_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    )
  }

  const currentRows: Row[] =
    reportType === 'bandwidth-summary' ? (data?.ports || []) : (data?.devices || [])

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 8 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>{t('reports.title')}</Typography>
        <Typography variant="body2" color="text.secondary">{t('reports.description')}</Typography>
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 1.5 }}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>{t('reports.reportType')}</InputLabel>
            <Select
              value={reportType}
              label={t('reports.reportType')}
              onChange={e => setReportType(e.target.value as ReportType)}
            >
              <MenuItem value="device-status">{t('reports.deviceStatus')}</MenuItem>
              <MenuItem value="bandwidth-summary">{t('reports.bandwidthSummary')}</MenuItem>
            </Select>
          </FormControl>
          {loading && <CircularProgress size={18} />}
          <Box sx={{ flexGrow: 1 }} />
          <Button
            size="small"
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={exportCsv}
            disabled={currentRows.length === 0}
          >
            {t('reports.exportCsv')}
          </Button>
        </Box>
        <LocationFilter selectedLocation={location} onChange={setLocation} locations={locations} />
      </Paper>

      {!loading && currentRows.length === 0 ? (
        <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
          {t('reports.empty')}
        </Typography>
      ) : (
        <>
          {reportType === 'device-status' && renderVersions()}
          {reportType === 'bandwidth-summary' && renderBandwidth()}
        </>
      )}
    </Container>
  )
}
