import React from 'react'
import { Box, Paper, Typography, Grid, Card, CardContent, Chip, IconButton, Tooltip, Badge } from '@mui/material'
import { Storage, NetworkWifi, CloudUpload, Refresh as RefreshIcon, Edit, Delete } from '@mui/icons-material'
import { getDeviceColor, getTypeLabel } from './deviceUtils'
import { useI18n } from '../../i18n'
import type { Device } from '../../types'

interface DeviceCardGridProps {
  devices: Device[]
  selectedLocation: string
  collecting: boolean
  onCollect: (d: Device) => void
  onEdit: (d: Device) => void
  onDelete: (d: Device) => void
}

const DeviceCardGrid: React.FC<DeviceCardGridProps> = React.memo(({ devices, selectedLocation, collecting, onCollect, onEdit, onDelete }) => {
  const { t } = useI18n()

  if (devices.length === 0) {
    return (
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography color="text.secondary">{t('devices.noDeviceAtLocation').replace('{location}', selectedLocation)}</Typography>
          </Paper>
        </Grid>
      </Grid>
    )
  }

  return (
    <Grid container spacing={3} sx={{ mb: 4 }}>
      {devices.map((device) => {
        const colors = getDeviceColor(device.type)
        return (
          <Grid item xs={12} sm={6} md={4} lg={3} key={device.name}>
            <Card
              sx={{
                height: '100%',
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                transition: 'box-shadow 200ms ease, transform 200ms ease',
                '&:hover': {
                  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  transform: 'translateY(-2px)',
                },
              }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Badge
                    overlap="circular"
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                    variant="dot"
                    color="success"
                    sx={{ mr: 1.5, mt: 0.5 }}
                  >
                    <Storage sx={{ color: colors.primary, fontSize: 20 }} />
                  </Badge>
                  <Box>
                    <Typography variant="h6" sx={{ color: 'text.primary', fontWeight: 600 }}>{device.name}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <NetworkWifi sx={{ fontSize: 14 }} />{device.ip}
                    </Typography>
                  </Box>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Chip
                    label={getTypeLabel(device.type, t)}
                    sx={{
                      bgcolor: colors.secondary, color: colors.primary,
                      border: '1px solid', borderColor: colors.border,
                      fontWeight: 500, fontSize: '0.75rem', mr: 0.5, mb: 0.5,
                    }}
                  />
                  {device.location && (
                    <Chip
                      label={device.location}
                      sx={{
                        bgcolor: 'rgba(148,163,184,0.08)', color: 'text.secondary',
                        border: '1px solid', borderColor: 'divider',
                        fontWeight: 500, fontSize: '0.75rem', ml: 0.5, mb: 0.5,
                      }}
                    />
                  )}
                </Box>

                {device.notes && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontSize: '0.75rem' }}
                  >
                    {device.notes}
                  </Typography>
                )}

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {device.platform || t('common.unknown')}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Tooltip title={collecting ? t('devices.collecting') : t('devices.collectTooltip')}>
                      <IconButton size="small" onClick={() => onCollect(device)} disabled={collecting}
                        sx={{ color: colors.primary, '&:hover': { bgcolor: colors.secondary } }}>
                        <CloudUpload fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('devices.viewDetailsTooltip')}>
                      <IconButton size="small" component="a" href={`/devices/${device.name}`}
                        sx={{ color: 'primary.main', '&:hover': { bgcolor: 'rgba(34,197,94,0.08)' } }}>
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('devices.editTooltip')}>
                      <IconButton size="small" onClick={() => onEdit(device)}
                        sx={{ color: 'warning.main', '&:hover': { bgcolor: 'rgba(245,158,11,0.08)' } }}>
                        <Edit fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('devices.deleteTooltip')}>
                      <IconButton size="small" onClick={() => onDelete(device)}
                        sx={{ color: 'error.main', '&:hover': { bgcolor: 'rgba(239,68,68,0.08)' } }}>
                        <Delete fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        )
      })}
    </Grid>
  )
})

export default DeviceCardGrid
