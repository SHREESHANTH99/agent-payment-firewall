'use client'

import React from 'react'
import { FolderX } from 'lucide-react'
import { cn } from '@/lib/utils'

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = FolderX,
  className,
}: {
  title: string
  description?: string
  action?: React.ReactNode
  icon?: any
  className?: string
}) {
  return (
    <div
      className={cn(
        'p-12 border border-dashed border-border bg-paper-low text-center flex flex-col items-center justify-center gap-2',
        className
      )}
    >
      <Icon className="w-8 h-8 text-ink-muted opacity-40 mb-1" />
      <h3 className="font-sans font-semibold text-sm text-ink">{title}</h3>
      {description && <p className="font-sans text-xs text-ink-muted max-w-sm">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('bg-paper-high animate-pulse rounded-none', className)} />
}
