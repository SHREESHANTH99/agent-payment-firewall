export interface IntentItem {
  id: string
  mandate_id: string | null
  idempotency_key: string
  amount: number // in cents
  currency: string
  merchant: string
  description?: string | null
  reasoning?: string | null
  status: string
  decision_reasons?: Array<{ code: string; message: string }> | null
  risk_details?: {
    canary?: {
      tripped: boolean
      honeypot_calls: Array<{ name: string; arguments: any }>
      segments: number
      error?: string | null
      meta?: any
    }
    judge?: {
      safe: boolean
      confidence: number
      injection_suspected: boolean
      reasons: string[]
      verdict: string
      meta?: any
    }
  } | null
  paypal_ref?: string | null
  created_at: string
  updated_at: string
  audit_events?: Array<{
    id: string
    event: string
    payload: any
    hash: string
    created_at: string
  }>
}

export interface MandateItem {
  mandate_id: string
  agent_id: string
  budget_total: number
  budget_total_formatted?: string
  spent_cents: number
  spent_formatted?: string
  reserved_cents: number
  reserved_formatted?: string
  remaining_cents: number
  remaining_formatted?: string
  per_transaction_cap: number
  per_transaction_cap_formatted?: string
  allowlist_merchants: string[]
  allowed_currencies: string[]
  period: string
  valid_from: string
  valid_until: string
  status: string
  escalation_threshold?: number | null
}

export interface StatsData {
  by_status: Record<string, number>
  total_spent_cents: number
  total_reserved_cents: number
  total_remaining_cents: number
  escalations_pending: number
  frozen_mandates: number
  last_24h_decisions: Record<string, number>
}

export interface AuditItem {
  id: string
  intent_id: string | null
  event: string
  payload: Record<string, any>
  prev_hash: string | null
  hash: string
  created_at: string
}

export interface RiskConfig {
  canary_enabled: boolean
  judge_enabled: boolean
}
