'use client'

import React from 'react'
import { getStatusBadge } from '@/lib/utils'
import { cn } from '@/lib/utils'

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const { bg, label } = getStatusBadge(status)
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 border rounded-sm font-sans font-medium text-xs',
        bg,
        className
      )}
    >
      {label}
    </span>
  )
}
