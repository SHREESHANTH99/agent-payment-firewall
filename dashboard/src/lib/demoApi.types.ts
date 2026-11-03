export type DemoDecision = 'approved' | 'denied' | 'escalated' | 'rejected'
export type DemoIntentStatus =
  | 'pending'
  | 'denied'
  | 'escalated'
  | 'approved'
  | 'executing'
  | 'executed'
  | 'rejected'
  | 'expired'
  | 'failed'
export type MandateStatus = 'active' | 'frozen' | 'revoked' | 'expired'
export type DemoPeriod = 'lifetime' | 'daily' | 'weekly'
export type AgentRunEventType =
  | 'step'
  | 'tool_call'
  | 'browse'
  | 'intent_decision'
  | 'fallback'
  | 'done'
  | 'error'

export interface DemoQuota {
  limit: number
  used: number
  remaining: number
}

export interface DemoConfig {
  canary_enabled: boolean
  judge_enabled: boolean
}

export interface Session {
  id: string
  created_at: string
  expires_at: string
  quota: DemoQuota
  config: DemoConfig
  agents: AgentInfo[]
}

export interface CreateSessionRequest {
  display_name?: string
  scenario?: 'clean_purchase' | 'over_limit' | 'prompt_injection' | 'redirect'
}

export interface CreateSessionResponse {
  session: Session
  session_secret: string
}

export interface MandateView {
  mandate_id: string
  agent_id: string
  budget_total_cents: number
  per_transaction_cap_cents: number
  allowlist_merchants: string[]
  allowed_currencies: string[]
  period: DemoPeriod
  valid_from: string
  valid_until: string
  escalation_threshold_cents: number | null
  spent_cents: number
  reserved_cents: number
  remaining_cents: number
  status: MandateStatus
  freeze_reason?: string
}

export interface AgentInfo {
  id: string
  name: string
  description: string
  mandate: MandateView
}

export interface IntentRequest {
  agent_id: string
  idempotency_key: string
  mandate_id: string
  amount: string | number
  currency: string
  merchant: string
  description?: string
  reasoning?: string
  user_task?: string
  source_context?: string
}

export interface DecisionReason {
  code: string
  message: string
  [key: string]: unknown
}

export interface CanaryRisk {
  tripped: boolean
  honeypot_calls?: Array<{ name: string; arguments: Record<string, unknown> }>
  segments?: number
  error?: string | null
  meta?: Record<string, unknown>
}

export interface JudgeRisk {
  safe: boolean
  confidence?: number
  injection_suspected?: boolean
  reasons?: string[]
  mismatch_reasons: string[]
  verdict: 'allow' | 'escalate' | 'deny' | string
  meta?: Record<string, unknown>
}

export interface DemoBalances {
  spent_cents: number
  reserved_cents: number
  remaining_cents: number
}

export interface AuditEntry {
  id?: string
  event: string
  payload?: Record<string, unknown>
  hash: string
  created_at?: string
}

export interface OperatorView {
  risk: {
    canary?: CanaryRisk
    judge?: JudgeRisk
  }
  denial_cause: string | null
  escalation_cause: string | null
  balances: DemoBalances
  new_audit_entries: AuditEntry[]
}

export interface IntentResult {
  intent_id: string
  decision: DemoDecision
  status: DemoIntentStatus
  reasons: DecisionReason[]
  risk: {
    canary?: CanaryRisk
    judge?: JudgeRisk
    denial_cause?: string
    escalation_cause?: string
    [key: string]: unknown
  }
  dry_run: true
  operatorView: OperatorView
}

export interface Escalation {
  id: string
  status: 'escalated' | 'approved' | 'rejected'
  amount_cents: number
  currency: string
  merchant: string
  agent_id: string
  reasons: DecisionReason[]
  risk: IntentResult['risk']
  created_at: string
  expires_at: string
}

export interface AttackPreset {
  id: string
  name: string
  description: string
  default_agent_id: string
  default_intent: Partial<IntentRequest>
}

export interface AgentRunEvent {
  type: AgentRunEventType
  sequence: number
  ts: string
  message: string
  data: Record<string, unknown>
}

export interface DemoError {
  code: string
  message: string
  fallback: boolean
}

export interface DemoState {
  session: Session & {
    escalations: Escalation[]
    recent_intents: IntentResult[]
  }
}
