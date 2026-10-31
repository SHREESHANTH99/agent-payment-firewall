'use client'

import { useState, useEffect, useCallback } from 'react'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime } from '@/hooks/useRealtime'
import { MandateItem } from '@/types'
import { formatCents, formatDate } from '@/lib/utils'
import { Button, Banner, Skeleton, EmptyState } from '@/components/ui'
import { Scale, AlertTriangle } from 'lucide-react'

function BudgetBar({ spent, reserved, total }: { spent: number; reserved: number; total: number }) {
  if (!total) return null
  const spentPct = Math.min(100, (spent / total) * 100)
  const resPct = Math.min(100 - spentPct, (reserved / total) * 100)
  return (
    <div className="flex h-2 w-full gap-px overflow-hidden bg-paper-high" title={`Spent ${formatCents(spent)} / Reserved ${formatCents(reserved)} / Total ${formatCents(total)}`}>
      <div className="bg-forest h-full transition-all" style={{ width: `${spentPct}%` }} />
      <div className="bg-amber h-full transition-all" style={{ width: `${resPct}%` }} />
    </div>
  )
}

function MandateCard({
  mandate,
  onFreeze,
  onUnfreeze,
  onRevoke,
}: {
  mandate: MandateItem
  onFreeze: (id: string) => Promise<void>
  onUnfreeze: (id: string) => Promise<void>
  onRevoke: (id: string) => Promise<void>
}) {
  const id = mandate.id ?? mandate.mandate_id ?? ''
  const total = mandate.budget_total_cents ?? (mandate.budget_total ? mandate.budget_total * 100 : 0)
  const spent = mandate.budget_spent_cents ?? (mandate.spent_cents ?? 0)
  const reserved = mandate.budget_reserved_cents ?? (mandate.reserved_cents ?? 0)
  const remaining = mandate.budget_remaining_cents ?? (mandate.remaining_cents ?? (total - spent - reserved))
  const frozen = mandate.status === 'frozen'
  const revoked = mandate.status === 'revoked'

  return (
    <div className={`border ${frozen ? 'border-vermilion' : 'border-border'} bg-paper-low flex flex-col`}>
      {frozen && mandate.freeze_reason && (
        <div className="px-4 py-2 bg-vermilion/10 border-b border-vermilion/20 flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-vermilion shrink-0 mt-0.5" />
          <p className="font-sans text-xs text-vermilion">{mandate.freeze_reason}</p>
        </div>
      )}

      <div className="px-4 py-3 border-b border-border flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-sans text-sm font-semibold text-ink">{mandate.agent_id}</p>
          <p className="font-mono text-2xs text-ink-muted">{id}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 text-2xs font-mono font-bold uppercase border ${
            frozen ? 'border-vermilion text-vermilion bg-vermilion/5' :
            revoked ? 'border-ink-muted text-ink-muted' :
            'border-forest text-forest bg-forest/5'
          }`}>{mandate.status}</span>
          <span className="font-sans text-xs text-ink-muted capitalize">{mandate.period}</span>
        </div>
      </div>

      <div className="px-4 py-3 space-y-3">
        <BudgetBar spent={spent} reserved={reserved} total={total} />
        <div className="grid grid-cols-3 gap-2 text-center">
          {[
            { label: 'Settled', value: spent, color: 'text-forest' },
            { label: 'Reserved', value: reserved, color: 'text-amber' },
            { label: 'Remaining', value: remaining, color: 'text-ink' },
          ].map(({ label, value, color }) => (
            <div key={label}>
              <p className="font-mono text-sm font-bold tabular-nums {color}" title={formatCents(value)}>
                {formatCents(value)}
              </p>
              <p className="font-sans text-2xs text-ink-muted uppercase">{label}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-sans text-ink-muted">
          <span>Per-transaction cap: <span className="font-mono text-ink">{formatCents(mandate.per_transaction_cap_cents ?? (mandate.per_transaction_cap ? mandate.per_transaction_cap * 100 : 0))}</span></span>
          <span>Threshold: <span className="font-mono text-ink">{formatCents(mandate.escalation_threshold_cents ?? (mandate.escalation_threshold ? mandate.escalation_threshold * 100 : 0))}</span></span>
          <span>From: <span className="font-mono text-ink">{formatDate(mandate.valid_from)}</span></span>
          <span>Until: <span className="font-mono text-ink">{formatDate(mandate.valid_until)}</span></span>
        </div>

        {(mandate.allowed_merchants ?? mandate.allowlist_merchants ?? []).length > 0 && (
          <div>
            <p className="font-sans text-2xs uppercase text-ink-muted mb-1">Allowlisted merchants</p>
            <div className="flex flex-wrap gap-1.5">
              {(mandate.allowed_merchants ?? mandate.allowlist_merchants ?? []).map((m) => (
                <span key={m} className="font-mono text-2xs px-1.5 py-0.5 bg-paper-high border border-border">{m}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {!revoked && (
        <div className="px-4 py-3 border-t border-border flex gap-2">
          {frozen ? (
            <Button variant="secondary" size="sm" onClick={() => onUnfreeze(id)}>Unfreeze</Button>
          ) : (
            <Button variant="danger" size="sm" onClick={() => onFreeze(id)}>Freeze</Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => onRevoke(id)}>Revoke</Button>
        </div>
      )}
    </div>
  )
}

export default function MandatesPage() {
  const [mandates, setMandates] = useState<MandateItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const demo = typeof window !== 'undefined' && isDemoMode()

  // Create form state
  const [agentId, setAgentId] = useState('agent-007')
  const [budget, setBudget] = useState('100.00')
  const [cap, setCap] = useState('25.00')
  const [threshold, setThreshold] = useState('15.00')
  const [period, setPeriod] = useState('monthly')
  const [merchants, setMerchants] = useState('developer-tools.com, supplies@store.com')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const m = await activeApi.getMandates()
      setMandates(m)
    } catch {}
    finally { setLoading(false) }
  }, [])

  useRealtime((event) => {
    if (['mandate_frozen', 'mandate_unfrozen', 'intent_status_changed'].includes(event.type)) load()
  })

  useEffect(() => { load() }, [load])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await activeApi.createMandate({
        agent_id: agentId,
        budget_total: budget,
        per_transaction_cap: cap,
        escalation_threshold: threshold,
        period,
        allowed_merchants: merchants.split(',').map((m) => m.trim()).filter(Boolean),
      })
      setShowCreate(false)
      load()
    } catch {}
    setCreating(false)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl text-ink">Spending mandates</h1>
          <p className="font-sans text-xs text-ink-muted mt-0.5">
            Budget limits and policy rules assigned to each autonomous agent.
          </p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} variant="secondary">
          {showCreate ? 'Cancel' : '+ New mandate'}
        </Button>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">Sample mandates — no real budgets affected.</Banner>
      )}

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="border border-border bg-paper-low p-4 space-y-3">
          <p className="font-sans font-semibold text-sm text-ink">Create mandate</p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Agent ID', value: agentId, setter: setAgentId },
              { label: 'Total budget (USD)', value: budget, setter: setBudget, type: 'number' },
              { label: 'Per-transaction cap (USD)', value: cap, setter: setCap, type: 'number' },
              { label: 'Escalation threshold (USD)', value: threshold, setter: setThreshold, type: 'number' },
            ].map(({ label, value, setter, type = 'text' }) => (
              <div key={label}>
                <label className="font-sans text-2xs uppercase text-ink-muted block mb-1">{label}</label>
                <input
                  type={type}
                  value={value}
                  onChange={(e) => setter(e.target.value)}
                  className="w-full font-mono text-xs px-2 py-1.5 bg-paper border border-border focus:outline-none focus:border-ink"
                  required
                />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-sans text-2xs uppercase text-ink-muted block mb-1">Period</label>
              <select value={period} onChange={(e) => setPeriod(e.target.value)}
                className="w-full font-sans text-xs px-2 py-1.5 bg-paper border border-border focus:outline-none">
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="lifetime">Lifetime</option>
              </select>
            </div>
            <div>
              <label className="font-sans text-2xs uppercase text-ink-muted block mb-1">Allowlisted merchants (comma-separated)</label>
              <input type="text" value={merchants} onChange={(e) => setMerchants(e.target.value)}
                className="w-full font-mono text-xs px-2 py-1.5 bg-paper border border-border focus:outline-none focus:border-ink" />
            </div>
          </div>
          <Button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Create mandate'}</Button>
        </form>
      )}

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      ) : mandates.length === 0 ? (
        <EmptyState icon={Scale} title="No mandates found" description="Create a mandate to authorize an agent to make payments." />
      ) : (
        <div className="space-y-4">
          {mandates.map((m) => (
            <MandateCard
              key={m.id ?? m.mandate_id}
              mandate={m}
              onFreeze={async (id) => { await activeApi.freezeMandate(id); load() }}
              onUnfreeze={async (id) => { await activeApi.unfreezeMandate(id); load() }}
              onRevoke={async (id) => { await activeApi.revokeMandate(id); load() }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
