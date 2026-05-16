import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions, Alert } from '@mui/material'
import { CloudUpload } from '@mui/icons-material'
import type { CollectResult } from '../../types'

interface CollectResultDialogProps {
  open: boolean
  onClose: () => void
  result: CollectResult | null
  error: string
  deviceName?: string
}

const CollectResultDialog: React.FC<CollectResultDialogProps> = React.memo(({ open, onClose, result, error, deviceName }) => {
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
            <Typography variant="h6" sx={{ fontWeight: 600 }}>Configuration Collection</Typography>
            <Typography variant="subtitle2" color="text.secondary">
              {result?.status === 'success' ? 'Success' : 'Failed'}
            </Typography>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {result?.status === 'success' && (
          <Box sx={{ p: 2 }}>
            <Box sx={{ p: 2, bgcolor: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 1, mb: 2 }}>
              <Typography variant="body1" gutterBottom>
                <strong style={{ color: '#22C55E' }}>Device:</strong>{' '}
                <span>{result.name}</span>
              </Typography>
              <Typography variant="body1">
                <strong style={{ color: '#22C55E' }}>IP:</strong>{' '}
                <span>{result.ip}</span>
              </Typography>
              <Typography variant="body1">
                <strong style={{ color: '#22C55E' }}>Software Version:</strong>{' '}
                <span>{result.software_version}</span>
              </Typography>
              <Typography variant="body1">
                <strong style={{ color: '#22C55E' }}>Serial Number:</strong>{' '}
                <span>{result.serial_number || 'Unknown'}</span>
              </Typography>
              <Typography variant="body1" sx={{ mt: 1, fontWeight: 500 }}>
                <strong style={{ color: '#22C55E' }}>Running Config Lines:</strong>{' '}
                <span style={{ color: '#4ADE80' }}>{result.running_lines}</span>
              </Typography>
            </Box>
            {result.type_mismatch && (
              <Alert severity="warning" sx={{ mb: 2, fontSize: '0.8rem' }}>
                设备类型已自动修正：{result.configured_type} → {result.device_type}
              </Alert>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        {result?.status === 'success' && (
          <Button variant="contained" onClick={handleViewData}>
            View Data
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
})

export default CollectResultDialog
