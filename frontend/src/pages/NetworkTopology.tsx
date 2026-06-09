import { useState, useEffect, useMemo, useCallback } from 'react'
import { Box, Paper, Typography, CircularProgress, Stack } from '@mui/material'
import { Hub as HubIcon } from '@mui/icons-material'
import { deviceApi, topologyApi } from '../services/api'
import { useI18n } from '../i18n'
import LocationFilter from '../components/devices/LocationFilter'
import LocationTopologyCanvas from '../components/topology/LocationTopologyCanvas'
import type { Device } from '../types'
import type { LocationTopologyData } from '../types/topology'

const LEGEND_ITEMS = [
  { type: 'switch', labelZh: '交换机', labelEn: 'Switch', color: '#3B82F6' },
  { type: 'router', labelZh: '路由器', labelEn: 'Router', color: '#F59E0B' },
  { type: 'firewall', labelZh: '防火墙', labelEn: 'Firewall', color: '#EF4444' },
  { type: 'wireless', labelZh: '无线控制器', labelEn: 'Wireless Controller', color: '#8B5CF6' },
  { type: 'sdwan', labelZh: 'SD-WAN', labelEn: 'SD-WAN', color: '#10B981' },
  { type: 'server', labelZh: '服务器', labelEn: 'Server', color: '#06B6D4' },
]

export default function NetworkTopology() {
  const { t, lang } = useI18n()
  const [devices, setDevices] = useState<Device[]>([])
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [topoData, setTopoData] = useState<LocationTopologyData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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

  // 当 location 变化时, 加载拓扑数据
  const loadTopology = useCallback((loc: string | null) => {
    setSelectedLocation(loc)
    if (!loc) {
      setTopoData(null)
      setError('')
      return
    }
    setLoading(true)
    setError('')
    setTopoData(null)
    topologyApi.getLocationTopology(loc)
      .then((data) => {
        setTopoData(data)
        setLoading(false)
      })
      .catch((err) => {
        console.error(err)
        setError(err.response?.data?.detail || err.message || 'Failed to load topology')
        setLoading(false)
      })
  }, [])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', px: 2, py: 2 }}>
      {/* 页面头部 */}
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
            {t('topology.networkTitle')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.85rem', ml: 0.5 }}>
            {t('topology.networkDesc')}
          </Typography>
        </Box>
      </Box>

      {/* Location 选择 */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
        <LocationFilter
          selectedLocation={selectedLocation}
          onChange={loadTopology}
          locations={locations}
        />
        {selectedLocation && topoData && (
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', ml: 2 }}>
            {topoData.node_count} nodes, {topoData.edges.length} edges
            {topoData.skipped_count > 0 && ` (${topoData.skipped_count} skipped)`}
          </Typography>
        )}
      </Paper>

      {/* 主区域 */}
      <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
        {!selectedLocation ? (
          <Paper sx={{ p: 6, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
            <HubIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h5" sx={{ color: 'text.secondary', mb: 0.5 }}>
              {t('topology.selectLocationHint')}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.disabled', fontSize: '0.82rem' }}>
              {t('topology.selectLocationDesc')}
            </Typography>
          </Paper>
        ) : loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500 }}>
            <CircularProgress size={32} />
          </Box>
        ) : error ? (
          <Paper sx={{ p: 4, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid #EF444440', textAlign: 'center' }}>
            <Typography sx={{ color: '#EF4444', mb: 1 }}>{error}</Typography>
          </Paper>
        ) : topoData && topoData.nodes.length === 0 ? (
          <Paper sx={{ p: 4, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
            <Typography sx={{ color: 'text.secondary' }}>{t('topology.noConnections')}</Typography>
          </Paper>
        ) : topoData ? (
          <Box sx={{ width: '100%', height: '100%' }}>
            <LocationTopologyCanvas location={selectedLocation!} data={topoData} />
          </Box>
        ) : null}

        {/* 图例 */}
        {topoData && topoData.nodes.length > 0 && (
          <Paper
            sx={{
              position: 'absolute', left: 16, top: 16, zIndex: 10,
              px: 1.2, py: 1, borderRadius: 2,
              bgcolor: 'rgba(15, 18, 35, 0.78)',
              backdropFilter: 'blur(10px)',
              border: '1px solid', borderColor: 'divider',
              minWidth: 100,
            }}
          >
            <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', mb: 0.6, letterSpacing: '0.06em', textTransform: 'uppercase', textAlign: 'center' }}>
              {t('topology.legend')}
            </Typography>

            {/* Tier 标注 */}
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: '#F59E0B', mt: 0.5, mb: 0.3 }}>
              WAN ({t('topology.wanTier')})
            </Typography>
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: '#3B82F6', mb: 0.3 }}>
              Core ({t('topology.coreTier')})
            </Typography>
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: '#64748b', mb: 0.6 }}>
              Access ({t('topology.accessTier')})
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
