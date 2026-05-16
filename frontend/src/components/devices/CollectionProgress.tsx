import React from 'react'
import { Box, Paper, Typography, CircularProgress, LinearProgress } from '@mui/material'

interface CollectionProgressProps {
  phase: 'ping' | 'collect' | null
  device: { name: string; ip: string }
}

const CollectionProgress: React.FC<CollectionProgressProps> = React.memo(({ phase, device }) => {
  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <CircularProgress size={24} />
        <Box sx={{ flex: 1 }}>
          <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 600 }}>
            {phase === 'ping'
              ? `正在 Ping ${device.ip} ...`
              : `正在收集 ${device.name} (${device.ip}) ...`}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {phase === 'ping' ? '检测设备在线状态' : 'SSH 连接交换机，下载配置（10-30 秒）'}
          </Typography>
        </Box>
      </Box>
      <LinearProgress sx={{ mt: 1.5 }} />
    </Paper>
  )
})

export default CollectionProgress
