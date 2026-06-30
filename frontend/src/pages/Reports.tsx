import { useState, useEffect } from 'react'
import {
  Box, Container, Typography, Paper, Select, MenuItem, FormControl, InputLabel,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Chip, CircularProgress, Divider,
} from '@mui/material'
import { Warning as WarningIcon } from '@mui/icons-material'
import { reportsApi } from '../services/api'
import { useI18n } from '../i18n'

type ReportType = 'software-versions' | 'device-uptime' | 'bandwidth-summary'

export default function ReportsPage() {
  const { t } = useI18n()
  const [reportType, setReportType] = useState<ReportType>('software-versions')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)
  const [filterType, setFilterType] = useState('')

  useEffect(() => { fetchReport() }, [reportType, filterType])

  const fetchReport = async () => {
    setLoading(true)
    try {
      let res: any
      switch (reportType) {
        case 'software-versions':
          res = await reportsApi.softwareVersions(filterType ? { device_type: filterType } : undefined)
          break
        case 'device-uptime':
          res = await reportsApi.deviceUptime()
          break
        case 'bandwidth-summary':
          res = await reportsApi.bandwidthSummary()
          break
      }
      setData(res.data)
    } catch (e) {
      console.error('Report fetch failed:', e)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  const renderVersions = () => {
    if (!data) return null
    const byModel = data.by_model || {}

    return (
      <Box>
        {Object.entries(byModel).map(([model, info]: [string, any]) => (
          <Paper key={model} sx={{ mb: 2, p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="subtitle1" fontWeight="bold">{model}</Typography>
              {info.has_mismatch && (
                <Chip icon={<WarningIcon />} label={t('reports.versionMismatch')} color="warning" size="small" />
              )}
            </Box>
            {info.has_mismatch && (
              <Typography variant="body2" color="warning.main" sx={{ mb: 1 }}>
                {t('reports.versions')}: {info.versions.join(', ')}
              </Typography>
            )}
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('reports.device')}</TableCell>
                  <TableCell>{t('reports.type')}</TableCell>
                  <TableCell>{t('reports.version')}</TableCell>
                  <TableCell>{t('reports.lastSynced')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {info.devices.map((d: any) => (
                  <TableRow key={d.name}>
                    <TableCell>{d.name}</TableCell>
                    <TableCell>{d.type}</TableCell>
                    <TableCell>
                      <Chip label={d.version} size="small" color={info.has_mismatch ? 'warning' : 'default'} />
                    </TableCell>
                    <TableCell>{d.last_synced}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        ))}
      </Box>
    )
  }

  const renderUptime = () => {
    if (!data) return null
    const devices = data.devices || []
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t('reports.device')}</TableCell>
              <TableCell>{t('reports.type')}</TableCell>
              <TableCell>{t('reports.uptime')}</TableCell>
              <TableCell>{t('reports.version')}</TableCell>
              <TableCell>{t('reports.lastSynced')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {devices.map((d: any) => (
              <TableRow key={d.name}>
                <TableCell>{d.name}</TableCell>
                <TableCell>{d.type}</TableCell>
                <TableCell>
                  <Chip
                    label={t('reports.uptimeDays', { days: String(d.uptime_days) })}
                    color={d.uptime_days < 1 ? 'error' : d.uptime_days < 7 ? 'warning' : 'success'}
                    size="small"
                  />
                </TableCell>
                <TableCell>{d.software_version}</TableCell>
                <TableCell>{d.collected_at ? new Date(d.collected_at).toLocaleString('zh-CN') : '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    )
  }

  const renderBandwidth = () => {
    if (!data) return null
    const ports = data.ports || []
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t('reports.device')}</TableCell>
              <TableCell>端口</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>RX Mbps</TableCell>
              <TableCell>TX Mbps</TableCell>
              <TableCell>RX %</TableCell>
              <TableCell>TX %</TableCell>
              <TableCell>描述</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {ports.map((p: any) => (
              <TableRow
                key={`${p.device_name}-${p.port_name}`}
                sx={{ bgcolor: Math.max(p.rx_util_pct, p.tx_util_pct) > 80 ? 'error.light' : 'inherit' }}
              >
                <TableCell>{p.device_name}</TableCell>
                <TableCell>{p.port_name}</TableCell>
                <TableCell>{p.status}</TableCell>
                <TableCell>{p.rx_mbps?.toFixed(1)}</TableCell>
                <TableCell>{p.tx_mbps?.toFixed(1)}</TableCell>
                <TableCell>
                  <Chip label={`${p.rx_util_pct?.toFixed(0) || 0}%`} size="small"
                    color={p.rx_util_pct > 80 ? 'error' : p.rx_util_pct > 50 ? 'warning' : 'default'} />
                </TableCell>
                <TableCell>
                  <Chip label={`${p.tx_util_pct?.toFixed(0) || 0}%`} size="small"
                    color={p.tx_util_pct > 80 ? 'error' : p.tx_util_pct > 50 ? 'warning' : 'default'} />
                </TableCell>
                <TableCell>{p.description}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 8 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>{t('reports.title')}</Typography>
        <Typography variant="body2" color="text.secondary">{t('reports.description')}</Typography>
      </Box>

      <Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>报告类型</InputLabel>
          <Select value={reportType} label="报告类型" onChange={e => setReportType(e.target.value as ReportType)}>
            <MenuItem value="software-versions">{t('reports.softwareVersions')}</MenuItem>
            <MenuItem value="device-uptime">{t('reports.deviceUptime')}</MenuItem>
            <MenuItem value="bandwidth-summary">{t('reports.bandwidthSummary')}</MenuItem>
          </Select>
        </FormControl>
        {reportType === 'software-versions' && (
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>{t('reports.filterByType')}</InputLabel>
            <Select value={filterType} label={t('reports.filterByType')} onChange={e => setFilterType(e.target.value)}>
              <MenuItem value="">{t('reports.allTypes')}</MenuItem>
              <MenuItem value="cisco_ios">Cisco IOS</MenuItem>
              <MenuItem value="cisco_ios_router">Cisco Router</MenuItem>
              <MenuItem value="aruba_aoscx">Aruba CX</MenuItem>
            </Select>
          </FormControl>
        )}
      </Paper>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
      ) : (
        <>
          {reportType === 'software-versions' && renderVersions()}
          {reportType === 'device-uptime' && renderUptime()}
          {reportType === 'bandwidth-summary' && renderBandwidth()}
        </>
      )}
    </Container>
  )
}
