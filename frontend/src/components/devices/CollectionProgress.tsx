import React from 'react'
import { Box, Paper, Typography, CircularProgress, LinearProgress } from '@mui/material'
import { useI18n } from '../../i18n'

interface CollectionProgressProps {
  phase: 'ping' | 'collect' | null
  device: { name: string; ip: string }
}

const CollectionProgress: React.FC<CollectionProgressProps> = React.memo(({ phase, device }) => {
  const { t } = useI18n()
  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <CircularProgress size={24} />
        <Box sx={{ flex: 1 }}>
          <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 600 }}>
            {phase === 'ping'
              ? t('devices.pinging').replace('{ip}', device.ip)
              : t('devices.collectingDevice').replace('{name}', device.name).replace('{ip}', device.ip)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {phase === 'ping' ? t('devices.pingCheck') : t('devices.sshCollect')}
          </Typography>
        </Box>
      </Box>
      <LinearProgress sx={{ mt: 1.5 }} />
    </Paper>
  )
})

export default CollectionProgress
