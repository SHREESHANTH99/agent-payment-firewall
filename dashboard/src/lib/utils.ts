import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCents(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100)
}

export function formatCompactNumber(cents: number | null | undefined): { compact: string; full: string } {
  if (cents === null || cents === undefined) return { compact: '$0', full: '$0.00' }
  const dollars = cents / 100
  const full = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(dollars)

  const compact = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    compactDisplay: 'short',
    maximumFractionDigits: 1,
  }).format(dollars)

  return { compact, full }
}

export function formatDate(isoStr: string | null | undefined): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return isoStr
  }
}

export function formatShortHash(hash: string | null | undefined): string {
  if (!hash) return '-'
  if (hash.length <= 12) return hash
  return `${hash.slice(0, 6)}...${hash.slice(-4)}`
}

export function getStatusBadge(status: string) {
  switch (status?.toLowerCase()) {
    case 'approved':
    case 'executed':
      return {
        bg: 'bg-forest/10 text-forest border-forest/30',
        label: 'Approved',
        verdict: 'APPROVED',
      }
    case 'escalated':
      return {
        bg: 'bg-amber/10 text-amber border-amber/30',
        label: 'Escalated',
        verdict: 'ESCALATED',
      }
    case 'denied':
    case 'failed':
      return {
        bg: 'bg-vermilion/10 text-vermilion border-vermilion/30',
        label: 'Blocked',
        verdict: 'BLOCKED',
      }
    case 'frozen':
      return {
        bg: 'bg-vermilion/15 text-vermilion border-vermilion/40 font-bold',
        label: 'Frozen',
        verdict: 'FROZEN',
      }
    case 'executing':
      return {
        bg: 'bg-blue-600/10 text-blue-700 border-blue-600/30',
        label: 'Settling',
        verdict: 'SETTLING',
      }
    default:
      return {
        bg: 'bg-muted text-ink-muted border-border',
        label: status || 'Pending',
        verdict: 'PENDING',
      }
  }
}
