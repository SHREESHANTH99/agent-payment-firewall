import { MOCK_STATS, MOCK_MANDATES, MOCK_INTENTS, MOCK_ESCALATIONS, MOCK_AUDIT, MOCK_RISK_CONFIG } from './mockData'
import { IntentItem, MandateItem, AuditItem, StatsData, RiskConfig } from '@/types'

class MockService {
  private stats: StatsData = JSON.parse(JSON.stringify(MOCK_STATS))
  private mandates: MandateItem[] = JSON.parse(JSON.stringify(MOCK_MANDATES))
  private intents: IntentItem[] = JSON.parse(JSON.stringify(MOCK_INTENTS))
  private audit: AuditItem[] = JSON.parse(JSON.stringify(MOCK_AUDIT))
  private riskConfig: RiskConfig = JSON.parse(JSON.stringify(MOCK_RISK_CONFIG))

  async getStats(): Promise<StatsData> {
    return { ...this.stats }
  }

  async getIntents(params: Record<string, any> = {}): Promise<{ items: IntentItem[]; total: number; page: number; page_size: number }> {
    let filtered = [...this.intents]
    if (params.status) {
      filtered = filtered.filter((i) => i.status === params.status)
    }
    const page = params.page || 1
    const pageSize = params.page_size || 25
    const start = (page - 1) * pageSize
    const items = filtered.slice(start, start + pageSize)
    return {
      items,
      total: filtered.length,
      page,
      page_size: pageSize,
    }
  }

  async getIntent(id: string): Promise<IntentItem | null> {
    const item = this.intents.find((i) => i.id === id)
    return item ? { ...item } : null
  }

  async approveIntent(id: string): Promise<any> {
    const item = this.intents.find((i) => i.id === id)
    if (item) {
      item.status = 'executed'
      this.stats.escalations_pending = Math.max(0, this.stats.escalations_pending - 1)
      this.stats.total_spent_cents += item.amount
      this.stats.total_reserved_cents = Math.max(0, this.stats.total_reserved_cents - item.amount)
    }
    return { success: true, status: 'executed' }
  }

  async rejectIntent(id: string, reason?: string): Promise<any> {
    const item = this.intents.find((i) => i.id === id)
    if (item) {
      item.status = 'denied'
      this.stats.escalations_pending = Math.max(0, this.stats.escalations_pending - 1)
      this.stats.total_reserved_cents = Math.max(0, this.stats.total_reserved_cents - item.amount)
    }
    return { success: true, status: 'denied', reason }
  }

  async getMandates(): Promise<MandateItem[]> {
    return [...this.mandates]
  }

  async createMandate(data: any): Promise<MandateItem> {
    const newMandate: MandateItem = {
      id: `mnd-${Date.now()}`,
      agent_id: data.agent_id || 'agent-007',
      budget_total_cents: Math.round(parseFloat(data.budget_total) * 100),
      budget_spent_cents: 0,
      budget_reserved_cents: 0,
      budget_remaining_cents: Math.round(parseFloat(data.budget_total) * 100),
      per_transaction_cap_cents: Math.round(parseFloat(data.per_transaction_cap) * 100),
      escalation_threshold_cents: Math.round(parseFloat(data.escalation_threshold) * 100),
      period: data.period || 'monthly',
      allowed_currencies: ['USD'],
      allowed_merchants: data.allowed_merchants || [],
      valid_from: new Date().toISOString(),
      valid_until: new Date(Date.now() + 86400000 * 30).toISOString(),
      status: 'active',
    }
    this.mandates.unshift(newMandate)
    return newMandate
  }

  async freezeMandate(id: string): Promise<any> {
    const m = this.mandates.find((x) => x.id === id)
    if (m) {
      m.status = 'frozen'
      m.freeze_reason = 'Operator manually initiated security freeze'
      this.stats.frozen_mandates += 1
    }
    return { success: true }
  }

  async unfreezeMandate(id: string): Promise<any> {
    const m = this.mandates.find((x) => x.id === id)
    if (m) {
      m.status = 'active'
      delete m.freeze_reason
      this.stats.frozen_mandates = Math.max(0, this.stats.frozen_mandates - 1)
    }
    return { success: true }
  }

  async revokeMandate(id: string): Promise<any> {
    const m = this.mandates.find((x) => x.id === id)
    if (m) m.status = 'revoked'
    return { success: true }
  }

  async getAudit(limit = 50, offset = 0): Promise<{ items: AuditItem[]; total: number }> {
    return {
      items: this.audit.slice(offset, offset + limit),
      total: this.audit.length,
    }
  }

  async verifyChain(): Promise<any> {
    return {
      valid: true,
      checked_count: this.audit.length,
      first_broken_index: null,
      chain_head_hash: this.audit[0]?.hash || '8c43fe11...',
    }
  }

  async getRiskConfig(): Promise<RiskConfig> {
    return { ...this.riskConfig }
  }

  async updateRiskConfig(canary: boolean, judge: boolean): Promise<RiskConfig> {
    this.riskConfig = { canary_enabled: canary, judge_enabled: judge }
    return { ...this.riskConfig }
  }
}

export const mockApi = new MockService()
