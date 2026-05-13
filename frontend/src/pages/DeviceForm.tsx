import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Grid,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  Stack,
  CircularProgress,
} from '@mui/material'
import { useForm, Controller, SubmitHandler } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Storage,
  Save as SaveIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material'
import { deviceApi } from '../services/api'

// 设备表单 Schema 定义
const deviceSchema = z.object({
  name: z.string()
    .min(1, 'Device name is required')
    .max(50, 'Device name cannot exceed 50 characters')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Device name can only contain letters, numbers, underscores, and hyphens'),
  ip: z.string()
    .min(1, 'IP address is required')
    .regex(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/, 'Please enter a valid IP address'),
  type: z.string()
    .min(1, 'Device type is required')
    .max(30, 'Device type cannot exceed 30 characters'),
  platform: z.string().max(50, 'Platform type cannot exceed 50 characters').optional().nullable(),
  location: z.string().max(100, 'Location cannot exceed 100 characters').optional().nullable(),
  notes: z.string().max(500, 'Notes cannot exceed 500 characters').optional().nullable(),
})

export type DeviceFormValues = z.infer<typeof deviceSchema>

// 设备类型选项
const deviceTypes = [
  { value: 'cisco_ios', label: 'Cisco IOS' },
  { value: 'aruba_osswitch', label: 'Aruba OS Switch' },
]

// 平台类型选项
const platformTypes = [
  { value: 'cisco_ios_xe', label: 'Cisco IOS XE' },
  { value: 'cisco_ios', label: 'Cisco IOS' },
  { value: 'aruba_osswitch', label: 'Aruba OS Switch' },
  { value: 'aruba_os', label: 'Aruba OS' },
]

interface DeviceFormProps {
  deviceName?: string | null
  deviceData?: Partial<DeviceFormValues> | null
  onSubmit: (data: DeviceFormValues) => void
  onCancel: () => void
  loading?: boolean
}

