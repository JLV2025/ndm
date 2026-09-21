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
  listOffline: (days = 30) => apiJson.get('/devices/offline', { params: { days } }),
  deleteOffline: (serial: string) => apiJson.delete(`/devices/offline/${encodeURIComponent(serial)}`),
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

}

// 数据文件
export const dataApi = {
  getFile: (deviceName: string, week: string, filename: string) =>
    apiJson.get(`/data/${deviceName}/${week}/${filename}`),
  getFilesList: (deviceName: string, week: string) =>
    apiJson.get(`/data/${deviceName}/${week}/files`),
  getDeviceWeeks: (deviceName: string) =>
    apiJson.get(`/data/${deviceName}/weeks`),
  getCollection: (deviceName: string, week: string) =>
    apiJson.get(`/data/${deviceName}/${week}/collection`),
  getRawData: (deviceName: string, week: string, dataType: string) =>
    apiJson.get(`/data/${deviceName}/${week}/raw/${dataType}`),
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

  getLocationStp: (location: string): Promise<import('../types/topology').StpTopologyData> =>
    apiJson.get(`/topology/location/${encodeURIComponent(location)}/stp`).then(res => res.data),

  /** Visio 导出 — 发送拓扑数据，返回 .vsdx 文件 Blob */
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

// 告警
export const alertsApi = {
  list: (params?: Record<string, string | number | boolean>) =>
    apiJson.get('/alerts', { params }),
  summary: () => apiJson.get('/alerts/summary'),
  markRead: (id: number) => apiJson.put(`/alerts/${id}/read`),
  resolve: (id: number) => apiJson.put(`/alerts/${id}/resolve`),
  // 全部清除：过滤参数与 list 一致（页面上看到什么就清除什么）
  resolveAll: (params?: Record<string, string | number | boolean>) =>
    apiJson.put('/alerts/resolve-all', null, { params }),
  getSuggestion: (id: number) => apiJson.get(`/alerts/${id}/suggestion`),
}

// 报告
export const reportsApi = {
  softwareVersions: (params?: { device_type?: string; location?: string }) =>
    apiJson.get('/reports/software-versions', { params }),
  portTrend: (deviceName: string, portName: string, weeks = 8) =>
    apiJson.get('/reports/port-trend', { params: { device_name: deviceName, port_name: portName, weeks } }),
  bandwidthSummary: (params?: { location?: string }) =>
    apiJson.get('/reports/bandwidth-summary', { params }),
}


// 日志分析
export const logApi = {
  getTree: (params?: { week?: string }) =>
    apiJson.get('/logs/tree', { params }),
  getLogs: (deviceName: string, params?: { week?: string; severity?: string; limit?: number }) =>
    apiJson.get(`/logs/${deviceName}`, { params }),
  analyze: (logIds: number[], deviceName: string) =>
    apiJson.post('/logs/analyze', { log_ids: logIds, device_name: deviceName }),
  history: (limit?: number) =>
    apiJson.get('/logs/analysis-history', { params: { limit } }),
}

// LLM 配置
export const llmApi = {
  getSettings: () => apiJson.get('/settings/llm'),
  saveSettings: (data: { timeout: number; providers: any[] }) =>
    apiJson.put('/settings/llm', data),
}

// 配置审计（规则库 / 单台审计 / 全量入库 / 规则编辑）
export const auditApi = {
  /** 规则库概览（含已停用规则——标准页要能重新启用） */
  ruleset: (): Promise<import('../types').AuditRuleset> =>
    apiJson.get('/audit/ruleset').then(res => res.data),

  /**
   * 单台设备的即时审计（不落库）。
   * 返回体里带**配置原文**——面板必须渲染这一份：标红只认行号，
   * 而行号只对同一份文本有意义（磁盘上的 .raw 是 CRLF，与库里全文行号对不上）。
   */
  device: (name: string): Promise<import('../types').AuditEnvelope> =>
    apiJson.get(`/audit/device/${encodeURIComponent(name)}`).then(res => res.data),

  /** 导出报告（服务端渲染，前端不拼） */
  exportReport: async (name: string, format: 'md' | 'json' = 'md'): Promise<Blob> => {
    const res = await fetch(
      apiUrl(`/audit/device/${encodeURIComponent(name)}/export?format=${format}`),
      { credentials: 'include' })
    if (!res.ok) throw new Error(`导出失败 (${res.status})`)
    return res.blob()
  },

  /** 全网审计并入库（实测 36 台约 0.9 秒，同步返回） */
  run: (trigger: 'manual' | 'scheduled' | 'post_collect' = 'manual') =>
    apiJson.post('/audit/run', null, { params: { trigger } }).then(res => res.data),

  runs: (limit = 20) => apiJson.get('/audit/runs', { params: { limit } }).then(res => res.data),
  runDetail: (id: number, params?: { level?: string; device?: string; rule?: string }) =>
    apiJson.get(`/audit/runs/${id}`, { params }).then(res => res.data),

  /** 按发现看设备：某次运行按规则聚合（命中台数 + 设备名单，按台数降序） */
  byRule: (id: number): Promise<import('../types').AuditByRule> =>
    apiJson.get(`/audit/runs/${id}/by-rule`).then(res => res.data),

  /**
   * 编辑一条规则并写回来源文件（保留注释）。
   * 传 base_hash 做乐观锁；停用规则必须带 superseded_by 或 disabled_reason。
   */
  updateRule: (ruleId: string, patch: Record<string, unknown>) =>
    apiJson.put(`/audit/standards/rule/${encodeURIComponent(ruleId)}`, patch).then(res => res.data),

  // ---- 例外登记（已批准的偏离） ----

  /** 例外登记表（含推导状态、规则标题、剩余天数）。state: active/expiring/expired/revoked */
  exceptions: (state?: string): Promise<import('../types').AuditExceptionsResponse> =>
    apiJson.get('/audit/exceptions', { params: state ? { state } : undefined }).then(res => res.data),

  /** 登记一条例外（到期日缺省 = 批准日 + 180 天）；传 base_hash 做乐观锁 */
  createException: (body: Record<string, unknown>) =>
    apiJson.post('/audit/exceptions', body).then(res => res.data),

  /** 续期 / 改理由（改 scope/rule_id 等于换一条，须撤销后重登记） */
  updateException: (id: string, patch: Record<string, unknown>) =>
    apiJson.put(`/audit/exceptions/${encodeURIComponent(id)}`, patch).then(res => res.data),

  /** 撤销（软删除：写 revoked 块，历史审计可追溯） */
  revokeException: (id: string, body: { by: string; reason: string; base_hash?: string }) =>
    apiJson.post(`/audit/exceptions/${encodeURIComponent(id)}/revoke`, body).then(res => res.data),

  // ---- 趋势与历史 ----

  /** 趋势序列：每周取该周最后一次运行（本周无运行则该周不出现） */
  trends: (weeks = 26, site?: string): Promise<import('../types').AuditTrends> =>
    apiJson.get('/audit/trends', { params: { weeks, site: site || undefined } }).then(res => res.data),

  /** 收敛/恶化榜：缺省对比最新周与上一周（数据不足时返回 reason） */
  trendDiff: (fromRun?: number, toRun?: number): Promise<import('../types').AuditTrendDiff> =>
    apiJson.get('/audit/trends/diff', {
      params: { from_run: fromRun, to_run: toRun },
    }).then(res => res.data),

  /** AI 单台专家简报（把该设备的确定性结论讲成人话；不落库） */
  briefingDevice: (name: string): Promise<import('../types').AuditBriefing> =>
    apiJson.post(`/audit/device/${encodeURIComponent(name)}/briefing`).then(res => res.data),

  /** AI 全网简报；缺省用最新一次运行 */
  briefingNetwork: (runId?: number): Promise<import('../types').AuditBriefing> =>
    apiJson.post('/audit/briefing', null, { params: { run_id: runId } }).then(res => res.data),
}

// 设备生命周期（EoL / 保修期）—— 手工登记为主，Cisco EoX 可自动刷新
export const lifecycleApi = {
  device: (name: string): Promise<import('../types').DeviceLifecycle> =>
    apiJson.get(`/lifecycle/device/${encodeURIComponent(name)}`).then(res => res.data),

  /** 逐序列号保存保修期（source=manual + 核实人） */
  saveDevice: (name: string, rows: { serial: string; warranty_end: string; note?: string }[],
               verifiedBy: string) =>
    apiJson.put(`/lifecycle/device/${encodeURIComponent(name)}`,
      { rows, verified_by: verifiedBy }).then(res => res.data),

  /** 批量粘贴导入：每行 `序列号,到期日[,备注]`；未匹配的原样回显 */
  importText: (text: string, verifiedBy: string): Promise<import('../types').LifecycleImportResult> =>
    apiJson.post('/lifecycle/import', { text, verified_by: verifiedBy }).then(res => res.data),

  /** 手工登记型号 EoL（覆盖已有记录） */
  saveModel: (model: string, patch: Record<string, unknown>) =>
    apiJson.put(`/lifecycle/model/${encodeURIComponent(model)}`, patch).then(res => res.data),

  /** 按型号刷新 Cisco EoX（未配凭据 → 400 + 可读原因） */
  refresh: (force = false) =>
    apiJson.post('/lifecycle/refresh', null, { params: { force } }).then(res => res.data),

  overview: (): Promise<{ devices: import('../types').LifecycleOverviewRow[]; refresh: import('../types').LifecycleRefreshStatus }> =>
    apiJson.get('/lifecycle/overview').then(res => res.data),
}

export default apiJson
