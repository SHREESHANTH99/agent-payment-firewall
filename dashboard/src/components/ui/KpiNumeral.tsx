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
  const { compact, full } = isCents
    ? formatCompactNumber(cents)
    : { compact: `${count ?? 0}`, full: `${count ?? 0}` }

  return (
    <div
      className={cn(
        'p-4 bg-paper-low border border-border rounded-lg flex flex-col justify-between min-w-0 transition-all hover:border-ink/20 shadow-2xs',
        className
      )}
      title={isCents ? `Exact amount: ${full}` : `${label}: ${full}`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-sans text-xs text-ink-muted uppercase tracking-wider font-medium truncate">
          {label}
        </span>
        {trend === 'danger' && <span className="w-2 h-2 rounded-full bg-vermilion" />}
        {trend === 'warning' && <span className="w-2 h-2 rounded-full bg-amber" />}
        {trend === 'positive' && <span className="w-2 h-2 rounded-full bg-forest" />}
      </div>

      <div className="flex items-baseline gap-2 min-w-0">
        <span className="font-mono text-2xl lg:text-3xl font-semibold tracking-tight text-ink tabular-nums truncate">
          {compact}
        </span>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-ink-muted truncate">
        {subtext ? (
          <span className="font-sans text-xs text-ink-muted/80 truncate">{subtext}</span>
        ) : isCents && full !== compact ? (
          <span className="font-mono text-2xs text-ink-muted/80 truncate">{full}</span>
        ) : (
          <span className="font-sans text-xs text-ink-muted/50 truncate">Live metric</span>
        )}
      </div>
    </div>
  )
}
