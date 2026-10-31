'use client'

import React from 'react'
import { cn } from '@/lib/utils'

export interface CheckpointInfo {
  id: string
  name: string
  stoppedCount?: number
  description: string
}

const CHECKPOINTS: CheckpointInfo[] = [
  { id: 'idempotency', name: '1. Idempotency', description: 'Atomic replay deduplication' },
  { id: 'mandate', name: '2. Mandate & Rules', description: 'Deterministic policy & limits' },
  { id: 'budget', name: '3. Atomic Budget', description: 'Redis reserve / commit / release' },
  { id: 'canary', name: '4. Canary Scan', description: 'Honeypot token trap' },
  { id: 'judge', name: '5. Risk Judge', description: 'LLM adversarial verification' },
  { id: 'decision', name: '6. Decision & Payout', description: 'PayPal sandbox or human approval' },
]

export function PipelineStrip({
  stoppedCounts,
  className,
}: {
  stoppedCounts?: Record<string, number>
  className?: string
}) {
  return (
    <div className={cn('bg-paper-low border border-border p-3 flex flex-col gap-2', className)}>
      <div className="flex items-center justify-between text-2xs uppercase tracking-wider font-mono text-ink-muted">
        <span>6-Stage Deterministic Inspection Chain</span>
        <span className="text-forest font-semibold">Active & Armed</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {CHECKPOINTS.map((cp) => {
          const stops = stoppedCounts?.[cp.id] ?? 0
          return (
            <div
              key={cp.id}
              className="p-2 bg-paper-high border border-border flex flex-col justify-between min-h-[58px]"
            >
              <div className="flex items-center justify-between gap-1">
                <span className="font-sans text-xs font-semibold text-ink truncate">{cp.name}</span>
                {stops > 0 && (
                  <span className="px-1 py-0.2 bg-vermilion/15 text-vermilion font-mono text-2xs font-bold">
                    {stops} stopped
                  </span>
                )}
              </div>
              <span className="font-sans text-2xs text-ink-muted leading-tight mt-1">{cp.description}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
