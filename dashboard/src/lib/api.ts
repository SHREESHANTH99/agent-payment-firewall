const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Simple in-memory response cache for lightning-fast tab navigation
const responseCache = new Map<string, { data: any; expiry: number }>()

function getCached<T>(key: string): T | null {
  const item = responseCache.get(key)
  if (!item) return null
  if (Date.now() > item.expiry) {
    responseCache.delete(key)
    return null
  }
  return item.data as T
}

function setCached<T>(key: string, data: T, ttlMs = 15000): void {
  responseCache.set(key, { data, expiry: Date.now() + ttlMs })
}

export function clearApiCache(prefix?: string): void {
  if (!prefix) {
    responseCache.clear()
  } else {
    Array.from(responseCache.keys()).forEach((key) => {
      if (key.startsWith(prefix)) responseCache.delete(key)
    })
  }
}

class ApiClient {
  private token: string | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = sessionStorage.getItem('apf_token')
    }
  }

  setToken(t: string | null) {
    this.token = t
    if (typeof window !== 'undefined') {
      if (t) {
        sessionStorage.setItem('apf_token', t)
      } else {
        sessionStorage.removeItem('apf_token')
      }
    }
    clearApiCache()
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = sessionStorage.getItem('apf_token')
    }
    return this.token
  }

  private headers(extra: Record<string, string> = {}): HeadersInit {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
      ...extra,
    }
    const t = this.getToken()
    if (t) {
      h['Authorization'] = `Bearer ${t}`
    }
    return h
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`
    const res = await fetch(url, {
      ...options,
      headers: this.headers(options.headers as Record<string, string> || {}),
    })

    if (res.status === 401) {
      this.setToken(null)
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      throw new Error('Unauthorized')
    }

    if (!res.ok) {
      const err = await res.text()
      throw new Error(`API error ${res.status}: ${err}`)
    }

    return res.json()
  }

  // Auth / WS Ticket
  async getWsTicket(): Promise<{ ticket: string; expires_at: string }> {
    return this.request('/ws/ticket', { method: 'POST' })
  }

  // Stats (cached with fast revalidation)
  async getStats(forceRefresh = false): Promise<any> {
    const cacheKey = 'stats'
    if (!forceRefresh) {
      const cached = getCached<any>(cacheKey)
      if (cached) return cached
    }
    const data = await this.request('/intents/stats')
    setCached(cacheKey, data, 10000)
    return data
  }

  // Intents
  async getIntents(params: Record<string, any> = {}, forceRefresh = false): Promise<any> {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') query.append(k, String(v))
    })
    const qs = query.toString() ? `?${query.toString()}` : ''
    const cacheKey = `intents:${qs}`
    if (!forceRefresh) {
      const cached = getCached<any>(cacheKey)
      if (cached) return cached
    }
    const data = await this.request(`/intents${qs}`)
    setCached(cacheKey, data, 8000)
    return data
  }

  async getIntent(id: string, forceRefresh = false): Promise<any> {
    const cacheKey = `intent:${id}`
    if (!forceRefresh) {
      const cached = getCached<any>(cacheKey)
      if (cached) return cached
    }
    const data = await this.request(`/intents/${id}`)
    setCached(cacheKey, data, 15000)
    return data
  }

  async approveIntent(id: string): Promise<any> {
    clearApiCache('intents')
    clearApiCache('stats')
    return this.request(`/intents/${id}/approve`, { method: 'POST' })
  }

  async rejectIntent(id: string, reason?: string): Promise<any> {
    clearApiCache('intents')
    clearApiCache('stats')
    return this.request(`/intents/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Rejected by operator' }),
    })
  }

  // Mandates
  async getMandates(forceRefresh = false): Promise<any[]> {
    const cacheKey = 'mandates'
    if (!forceRefresh) {
      const cached = getCached<any[]>(cacheKey)
      if (cached) return cached
    }
    const data = await this.request<any[]>('/mandates')
    setCached(cacheKey, data, 15000)
    return data
  }

  async createMandate(data: any): Promise<any> {
    clearApiCache('mandates')
    clearApiCache('stats')
    return this.request('/mandates', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async freezeMandate(id: string): Promise<any> {
    clearApiCache('mandates')
    clearApiCache('stats')
    return this.request(`/mandates/${id}/freeze`, { method: 'POST' })
  }

  async unfreezeMandate(id: string): Promise<any> {
    clearApiCache('mandates')
    clearApiCache('stats')
    return this.request(`/mandates/${id}/unfreeze`, { method: 'POST' })
  }

  async revokeMandate(id: string): Promise<any> {
    clearApiCache('mandates')
    clearApiCache('stats')
    return this.request(`/mandates/${id}/revoke`, { method: 'POST' })
  }

  // Audit
  async getAudit(limit = 50, offset = 0, forceRefresh = false): Promise<any> {
    const cacheKey = `audit:${limit}:${offset}`
    if (!forceRefresh) {
      const cached = getCached<any>(cacheKey)
      if (cached) return cached
    }
    const data = await this.request(`/audit?limit=${limit}&offset=${offset}`)
    setCached(cacheKey, data, 10000)
    return data
  }

  async verifyChain(): Promise<any> {
    return this.request('/audit/verify')
  }

  // Risk Controls
  async getRiskConfig(forceRefresh = false): Promise<any> {
    const cacheKey = 'risk_config'
    if (!forceRefresh) {
      const cached = getCached<any>(cacheKey)
      if (cached) return cached
    }
    const data = await this.request('/admin/risk-config')
    setCached(cacheKey, data, 20000)
    return data
  }

  async updateRiskConfig(canary: boolean, judge: boolean): Promise<any> {
    clearApiCache('risk_config')
    return this.request('/admin/risk-config', {
      method: 'POST',
      body: JSON.stringify({ canary_enabled: canary, judge_enabled: judge }),
    })
  }
}

export const api = new ApiClient()
