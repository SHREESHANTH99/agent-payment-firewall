import { describe, it, expect } from 'vitest'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'

describe('Dashboard Utility Functions', () => {
  it('formats integer cents to USD currency strings', () => {
    expect(formatCents(0)).toBe('$0.00')
    expect(formatCents(1500)).toBe('$15.00')
    expect(formatCents(450)).toBe('$4.50')
    expect(formatCents(null)).toBe('$0.00')
    expect(formatCents(undefined)).toBe('$0.00')
  })

  it('maps intent statuses to appropriate badge styles and labels', () => {
    const approved = getStatusBadge('approved')
    expect(approved.bg).toContain('emerald')

    const escalated = getStatusBadge('escalated')
    expect(escalated.bg).toContain('amber')

    const denied = getStatusBadge('denied')
    expect(denied.bg).toContain('rose')

    const frozen = getStatusBadge('frozen')
    expect(frozen.bg).toContain('red')

    const unknown = getStatusBadge('custom_unknown')
    expect(unknown.bg).toContain('slate')
  })

  it('formats ISO timestamps safely', () => {
    expect(formatDate(null)).toBe('-')
    expect(formatDate(undefined)).toBe('-')
    const formatted = formatDate('2026-10-25T12:00:00Z')
    expect(formatted).not.toBe('-')
  })
})
