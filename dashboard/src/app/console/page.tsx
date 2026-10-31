'use client'

import { useEffect, useState, useRef } from 'react'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime, RealtimeEvent } from '@/hooks/useRealtime'
import { KpiNumeral, PipelineStrip, Skeleton, Banner } from '@/components/ui'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { StatsData } from '@/types'
import { formatDate } from '@/lib/utils'
import { useRouter } from 'next/navigation'

const MAX_EVENTS = 50

function DecisionChart({ byStatus }: { byStatus: Record<string, number> }) {
  const entries = Object.entries(byStatus).filter(([, v]) => v > 0)
  const total = entries.reduce((s, [, v]) => s + v, 0)
  const colors: Record<string, string> = {
    executed: 'bg-forest',
    escalated: 'bg-amber',
    denied: 'bg-vermilion',
    executing: 'bg-blue-500',
  }
  return (
    <div className="p-4 bg-paper-low border border-border flex flex-col gap-3">
      <p className="font-sans font-semibold text-xs uppercase tracking-wider text-ink-muted">Decision breakdown</p>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden">
        {entries.map(([key, val]) => (
          <div
            key={key}
            className={`${colors[key] ?? 'bg-ink-muted'} h-full`}
            style={{ width: `${(val / total) * 100}%` }}
            title={`${key}: ${val}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {entries.map(([key, val]) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className={`w-2 h-2 shrink-0 ${colors[key] ?? 'bg-ink-muted'}`} />
            <span className="font-sans text-xs capitalize text-ink-muted">{key}</span>
            <span className="font-mono text-xs text-ink font-semibold tabular-nums">{val}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function EventRow({ event }: { event: RealtimeEvent }) {
  const labelMap: Record<string, string> = {
    intent_created: 'Intent created',
    intent_status_changed: 'Status changed',
    intent_escalated: 'Escalated',
    mandate_frozen: 'Mandate frozen',
    mandate_unfrozen: 'Mandate unfrozen',
    audit_appended: 'Audit entry',
    risk_config_changed: 'Risk config changed',
  }
  const label = labelMap[event.type] ?? event.type
  const isCritical = ['mandate_frozen', 'intent_escalated'].includes(event.type)
  return (
    <div className={`flex items-center justify-between gap-2 py-1.5 px-3 border-b border-border text-xs transition-colors ${isCritical ? 'bg-vermilion/5' : ''}`}>
      <div className="flex items-center gap-2 min-w-0">
        <span className={`w-1.5 h-1.5 rounded-none shrink-0 ${isCritical ? 'bg-vermilion' : 'bg-ink-muted'}`} />
        <span className={`font-sans font-medium truncate ${isCritical ? 'text-vermilion' : 'text-ink'}`}>{label}</span>
        {event.data?.merchant && (
          <span className="font-mono text-2xs text-ink-muted truncate hidden sm:block">{event.data.merchant}</span>
        )}
      </div>
      <span className="font-mono text-2xs text-ink-muted shrink-0">{formatDate(event.ts)}</span>
    </div>
  )
}

export default function ConsoleOverviewPage() {
  const router = useRouter()
  const [stats, setStats] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<RealtimeEvent[]>([])
  const [demo, setDemo] = useState(false)

  const load = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const isDemo = isDemoMode()
      setDemo(isDemo)
      if (!isDemo && !activeApi.getToken()) { router.replace('/console/login'); return }
      const s = await activeApi.getStats()
      setStats(s)
    } catch {}
    finally { setLoading(false) }
  }

  useRealtime((event) => {
    setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS))
    if (['intent_created', 'intent_status_changed', 'mandate_frozen', 'mandate_unfrozen'].includes(event.type)) {
      load(true)
    }
  })

  useEffect(() => { load() }, [])

  if (loading && !stats) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24" />)}
      </div>
      <Skeleton className="h-40" />
      <Skeleton className="h-64" />
    </div>
  )

  const byStatus = stats?.by_status ?? {}

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-2xl text-ink">System overview</h1>
        <p className="font-sans text-xs text-ink-muted mt-0.5">Real-time mandate, budget, and risk detection telemetry.</p>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">
          This view is using scripted sample data. No real transactions are shown.
        </Banner>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiNumeral label="Total settled" cents={stats?.total_spent_cents} trend="positive" />
        <KpiNumeral label="Reserved" cents={stats?.total_reserved_cents} trend="neutral" subtext="In-flight" />
        <KpiNumeral label="Remaining budget" cents={stats?.total_remaining_cents} trend="neutral" />
        <KpiNumeral label="Pending approvals" count={stats?.escalations_pending ?? 0} trend={stats?.escalations_pending ? 'warning' : 'neutral'} />
        <KpiNumeral label="Frozen mandates" count={stats?.frozen_mandates ?? 0} trend={stats?.frozen_mandates ? 'danger' : 'neutral'} />
      </div>

      {/* Decision chart */}
      {Object.keys(byStatus).length > 0 && <DecisionChart byStatus={byStatus} />}

      {/* Pipeline strip */}
      <PipelineStrip />

      {/* Activity ledger */}
      <div className="bg-paper-low border border-border flex flex-col">
        <div className="px-3 py-2 border-b border-border flex items-center justify-between">
          <p className="font-sans font-semibold text-xs uppercase tracking-wider text-ink-muted">Live activity</p>
          <span className="font-mono text-2xs text-ink-muted">{events.length} events</span>
        </div>
        {events.length === 0 ? (
          <div className="p-8 text-center font-sans text-xs text-ink-muted">
            Waiting for real-time events over WebSocket…
          </div>
        ) : (
          <div className="max-h-72 overflow-y-auto">
            {events.map((ev, i) => <EventRow key={i} event={ev} />)}
          </div>
        )}
      </div>
    </div>
  )
}
