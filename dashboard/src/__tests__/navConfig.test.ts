import { describe, expect, it } from 'vitest'
import {
  MAIN_BOTTOM_NAV_ITEMS,
  MORE_SHEET_ITEMS,
  FULL_TELEMETRY_ITEMS,
  FULL_GOVERNANCE_ITEMS,
} from '@/lib/navConfig'

describe('navConfig and breakpoint contract', () => {
  it('defines 4 main bottom items for phone view', () => {
    expect(MAIN_BOTTOM_NAV_ITEMS).toHaveLength(4)
    expect(MAIN_BOTTOM_NAV_ITEMS.map((i) => i.label)).toEqual([
      'Overview',
      'Approvals',
      'Intents',
      'Mandates',
    ])
  })

  it('defines more sheet items with audit, risk controls and playground link', () => {
    expect(MORE_SHEET_ITEMS.map((i) => i.label)).toEqual([
      'Audit chain',
      'Risk controls',
      'Try the Playground',
    ])
  })

  it('maintains full sidebar telemetry and governance groups', () => {
    expect(FULL_TELEMETRY_ITEMS).toHaveLength(3)
    expect(FULL_GOVERNANCE_ITEMS).toHaveLength(3)
  })
})
