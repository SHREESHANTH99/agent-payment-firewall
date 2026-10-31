import { api as realApi } from './api'
import { mockApi } from './mockService'

export function isDemoMode(): boolean {
  if (typeof window === 'undefined') return false
  const urlParams = new URLSearchParams(window.location.search)
  if (urlParams.get('demo') === '1') {
    sessionStorage.setItem('apf_demo_mode', '1')
    return true
  }
  return sessionStorage.getItem('apf_demo_mode') === '1'
}

export function setDemoMode(enabled: boolean): void {
  if (typeof window === 'undefined') return
  if (enabled) {
    sessionStorage.setItem('apf_demo_mode', '1')
  } else {
    sessionStorage.removeItem('apf_demo_mode')
  }
}

export const activeApi = {
  getToken: () => (isDemoMode() ? 'demo-operator-token' : realApi.getToken()),
  setToken: (t: string | null) => realApi.setToken(t),
  getWsTicket: () => (isDemoMode() ? Promise.resolve({ ticket: 'demo-ticket', expires_at: '' }) : realApi.getWsTicket()),
  getStats: (force = false) => (isDemoMode() ? mockApi.getStats() : realApi.getStats(force)),
  getIntents: (params = {}, force = false) => (isDemoMode() ? mockApi.getIntents(params) : realApi.getIntents(params, force)),
  getIntent: (id: string, force = false) => (isDemoMode() ? mockApi.getIntent(id) : realApi.getIntent(id, force)),
  approveIntent: (id: string) => (isDemoMode() ? mockApi.approveIntent(id) : realApi.approveIntent(id)),
  rejectIntent: (id: string, reason?: string) => (isDemoMode() ? mockApi.rejectIntent(id, reason) : realApi.rejectIntent(id, reason)),
  getMandates: (force = false) => (isDemoMode() ? mockApi.getMandates() : realApi.getMandates(force)),
  createMandate: (data: any) => (isDemoMode() ? mockApi.createMandate(data) : realApi.createMandate(data)),
  freezeMandate: (id: string) => (isDemoMode() ? mockApi.freezeMandate(id) : realApi.freezeMandate(id)),
  unfreezeMandate: (id: string) => (isDemoMode() ? mockApi.unfreezeMandate(id) : realApi.unfreezeMandate(id)),
  revokeMandate: (id: string) => (isDemoMode() ? mockApi.revokeMandate(id) : realApi.revokeMandate(id)),
  getAudit: (limit = 50, offset = 0, force = false) => (isDemoMode() ? mockApi.getAudit(limit, offset) : realApi.getAudit(limit, offset, force)),
  verifyChain: () => (isDemoMode() ? mockApi.verifyChain() : realApi.verifyChain()),
  getRiskConfig: (force = false) => (isDemoMode() ? mockApi.getRiskConfig() : realApi.getRiskConfig(force)),
  updateRiskConfig: (canary: boolean, judge: boolean) => (isDemoMode() ? mockApi.updateRiskConfig(canary, judge) : realApi.updateRiskConfig(canary, judge)),
}
