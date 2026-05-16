import React from 'react'
import { Box, Paper, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Chip, Button, IconButton, Tooltip, Avatar, Checkbox } from '@mui/material'
import { Storage, CloudUpload, Delete } from '@mui/icons-material'
import { getDeviceColor, getTypeLabel } from './deviceUtils'
import { useI18n } from '../../i18n'
import type { Device, BatchItemStatus } from '../../types'

interface DeviceTableProps {
  devices: Device[]
  sortField: string
  sortDir: 'asc' | 'desc'
  sortStyle: (field: string) => object
  selectedDevices: Set<string>
  batchStatus: Record<string, BatchItemStatus>
  collecting: boolean
  allSelected: boolean
  someSelected: boolean
  totalCount: number
  batchRunning: boolean
  onSelectAll: (checked: boolean) => void
  onSelectOne: (name: string, checked: boolean) => void
  onSort: (field: string) => void
  onCollect: (d: Device) => void
  onDelete: (d: Device) => void
  onBatchCollect: () => void
}

const DeviceTable: React.FC<DeviceTableProps> = React.memo(({
  devices, sortField, sortDir, sortStyle, selectedDevices, batchStatus,
  collecting, allSelected, someSelected, totalCount, batchRunning,
  onSelectAll, onSelectOne, onSort, onCollect, onDelete, onBatchCollect,
}) => {
  const { t } = useI18n()

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.875rem' }}>
          Device Inventory
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {selectedDevices.size > 0 && (
            <Button
              variant="contained"
              size="small"
              disabled={batchRunning}
              onClick={onBatchCollect}
              sx={{ fontWeight: 600, fontSize: '0.75rem' }}
            >
              批量收集 ({selectedDevices.size})
            </Button>
          )}
          <Typography variant="caption" color="text.secondary">
            Total: {totalCount}
          </Typography>
        </Box>
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected}
                  onChange={(_, checked) => onSelectAll(checked)}
                  sx={{ color: 'text.secondary', '&.Mui-checked': { color: 'primary.main' }, '&.MuiCheckbox-indeterminate': { color: 'primary.main' } }}
                />
              </TableCell>
              <TableCell onClick={() => onSort('name')} sx={sortStyle('name')}>
                {t('dashboard.device')} {sortField === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableCell>
              <TableCell onClick={() => onSort('type')} sx={sortStyle('type')}>
                {t('dashboard.type')} {sortField === 'type' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableCell>
              <TableCell>{t('dashboard.ipAddress')}</TableCell>
              <TableCell onClick={() => onSort('location')} sx={sortStyle('location')}>
                {t('dashboard.location')} {sortField === 'location' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableCell>
              <TableCell>{t('devices.platform')}</TableCell>
              <TableCell>{t('devices.lastSync')}</TableCell>
              <TableCell>{t('devices.actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {devices.map((device) => {
              const colors = getDeviceColor(device.type)
              const isSelected = selectedDevices.has(device.name)
              const bs = batchStatus[device.name]
              return (
                <TableRow key={device.name} hover selected={isSelected}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={isSelected}
                      onChange={(_, checked) => onSelectOne(device.name, checked)}
                      sx={{ color: 'text.secondary', '&.Mui-checked': { color: 'primary.main' } }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Avatar sx={{ bgcolor: colors.secondary, color: colors.primary, mr: 1.5, width: 28, height: 28, border: '1px solid', borderColor: colors.border }}>
                        <Storage fontSize="small" />
                      </Avatar>
                      <Box>
                        <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>{device.name}</Typography>
                        {bs && (
                          <Chip
                            label={bs.status === 'success' ? 'OK' : bs.status === 'failed' ? '失败' : bs.status}
                            size="small"
                            sx={{
                              height: 16, fontSize: '0.6rem', mt: 0.25,
                              bgcolor: bs.status === 'success' ? 'rgba(34,197,94,0.1)' : bs.status === 'failed' ? 'rgba(239,68,68,0.1)' : 'rgba(148,163,184,0.06)',
                              color: bs.status === 'success' ? 'success.main' : bs.status === 'failed' ? 'error.main' : 'text.secondary',
                            }}
                          />
                        )}
                      </Box>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={getTypeLabel(device.type, t)}
                      size="small"
                      sx={{
                        bgcolor: colors.secondary, color: colors.primary,
                        border: '1px solid', borderColor: colors.border,
                        fontWeight: 500, height: 20, fontSize: '0.65rem',
                      }}
                    />
                  </TableCell>
                  <TableCell>{device.ip}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{device.location || '-'}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{device.platform || '-'}</TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
                    {device.last_synced
                      ? (() => { const [d, t2] = device.last_synced.split(' '); return `${d} ${t2 || ''}`; })()
                      : '-'}
                  </TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Tooltip title="Collect">
                        <IconButton size="small" onClick={() => onCollect(device)} disabled={collecting}
                          sx={{ color: colors.primary, '&:hover': { bgcolor: colors.secondary } }}>
                          <CloudUpload fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton size="small" onClick={() => onDelete(device)}
                          sx={{ color: 'error.main', '&:hover': { bgcolor: 'rgba(239,68,68,0.08)' } }}>
                          <Delete fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
})

export default DeviceTable
