import { useState, useEffect, useMemo } from 'react'
import {
  Box,
  Paper,
  Typography,
  Autocomplete,
  TextField,
  CircularProgress,
  Chip,
  Stack,
} from '@mui/material'
import { Hub as HubIcon } from '@mui/icons-material'
import { deviceApi, topologyApi } from '../services/api'
import { useI18n } from '../i18n'
import LocationFilter from '../components/devices/LocationFilter'
import TopologyCanvas from '../components/topology/TopologyCanvas'
import type { Device } from '../types'
import type { NeighborNode } from '../types/topology'

const LEGEND_ITEMS = [
  { type: 'switch', labelZh: '交换机', labelEn: 'Switch', color: '#3B82F6' },
  { type: 'router', labelZh: '路由器', labelEn: 'Router', color: '#F59E0B' },
  { type: 'firewall', labelZh: '防火墙', labelEn: 'Firewall', color: '#EF4444' },
  { type: 'wireless', labelZh: '无线控制器', labelEn: 'Wireless Controller', color: '#8B5CF6' },
  { type: 'sdwan', labelZh: 'SD-WAN', labelEn: 'SD-WAN', color: '#10B981' },
  { type: 'server', labelZh: '服务器', labelEn: 'Server', color: '#06B6D4' },
  { type: 'printer', labelZh: '打印机', labelEn: 'Printer', color: '#6366F1' },
  { type: 'endpoint', labelZh: '端点设备', labelEn: 'Endpoint', color: '#94A3B8' },
]

export default function Topology() {
  const { t, lang } = useI18n()
  const [devices, setDevices] = useState<Device[]>([])
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [neighbors, setNeighbors] = useState<NeighborNode[]>([])
  const [stackMembers, setStackMembers] = useState<string[]>([])
  const [memberNeighbors, setMemberNeighbors] = useState<Record<string, NeighborNode[]>>({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    deviceApi.list().then((res) => setDevices(res.data)).catch(console.error)
  }, [])

  const locations = useMemo(() => {
    const locSet = new Set<string>()
    for (const d of devices) {
      if (d.location) locSet.add(d.location)
    }
    return Array.from(locSet).sort()
  }, [devices])

  const filteredDevices = useMemo(() => {
    if (!selectedLocation) return devices
    return devices.filter((d) => d.location === selectedLocation)
  }, [devices, selectedLocation])

  useEffect(() => {
    if (selectedDevice && selectedDevice.location !== selectedLocation) {
      setSelectedDevice(null)
      setNeighbors([])
      setStackMembers([])
      setMemberNeighbors({})
    }
  }, [selectedLocation])

  useEffect(() => {
    if (!selectedDevice) {
      setNeighbors([])
      setStackMembers([])
      setMemberNeighbors({})
      return
    }
    setLoading(true)
    topologyApi
      .getTopology(selectedDevice.name)
      .then((data) => {
        setNeighbors(data.neighbors || [])
        setStackMembers(data.stack_members || [])
        setMemberNeighbors(data.member_neighbors || {})
      })
      .catch((err) => {
        console.error(err)
        setNeighbors([])
        setStackMembers([])
        setMemberNeighbors({})
      })
      .finally(() => setLoading(false))
  }, [selectedDevice])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', px: 2, py: 2 }}>
      {/* 页面头部 */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'flex-start', gap: 2, flexShrink: 0 }}>
        <Box
          sx={{
            width: 40, height: 40, borderRadius: 1.5,
            bgcolor: 'rgba(45, 212, 110, 0.08)',
            border: '1px solid', borderColor: 'rgba(45, 212, 110, 0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}
        >
          <HubIcon sx={{ color: 'primary.main', fontSize: 20 }} />
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.25 }}>
            {t('topology.title')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>
            {t('topology.description')}
          </Typography>
        </Box>
      </Box>

      {/* 位置筛选 + 设备选择器 */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 2.5, flexWrap: 'wrap', flexShrink: 0 }}>
        <LocationFilter selectedLocation={selectedLocation} onChange={(v) => setSelectedLocation(v)} locations={locations} />
        <Autocomplete
          options={filteredDevices}
          value={selectedDevice}
          onChange={(_, newValue) => setSelectedDevice(newValue)}
          getOptionLabel={(option) => `${option.name} (${option.ip})`}
          isOptionEqualToValue={(option, value) => option.name === value.name}
          renderInput={(params) => (
            <TextField
              {...params} label={t('topology.selectDevice')} size="small"
              InputProps={{ ...params.InputProps, endAdornment: (<>{loading && <CircularProgress size={20} />}{params.InputProps.endAdornment}</>) }}
            />
          )}
          noOptionsText={t('devices.noDevices')}
          sx={{ minWidth: 300, maxWidth: 420 }}
        />
      </Paper>

      {/* 拓扑画布 — 占满剩余高度 */}
      <Box sx={{ flex: 1, minHeight: 0 }}>
        {!selectedDevice ? (
          <Paper sx={{ p: 6, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
            <HubIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>{t('topology.empty')}</Typography>
          </Paper>
        ) : loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500 }}>
            <CircularProgress size={32} />
          </Box>
        ) : (
          <TopologyCanvas deviceName={selectedDevice.name} neighbors={neighbors} stackMembers={stackMembers} memberNeighbors={memberNeighbors} />
        )}
      </Box>

      {/* 图例 — 底部横排 */}
      <Paper sx={{ p: 1.5, mt: 2, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Stack direction="row" alignItems="center" gap={0.5} flexWrap="wrap">
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary', mr: 0.5 }}>{t('topology.legend')}:</Typography>
          {LEGEND_ITEMS.map((item) => (
            <Chip
              key={item.type}
              label={lang === 'zh' ? item.labelZh : item.labelEn}
              size="small"
              sx={{ fontSize: '0.65rem', fontWeight: 500, bgcolor: `${item.color}18`, color: item.color, border: '1px solid', borderColor: `${item.color}40` }}
            />
          ))}
        </Stack>
      </Paper>
    </Box>
  )
}
