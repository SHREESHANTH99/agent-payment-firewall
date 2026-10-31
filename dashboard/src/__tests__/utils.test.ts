import { describe, it, expect } from 'vitest'
import { formatCents, formatDate, getStatusBadge, formatCompactNumber, formatShortHash, cn } from '@/lib/utils'

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
    expect(approved.bg).toContain('forest')
    expect(approved.verdict).toBe('APPROVED')

    const escalated = getStatusBadge('escalated')
    expect(escalated.bg).toContain('amber')
    expect(escalated.verdict).toBe('ESCALATED')

    const denied = getStatusBadge('denied')
    expect(denied.bg).toContain('vermilion')
    expect(denied.verdict).toBe('BLOCKED')

    const frozen = getStatusBadge('frozen')
    expect(frozen.bg).toContain('vermilion')
    expect(frozen.verdict).toBe('FROZEN')

    const unknown = getStatusBadge('custom_unknown')
    expect(unknown.bg).toContain('muted')
    expect(unknown.verdict).toBe('PENDING')
  })

  it('formats compact numbers accurately', () => {
    expect(formatCompactNumber(null)).toEqual({ compact: '$0', full: '$0.00' })
    const { compact, full } = formatCompactNumber(150000)
    expect(full).toBe('$1,500.00')
    expect(compact).toContain('1.5')
  })

  it('formats short hashes correctly', () => {
    expect(formatShortHash(null)).toBe('-')
    expect(formatShortHash('short')).toBe('short')
    expect(formatShortHash('911a3c7e48b894101e4a30e87b7a696cb88a381e091563f8290e2f5b66d48271')).toBe('911a3c...8271')
  })

  it('merges class names with cn utility', () => {
    expect(cn('px-2', 'py-1', false && 'hidden', 'px-4')).toBe('py-1 px-4')
  })

  it('formats ISO timestamps safely', () => {
    expect(formatDate(null)).toBe('-')
    expect(formatDate(undefined)).toBe('-')
    const formatted = formatDate('2026-10-25T12:00:00Z')
    expect(formatted).not.toBe('-')
  })
})
