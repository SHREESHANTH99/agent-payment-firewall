'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { StatsData } from '@/types'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'
import { useRealtime, RealtimeEvent } from '@/hooks/useRealtime'
import { DollarSign, Clock, ShieldAlert, CheckCircle2, XCircle, ArrowUpRight } from 'lucide-react'

export default function OverviewPage() {
  const router = useRouter()
  const [stats, setStats] = useState<StatsData | null>(null)
  const [events, setEvents] = useState<RealtimeEvent[]>([])
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    try {
      const s = await api.getStats()
      setStats(s)
    } catch {
      // 401 redirects to login automatically in api.ts
    } finally {
      setLoading(false)
    }
  }

  useRealtime((event) => {
    // Append to live activity feed (max 50)
    setEvents((prev) => [event, ...prev].slice(0, 50))
    // Refresh stats when state changes
    if (['intent_created', 'intent_status_changed', 'mandate_frozen', 'mandate_unfrozen'].includes(event.type)) {
      loadData()
    }
  })

  useEffect(() => {
    if (!api.getToken()) {
      router.push('/login')
      return
    }
    loadData()
  }, [])

  if (loading && !stats) {
    return (
      <div className="space-y-6 animate-pulse">
        <div>
          <div className="h-6 w-48 bg-muted rounded mb-2" />
          <div className="h-4 w-80 bg-muted/60 rounded" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 bg-card border border-border rounded-lg" />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 h-72 bg-card border border-border rounded-lg" />
          <div className="h-72 bg-card border border-border rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold tracking-tight">System Overview</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Real-time transaction state, budget allocations, and policy circuit breaker status.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="p-4 border border-border bg-card rounded-lg">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-xs font-medium">Total Spent</span>
            <DollarSign className="w-4 h-4" />
          </div>
          <div className="text-lg font-bold text-emerald-500">
            {formatCents(stats?.total_spent_cents)}
          </div>
          <span className="text-[10px] text-muted-foreground">Executed payouts</span>
        </div>

        <div className="p-4 border border-border bg-card rounded-lg">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-xs font-medium">Reserved</span>
            <Clock className="w-4 h-4" />
          </div>
          <div className="text-lg font-bold text-amber-500">
            {formatCents(stats?.total_reserved_cents)}
          </div>
          <span className="text-[10px] text-muted-foreground">Escalated / In-flight</span>
        </div>

        <div className="p-4 border border-border bg-card rounded-lg">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-xs font-medium">Remaining</span>
            <DollarSign className="w-4 h-4" />
          </div>
          <div className="text-lg font-bold">
            {formatCents(stats?.total_remaining_cents)}
          </div>
          <span className="text-[10px] text-muted-foreground">Active mandates pool</span>
        </div>

        <div className="p-4 border border-border bg-card rounded-lg">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-xs font-medium">Pending Escalations</span>
            <span className="w-2 h-2 rounded-full bg-amber-500" />
          </div>
          <div className="text-lg font-bold text-amber-400">
            {stats?.escalations_pending || 0}
          </div>
          <span className="text-[10px] text-muted-foreground">Awaiting human sign-off</span>
        </div>

        <div className="p-4 border border-border bg-card rounded-lg">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-xs font-medium">Frozen Mandates</span>
            <ShieldAlert className="w-4 h-4 text-rose-500" />
          </div>
          <div className={`text-lg font-bold ${stats?.frozen_mandates ? 'text-rose-500' : 'text-muted-foreground'}`}>
            {stats?.frozen_mandates || 0}
          </div>
          <span className="text-[10px] text-muted-foreground">Circuit breaker trips</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Decision Breakdown (SVG / Chart) */}
        <div className="p-5 border border-border bg-card rounded-lg flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold tracking-tight mb-1">24h Decisions Breakdown</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Decisions processed by autonomous rule checks & AI risk engine.
            </p>

            <div className="space-y-3">
              {Object.entries(stats?.last_24h_decisions || {}).map(([decision, count]) => {
                const total = Object.values(stats?.last_24h_decisions || {}).reduce((a, b) => a + b, 0) || 1
                const pct = Math.round((count / total) * 100)
                const { bg } = getStatusBadge(decision)
                return (
                  <div key={decision} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="capitalize font-medium">{decision}</span>
                      <span className="text-muted-foreground">{count} ({pct}%)</span>
                    </div>
                    <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full ${
                          decision === 'approved'
                            ? 'bg-emerald-500'
                            : decision === 'escalated'
                            ? 'bg-amber-500'
                            : 'bg-rose-500'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="pt-4 border-t border-border mt-6 text-[11px] text-muted-foreground">
            Lifetime Intents Processed:{' '}
            <span className="font-semibold text-foreground">
              {Object.values(stats?.by_status || {}).reduce((a, b) => a + b, 0)}
            </span>
          </div>
        </div>

        {/* Live Activity Feed */}
        <div className="lg:col-span-2 p-5 border border-border bg-card rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold tracking-tight">Real-Time Event Stream</h2>
              <p className="text-xs text-muted-foreground">Live feed subscribed to Redis channel <code className="font-mono">apf:events</code></p>
            </div>
            <span className="text-[10px] text-muted-foreground font-mono">{events.length} events buffered</span>
          </div>

          <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
            {events.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground border border-dashed border-border rounded">
                Awaiting telemetry events... Transactions and status transitions will stream in real-time.
              </div>
            ) : (
              events.map((e, idx) => (
                <div
                  key={idx}
                  className="p-2.5 text-xs bg-muted/40 border border-border rounded flex items-center justify-between font-mono"
                >
                  <div className="flex items-center space-x-2 truncate">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                    <span className="font-semibold text-accent">{e.type}</span>
                    <span className="text-muted-foreground truncate">
                      {JSON.stringify(e.data)}
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground flex-shrink-0 ml-3">
                    {formatDate(e.ts)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
