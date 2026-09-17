import { useState, useEffect, useMemo, useCallback } from 'react'
import { Box, Paper, Typography, CircularProgress } from '@mui/material'
import { AccountTree as TreeIcon } from '@mui/icons-material'
import { deviceApi, topologyApi } from '../services/api'
import { useI18n } from '../i18n'
import LocationFilter from '../components/devices/LocationFilter'
import StpTopologyCanvas from '../components/topology/StpTopologyCanvas'
import type { Device } from '../types'
import type { StpTopologyData } from '../types/topology'

export default function StpTopology() {
  const { t } = useI18n()
  const [devices, setDevices] = useState<Device[]>([])
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [topoData, setTopoData] = useState<StpTopologyData | null>(null)
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

  const loadStp = useCallback((loc: string | null) => {
    setSelectedLocation(loc)
    if (!loc) {
      setTopoData(null)
      setError('')
      return
    }
    setLoading(true)
    setError('')
    setTopoData(null)
    topologyApi.getLocationStp(loc)
      .then((data) => {
        setTopoData(data)
        setLoading(false)
      })
      .catch((err) => {
        console.error(err)
        setError(err.response?.data?.detail || err.message || 'Failed to load STP topology')
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
            {t('topology.stpTitle')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.85rem', ml: 0.5 }}>
            {t('topology.stpDesc')}
          </Typography>
        </Box>
      </Box>

      {/* Location 选择 */}
      <Paper sx={{ p: 2, mb: 2, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
        <LocationFilter
          selectedLocation={selectedLocation}
          onChange={loadStp}
          locations={locations}
          showAll={false}
        />
        {selectedLocation && topoData && (
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', ml: 2 }}>
            {topoData.summary.node_count} {t('topology.stpStatsDevices')} · {topoData.summary.edge_count} {t('topology.stpStatsEdges')} · {topoData.summary.vlan_count} {t('topology.stpStatsVlans')}
          </Typography>
        )}
      </Paper>

      {/* 画布区域 */}
      <Box sx={{ flex: 1, position: 'relative', borderRadius: 2, overflow: 'hidden', bgcolor: '#020617', border: '1px solid', borderColor: 'divider' }}>
        {loading && (
          <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 2, zIndex: 10 }}>
            <CircularProgress size={36} />
            <Typography sx={{ color: 'text.secondary', fontSize: '0.85rem' }}>Loading...</Typography>
          </Box>
        )}
        {error && (
          <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
            <Typography sx={{ color: 'error.main', fontSize: '0.85rem' }}>{error}</Typography>
          </Box>
        )}
        {!selectedLocation && !loading && !error && (
          <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 1.5 }}>
            <TreeIcon sx={{ fontSize: 56, color: '#1E293B' }} />
            <Typography sx={{ color: 'text.secondary', fontSize: '0.85rem' }}>
              {t('topology.selectDeviceDesc')}
            </Typography>
          </Box>
        )}
        {selectedLocation && topoData && !loading && (
          <StpTopologyCanvas key={selectedLocation} location={selectedLocation} data={topoData} />
        )}
      </Box>
    </Box>
  )
}
