interface Session {
  username: string
  password: string
  deviceIp: string
  expiresAt: number
}

const SESSION_KEY = 'ndm_session'

// 简单的前端加密/解密（基于 base64 编码，防止明文存储）
// 生产环境应使用 Web Crypto API 的 SubtleCrypto
function encode(value: string): string {
  return btoa(encodeURIComponent(value))
}

function decode(value: string): string {
  return decodeURIComponent(atob(value))
}

class SessionManager {
  private session: Session | null = null

  async login(username: string, password: string): Promise<string> {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    formData.append('device_ip', '10.210.255.1')

    const response = await fetch('/api/auth/login', {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '登录失败' }))
      throw new Error(errorData.detail || '登录失败')
    }
    const data = await response.json()
    if (!data.success) {
      throw new Error(data.detail || '登录失败')
    }

    this.session = {
      username,
      password,
      deviceIp: data.device_ip,
      expiresAt: Date.now() + 4 * 60 * 60 * 1000,
    }

    this.save()
    return data.device_ip
  }

  setCredentials(username: string, password: string): void {
    this.session = {
      username,
      password,
      deviceIp: '10.210.255.1',
      expiresAt: Date.now() + 4 * 60 * 60 * 1000,
    }
    this.save()
  }

  logout(): void {
    this.session = null
    this.clear()
  }

  getSession(): Session | null {
    if (this.session) return this.session

    const stored = sessionStorage.getItem(SESSION_KEY)
    if (!stored) return null

    try {
      const parsed = JSON.parse(stored)
      if (Date.now() > parsed.expiresAt) {
        this.clear()
        return null
      }
      // 解密密码
      this.session = {
        username: decode(parsed.username),
        password: decode(parsed.password),
        deviceIp: parsed.deviceIp,
        expiresAt: parsed.expiresAt,
      }
      return this.session
    } catch {
      this.clear()
      return null
    }
  }

  isExpired(): boolean {
    const session = this.getSession()
    if (!session) return true
    return Date.now() > session.expiresAt
  }

  clear(): void {
    sessionStorage.removeItem(SESSION_KEY)
  }

  private save(): void {
    if (this.session) {
      // 加密后存储
      const encrypted = {
        username: encode(this.session.username),
        password: encode(this.session.password),
        deviceIp: this.session.deviceIp,
        expiresAt: this.session.expiresAt,
      }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(encrypted))
    }
  }
}

export const sessionManager = new SessionManager()
