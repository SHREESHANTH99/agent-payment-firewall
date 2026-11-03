import { describe, expect, it } from 'vitest'

const sessionHeaders = {
  'X-Demo-Session-Id': 'demo_01JZ7Q7K4E',
  'X-Demo-Session-Secret': 'ds_demo_secret_only_for_mock',
  'Content-Type': 'application/json',
}

describe('Judge Playground MSW handlers', () => {
  it('creates a session without exposing operator authentication', async () => {
    const response = await fetch('http://localhost/demo/sessions', {
      method: 'POST',
      body: JSON.stringify({ scenario: 'prompt_injection' }),
    })
    const body = await response.json()

    expect(response.status).toBe(201)
    expect(body.session.id).toBe('demo_01JZ7Q7K4E')
    expect(body.session_secret).toBeTruthy()
    expect(body.OPERATOR_TOKEN).toBeUndefined()
  })

  it('returns a quota fallback response for quota-triggering intent traffic', async () => {
    const response = await fetch('http://localhost/demo/sessions/demo_01JZ7Q7K4E/intents', {
      method: 'POST',
      headers: sessionHeaders,
      body: JSON.stringify({ source_context: 'quota' }),
    })
    const body = await response.json()

    expect(response.status).toBe(429)
    expect(body).toMatchObject({ code: 'demo_quota', fallback: true })
  })

  it('does not reveal risk details for a cross-agent mandate probe', async () => {
    const response = await fetch('http://localhost/demo/sessions/demo_01JZ7Q7K4E/intents', {
      method: 'POST',
      headers: sessionHeaders,
      body: JSON.stringify({ agent_id: 'A', mandate_id: 'mnd-demo-b' }),
    })
    const body = await response.json()

    expect(body.decision).toBe('denied')
    expect(body.reasons).toEqual([{ code: 'MANDATE_NOT_FOUND', message: 'Mandate not found' }])
    expect(body.risk).toEqual({})
    expect(body.operatorView.risk).toEqual({})
  })

  it('uses the same agent identifier for mandate freeze and unfreeze', async () => {
    const freezeResponse = await fetch('http://localhost/demo/sessions/demo_01JZ7Q7K4E/mandates/B/freeze', {
      method: 'POST',
      headers: sessionHeaders,
      body: JSON.stringify({ reason: 'test freeze' }),
    })
    const frozen = await freezeResponse.json()
    const unfreezeResponse = await fetch('http://localhost/demo/sessions/demo_01JZ7Q7K4E/mandates/B/unfreeze', {
      method: 'POST',
      headers: sessionHeaders,
    })
    const unfrozen = await unfreezeResponse.json()

    expect(frozen.mandate.agent_id).toBe('B')
    expect(frozen.mandate.status).toBe('frozen')
    expect(unfrozen.mandate.agent_id).toBe('B')
    expect(unfrozen.mandate.status).toBe('active')
  })

  it('streams agent events as SSE', async () => {
    const response = await fetch('http://localhost/demo/sessions/demo_01JZ7Q7K4E/agent-runs/run-demo-001/events', {
      headers: sessionHeaders,
    })
    const body = await response.text()

    expect(response.headers.get('content-type')).toContain('text/event-stream')
    expect(body).toContain('event: browse')
    expect(body).toContain('event: done')
  })
})
