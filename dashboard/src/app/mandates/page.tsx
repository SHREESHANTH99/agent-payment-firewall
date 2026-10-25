'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { MandateItem } from '@/types'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'
import { useRealtime } from '@/hooks/useRealtime'
import { Plus, ShieldAlert, Lock, Unlock, Ban, AlertCircle } from 'lucide-react'

export default function MandatesPage() {
  const [mandates, setMandates] = useState<MandateItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)

  // Form fields
  const [agentId, setAgentId] = useState('agent-007')
  const [budgetTotal, setBudgetTotal] = useState('100.00')
  const [cap, setCap] = useState('25.00')
  const [threshold, setThreshold] = useState('15.00')
  const [period, setPeriod] = useState('lifetime')
  const [merchants, setMerchants] = useState('merchant@example.com, supplies@store.com')

  const loadMandates = async () => {
    try {
      const res = await api.getMandates()
      setMandates(res)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useRealtime((event) => {
    if (event.type === 'mandate_frozen' || event.type === 'mandate_unfrozen' || event.type === 'intent_status_changed') {
      loadMandates()
    }
  })

  useEffect(() => {
    loadMandates()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createMandate({
        agent_id: agentId,
        budget_total: budgetTotal,
        per_transaction_cap: cap,
        escalation_threshold: threshold || undefined,
        period,
        allowlist_merchants: merchants.split(',').map((m) => m.trim()).filter(Boolean),
        allowed_currencies: ['USD'],
      })
      setShowCreateModal(false)
      loadMandates()
    } catch (err: any) {
      alert(`Mandate creation failed: ${err.message}`)
    }
  }

  const handleFreeze = async (id: string) => {
    if (!confirm(`Are you sure you want to FREEZE mandate ${id}? Autonomous payments will be immediately rejected.`)) return
    try {
      await api.freezeMandate(id)
      loadMandates()
    } catch (err: any) {
      alert(`Freeze failed: ${err.message}`)
    }
  }

  const handleUnfreeze = async (id: string) => {
    if (!confirm(`Unfreeze mandate ${id}? Agent will regain autonomous spending capability.`)) return
    try {
      await api.unfreezeMandate(id)
      loadMandates()
    } catch (err: any) {
      alert(`Unfreeze failed: ${err.message}`)
    }
  }

  const handleRevoke = async (id: string) => {
    if (!confirm(`Revoke mandate ${id}? This is permanent.`)) return
    try {
      await api.revokeMandate(id)
      loadMandates()
    } catch (err: any) {
      alert(`Revoke failed: ${err.message}`)
    }
  }

  if (loading) {
    return <div className="p-8 text-xs text-muted-foreground">Loading mandates...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Spending Mandates</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configure agent budget caps, merchant allowlists, and manage circuit-breaker frozen states.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="px-3 py-1.5 bg-accent text-accent-foreground text-xs font-semibold rounded flex items-center space-x-1.5 hover:opacity-90"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create Mandate</span>
        </button>
      </div>

      {/* Mandates Table / Cards */}
      <div className="space-y-4">
        {mandates.map((m) => {
          const isFrozen = m.status === 'frozen'
          const spent = m.spent_cents || 0
          const reserved = m.reserved_cents || 0
          const total = m.budget_total || 1
          const spentPct = Math.min(100, Math.round((spent / total) * 100))
          const reservedPct = Math.min(100 - spentPct, Math.round((reserved / total) * 100))

          return (
            <div
              key={m.mandate_id}
              className={`p-5 border bg-card rounded-lg transition-colors ${
                isFrozen ? 'border-rose-800 bg-rose-950/10' : 'border-border'
              }`}
            >
              {isFrozen && (
                <div className="mb-3 p-2 bg-rose-950 text-rose-200 border border-rose-900 rounded text-xs flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
                  <span className="font-semibold">MANDATE FROZEN BY CIRCUIT BREAKER</span>
                  <span className="text-[11px] text-rose-300">All agent transactions under this mandate are strictly blocked.</span>
                </div>
              )}

              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-border">
                <div>
                  <div className="flex items-center space-x-3">
                    <span className="font-bold text-sm font-mono">{m.mandate_id}</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase ${
                      isFrozen ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-muted text-muted-foreground'
                    }`}>
                      {m.status}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">Agent: {m.agent_id}</span>
                  </div>
                </div>

                {/* Operations */}
                <div className="flex items-center space-x-2 text-xs">
                  {isFrozen ? (
                    <button
                      onClick={() => handleUnfreeze(m.mandate_id)}
                      className="px-2.5 py-1 bg-emerald-700 hover:bg-emerald-800 text-white rounded flex items-center space-x-1"
                    >
                      <Unlock className="w-3.5 h-3.5" />
                      <span>Unfreeze</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleFreeze(m.mandate_id)}
                      className="px-2.5 py-1 bg-rose-700 hover:bg-rose-800 text-white rounded flex items-center space-x-1"
                    >
                      <Lock className="w-3.5 h-3.5" />
                      <span>Freeze</span>
                    </button>
                  )}

                  <button
                    onClick={() => handleRevoke(m.mandate_id)}
                    className="px-2.5 py-1 bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground rounded"
                  >
                    Revoke
                  </button>
                </div>
              </div>

              {/* Live Budget Bar */}
              <div className="mt-4 space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span>
                    Spent: <span className="text-emerald-400 font-semibold">{formatCents(spent)}</span>
                    {' '}| Reserved: <span className="text-amber-400 font-semibold">{formatCents(reserved)}</span>
                  </span>
                  <span>
                    Budget: <span className="font-semibold">{formatCents(m.budget_total)}</span>
                  </span>
                </div>

                <div className="w-full h-2.5 bg-muted rounded-full overflow-hidden flex">
                  <div className="bg-emerald-500 h-full transition-all" style={{ width: `${spentPct}%` }} />
                  <div className="bg-amber-500 h-full transition-all" style={{ width: `${reservedPct}%` }} />
                </div>
              </div>

              {/* Policy parameters */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-3 border-t border-border text-xs text-muted-foreground">
                <div>
                  <span className="block font-medium">Per-Tx Cap:</span>
                  <span className="font-mono text-foreground">{formatCents(m.per_transaction_cap)}</span>
                </div>
                <div>
                  <span className="block font-medium">Escalation Threshold:</span>
                  <span className="font-mono text-foreground">
                    {m.escalation_threshold ? formatCents(m.escalation_threshold) : 'None'}
                  </span>
                </div>
                <div>
                  <span className="block font-medium">Period:</span>
                  <span className="capitalize text-foreground">{m.period}</span>
                </div>
                <div>
                  <span className="block font-medium">Allowlisted Merchants:</span>
                  <span className="text-foreground truncate block font-mono text-[11px]">
                    {m.allowlist_merchants?.join(', ') || 'Any'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg p-6 bg-card border border-border rounded-lg shadow-xl">
            <h2 className="text-sm font-bold tracking-tight mb-4">Create New Spending Mandate</h2>
            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1 font-medium">Agent ID</label>
                <input
                  type="text"
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                  className="w-full px-3 py-1.5 bg-background border border-border rounded"
                  required
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1 font-medium">Total Budget ($)</label>
                  <input
                    type="text"
                    value={budgetTotal}
                    onChange={(e) => setBudgetTotal(e.target.value)}
                    className="w-full px-3 py-1.5 bg-background border border-border rounded"
                    required
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1 font-medium">Per-Tx Cap ($)</label>
                  <input
                    type="text"
                    value={cap}
                    onChange={(e) => setCap(e.target.value)}
                    className="w-full px-3 py-1.5 bg-background border border-border rounded"
                    required
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1 font-medium">Escalation ($)</label>
                  <input
                    type="text"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    className="w-full px-3 py-1.5 bg-background border border-border rounded"
                  />
                </div>
              </div>

              <div>
                <label className="block text-muted-foreground mb-1 font-medium">Allowlisted Merchants (comma-separated)</label>
                <input
                  type="text"
                  value={merchants}
                  onChange={(e) => setMerchants(e.target.value)}
                  className="w-full px-3 py-1.5 bg-background border border-border rounded font-mono text-[11px]"
                  placeholder="merchant1@paypal.com, store@example.com"
                  required
                />
              </div>

              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 border border-border hover:bg-muted rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-accent text-accent-foreground font-semibold rounded hover:opacity-90"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
