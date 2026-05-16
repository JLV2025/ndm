import React from 'react'
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material'
import { DeleteForever } from '@mui/icons-material'

interface DeleteConfirmDialogProps {
  open: boolean
  deviceName?: string
  onCancel: () => void
  onConfirm: () => void
}

const DeleteConfirmDialog: React.FC<DeleteConfirmDialogProps> = React.memo(({ open, deviceName, onCancel, onConfirm }) => {
  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <DeleteForever color="error" sx={{ fontSize: 40 }} />
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>Delete Device</Typography>
            <Typography variant="subtitle2" color="text.secondary">Confirm Deletion</Typography>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
          Are you sure you want to delete device <strong style={{ color: '#EF4444' }}>{deviceName}</strong>? This action cannot be undone.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button onClick={onConfirm} variant="contained" color="error">Delete</Button>
      </DialogActions>
    </Dialog>
  )
})

export default DeleteConfirmDialog
