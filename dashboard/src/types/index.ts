export interface IntentItem {
  id: string
  mandate_id: string | null
  idempotency_key?: string
  agent_id?: string
  amount: number // in cents
  currency: string
  merchant: string
  description?: string | null
  reasoning?: string | null
  source_context?: string | null
  status: string
  decision_reasons?: string[] | Array<{ code: string; message: string }> | null
  risk_details?: {
    // real backend shape
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
    // mock/flat shape
    canary_tripped?: boolean
    canary_tokens_found?: string[]
    judge_score?: number
    judge_reasoning?: string
  } | null
  paypal_ref?: string | null
  created_at: string
  updated_at?: string
  expires_at?: string
  audit_events?: Array<{
    id: string
    event: string
    payload: any
    hash: string
    created_at: string
  }>
}

export interface MandateItem {
  // backend shape
  mandate_id?: string
  // unified id field
  id?: string
  agent_id: string
  budget_total?: number
  budget_total_cents?: number
  budget_total_formatted?: string
  spent_cents?: number
  budget_spent_cents?: number
  spent_formatted?: string
  reserved_cents?: number
  budget_reserved_cents?: number
  reserved_formatted?: string
  remaining_cents?: number
  budget_remaining_cents?: number
  remaining_formatted?: string
  per_transaction_cap?: number
  per_transaction_cap_cents?: number
  per_transaction_cap_formatted?: string
  escalation_threshold?: number | null
  escalation_threshold_cents?: number | null
  allowlist_merchants?: string[]
  allowed_merchants?: string[]
  allowed_currencies: string[]
  period: string
  valid_from: string
  valid_until: string
  status: string
  freeze_reason?: string
}

export interface StatsData {
  by_status: Record<string, number>
  total_spent_cents: number
  total_reserved_cents: number
  total_remaining_cents: number
  escalations_pending: number
  frozen_mandates: number
  total_intents?: number
  last_24h_decisions?: Record<string, number>
  last_24h?: Record<string, number>
}

export interface AuditItem {
  id: string
  intent_id: string | null
  mandate_id?: string | null
  event: string
  payload?: Record<string, any>
  data?: Record<string, any>
  prev_hash: string | null
  hash: string
  created_at: string
}

export interface RiskConfig {
  canary_enabled: boolean
  judge_enabled: boolean
}
