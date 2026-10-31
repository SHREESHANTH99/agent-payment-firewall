import { describe, it, expect } from 'vitest'
import { mockApi } from '@/lib/mockService'

describe('MockService for Demo Mode', () => {
  it('loads initial stats', async () => {
    const stats = await mockApi.getStats()
    expect(stats).toBeDefined()
    expect(stats.total_spent_cents).toBeGreaterThan(0)
    expect(stats.escalations_pending).toBeGreaterThanOrEqual(0)
  })

  it('retrieves and filters intents', async () => {
    const all = await mockApi.getIntents()
    expect(all.items.length).toBeGreaterThan(0)

    const escalated = await mockApi.getIntents({ status: 'escalated' })
    expect(escalated.items.every(i => i.status === 'escalated')).toBe(true)
  })

  it('approves an intent and updates budget & escalation counts', async () => {
    const pendingList = await mockApi.getIntents({ status: 'escalated' })
    const target = pendingList.items[0]
    expect(target).toBeDefined()

    const initialStats = await mockApi.getStats()
    const res = await mockApi.approveIntent(target.id)
    expect(res.success).toBe(true)
    expect(res.status).toBe('executed')

    const updated = await mockApi.getIntent(target.id)
    expect(updated?.status).toBe('executed')

    const updatedStats = await mockApi.getStats()
    expect(updatedStats.escalations_pending).toBe(Math.max(0, initialStats.escalations_pending - 1))
  })

  it('freezes and unfreezes mandates', async () => {
    const mandates = await mockApi.getMandates()
    const target = mandates[0]
    expect(target).toBeDefined()

    await mockApi.freezeMandate(target.id!)
    const frozenList = await mockApi.getMandates()
    const frozenTarget = frozenList.find(m => m.id === target.id)
    expect(frozenTarget?.status).toBe('frozen')
    expect(frozenTarget?.freeze_reason).toBeDefined()

    await mockApi.unfreezeMandate(target.id!)
    const unfrozenList = await mockApi.getMandates()
    const unfrozenTarget = unfrozenList.find(m => m.id === target.id)
    expect(unfrozenTarget?.status).toBe('active')
  })

  it('verifies the audit chain integrity', async () => {
    const result = await mockApi.verifyChain()
    expect(result.valid).toBe(true)
    expect(result.checked_count).toBeGreaterThan(0)
    expect(result.first_broken_index).toBeNull()
  })
})
