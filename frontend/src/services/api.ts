import axios from 'axios'
import type { Device } from '../types'

const API_BASE = import.meta.env.PROD ? 'http://localhost:8002/api' : '/api'

// fetch 用绝对路径（preview 模式不代理）
const apiUrl = (path: string) => `${API_BASE}${path}`

// 创建 JSON 实例
const apiJson = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 设备管理
export const deviceApi = {
  list: () => apiJson.get('/devices/'),
  get: (name: string) => apiJson.get(`/devices/${name}`),
  add: (device: Device) => apiJson.post('/devices/', device),
  delete: (name: string) => apiJson.delete(`/devices/${name}`),
  update: (name: string, updates: Partial<Device>) => apiJson.patch(`/devices/${name}`, updates),
  search: (params: Record<string, string>) => apiJson.get('/devices/search', { params }),
  batchImport: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiJson.post('/devices/batch-import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    })
  },
  downloadTemplate: async () => {
    const res = await fetch(apiUrl('/devices/batch-import/template'), { credentials: 'include' })
    if (!res.ok) throw new Error('下载模板失败')
    return res.blob()
  },
}

// 配置收集 — 使用 FormData 发送凭据（需时较长，可能 10-30 秒）
export const collectorApi = {
  // Ping 设备检查可达性
  ping: async (deviceName: string, signal?: AbortSignal) => {
    const res = await fetch(apiUrl(`/collect/ping/${deviceName}`), { method: 'POST', signal, credentials: 'include' })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Ping 失败 (${res.status})`)
    }
    return res.json() as Promise<{ reachable: boolean; ip: string; detail: string }>
  },

  // 收集设备配置
  collect: async (deviceName: string, username: string, password: string) => {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    const res = await fetch(apiUrl(`/collect/${deviceName}`), {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })
    const data = await res.json()
    // 后端返回 success: false 表示收集失败
    if (!data.success) {
      throw new Error(data.detail || `收集失败 (${data.error || '未知错误'})`)
    }
    return data
  },

  // 批量收集设备配置
  batchCollect: async (deviceNames: string[], username: string, password: string) => {
    const res = await fetch(apiUrl('/collect/batch'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ devices: deviceNames, username, password }),
      credentials: 'include',
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `批量收集失败 (${res.status})`)
    }
    return res.json()
  },
}

// 数据文件
export const dataApi = {
  getFile: (deviceName: string, week: string, filename: string) =>
    apiJson.get(`/data/${deviceName}/${week}/${filename}`),
  getFilesList: (deviceName: string, week: string) =>
    apiJson.get(`/data/${deviceName}/${week}/files`),
  getDeviceWeeks: (deviceName: string) =>
    apiJson.get(`/data/${deviceName}/weeks`),
}

// 认证 - 使用 fetch 发送 FormData
export const authApi = {
  login: (username: string, password: string) => {
    const params = new URLSearchParams({ username, password })
    return fetch(apiUrl('/auth/login'), {
      method: 'POST',
      body: params,
      credentials: 'include',
    }).then(res => res.json())
  },
  logout: () => fetch(apiUrl('/auth/logout'), { method: 'POST', credentials: 'include' }).then(res => res.json()),
}

// 拓扑图
export const topologyApi = {
  getTopology: (deviceName: string): Promise<{ device_name: string; neighbors: any[]; endpoints: any[]; network_devices: any[]; stack_members?: string[]; member_neighbors?: Record<string, any[]> }> =>
    apiJson.get(`/topology/${encodeURIComponent(deviceName)}`).then(res => res.data),

  getLocationTopology: (location: string): Promise<import('../types/topology').LocationTopologyData> =>
    apiJson.get(`/topology/location/${encodeURIComponent(location)}`).then(res => res.data),

  /** Visio 导出 — 发送拓扑数据，返回 .vdx 文件 Blob */
  exportVisio: async (data: any): Promise<Blob> => {
    const res = await fetch(apiUrl('/topology/export/visio'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      credentials: 'include',
    })
    if (!res.ok) throw new Error('Visio export failed')
    return res.blob()
  },
}

export default apiJson
