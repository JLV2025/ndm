import { useState, useEffect, useMemo } from 'react'
import {
  Box,
  Paper,
  Typography,
  Autocomplete,
  TextField,
  CircularProgress,
  Stack,
  keyframes,
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

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
`

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
      {/* 页面头部 — 左侧绿色装饰条 */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'flex-start', gap: 2, flexShrink: 0 }}>
        <Box
          sx={{
            width: 4, height: 48, borderRadius: 2,
            bgcolor: 'primary.main',
            boxShadow: '0 0 12px rgba(45, 212, 110, 0.35)',
            flexShrink: 0, mt: 0.5,
          }}
        />
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.25, letterSpacing: '-0.01em' }}>
            {t('topology.title')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.85rem', ml: 0.5 }}>
            {t('topology.description')}
          </Typography>
        </Box>
      </Box>

      {/* 步骤1：选择位置 */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 2.5, flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: 'text.secondary', whiteSpace: 'nowrap', letterSpacing: '0.04em', textTransform: 'uppercase', bgcolor: 'rgba(45,212,110,0.06)', px: 1, py: 0.5, borderRadius: 1 }}>
            STEP 1
          </Typography>
          <LocationFilter selectedLocation={selectedLocation} onChange={(v) => setSelectedLocation(v)} locations={locations} />
        </Box>

        {/* 步骤2：选择设备（仅在选择位置后出现） */}
        {selectedLocation && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, animation: `${fadeIn} 0.35s ease` }}>
            <Box sx={{ width: 1, height: 28, bgcolor: 'divider', mx: 1 }} />
            <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: 'text.secondary', whiteSpace: 'nowrap', letterSpacing: '0.04em', textTransform: 'uppercase', bgcolor: 'rgba(45,212,110,0.06)', px: 1, py: 0.5, borderRadius: 1 }}>
              STEP 2
            </Typography>
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
          </Box>
        )}
      </Paper>

      {/* 拓扑画布区域 */}
      <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
        {!selectedDevice ? (
          <Paper sx={{ p: 6, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
            <HubIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h5" sx={{ color: 'text.secondary', mb: 0.5 }}>
              {selectedLocation ? t('topology.selectDeviceHint') : t('topology.selectLocationHint')}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.disabled', fontSize: '0.82rem' }}>
              {selectedLocation ? t('topology.selectDeviceDesc') : t('topology.selectLocationDesc')}
            </Typography>
          </Paper>
        ) : loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500 }}>
            <CircularProgress size={32} />
          </Box>
        ) : (
          <Box key={selectedDevice.name} sx={{ width: '100%', height: '100%', animation: `${fadeIn} 0.45s ease` }}>
            <TopologyCanvas deviceName={selectedDevice.name} neighbors={neighbors} stackMembers={stackMembers} memberNeighbors={memberNeighbors} />
          </Box>
        )}

        {/* 图例 — 画布左侧纵向排列 */}
        {selectedDevice && !loading && (
          <Paper
            sx={{
              position: 'absolute', left: 16, top: 16, zIndex: 10,
              px: 1.2, py: 1, borderRadius: 2,
              bgcolor: 'rgba(15, 18, 35, 0.78)',
              backdropFilter: 'blur(10px)',
              border: '1px solid', borderColor: 'divider',
              animation: `${fadeIn} 0.35s ease`,
              minWidth: 100,
            }}
          >
            <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', mb: 0.6, letterSpacing: '0.06em', textTransform: 'uppercase', textAlign: 'center' }}>
              {t('topology.legend')}
            </Typography>
            <Stack alignItems="flex-start" gap={0.4}>
              {LEGEND_ITEMS.map((item) => (
                <Box key={item.type} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: item.color, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.58rem', fontWeight: 500, color: '#cbd5e1', lineHeight: 1.2, whiteSpace: 'nowrap' }}>
                    {lang === 'zh' ? item.labelZh : item.labelEn}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Paper>
        )}
      </Box>
    </Box>
  )
}
