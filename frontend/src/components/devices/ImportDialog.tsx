import React, { useState, useRef } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
} from '@mui/material'
import {
  CloudUpload,
  Download,
  Close,
  CheckCircle,
  Error as ErrorIcon,
  SkipNext,
} from '@mui/icons-material'
import { deviceApi } from '../../services/api'
import { useI18n } from '../../i18n'

interface ImportResult {
  row: number
  name: string
  status: 'success' | 'failed' | 'skipped'
  errors: string[]
}

interface ImportResponse {
  success: boolean
  total: number
  success_count: number
  failed_count: number
  skipped_count: number
  results: ImportResult[]
}

const ImportDialog: React.FC<{ open: boolean; onClose: () => void; onImported: () => void }> = ({
  open,
  onClose,
  onImported,
}) => {
  const { t } = useI18n()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ImportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null
    setFile(f)
    setResult(null)
    setError(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0] || null
    if (f && (f.name.endsWith('.csv') || f.type === 'text/csv')) {
      setFile(f)
      setResult(null)
      setError(null)
    }
  }

  const handleImport = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await deviceApi.batchImport(file)
      setResult(res.data)
      onImported()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('import.importFailed')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadTemplate = async () => {
    try {
      const blob = await deviceApi.downloadTemplate()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'NDM_Device_Import_Template.csv'
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      // 延迟 revoke：给浏览器时间处理下载，否则文件会为空
      setTimeout(() => {
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }, 1000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('import.importFailed')
      setError(msg)
    }
  }

  const handleClose = () => {
    setFile(null)
    setResult(null)
    setError(null)
    onClose()
  }

  const statusIcon = (status: string) => {
    if (status === 'success') return <CheckCircle sx={{ color: '#2DD46E', fontSize: 18 }} />
    if (status === 'failed') return <ErrorIcon sx={{ color: '#ef4444', fontSize: 18 }} />
    return <SkipNext sx={{ color: '#f59e0b', fontSize: 18 }} />
  }

  const statusLabel = (status: string) => {
    if (status === 'success') return t('import.success') || 'Success'
    if (status === 'failed') return t('import.failed') || 'Failed'
    return t('import.skipped') || 'Skipped'
  }

  return (
    <Dialog open={open} onClose={loading ? undefined : handleClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, fontSize: '0.95rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {t('import.title') || 'Batch Import Devices'}
        <IconButton onClick={handleClose} disabled={loading} size="small">
          <Close fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {/* Upload area */}
        {!result && (
          <Box>
            <Box
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              sx={{
                border: '2px dashed',
                borderColor: file ? 'primary.main' : 'rgba(255,255,255,0.15)',
                borderRadius: 2,
                p: 4,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: file ? 'rgba(45,212,110,0.04)' : 'transparent',
                transition: 'all 0.2s',
                '&:hover': { borderColor: 'primary.main', bgcolor: 'rgba(45,212,110,0.04)' },
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                hidden
                onChange={handleFileChange}
              />
              <CloudUpload sx={{ fontSize: 48, color: file ? 'primary.main' : 'text.disabled', mb: 1 }} />
              <Typography variant="body1" sx={{ fontWeight: 600, mb: 0.5 }}>
                {file ? file.name : t('import.dropHint') || 'Drop CSV file here or click to select'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {file ? `${(file.size / 1024).toFixed(1)} KB` : t('import.csvOnly') || 'Only .csv files supported'}
              </Typography>
            </Box>

            {/* Template download */}
            <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button
                size="small"
                variant="text"
                startIcon={<Download />}
                onClick={handleDownloadTemplate}
                sx={{ fontSize: '0.75rem' }}
              >
                {t('import.downloadTemplate') || 'Download Template'}
              </Button>
            </Box>

            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}
          </Box>
        )}

        {/* Loading */}
        {loading && <LinearProgress sx={{ my: 2 }} />}

        {/* Results */}
        {result && (
          <Box>
            {/* Summary */}
            <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
              <Chip
                icon={<CheckCircle />}
                label={`${t('import.success') || 'Success'}: ${result.success_count}`}
                sx={{ bgcolor: 'rgba(45,212,110,0.12)', color: '#2DD46E', fontWeight: 600 }}
              />
              <Chip
                icon={<SkipNext />}
                label={`${t('import.skipped') || 'Skipped'}: ${result.skipped_count}`}
                sx={{ bgcolor: 'rgba(245,158,11,0.12)', color: '#f59e0b', fontWeight: 600 }}
              />
              <Chip
                icon={<ErrorIcon />}
                label={`${t('import.failed') || 'Failed'}: ${result.failed_count}`}
                sx={{ bgcolor: 'rgba(239,68,68,0.12)', color: '#ef4444', fontWeight: 600 }}
              />
            </Box>

            {/* Detail table (only if there are errors/skipped) */}
            {(result.failed_count > 0 || result.skipped_count > 0) && (
              <TableContainer sx={{ maxHeight: 320 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem' }}>Row</TableCell>
                      <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem' }}>Name</TableCell>
                      <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem' }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem' }}>Detail</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {result.results
                      .filter((r) => r.status !== 'success')
                      .map((r, i) => (
                        <TableRow key={i}>
                          <TableCell sx={{ fontSize: '0.75rem' }}>{r.row}</TableCell>
                          <TableCell sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>{r.name}</TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              {statusIcon(r.status)}
                              <Typography variant="caption">{statusLabel(r.status)}</Typography>
                            </Box>
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.75rem', color: 'error.main' }}>
                            {r.errors.join('; ')}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {result.failed_count === 0 && result.skipped_count === 0 && (
              <Alert severity="success" sx={{ mt: 1 }}>
                {t('import.allSuccess') || `All ${result.total} devices imported successfully.`}
              </Alert>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        {!result ? (
          <>
            <Button onClick={handleClose} disabled={loading}>
              {t('form.cancel') || 'Cancel'}
            </Button>
            <Button variant="contained" disabled={!file || loading} onClick={handleImport}>
              {t('import.startImport') || 'Start Import'}
            </Button>
          </>
        ) : (
          <Button variant="contained" onClick={handleClose}>
            {t('import.done') || 'Done'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
}

export default ImportDialog
