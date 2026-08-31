import type { Device, PhysicalDevice } from '../../types'

export function getDeviceColor(type: string) {
  if (type === 'cisco_ios') return {
    primary: '#3B82F6',
    secondary: 'rgba(59, 130, 246, 0.1)',
    border: 'rgba(59, 130, 246, 0.2)',
  }
  if (type === 'aruba_aoscx') return {
    primary: '#06B6D4',
    secondary: 'rgba(6, 182, 212, 0.1)',
    border: 'rgba(6, 182, 212, 0.2)',
  }
  return {
    primary: '#94A3B8',
    secondary: 'rgba(148, 163, 184, 0.08)',
    border: 'rgba(148, 163, 184, 0.15)',
  }
}

export function getTypeLabel(type: string, t: (key: string) => string) {
  if (type === 'cisco_ios') return t('dashboard.cisco')
  if (type === 'aruba_aoscx') return t('dashboard.aruba')
  return type
}

/** 判断设备是否为堆叠设备 */
export function isStackedDevice(device: Device): boolean {
  const sn = (device.serial_number || '').trim()
  return sn.includes(',') && sn !== '未知'
}

/**
 * 将逻辑设备列表展开为物理设备列表
 * 堆叠设备（serial_number 含逗号）按逗号拆分为多个物理设备
 */
export function expandStackedDevices(devices: Device[]): PhysicalDevice[] {
  const result: PhysicalDevice[] = []
  for (const dev of devices) {
    const sn = (dev.serial_number || '').trim()
    if (!sn || sn === '未知' || !sn.includes(',')) {
      result.push({
        name: dev.name,
        logical_name: dev.name,
        ip: dev.ip,
        type: dev.type,
        platform: dev.platform,
        location: dev.location,
        notes: dev.notes,
        serial_number: dev.serial_number,
        model: dev.model,
        version: dev.version,
        last_synced: dev.last_synced,
        physical_index: 1,
        physical_count: 1,
      })
      continue
    }

    const snList = sn.split(',').map(s => s.trim()).filter(Boolean)
    const modelStr = (dev.model || '').trim()
    const modelList = modelStr ? modelStr.split(',').map(m => m.trim()) : []
    const verStr = (dev.version || '').trim()
    const verList = verStr ? verStr.split(',').map(v => v.trim()) : []
    // 真实成员 ID（member_ids 与序列号同序 1:1，全数字才采用；否则回退序号）
    const midStr = (dev.member_ids || '').trim()
    const midList = midStr ? midStr.split(',').map(m => m.trim()).filter(Boolean) : []
    const useRealIds = midList.length === snList.length && midList.every(v => /^\d+$/.test(v))

    for (let i = 0; i < snList.length; i++) {
      result.push({
        name: `${dev.name}-${useRealIds ? midList[i] : String(i + 1).padStart(2, '0')}`,
        logical_name: dev.name,
        ip: dev.ip,
        type: dev.type,
        platform: dev.platform,
        location: dev.location,
        notes: dev.notes,
        serial_number: snList[i],
        model: modelList[i] || '',
        version: verList[i] || '',
        last_synced: dev.last_synced,
        physical_index: i + 1,
        physical_count: snList.length,
      })
    }
  }
  return result
}
