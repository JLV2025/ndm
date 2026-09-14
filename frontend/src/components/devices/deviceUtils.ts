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

/**
 * 解析堆叠成员编号后缀（每成员一个后缀，与序列号同序）
 *
 * member_ids 与 serial_number 同序 1:1；仅当两者数量一致且成员 ID 全为数字时
 * 才采用真实 Member ID，否则回退为按序号编号。
 * 真实 ID 不补零（-1/-3 原样，跳号也正确）；回退编号按 padWidth 补零。
 *
 * @param serialNumber 逗号分隔的序列号串
 * @param memberIds    逗号分隔的 VSF 成员 ID 串（非堆叠/未采集时为空）
 * @param padWidth     回退编号的补零宽度
 */
export function memberSuffixes(serialNumber: string, memberIds: string, padWidth: number): string[] {
  const snList = (serialNumber || '').split(',').map(s => s.trim()).filter(Boolean)
  const midList = (memberIds || '').split(',').map(m => m.trim()).filter(Boolean)
  const useRealIds = midList.length === snList.length && midList.every(v => /^\d+$/.test(v))
  return snList.map((_, i) => useRealIds ? midList[i] : String(i + 1).padStart(padWidth, '0'))
}
