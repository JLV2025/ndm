import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  Dialog,
  LinearProgress,
  Alert,
} from '@mui/material'
import { Add, Storage, NetworkWifi, CloudUpload } from '@mui/icons-material'
import { deviceApi, collectorApi } from '../services/api'
import { sessionManager } from '../services/auth'
import DeviceForm from './DeviceForm'
import type { Device, BatchItemStatus, CollectResult } from '../types'
import { useI18n } from '../i18n'
import LocationFilter from '../components/devices/LocationFilter'
import CollectionProgress from '../components/devices/CollectionProgress'
import BatchCollectionPanel from '../components/devices/BatchCollectionPanel'
import DeviceCardGrid from '../components/devices/DeviceCardGrid'
import DeviceTable from '../components/devices/DeviceTable'
import CollectResultDialog from '../components/devices/CollectResultDialog'
import DeleteConfirmDialog from '../components/devices/DeleteConfirmDialog'
import ImportDialog from '../components/devices/ImportDialog'

const DeviceList: React.FC = () => {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [openDialog, setOpenDialog] = useState(false)
  const [openEditDialog, setOpenEditDialog] = useState(false)
  const [editingDevice, setEditingDevice] = useState<string | null>(null)
  const [openConfirm, setOpenConfirm] = useState(false)
  const [openCollect, setOpenCollect] = useState(false)
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [collecting, setCollecting] = useState(false)
  const [collectError, setCollectError] = useState('')
  const [collectResult, setCollectResult] = useState<CollectResult | null>(null)
  const [collectPhase, setCollectPhase] = useState<'ping' | 'collect' | null>(null)
  const [collectKey, setCollectKey] = useState(0)
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set())
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchStatus, setBatchStatus] = useState<Record<string, BatchItemStatus>>({})
  const [sortField, setSortField] = useState<string>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [openImport, setOpenImport] = useState(false)

  useEffect(() => {
    loadDevices()
  }, [])

  // 位置切换时清除所有选中状态和批量结果，避免跨 location 的数据污染
  useEffect(() => {
    setSelectedDevices(new Set())
    setBatchStatus({})
    setBatchRunning(false)
  }, [selectedLocation])

  const loadDevices = async () => {
    try {
      const response = await deviceApi.list()
      setDevices(response.data)
    } catch (error: unknown) {
      console.error('加载设备失败:', error instanceof Error ? error.message : error)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenDialog = () => setOpenDialog(true)
  const handleCloseDialog = () => setOpenDialog(false)

  const handleSaveDevice = async () => {
    handleCloseDialog()
    await loadDevices()
  }

  const handleEdit = (device: Device) => {
    setEditingDevice(device.name)
    setOpenEditDialog(true)
  }

  const handleCloseEditDialog = () => {
    setOpenEditDialog(false)
    setEditingDevice(null)
  }

  const handleSaveEdit = async () => {
    handleCloseEditDialog()
    await loadDevices()
  }

  const handleDelete = (device: Device) => {
    setSelectedDevice(device)
    setOpenConfirm(true)
  }

  const handleConfirmDelete = async () => {
    try {
      if (!selectedDevice) return
      await deviceApi.delete(selectedDevice.name)
      loadDevices()
      setOpenConfirm(false)
    } catch (error: unknown) {
      alert(error instanceof Error ? error.message : t('common.deleteFailed'))
    }
  }

  const handleCollect = async (device: Device) => {
    const session = sessionManager.getSession()
    if (!session) {
      alert(t('common.pleaseLogin'))
      navigate('/login')
      return
    }

    setSelectedDevice(device)
    setCollecting(true)
    setCollectPhase('collect')
    setCollectError('')
    setCollectKey(k => k + 1)

    try {
      // Ping 预检：不可达设备提前拒绝，避免等待 SSH 超时
      const pingResult = await collectorApi.ping(device.name)
      if (!pingResult.reachable) {
        setCollectError(pingResult.detail || t('devices.pinging'))
        return
      }

      const data = await collectorApi.collect(device.name, session.username, session.password)
      setCollectResult(data.result)
      setOpenCollect(true)
      await loadDevices()
    } catch (error: unknown) {
      setCollectError(error instanceof Error ? error.message : t('common.collectFailed'))
    } finally {
      setCollecting(false)
      setCollectPhase(null)
    }
  }

  const handleSelectAll = (checked: boolean) => {
    const visibleNames = sortedDevices.map((d) => d.name)
    const next = new Set(selectedDevices)
    if (checked) {
      visibleNames.forEach((n) => next.add(n))
    } else {
      visibleNames.forEach((n) => next.delete(n))
    }
    setSelectedDevices(next)
  }

  const handleSelectOne = (name: string, checked: boolean) => {
    const next = new Set(selectedDevices)
    if (checked) {
      next.add(name)
    } else {
      next.delete(name)
    }
    setSelectedDevices(next)
  }

  const handleBatchCollect = async () => {
    const session = sessionManager.getSession()
    if (!session) { alert(t('common.pleaseLogin')); navigate('/login'); return }

    const deviceNames = Array.from(selectedDevices)
    if (deviceNames.length === 0) { alert(t('common.pleaseSelectDevice')); return }

    setBatchRunning(true)

    const initial: Record<string, BatchItemStatus> = {}
    deviceNames.forEach((n) => { initial[n] = { status: 'pending' } })
    setBatchStatus(initial)

    const queue = [...deviceNames]
    const maxConcurrent = 3

    /** 单个设备的完整收集流程（Ping → Collect） */
    const worker = async (deviceName: string) => {
      // Ping 预检
      setBatchStatus(prev => ({ ...prev, [deviceName]: { ...prev[deviceName], status: 'pinging' } }))
      try {
        const pingResult = await collectorApi.ping(deviceName)
        if (!pingResult.reachable) {
          setBatchStatus(prev => ({
            ...prev,
            [deviceName]: { status: 'failed', error: pingResult.detail },
          }))
          return
        }
      } catch {
        setBatchStatus(prev => ({
          ...prev,
          [deviceName]: { status: 'failed', error: t('devices.pinging') },
        }))
        return
      }

      // SSH 收集
      setBatchStatus(prev => ({ ...prev, [deviceName]: { ...prev[deviceName], status: 'collecting' } }))
      try {
        const data = await collectorApi.collect(deviceName, session.username, session.password)
        setBatchStatus(prev => ({
          ...prev,
          [deviceName]: { status: 'success', result: data.result },
        }))
      } catch (error: unknown) {
        const errMsg = error instanceof Error ? error.message : t('common.collectFailed')
        setBatchStatus(prev => ({
          ...prev,
          [deviceName]: { status: 'failed', error: errMsg },
        }))
      }
    }

    /** 从队列取一个设备执行，完成后递归取下一个 */
    const runNext = async (): Promise<void> => {
      const next = queue.shift()
      if (!next) return
      await worker(next)
      await runNext()
    }

    // 启动初始并发 workers（最多 maxConcurrent 个）
    const workers: Promise<void>[] = []
    const numWorkers = Math.min(maxConcurrent, queue.length)
    for (let i = 0; i < numWorkers; i++) {
      workers.push(runNext())
    }
    await Promise.all(workers)
    setBatchRunning(false)
    loadDevices()
  }

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const sortStyle = (field: string) => ({
    cursor: 'pointer',
    userSelect: 'none',
    '&:hover': { color: 'primary.main' },
    color: sortField === field ? 'primary.main' : 'text.secondary',
  } as const)

  const uniqueLocations: string[] = useMemo(() => [...new Set(devices.map(d => d.location).filter((l): l is string => !!l))].sort(), [devices])

  const filteredDevices = selectedLocation
    ? devices.filter((d) => (d.location || '').toUpperCase() === selectedLocation.toUpperCase())
    : devices

  const sortedDevices = [...filteredDevices].sort((a: Device, b: Device) => {
    const va = (a[sortField] || '').toString().toLowerCase()
    const vb = (b[sortField] || '').toString().toLowerCase()
    return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
  })

  const allSelected = sortedDevices.length > 0 && sortedDevices.every((d) => selectedDevices.has(d.name))
  const someSelected = sortedDevices.some((d) => selectedDevices.has(d.name)) && !allSelected

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <LinearProgress />
      </Container>
    )
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* 顶部标题栏 + 位置筛选 */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
            {t('devices.title')}
          </Typography>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleOpenDialog}
            sx={{ px: 2, py: 0.75, fontWeight: 700, fontSize: '0.75rem', letterSpacing: '0.02em' }}
          >
            {t('devices.addDevice')}
          </Button>
          <Button
            variant="outlined"
            startIcon={<CloudUpload />}
            onClick={() => setOpenImport(true)}
            sx={{ px: 2, py: 0.75, fontWeight: 700, fontSize: '0.75rem', letterSpacing: '0.02em' }}
          >
            {t('import.title') || 'Batch Import'}
          </Button>
        </Box>
        <LocationFilter selectedLocation={selectedLocation} onChange={setSelectedLocation} locations={uniqueLocations} />
      </Paper>

      {/* 单设备收集进度 */}
      {collecting && selectedDevice && (
        <CollectionProgress
          key={collectKey}
          deviceName={selectedDevice.name}
          deviceIp={selectedDevice.ip}
          onComplete={() => {
            setCollecting(false)
            setCollectPhase(null)
          }}
          onError={(msg) => {
            setCollectError(msg)
            setCollecting(false)
            setCollectPhase(null)
          }}
        />
      )}

      {collectError && !collecting && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setCollectError('')}>
          {collectError}
        </Alert>
      )}

      {/* 批量收集进度 */}
      <BatchCollectionPanel
          running={batchRunning}
          statuses={batchStatus}
          devices={devices}
          onDeviceProgress={(name, pct, cmdDone, totalCmds) => {
            setBatchStatus(prev => {
              const cur = prev[name]
              if (!cur || cur.status === 'success' || cur.status === 'failed') return prev
              return { ...prev, [name]: { ...cur, progress: pct, cmdDone, totalCmds } }
            })
          }}
        />

      {/* 设备卡片网格 */}
      {selectedLocation && (
        <DeviceCardGrid
          devices={sortedDevices}
          selectedLocation={selectedLocation}
          collecting={collecting}
          onCollect={handleCollect}
          onEdit={handleEdit}
          onDelete={handleDelete}
        />
      )}

      {/* 空状态提示 */}
      {!selectedLocation && devices.length > 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
          <NetworkWifi sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="body1" color="text.secondary" sx={{ mb: 0.5 }}>
            {t('devices.clickLocationHint')}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {t('devices.selectLocationHint')}
          </Typography>
        </Paper>
      )}

      {devices.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
          <Box sx={{ mb: 3 }}>
            <Storage sx={{ fontSize: 56, color: 'text.disabled' }} />
          </Box>
          <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 500, mb: 1 }}>{t('devices.noDevices')}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t('devices.noDevicesHint')}</Typography>
          <Button variant="contained" startIcon={<Add />} onClick={handleOpenDialog} sx={{ px: 3, py: 1, fontWeight: 700 }}>
            Add Device
          </Button>
        </Paper>
      )}

      {/* 设备表格 */}
      <DeviceTable
        devices={sortedDevices}
        sortField={sortField}
        sortDir={sortDir}
        sortStyle={sortStyle}
        selectedDevices={selectedDevices}
        batchStatus={batchStatus}
        collecting={collecting}
        allSelected={allSelected}
        someSelected={someSelected}
        totalCount={sortedDevices.length}
        batchRunning={batchRunning}
        onSelectAll={handleSelectAll}
        onSelectOne={handleSelectOne}
        onSort={handleSort}
        onCollect={handleCollect}
        onDelete={handleDelete}
        onBatchCollect={handleBatchCollect}
      />

      {/* 添加设备对话框 */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DeviceForm deviceName={null} onSubmit={handleSaveDevice} onCancel={handleCloseDialog} loading={collecting} />
      </Dialog>

      {/* 编辑设备对话框 */}
      <Dialog open={openEditDialog} onClose={handleCloseEditDialog} maxWidth="md" fullWidth>
        <DeviceForm deviceName={editingDevice} onSubmit={handleSaveEdit} onCancel={handleCloseEditDialog} loading={collecting} />
      </Dialog>

      {/* 收集结果对话框 */}
      <CollectResultDialog
        open={openCollect}
        onClose={() => setOpenCollect(false)}
        result={collectResult}
        error={collectError}
        deviceName={selectedDevice?.name}
      />

      {/* 删除确认 */}
      <DeleteConfirmDialog
        open={openConfirm}
        deviceName={selectedDevice?.name}
        onCancel={() => setOpenConfirm(false)}
        onConfirm={handleConfirmDelete}
      />

      {/* 批量导入 */}
      <ImportDialog
        open={openImport}
        onClose={() => setOpenImport(false)}
        onImported={loadDevices}
      />
    </Container>
  )
}

export default DeviceList
