'use client'

import React from 'react'
import { cn } from '@/lib/utils'

export function Stamp({
  verdict,
  className,
}: {
  verdict: 'APPROVED' | 'BLOCKED' | 'ESCALATED' | 'FROZEN' | 'PASS' | 'TRIPPED' | string
  className?: string
}) {
  const isDanger = ['BLOCKED', 'FROZEN', 'TRIPPED', 'FAIL'].includes(verdict.toUpperCase())
  const isSuccess = ['APPROVED', 'EXECUTED', 'PASS'].includes(verdict.toUpperCase())
  const isWarning = ['ESCALATED', 'FLAGGED'].includes(verdict.toUpperCase())

  return (
    <span
      className={cn(
        'inline-block px-2 py-0.5 border font-mono font-bold tracking-wider uppercase text-2xs select-none transition-transform duration-120 scale-100',
        isDanger && 'border-vermilion text-vermilion bg-vermilion/5',
        isSuccess && 'border-forest text-forest bg-forest/5',
        isWarning && 'border-amber text-amber bg-amber/5',
        !isDanger && !isSuccess && !isWarning && 'border-ink-muted text-ink-muted bg-paper-high',
        className
      )}
    >
      {verdict}
    </span>
  )
}
