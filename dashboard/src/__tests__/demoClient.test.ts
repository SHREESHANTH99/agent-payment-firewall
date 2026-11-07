import { describe, expect, it, vi } from 'vitest'
import { generateApiSnippets, loadRecordedRun } from '@/lib/demoClient'

describe('demo client helpers', () => {
  it('generates snippets from the supplied session values', () => {
    const snippets = generateApiSnippets('https://sandbox.example.test/', 'demo-session', 'short-lived-demo-key')
    expect(snippets.curl).toContain('https://sandbox.example.test/demo/sessions/demo-session/intents')
    expect(snippets.curl).toContain('short-lived-demo-key')
    expect(snippets.python).toContain('DEMO_SESSION_SECRET')
    expect(snippets.python).not.toContain('short-lived-demo-key')
  })

  it('loads a recorded run and keeps a usable fallback when the file is empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }))
    const recorded = await loadRecordedRun()
    expect(recorded?.id).toBe('recorded-default')
    expect(recorded?.events?.some((event) => event.type === 'done')).toBe(true)
    vi.unstubAllGlobals()
  })
})
