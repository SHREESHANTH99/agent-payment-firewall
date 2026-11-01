'use client'

import React from 'react'
import { cn } from '@/lib/utils'

export interface CheckpointInfo {
  id: string
  step: string
  name: string
  stoppedCount?: number
  description: string
}

const CHECKPOINTS: CheckpointInfo[] = [
  { id: 'idempotency', step: '01', name: 'Idempotency', description: 'Atomic replay deduplication' },
  { id: 'mandate', step: '02', name: 'Mandate & Rules', description: 'Deterministic policy & limits' },
  { id: 'budget', step: '03', name: 'Atomic Budget', description: 'Redis reserve / commit' },
  { id: 'canary', step: '04', name: 'Canary Scan', description: 'Honeypot token trap' },
  { id: 'judge', step: '05', name: 'Risk Judge', description: 'LLM adversarial verification' },
  { id: 'decision', step: '06', name: 'Decision & Payout', description: 'Sandbox or human approval' },
]

export function PipelineStrip({
  stoppedCounts,
  className,
}: {
  stoppedCounts?: Record<string, number>
  className?: string
}) {
  return (
    <div className={cn('bg-paper-low border border-border rounded-lg p-4 flex flex-col gap-3 shadow-2xs', className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="font-sans font-semibold text-xs uppercase tracking-wider text-ink-muted">
          6-Stage Deterministic Inspection Chain
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-forest font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-forest animate-pulse" />
          Active &amp; Armed
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {CHECKPOINTS.map((cp) => {
          const stops = stoppedCounts?.[cp.id] ?? 0
          return (
            <div
              key={cp.id}
              className="p-3 bg-paper border border-border/80 rounded-md flex flex-col justify-between min-h-[76px] transition-all hover:border-ink/20"
            >
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className="font-mono text-2xs text-vermilion font-bold">{cp.step}</span>
                {stops > 0 ? (
                  <span className="px-1.5 py-0.2 bg-vermilion/15 text-vermilion font-mono text-2xs font-bold rounded">
                    {stops} blocked
                  </span>
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-forest/40" />
                )}
              </div>
              <div>
                <p className="font-sans text-xs font-semibold text-ink leading-snug">{cp.name}</p>
                <p className="font-sans text-2xs text-ink-muted leading-tight mt-0.5">{cp.description}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
