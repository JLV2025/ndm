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
import { useI18n } from '../i18n'

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
  uplink_ports: z.string().max(200, 'Uplink ports cannot exceed 200 characters').optional().nullable(),
})

export type DeviceFormValues = z.infer<typeof deviceSchema>

// 设备类型选项
const deviceTypes = [
  { value: 'aruba_aoscx', label: 'Aruba CX' },
  { value: 'cisco_ios', label: 'Cisco IOS' },
  { value: 'cisco_ios_router', label: 'Cisco IOS Router' },
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
  cisco_ios_router: [
    { value: 'cisco_ios_router', label: 'Cisco IOS Router' },
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
  const { t } = useI18n()
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
      uplink_ports: '',
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
        uplink_ports: Array.isArray(data.uplink_ports) ? data.uplink_ports.join(', ') : (data.uplink_ports || ''),
      })
    } catch (error: unknown) {
      console.error('Load device details failed:', error instanceof Error ? error.message : error)
      setLocalError(error instanceof Error ? error.message : t('form.loadFailed'))
    }
  }

  // 提交处理
  const handleSubmit: SubmitHandler<DeviceFormValues> = async (data) => {
    try {
      // 将 null 转为 undefined 以匹配 Device 接口类型
      // uplink_ports: 逗号分隔字符串 → string[]
      const uplinkArray = data.uplink_ports
        ? data.uplink_ports.split(/[,，]/).map(s => s.trim()).filter(Boolean)
        : undefined
      const payload = {
        ...data,
        platform: data.platform ?? undefined,
        location: data.location ?? undefined,
        notes: data.notes ?? undefined,
        uplink_ports: uplinkArray,
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
      setLocalError(error instanceof Error ? error.message : t('form.saveFailed'))
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
      uplink_ports: '',
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
              {deviceName ? t('form.editTitle') : t('form.addTitle')}
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              {deviceName ? t('form.editSubtitle') : t('form.addSubtitle')}
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
                  label={t('form.name')}
                  required
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">
                  {t('form.nameHelp')}
                </Typography>
                <Typography variant="caption" color="error.main">
                  {t('form.nameRule')}
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
                  label={t('form.ip')}
                  required
                  placeholder="e.g., 192.168.1.1"
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
              {t('form.ipHelp')}
            </FormHelperText>
          </Grid>

          {/* 设备类型 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="type"
              control={methods.control}
              render={({ field }) => (
                <FormControl fullWidth required sx={{ mt: 0.5 }}>
                  <InputLabel>{t('form.type')}</InputLabel>
                  <Select {...field} label={t('form.type')}>
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
                  <InputLabel>{t('form.platform')}</InputLabel>
                  <Select {...field} label={t('form.platform')} value={field.value || ''}>
                    <MenuItem value="">{t('form.none')}</MenuItem>
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
                  label={t('form.location')}
                  placeholder="e.g., Data Center A"
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
              {t('form.locationHelp')}
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
                  label={t('form.notes')}
                  multiline
                  rows={2}
                  placeholder="Device information, configuration notes, etc."
                  sx={{ mt: 0.5 }}
                />
              )}
            />
            <FormHelperText sx={{ mt: 0.5, fontSize: '0.7rem' }}>
              {t('form.notesHelp')}
            </FormHelperText>
          </Grid>

          {/* 上联端口 */}
          <Grid item xs={12} md={6}>
            <Controller
              name="uplink_ports"
              control={methods.control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t('form.uplinkPorts')}
                  placeholder="e.g., 1/1/49, 1/1/50, lag1"
                  helperText={t('form.uplinkHint')}
                  sx={{ mt: 0.5 }}
                  InputLabelProps={{ shrink: true }}
                />
              )}
            />
          </Grid>
        </Grid>

      {/* 底部操作按钮 */}
      <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button
          variant="outlined"
          onClick={onCancel}
          startIcon={<RefreshIcon />}
        >
          {t('form.cancel')}
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
              {t('form.saving')}
            </Box>
          ) : (
            t('form.save')
          )}
        </Button>
      </Box>
      </Box>
    </Paper>
  )
}

export default DeviceForm
