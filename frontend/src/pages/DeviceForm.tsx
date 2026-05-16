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
  { value: 'aruba_aoscx', label: 'Aruba CX' },
  { value: 'cisco_ios', label: 'Cisco IOS' },
]

// 平台类型选项（按设备类型分组，动态联动）
const platformOptionsMap: Record<string, { value: string; label: string }[]> = {
  aruba_aoscx: [
    { value: 'aruba_aoscx', label: 'Aruba AOS-CX' },
  ],
  cisco_ios: [
    { value: 'cisco_ios', label: 'Cisco IOS' },
    { value: 'cisco_ios_xe', label: 'Cisco IOS XE' },
  ],
}

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
      type: 'aruba_aoscx',
      platform: null,
      location: null,
      notes: null,
    },
  })

  const selectedType = methods.watch('type')

  // 设备类型变更时，重置平台选项
  useEffect(() => {
    methods.setValue('platform', null)
  }, [selectedType])

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
    } catch (error: unknown) {
      console.error('Load device details failed:', error instanceof Error ? error.message : error)
      setLocalError(error instanceof Error ? error.message : 'Failed to load device information')
    }
  }

  // 提交处理
  const handleSubmit: SubmitHandler<DeviceFormValues> = async (data) => {
    try {
      // 将 null 转为 undefined 以匹配 Device 接口类型
      const payload = {
        ...data,
        platform: data.platform ?? undefined,
        location: data.location ?? undefined,
        notes: data.notes ?? undefined,
      }
      // 使用 deviceData 判断是编辑还是添加
      if (deviceData && deviceData.name) {
        // Update existing device
        await deviceApi.update(deviceData.name, payload)
      } else {
        // Add new device
        await deviceApi.add(payload)
      }
      onSubmit(data)
      handleReset()
    } catch (error: unknown) {
      console.error('Save device failed:', error instanceof Error ? error.message : error)
      setLocalError(error instanceof Error ? error.message : 'Failed to save device information')
    }
  }

  // 重置表单
  const handleReset = () => {
    methods.reset({
      name: '',
      ip: '',
      type: 'aruba_aoscx',
      platform: '',
      location: '',
      notes: '',
    })
    setLocalError(null)
    setDeviceData(null)
  }

  return (
    <Paper sx={{ p: 4, height: '100%' }}>
      {/* 顶部标题栏 */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 1.5,
              bgcolor: 'rgba(34, 197, 94, 0.1)',
              border: '1px solid',
              borderColor: 'rgba(34, 197, 94, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Storage sx={{ color: 'primary.main', fontSize: 24 }} />
          </Box>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>
              {deviceName ? 'Edit Device' : 'Add New Device'}
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              {deviceName ? 'Update Device Configuration' : 'Enter device information to add a new device'}
            </Typography>
          </Box>
        </Box>
      </Box>

      {localError && (
        <Alert severity="error" sx={{ mb: 2 }}>
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
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
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
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
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
                  <InputLabel>Device Type</InputLabel>
                  <Select {...field} label="Device Type">
                    {deviceTypes.map((type) => (
                      <MenuItem key={type.value} value={type.value}>
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
                  <InputLabel>Platform Type</InputLabel>
                  <Select {...field} label="Platform Type" value={field.value || ''}>
                    <MenuItem value="">None</MenuItem>
                    {(platformOptionsMap[selectedType] || []).map((platform) => (
                      <MenuItem key={platform.value} value={platform.value}>
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
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
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
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
              Additional device information
            </FormHelperText>
          </Grid>
        </Grid>

      {/* 底部操作按钮 */}
      <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button
          variant="outlined"
          onClick={onCancel}
          startIcon={<RefreshIcon />}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          type="submit"
          disabled={loading}
          startIcon={loading ? undefined : <SaveIcon />}
        >
          {loading ? (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CircularProgress size={20} sx={{ mr: 1, color: 'primary.contrastText' }} />
              Saving...
            </Box>
          ) : (
            'Save Device'
          )}
        </Button>
      </Box>
      </Box>
    </Paper>
  )
}

export default DeviceForm
