import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions, Alert } from '@mui/material'
import { CloudUpload } from '@mui/icons-material'
import type { CollectResult } from '../../types'
import { useI18n } from '../../i18n'

interface CollectResultDialogProps {
  open: boolean
  onClose: () => void
  result: CollectResult | null
  error: string
  deviceName?: string
}

const CollectResultDialog: React.FC<CollectResultDialogProps> = React.memo(({ open, onClose, result, error, deviceName }) => {
  const { t } = useI18n()
  const navigate = useNavigate()

  const handleViewData = () => {
    onClose()
    navigate(`/viewer?device=${deviceName}`)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {result?.status === 'success'
            ? <CloudUpload color="success" sx={{ fontSize: 40 }} />
            : <CloudUpload color="error" sx={{ fontSize: 40 }} />}
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>{t('collect.configTitle')}</Typography>
            <Typography variant="subtitle2" color="text.secondary">
              {result?.status === 'success' ? t('collect.success') : t('collect.failed')}
            </Typography>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {result?.status === 'success' && (
          <Box sx={{ p: 2 }}>
            <Box sx={{ p: 2, bgcolor: 'rgba(45,212,110,0.06)', border: '1px solid rgba(45,212,110,0.2)', borderRadius: 1, mb: 2 }}>
              <Typography variant="body1" gutterBottom>
                <strong style={{ color: '#2DD46E' }}>{t('collect.deviceLabel')}:</strong>{' '}
                <span>{result.name}</span>
              </Typography>
              <Typography variant="body1">
                <strong style={{ color: '#2DD46E' }}>{t('collect.ipLabel')}:</strong>{' '}
                <span>{result.ip}</span>
              </Typography>
              <Typography variant="body1">
                <strong style={{ color: '#2DD46E' }}>{t('collect.softwareVersion')}:</strong>{' '}
                <span>{result.software_version}</span>
              </Typography>
              <Typography variant="body1">
                <strong style={{ color: '#2DD46E' }}>{t('collect.serialNumber')}:</strong>{' '}
                <span>{result.serial_number || t('collect.unknown')}</span>
              </Typography>
              <Typography variant="body1" sx={{ mt: 1, fontWeight: 500 }}>
                <strong style={{ color: '#2DD46E' }}>{t('collect.runningLines')}:</strong>{' '}
                <span style={{ color: '#5CE68C' }}>{result.running_lines}</span>
              </Typography>
            </Box>
            {result.type_mismatch && (
              <Alert severity="warning" sx={{ mb: 2, fontSize: '0.8rem' }}>
                {t('collect.typeCorrected').replace('{old}', result.configured_type || '').replace('{new}', result.device_type || '')}
              </Alert>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('collect.close')}</Button>
        {result?.status === 'success' && (
          <Button variant="contained" onClick={handleViewData}>
            {t('collect.viewData')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
})

export default CollectResultDialog