const DeviceForm: React.FC<DeviceFormProps> = ({
  deviceName,
  onSubmit,
  onCancel,
  loading = false,
}) => {
  const [localError, setLocalError] = useState<string | null>(null)
  const [deviceData, setDeviceData] = useState<Partial<DeviceFormValues> | null>(null)

  // React Hook Form 初始化
  const methods = useForm<DeviceFormValues>({
    resolver: zodResolver(deviceSchema),
    defaultValues: {
      name: '',
      ip: '',
      type: 'cisco_ios',
      platform: null,
      location: null,
      notes: null,
    },
  })

  // 加载设备数据
  useEffect(() => {
    if (deviceName) {
      loadDevice(deviceName)
    }
  }, [deviceName])

  // 加载设备详情
  const loadDevice = async (name: string) => {
    try {
      const response = await deviceApi.get(name)
      const data = response.data
      setDeviceData(data)

      // 填充表单数据
      methods.reset({
        name: data.name,
        ip: data.ip || '',
        type: data.type || 'cisco_ios',
        platform: data.platform || '',
        location: data.location || '',
        notes: data.notes || '',
      })
    } catch (error: any) {
      console.error('Load device details failed:', error)
      setLocalError(error.message || 'Failed to load device information')
    }
  }

  // 提交处理
  const handleSubmit: SubmitHandler<DeviceFormValues> = async (data) => {
    try {
      // 使用 deviceData 判断是编辑还是添加
      if (deviceData && deviceData.name) {
        // Update existing device
        await deviceApi.update(deviceData.name, data)
      } else {
        // Add new device
        await deviceApi.add(data)
      }
      onSubmit(data)
      handleReset()
    } catch (error: any) {
      console.error('Save device failed:', error)
      setLocalError(error.message || 'Failed to save device information')
    }
  }

  // 重置表单
  const handleReset = () => {
    methods.reset({
      name: '',
      ip: '',
      type: 'cisco_ios',
      platform: '',
      location: '',
      notes: '',
    })
    setLocalError(null)
    setDeviceData(null)
  }

  return (
    <Paper
      sx={{
        p: 4,
        height: '100%',
        bgcolor: '#0d121f',
        border: '1px solid rgba(52, 211, 153, 0.1)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 装饰性背景 */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          opacity: 0.02,
          backgroundImage: `
            linear-gradient(90deg, transparent 50%, rgba(52, 211, 153, 0.3) 50%),
            linear-gradient(rgba(52, 211, 153, 0.3) 1px, transparent 1px)
          `,
          backgroundSize: '300% 100%, 50px 50px',
          maskImage: 'linear-gradient(to bottom, transparent, 10%, black, transparent)',
        }}
      />

      {/* 装饰性边框 */}
      <Box
        sx={{
          position: 'absolute',
          top: 12,
          left: 12,
          right: 12,
          bottom: 12,
          border: '1px solid rgba(52, 211, 153, 0.15)',
          pointerEvents: 'none',
        }}
      />

      {/* 顶部标题栏 */}
      <Box sx={{ mb: 3, position: 'relative', zIndex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: 'rgba(52, 211, 153, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Storage sx={{ color: '#34d399', fontSize: 24 }} />
          </Box>
          <Box>
            <Typography variant="h5" sx={{ color: '#fff', fontWeight: 700 }}>
              {deviceName ? 'Edit Device' : 'Add New Device'}
            </Typography>
            <Typography variant="subtitle2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' }}>
              {deviceName ? 'Update Device Configuration' : 'Enter device information to add a new device'}
            </Typography>
          </Box>
        </Box>
      </Box>

      {localError && (
        <Alert severity="error" sx={{ mb: 2, bgcolor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
          {localError}
        </Alert>
      )}

      <Box component="form" onSubmit={methods.handleSubmit(handleSubmit)} noValidate>
        <Grid container spacing={3}>
          {/* 设备名称 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="name"
              control={methods.control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Device Name"
                  required
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem', color: '#64748b' }}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">
                  Device identifier for referencing in the system
                </Typography>
                <Typography variant="caption" color="error.main">
                  Letters, numbers, underscores, and hyphens only
                </Typography>
              </Stack>
            </FormHelperText>
          </Grid>

          {/* IP 地址 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="ip"
              control={methods.control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="IP Address"
                  required
                  placeholder="e.g., 192.168.1.1"
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem', color: '#64748b' }}>
              Management IP address of the device
            </FormHelperText>
          </Grid>

          {/* 设备类型 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="type"
              control={methods.control}
              render={({ field }) => (
                <FormControl fullWidth required sx={{ mt: 0.5 }}>
                  <InputLabel sx={{ color: '#94a3b8', fontWeight: 600 }}>Device Type</InputLabel>
                  <Select {...field} label="Device Type" sx={{ bgcolor: '#0d121f' }}>
                    {deviceTypes.map((type) => (
                      <MenuItem key={type.value} value={type.value} sx={{ bgcolor: '#0d121f' }}>
                        {type.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            />
          </Grid>

          {/* 平台类型 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="platform"
              control={methods.control}
              render={({ field }) => (
                <FormControl fullWidth sx={{ mt: 0.5 }}>
                  <InputLabel sx={{ color: '#94a3b8', fontWeight: 600 }}>Platform Type</InputLabel>
                  <Select {...field} label="Platform Type" value={field.value || ''} sx={{ bgcolor: '#0d121f' }}>
                    <MenuItem value="" sx={{ bgcolor: '#0d121f' }}>None</MenuItem>
                    {platformTypes.map((platform) => (
                      <MenuItem key={platform.value} value={platform.value} sx={{ bgcolor: '#0d121f' }}>
                        {platform.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            />
          </Grid>

          {/* 位置 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="location"
              control={methods.control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Location"
                  placeholder="e.g., Data Center A"
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem', color: '#64748b' }}>
              Physical location description
            </FormHelperText>
          </Grid>

          {/* 备注 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="notes"
              control={methods.control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Notes"
                  multiline
                  rows={2}
                  placeholder="Device information, configuration notes, etc."
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem', color: '#64748b' }}>
              Additional device information
            </FormHelperText>
          </Grid>
        </Grid>

      {/* 底部操作按钮 */}
      <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2, position: 'relative', zIndex: 1 }}>
        <Button
          variant="outlined"
          onClick={onCancel}
          sx={{
            textTransform: 'none',
            fontWeight: 600,
            letterSpacing: '0.025em',
            border: '1px solid rgba(148, 163, 184, 0.3)',
            color: '#94a3b8',
            bgcolor: 'rgba(148, 163, 184, 0.05)',
            '&:hover': {
              bgcolor: 'rgba(148, 163, 184, 0.15)',
              borderColor: '#94a3b8',
            },
          }}
        >
          <RefreshIcon sx={{ mr: 1, fontSize: 18 }} />
          Cancel
        </Button>
        <Button
          variant="contained"
          type="submit"
          disabled={loading}
          sx={{
            fontWeight: 700,
            letterSpacing: '0.025em',
            textTransform: 'uppercase',
            bgcolor: '#2563eb',
            color: '#fff',
            '&:hover': {
              bgcolor: '#3b82f6',
              boxShadow: '0 0 20px rgba(37, 99, 235, 0.4)',
            },
            '&:disabled': {
              bgcolor: '#1e40af',
            },
          }}
        >
          {loading ? (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CircularProgress size={20} sx={{ mr: 1, color: '#fff' }} />
              <Typography variant="body2" color="inherit">Saving...</Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <SaveIcon sx={{ mr: 1, fontSize: 18 }} />
              Save Device
            </Box>
          )}
        </Button>
      </Box>
      </Box>
    </Paper>
  )
}

export default DeviceForm
