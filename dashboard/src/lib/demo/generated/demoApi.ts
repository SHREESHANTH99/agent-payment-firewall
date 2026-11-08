/**
 * Demo API Types and Contract Definitions.
 * Aligned with backend OpenAPI schema at `docs/openapi-demo.json`.
 */

export interface DemoHealthResponse {
  enabled: boolean
  quota_remaining: number
  version: string
}

export interface DemoError {
  code: string
  message: string
  fallback?: boolean
}

export interface CreateSessionRequest {
  display_name?: string
  scenario?: 'clean_purchase' | 'over_limit' | 'prompt_injection' | 'redirect'
}

export interface DemoQuota {
  limit: number
  used: number
  remaining: number
}

export interface DemoConfig {
  canary_enabled: boolean
  judge_enabled: boolean
}

export interface MandateView {
  mandate_id: string
  agent_id: 'A' | 'B'
  budget_total_cents: number
  per_transaction_cap_cents: number
  allowlist_merchants: string[]
  allowed_currencies: string[]
  period: string
  valid_from: string
  valid_until: string
  escalation_threshold_cents: number | null
  spent_cents: number
  reserved_cents: number
  remaining_cents: number
  status: 'active' | 'frozen' | 'revoked' | 'expired'
  freeze_reason?: string
}

export interface AgentInfo {
  id: 'A' | 'B'
  name: string
  description: string
  mandate: MandateView
}

export interface Session {
  id: string
  created_at: string
  expires_at: string
  quota: DemoQuota
  config: DemoConfig
  agents: AgentInfo[]
}

export interface CreateSessionResponse {
  session: Session
  session_secret: string
}

export interface DemoState {
  session: Session & {
    escalations?: DemoEscalationItem[]
    recent_intents?: DemoRecentIntent[]
  }
}

export interface ConfigRequest {
  canary_enabled?: boolean
  judge_enabled?: boolean
  budget_total_cents?: number
  per_transaction_cap_cents?: number
  escalation_threshold_cents?: number
}

export interface IntentRequest {
  agent?: 'A' | 'B'
  agent_id?: 'A' | 'B'
  mandate_id?: string
  idempotency_key?: string
  amount: string
  currency?: string
  merchant: string
  description?: string
  reasoning?: string
  user_task?: string
  source_context?: string
  target_mandate?: 'own' | 'other'
}

export interface DecisionReason {
  code: string
  message: string
  [key: string]: unknown
}

export interface CanaryRisk {
  tripped: boolean
  honeypot_calls?: Array<{ name: string; arguments: Record<string, unknown> }>
  instruction_signals?: string[]
  llm_error?: boolean
  [key: string]: unknown
}

export interface RiskJudgeResult {
  score?: number
  reasoning?: string
  flags?: string[]
  tripped?: boolean
  llm_error?: boolean
  [key: string]: unknown
}

export interface IntentRiskView {
  denial_cause?: string | null
  escalation_cause?: string | null
  canary?: CanaryRisk
  judge?: RiskJudgeResult
  [key: string]: unknown
}

export type DemoAgentId = 'A' | 'B'

export interface AuditEntry {
  id: number | string
  event: string
  payload: Record<string, unknown>
  hash: string
  created_at: string
}

export interface OperatorView {
  risk: IntentRiskView
  denial_cause?: string | null
  escalation_cause?: string | null
  balances: {
    spent_cents: number
    reserved_cents: number
    remaining_cents: number
  }
  new_audit_entries: AuditEntry[]
}

export interface IntentResult {
  intent_id: string
  decision: 'approved' | 'denied' | 'escalated' | 'rejected'
  status: string
  dry_run: boolean
  reasons: DecisionReason[]
  risk?: IntentRiskView
  operatorView?: OperatorView
}

export interface DemoEscalationItem {
  intent_id?: string
  id?: string
  agent_id?: 'A' | 'B'
  amount?: string
  amount_cents?: number
  currency: string
  merchant: string
  description?: string
  status: string
  decision?: string
  created_at?: string
  expires_at?: string
  [key: string]: unknown
}

export type Escalation = DemoEscalationItem
export type DemoEscalation = DemoEscalationItem

export type DemoRecentIntent = Record<string, unknown> | IntentResult

export interface AttackPreset {
  id: string
  category: string
  name: string
  title: string
  description: string
  explanation: string
  default_agent_id: 'A' | 'B'
  default_intent: {
    amount: string
    currency?: string
    merchant: string
    description?: string
    user_task?: string
    source_context?: string
    target_mandate?: 'own' | 'other'
  }
}

export interface AgentRunRequest {
  task: string
  variant?: string
  custom_page_text?: string
  agent?: 'A' | 'B'
}

export interface AgentRunResponse {
  run_id: string
  status: 'running'
  dry_run: boolean
  events_url: string
}

export interface AgentRunEvent {
  type: 'step' | 'tool_call' | 'browse' | 'intent_decision' | 'fallback' | 'done' | 'error'
  sequence: number
  ts: string
  message: string
  data: Record<string, unknown>
}

export interface RejectRequest {
  reason?: string
}

export interface ApprovalResponse {
  intent_id: string
  status: string
  decision: 'approved' | 'rejected'
  dry_run: boolean
}
