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
