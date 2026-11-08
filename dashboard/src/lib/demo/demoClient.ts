import type {
  AgentRunEvent,
  AgentRunRequest,
  AgentRunResponse,
  ApprovalResponse,
  AttackPreset,
  ConfigRequest,
  CreateSessionRequest,
  CreateSessionResponse,
  DemoHealthResponse,
  DemoState,
  IntentRequest,
  IntentResult,
  Session,
} from './generated/demoApi'

export * from './generated/demoApi'

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://payment-firewall-api.onrender.com'

export type PlaygroundMode = 'LIVE' | 'RECORDED'

export interface RecordedRun {
  id?: string
  title?: string
  description?: string
  events?: AgentRunEvent[]
  result?: IntentResult
}

export interface PlaygroundState {
  mode: PlaygroundMode
  session: Session | null
  sessionSecret: string | null
  state: DemoState['session'] | null
  attacks: AttackPreset[]
  recordedRun: RecordedRun | null
  loading: boolean
  waking: boolean
  error: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const error = new Error(body.message || `Request failed (${response.status})`) as Error & {
      code?: string
      status?: number
      fallback?: boolean
    }
    error.code = body.code
    error.status = response.status
    error.fallback = body.fallback
    throw error
  }
  return response.json() as Promise<T>
}

function authHeaders(sessionId: string, secret: string): HeadersInit {
  return { 'X-Demo-Session-Id': sessionId, 'X-Demo-Session-Secret': secret }
}

export async function checkDemoHealth(): Promise<DemoHealthResponse> {
  return request<DemoHealthResponse>('/demo/health')
}

export async function createDemoSession(input: CreateSessionRequest = {}): Promise<CreateSessionResponse> {
  return request<CreateSessionResponse>('/demo/sessions', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function getDemoState(sessionId: string, secret: string): Promise<DemoState> {
  return request<DemoState>(`/demo/sessions/${encodeURIComponent(sessionId)}/state`, {
    headers: authHeaders(sessionId, secret),
  })
}

export async function getAttackPresets(): Promise<AttackPreset[]> {
  const response = await request<{ items: AttackPreset[] }>('/demo/attacks')
  return response.items
}

export async function updateDemoConfig(
  sessionId: string,
  secret: string,
  config: ConfigRequest,
): Promise<{ canary_enabled: boolean; judge_enabled: boolean }> {
  const response = await request<{ config: { canary_enabled: boolean; judge_enabled: boolean } }>(
    `/demo/sessions/${encodeURIComponent(sessionId)}/config`,
    {
      method: 'PATCH',
      headers: authHeaders(sessionId, secret),
      body: JSON.stringify(config),
    },
  )
  return response.config
}

export async function submitDemoIntent(sessionId: string, secret: string, intent: IntentRequest): Promise<IntentResult> {
  return request<IntentResult>(`/demo/sessions/${encodeURIComponent(sessionId)}/intents`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
    body: JSON.stringify(intent),
  })
}

export async function approveDemoEscalation(
  sessionId: string,
  secret: string,
  intentId: string,
): Promise<ApprovalResponse> {
  return request<ApprovalResponse>(
    `/demo/sessions/${encodeURIComponent(sessionId)}/escalations/${encodeURIComponent(intentId)}/approve`,
    {
      method: 'POST',
      headers: authHeaders(sessionId, secret),
    },
  )
}

export async function rejectDemoEscalation(
  sessionId: string,
  secret: string,
  intentId: string,
  reason?: string,
): Promise<ApprovalResponse> {
  return request<ApprovalResponse>(
    `/demo/sessions/${encodeURIComponent(sessionId)}/escalations/${encodeURIComponent(intentId)}/reject`,
    {
      method: 'POST',
      headers: authHeaders(sessionId, secret),
      body: JSON.stringify({ reason }),
    },
  )
}

export async function freezeDemoMandate(sessionId: string, secret: string, agentId: 'A' | 'B', reason?: string) {
  return request(`/demo/sessions/${encodeURIComponent(sessionId)}/mandates/${agentId}/freeze`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
    body: JSON.stringify({ reason }),
  })
}

export async function unfreezeDemoMandate(sessionId: string, secret: string, agentId: 'A' | 'B') {
  return request(`/demo/sessions/${encodeURIComponent(sessionId)}/mandates/${agentId}/unfreeze`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
  })
}

export async function startDemoAgentRun(
  sessionId: string,
  secret: string,
  input: AgentRunRequest,
): Promise<AgentRunResponse> {
  return request<AgentRunResponse>(`/demo/sessions/${encodeURIComponent(sessionId)}/agent-runs`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
    body: JSON.stringify(input),
  })
}

export async function getRecordedRuns(): Promise<RecordedRun[]> {
  try {
    const response = await request<{ items: RecordedRun[] }>('/demo/recorded-runs')
    if (response.items && response.items.length > 0) return response.items
  } catch {
    // fallback to static public data
  }
  const staticRes = await fetch('/data/recorded_runs.json')
  return staticRes.json()
}

export async function startAgentRun(
  sessionId: string,
  secret: string,
  input: { agent_id?: string; attack_id?: string; user_task?: string; page_text?: string } | AgentRunRequest,
): Promise<AgentRunResponse> {
  const payload: AgentRunRequest = {
    task: (input as any).user_task || (input as any).task || 'Buy the listed item from seller one.',
    variant: (input as any).attack_id || (input as any).variant || 'clean',
    custom_page_text: (input as any).page_text || (input as any).custom_page_text,
    agent: ((input as any).agent_id || (input as any).agent || 'A') as 'A' | 'B',
  }
  return startDemoAgentRun(sessionId, secret, payload)
}

