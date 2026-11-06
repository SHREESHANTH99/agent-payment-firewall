import type {
  AgentRunEvent,
  AttackPreset,
  CreateSessionRequest,
  CreateSessionResponse,
  DemoState,
  IntentRequest,
  IntentResult,
  Session,
} from './demoApi.types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

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
    const error = new Error(body.message || `Request failed (${response.status})`) as Error & { code?: string; status?: number }
    error.code = body.code
    error.status = response.status
    throw error
  }
  return response.json() as Promise<T>
}

function authHeaders(sessionId: string, secret: string): HeadersInit {
  return { 'X-Demo-Session-Id': sessionId, 'X-Demo-Session-Secret': secret }
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
  config: Partial<Session['config']>,
): Promise<Session['config']> {
  const response = await request<{ config: Session['config'] }>(`/demo/sessions/${encodeURIComponent(sessionId)}/config`, {
    method: 'PATCH',
    headers: authHeaders(sessionId, secret),
    body: JSON.stringify(config),
  })
  return response.config
}

export async function submitDemoIntent(sessionId: string, secret: string, intent: IntentRequest): Promise<IntentResult> {
  return request<IntentResult>(`/demo/sessions/${encodeURIComponent(sessionId)}/intents`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
    body: JSON.stringify(intent),
  })
}

export async function actOnEscalation(
  sessionId: string,
  secret: string,
  intentId: string,
  action: 'approve' | 'reject',
): Promise<IntentResult> {
  return request<IntentResult>(`/demo/sessions/${encodeURIComponent(sessionId)}/escalations/${encodeURIComponent(intentId)}/${action}`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
    body: action === 'reject' ? JSON.stringify({ reason: 'Rejected in Judge Playground.' }) : undefined,
  })
}

export async function startAgentRun(
  sessionId: string,
  secret: string,
  payload: { agent_id: string; attack_id: string; user_task: string; page_text: string },
): Promise<{ run_id: string }> {
  return request<{ run_id: string }>(`/demo/sessions/${encodeURIComponent(sessionId)}/agent-runs`, {
    method: 'POST',
    headers: authHeaders(sessionId, secret),
    body: JSON.stringify(payload),
  })
}

export async function readAgentEvents(sessionId: string, secret: string, runId: string): Promise<AgentRunEvent[]> {
  const response = await fetch(`${API_BASE}/demo/sessions/${encodeURIComponent(sessionId)}/agent-runs/${encodeURIComponent(runId)}/events`, {
    headers: authHeaders(sessionId, secret),
  })
  if (!response.ok) throw new Error(`Event stream failed (${response.status})`)
  const text = await response.text()
  return text.split('\n\n').flatMap((chunk) => {
    const data = chunk.split('\n').find((line) => line.startsWith('data: '))
    if (!data) return []
    try { return [JSON.parse(data.slice(6)) as AgentRunEvent] } catch { return [] }
  })
}

export async function loadRecordedRun(): Promise<RecordedRun | null> {
  const response = await fetch('/data/recorded_runs.json')
  if (!response.ok) return null
  const data = await response.json() as RecordedRun[] | { runs?: RecordedRun[] }
  const runs = Array.isArray(data) ? data : data.runs || []
  return runs[0] || {
    id: 'recorded-default',
    title: 'Recorded prompt injection',
    description: 'A deterministic example retained for when the demo server is unavailable.',
    events: [
      { type: 'browse', sequence: 1, ts: new Date().toISOString(), message: 'Reading page text', data: {} },
      { type: 'intent_decision', sequence: 2, ts: new Date().toISOString(), message: 'Firewall denied the intent', data: { decision: 'denied', dry_run: true } },
      { type: 'done', sequence: 3, ts: new Date().toISOString(), message: 'Recorded run complete', data: {} },
    ],
  }
}

export function generateApiSnippets(baseUrl: string, sessionId: string, sessionSecret: string): { curl: string; python: string } {
  const url = `${baseUrl.replace(/\/$/, '')}/demo/sessions/${sessionId}/intents`
  return {
    curl: [
      `curl -X POST ${url} \\`,
      `  -H "X-Demo-Session-Id: ${sessionId}" \\`,
      `  -H "X-Demo-Session-Secret: ${sessionSecret}" \\`,
      '  -H "Content-Type: application/json" \\',
      `  -d '{"agent_id":"A","mandate_id":"mnd-demo-a","amount":"25.00","currency":"USD","merchant":"seller-one@example.test","idempotency_key":"playground-001"}'`,
    ].join('\n'),
    python: `import os, requests\n\nbase_url = "${baseUrl.replace(/\/$/, '')}"\nheaders = {"X-Demo-Session-Id": "${sessionId}", "X-Demo-Session-Secret": os.environ["DEMO_SESSION_SECRET"]}\nresponse = requests.post(f"{base_url}/demo/sessions/${sessionId}/intents", headers=headers, json={"agent_id": "A", "mandate_id": "mnd-demo-a", "amount": "25.00", "currency": "USD", "merchant": "seller-one@example.test", "idempotency_key": "playground-001"})\nprint(response.json())`,
  }
}
