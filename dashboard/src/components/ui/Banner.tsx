'use client'

import React from 'react'
import { AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Banner({
  variant = 'warning',
  title,
  children,
  action,
  className,
}: {
  variant?: 'warning' | 'danger' | 'info'
  title?: string
  children: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div
      role="alert"
      className={cn(
        'w-full px-4 py-2 border text-xs flex items-center justify-between gap-3',
        variant === 'danger' && 'bg-vermilion/10 text-vermilion border-vermilion/30',
        variant === 'warning' && 'bg-amber/10 text-amber border-amber/30',
        variant === 'info' && 'bg-paper-high text-ink border-border',
        className
      )}
    >
      <div className="flex items-center gap-2">
        {variant === 'danger' && <AlertCircle className="w-4 h-4 shrink-0" />}
        {variant === 'warning' && <AlertTriangle className="w-4 h-4 shrink-0" />}
        {variant === 'info' && <Info className="w-4 h-4 shrink-0" />}
        <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
          {title && <span className="font-semibold uppercase tracking-wider text-2xs">{title}</span>}
          <span>{children}</span>
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