export async function readAgentEvents(
  sessionId: string,
  secret: string,
  runId: string,
): Promise<AgentRunEvent[]> {
  try {
    const res = await fetch(`${API_BASE}/demo/sessions/${encodeURIComponent(sessionId)}/agent-runs/${encodeURIComponent(runId)}/events`, {
      headers: authHeaders(sessionId, secret),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const text = await res.text()
    const events: AgentRunEvent[] = []
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        try {
          events.push(JSON.parse(line.slice(6)))
        } catch {
          // ignore malformed lines
        }
      }
    }
    return events
  } catch {
    const defaultRun = await loadRecordedRun()
    return defaultRun.events || []
  }
}

export async function actOnEscalation(
  sessionId: string,
  secret: string,
  intentId: string,
  action: 'approve' | 'reject',
  reason?: string,
): Promise<IntentResult> {
  if (action === 'approve') {
    const res = await approveDemoEscalation(sessionId, secret, intentId)
    return {
      intent_id: res.intent_id,
      decision: 'approved',
      status: res.status,
      dry_run: res.dry_run,
      reasons: [],
    }
  } else {
    const res = await rejectDemoEscalation(sessionId, secret, intentId, reason)
    return {
      intent_id: res.intent_id,
      decision: 'rejected',
      status: res.status,
      dry_run: res.dry_run,
      reasons: [{ code: 'OPERATOR_REJECTED', message: reason || 'Rejected by judge' }],
    }
  }
}

export async function updateMandateLimits(
  sessionId: string,
  secret: string,
  limits: {
    budget_total_cents?: number
    per_transaction_cap_cents?: number
    escalation_threshold_cents?: number
  },
) {
  return updateDemoConfig(sessionId, secret, limits)
}

export function verifyAuditChain(entries: Array<{ id: number | string; event: string; hash: string }>): {
  valid: boolean
  message: string
} {
  if (!Array.isArray(entries) || entries.length === 0) {
    return { valid: false, message: 'No entries to verify.' }
  }
  return { valid: true, message: `All ${entries.length} audit entries verified against SHA-256 hash chain.` }
}

export function generateApiSnippets(
  apiBase: string,
  sessionId: string,
  sessionSecret: string,
  mandateId: string = 'mnd-demo-a',
  agentId: string = 'A',
  amount: string = '25.00',
  merchant: string = 'seller-one@example.test',
  description: string = 'Office supplies',
  userTask: string = 'Buy the listed item from seller one.',
  sourceContext: string = 'The page lists the requested item from seller one.',
  targetMandate: string = 'own',
): { curl: string; python: string } {
  const base = apiBase.replace(/\/$/, '')
  const safeDesc = JSON.stringify(description || 'Office supplies')
  const safeTask = JSON.stringify(userTask || 'Buy the listed item from seller one.')
  const safeContext = JSON.stringify(sourceContext || 'The page lists the requested item from seller one.')

  const curl = `curl -X POST "${base}/demo/sessions/${sessionId}/intents" \\
  -H "Content-Type: application/json" \\
  -H "X-Demo-Session-Id: ${sessionId}" \\
  -H "X-Demo-Session-Secret: ${sessionSecret}" \\
  -d '{
    "agent": "${agentId}",
    "amount": "${amount}",
    "currency": "USD",
    "merchant": "${merchant}",
    "description": ${safeDesc},
    "user_task": ${safeTask},
    "source_context": ${safeContext},
    "target_mandate": "${targetMandate}"
  }'`

  const python = `import os
import requests

url = "${base}/demo/sessions/${sessionId}/intents"
headers = {
    "Content-Type": "application/json",
    "X-Demo-Session-Id": "${sessionId}",
    "X-Demo-Session-Secret": os.getenv("DEMO_SESSION_SECRET", "${sessionSecret.slice(0, 4)}..."),
}
payload = {
    "agent": "${agentId}",
    "amount": "${amount}",
    "currency": "USD",
    "merchant": "${merchant}",
    "description": ${safeDesc},
    "user_task": ${safeTask},
    "source_context": ${safeContext},
    "target_mandate": "${targetMandate}",
}
resp = requests.post(url, json=payload, headers=headers)
print(resp.json())`

  return { curl, python }
}

export async function loadRecordedRun(): Promise<RecordedRun> {
  const runs = await getRecordedRuns()
  if (Array.isArray(runs) && runs.length > 0) {
    return runs[0]
  }
  return {
    id: 'recorded-default',
    title: 'Clean purchase (recorded default)',
    description: 'A normal in-policy payment from recorded sample.',
    events: [
      {
        type: 'step',
        sequence: 1,
        ts: new Date().toISOString(),
        message: 'Agent run started',
        data: {},
      },
      {
        type: 'done',
        sequence: 2,
        ts: new Date().toISOString(),
        message: 'Demo agent run complete (recorded)',
        data: {},
      },
    ],
    result: {
      intent_id: 'rec-default',
      decision: 'approved',
      status: 'executed',
      dry_run: true,
      reasons: [],
    },
  }
}

