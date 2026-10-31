'use client'

import React from 'react'
import { formatCompactNumber } from '@/lib/utils'
import { cn } from '@/lib/utils'

export function KpiNumeral({
  label,
  cents,
  count,
  subtext,
  trend,
  className,
}: {
  label: string
  cents?: number | null
  count?: number | null
  subtext?: string
  trend?: 'neutral' | 'positive' | 'warning' | 'danger'
  className?: string
}) {
  const isCents = typeof cents === 'number'
  const { compact, full } = isCents ? formatCompactNumber(cents) : { compact: `${count ?? 0}`, full: `${count ?? 0}` }

  return (
    <div
      className={cn(
        'p-4 bg-paper-low border border-border flex flex-col justify-between min-w-0 transition-colors',
        className
      )}
      title={isCents ? `Exact amount: ${full}` : `${label}: ${full}`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="font-sans text-xs text-ink-muted uppercase tracking-wider font-medium truncate">
          {label}
        </span>
        {trend === 'danger' && <span className="w-2 h-2 bg-vermilion rounded-none" />}
        {trend === 'warning' && <span className="w-2 h-2 bg-amber rounded-none" />}
        {trend === 'positive' && <span className="w-2 h-2 bg-forest rounded-none" />}
      </div>

      <div className="flex items-baseline gap-2 min-w-0">
        <span className="font-mono text-2xl lg:text-3xl font-semibold tracking-tight text-ink tabular-nums truncate">
          {compact}
        </span>
      </div>

      <div className="mt-1 flex items-center justify-between text-2xs font-mono text-ink-muted truncate">
        <span>{full}</span>
        {subtext && <span className="font-sans text-ink-muted truncate">{subtext}</span>}
      </div>
    </div>
  )
}
