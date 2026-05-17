import React from 'react'
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material'
import { DeleteForever } from '@mui/icons-material'
import { useI18n } from '../../i18n'

interface DeleteConfirmDialogProps {
  open: boolean
  deviceName?: string
  onCancel: () => void
  onConfirm: () => void
}

const DeleteConfirmDialog: React.FC<DeleteConfirmDialogProps> = React.memo(({ open, deviceName, onCancel, onConfirm }) => {
  const { t } = useI18n()
  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <DeleteForever color="error" sx={{ fontSize: 40 }} />
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>{t('devices.deleteDevice')}</Typography>
            <Typography variant="subtitle2" color="text.secondary">{t('devices.confirmDeletion')}</Typography>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
          {t('devices.deleteWarning').replace('{name}', deviceName || '')}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>{t('common.cancel')}</Button>
        <Button onClick={onConfirm} variant="contained" color="error">{t('common.delete')}</Button>
      </DialogActions>
    </Dialog>
  )
})

export default DeleteConfirmDialog
