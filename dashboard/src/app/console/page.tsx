'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime, RealtimeEvent } from '@/hooks/useRealtime'
import { KpiNumeral, PipelineStrip, Skeleton, Banner } from '@/components/ui'
import { StatsData, IntentItem } from '@/types'
import { formatDate } from '@/lib/utils'
import { useRouter } from 'next/navigation'
import { ShieldAlert, ArrowRight } from 'lucide-react'

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
    <div className="p-4 bg-paper-low border border-border rounded-lg flex flex-col gap-3 shadow-2xs">
      <div className="flex items-center justify-between">
        <p className="font-sans font-semibold text-xs uppercase tracking-wider text-ink-muted">
          Decision breakdown
        </p>
        <span className="font-mono text-2xs text-ink-muted">
          {total} total intents evaluated
        </span>
      </div>
      <div className="flex h-3 w-full gap-0.5 rounded-full overflow-hidden bg-paper-high p-0.5">
        {entries.map(([key, val]) => (
          <div
            key={key}
            className={`${colors[key] ?? 'bg-ink-muted'} h-full first:rounded-l-full last:rounded-r-full transition-all`}
            style={{ width: `${(val / total) * 100}%` }}
            title={`${key}: ${val} (${((val / total) * 100).toFixed(1)}%)`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-2 pt-0.5">
        {entries.map(([key, val]) => (
          <div key={key} className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full shrink-0 ${colors[key] ?? 'bg-ink-muted'}`} />
            <span className="font-sans text-xs capitalize text-ink-muted">{key}</span>
            <span className="font-mono text-xs text-ink font-semibold tabular-nums">{val}</span>
            <span className="text-2xs font-mono text-ink-muted/70">
              ({((val / total) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function EventRow({ event }: { event: RealtimeEvent }) {
  const labelMap: Record<string, string> = {
    intent_created: 'Intent evaluated',
    intent_status_changed: 'Status updated',
    intent_escalated: 'Escalated for approval',
    mandate_frozen: 'Circuit breaker tripped',
    mandate_unfrozen: 'Mandate unfrozen',
    audit_appended: 'Audit block anchored',
    risk_config_changed: 'Risk detection updated',
  }
  const label = labelMap[event.type] ?? event.type
  const isCritical = ['mandate_frozen', 'intent_escalated'].includes(event.type)
  const isApproved = event.data?.status === 'executed'
  return (
    <div
      className={`flex items-center justify-between gap-3 py-2.5 px-4 border-b border-border text-xs transition-colors hover:bg-paper-high/40 ${
        isCritical ? 'bg-vermilion/5' : ''
      }`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            isCritical
              ? 'bg-vermilion animate-pulse'
              : isApproved
              ? 'bg-forest'
              : 'bg-ink-muted/50'
          }`}
        />
        <span
          className={`font-sans font-medium truncate ${
            isCritical ? 'text-vermilion font-semibold' : 'text-ink'
          }`}
        >
          {label}
        </span>
        {event.data?.merchant && (
          <span className="font-mono text-2xs text-ink-muted truncate hidden sm:inline px-1.5 py-0.5 bg-paper rounded border border-border/60">
            {event.data.merchant}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {event.data?.amount && (
          <span className="font-mono text-xs font-semibold text-ink">
            ${(event.data.amount / 100).toFixed(2)}
          </span>
        )}
        <span className="font-mono text-2xs text-ink-muted/80">{formatDate(event.ts)}</span>
      </div>
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
      if (!isDemo && !activeApi.getToken()) {
        router.replace('/console/login')
        return
      }
      const s = await activeApi.getStats()
      setStats(s)
    } catch {
    } finally {
      setLoading(false)
    }
  }

  useRealtime((event) => {
    setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS))
    if (
      [
        'intent_created',
        'intent_status_changed',
        'mandate_frozen',
        'mandate_unfrozen',
      ].includes(event.type)
    ) {
      load(true)
    }
  })

  useEffect(() => {
    load()
    if (isDemoMode()) {
      activeApi
        .getIntents()
        .then((res) => {
          const seeded: RealtimeEvent[] = ((res.items as IntentItem[]) || []).slice(0, 10).map((it: IntentItem) => ({
            type:
              it.status === 'escalated'
                ? 'intent_escalated'
                : it.status === 'executed'
                ? 'intent_created'
                : 'intent_status_changed',
            ts: it.created_at,
            data: {
              id: it.id,
              merchant: it.merchant,
              amount: it.amount,
              status: it.status,
            },
          }))
          setEvents((prev) => (prev.length === 0 ? seeded : prev))
        })
        .catch(() => {})
    }
  }, [])

  if (loading && !stats)
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-40 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    )

  const byStatus = stats?.by_status ?? {}
  const hasFrozen = (stats?.frozen_mandates ?? 0) > 0

  return (
    <div className="space-y-5">
      {/* Page Title & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h1 className="font-serif text-2xl text-ink">System overview</h1>
          <p className="font-sans text-xs text-ink-muted mt-0.5">
            Real-time mandate, budget, and risk detection telemetry.
          </p>
        </div>
      </div>

      {/* Critical Security Alert */}
      {hasFrozen && (
        <Banner
          variant="danger"
          title="Security alert"
          action={
            <Link
              href="/console/mandates"
              className="inline-flex items-center gap-1 font-semibold underline text-xs hover:text-vermilion"
            >
              <span>Review mandate</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          }
        >
          Mandate mnd-prod-007 was auto-frozen by the circuit breaker following a canary token trip.
        </Banner>
      )}

      {/* Demo Mode Notice */}
      {demo && (
        <div className="flex items-center justify-between px-3.5 py-1.5 rounded-md bg-paper-low border border-border text-xs text-ink-muted">
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-amber" />
            <span>Interactive demo &mdash; pre-loaded attack telemetry and simulated payouts.</span>
          </span>
          <span className="font-mono text-2xs text-ink-muted/70 hidden sm:inline">
            No real funds moved
          </span>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiNumeral
          label="Total settled"
          cents={stats?.total_spent_cents}
          trend="positive"
          subtext="settled via sandbox"
        />
        <KpiNumeral
          label="Reserved"
          cents={stats?.total_reserved_cents}
          trend="neutral"
          subtext="in-flight reservations"
        />
        <KpiNumeral
          label="Remaining budget"
          cents={stats?.total_remaining_cents}
          trend="neutral"
          subtext="$1,250.00 total allocated"
        />
        <KpiNumeral
          label="Pending approvals"
          count={stats?.escalations_pending ?? 0}
          trend={stats?.escalations_pending ? 'warning' : 'neutral'}
          subtext={stats?.escalations_pending ? 'awaiting human decision' : 'queue is clear'}
        />
        <KpiNumeral
          label="Frozen mandates"
          count={stats?.frozen_mandates ?? 0}
          trend={stats?.frozen_mandates ? 'danger' : 'neutral'}
          subtext={stats?.frozen_mandates ? 'circuit breaker tripped' : 'all policies active'}
        />
      </div>

      {/* Decision chart */}
      {Object.keys(byStatus).length > 0 && <DecisionChart byStatus={byStatus} />}

      {/* 6-Stage Deterministic Inspection Chain */}
      <PipelineStrip />

      {/* Live Activity Feed */}
      <div className="bg-paper-low border border-border rounded-lg flex flex-col shadow-2xs overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-paper-high/30">
          <div className="flex items-center gap-2">
            <p className="font-sans font-semibold text-xs uppercase tracking-wider text-ink-muted">
              Live activity ledger
            </p>
            <span className="w-1.5 h-1.5 rounded-full bg-forest animate-pulse" />
          </div>
          <span className="font-mono text-2xs text-ink-muted">{events.length} events logged</span>
        </div>
        {events.length === 0 ? (
          <div className="p-8 text-center font-sans text-xs text-ink-muted">
            Waiting for real-time events over WebSocket…
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto divide-y divide-border/50">
            {events.map((ev, i) => (
              <EventRow key={i} event={ev} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
