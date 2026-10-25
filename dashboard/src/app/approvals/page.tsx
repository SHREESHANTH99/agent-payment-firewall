'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { IntentItem } from '@/types'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'
import { useRealtime } from '@/hooks/useRealtime'
import { Check, X, AlertTriangle, ShieldAlert, ChevronDown, ChevronUp, Clock } from 'lucide-react'

export default function ApprovalsPage() {
  const [escalations, setEscalations] = useState<IntentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedContext, setExpandedContext] = useState<Record<string, boolean>>({})
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})
  const [confirmReject, setConfirmReject] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [highlightId, setHighlightId] = useState<string | null>(null)

  const loadEscalations = async () => {
    try {
      const res = await api.getIntents({ status: 'escalated', page_size: 50 })
      // For each item, fetch detail to get reasoning, risk details, source context
      const fullItems = await Promise.all(
        res.items.map((i: any) => api.getIntent(i.id).catch(() => i))
      )
      setEscalations(fullItems)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useRealtime((event) => {
    if (event.type === 'intent_escalated') {
      const intentId = event.data.intent_id
      setHighlightId(intentId)
      setTimeout(() => setHighlightId(null), 4000)
      loadEscalations()
    } else if (event.type === 'intent_status_changed') {
      loadEscalations()
    }
  })

  useEffect(() => {
    loadEscalations()
  }, [])

  const handleApprove = async (id: string) => {
    setActionLoading((prev) => ({ ...prev, [id]: true }))
    try {
      await api.approveIntent(id)
      setEscalations((prev) => prev.filter((item) => item.id !== id))
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`)
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }))
    }
  }

  const handleReject = async (id: string) => {
    setActionLoading((prev) => ({ ...prev, [id]: true }))
    try {
      await api.rejectIntent(id, rejectReason)
      setEscalations((prev) => prev.filter((item) => item.id !== id))
      setConfirmReject(null)
      setRejectReason('')
    } catch (err: any) {
      alert(`Rejection failed: ${err.message}`)
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }))
    }
  }

  const toggleContext = (id: string) => {
    setExpandedContext((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  if (loading) {
    return <div className="p-8 text-xs text-muted-foreground">Loading approval queue...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Escalations & Approvals</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          High-value transactions and AI risk layer escalations requiring human-in-the-loop authorization.
        </p>
      </div>

      {escalations.length === 0 ? (
        <div className="p-16 text-center border border-dashed border-border rounded-lg bg-card/40">
          <Clock className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
          <h3 className="text-sm font-semibold">Queue is clear</h3>
          <p className="text-xs text-muted-foreground mt-1">
            No transactions currently pending human authorization. Incoming escalations will appear in real time.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {escalations.map((intent) => {
            const isNew = highlightId === intent.id
            const canary = intent.risk_details?.canary
            const judge = intent.risk_details?.judge

            return (
              <div
                key={intent.id}
                className={`p-5 border border-border bg-card rounded-lg transition-all duration-500 ${
                  isNew ? 'ring-2 ring-accent bg-accent/5' : ''
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-lg font-bold">{formatCents(intent.amount)}</span>
                      <span className="text-xs font-medium text-muted-foreground font-mono">
                        {intent.currency}
                      </span>
                      <span className="text-xs text-muted-foreground">→</span>
                      <span className="text-xs font-semibold">{intent.merchant}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5 font-mono">
                      Intent ID: {intent.id} • Mandate: {intent.mandate_id || 'unlinked'}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleApprove(intent.id)}
                      disabled={actionLoading[intent.id]}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded flex items-center space-x-1 transition-colors disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{actionLoading[intent.id] ? 'Approving...' : 'Approve & Pay'}</span>
                    </button>

                    <button
                      onClick={() => setConfirmReject(intent.id)}
                      disabled={actionLoading[intent.id]}
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium rounded flex items-center space-x-1 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>
                  </div>
                </div>

                {/* Confirm Reject Modal / Inline Box */}
                {confirmReject === intent.id && (
                  <div className="mt-3 p-3 bg-rose-950/40 border border-rose-900 rounded space-y-2">
                    <p className="text-xs font-medium text-rose-200">
                      Confirm Rejection: Budget reservation will be instantly released.
                    </p>
                    <input
                      type="text"
                      placeholder="Optional rejection reason..."
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="w-full px-2 py-1 text-xs bg-background border border-border rounded"
                    />
                    <div className="flex justify-end space-x-2">
                      <button
                        onClick={() => setConfirmReject(null)}
                        className="px-2 py-1 text-xs hover:bg-muted rounded"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleReject(intent.id)}
                        className="px-2 py-1 text-xs bg-rose-700 hover:bg-rose-800 text-white rounded font-medium"
                      >
                        Confirm Rejection
                      </button>
                    </div>
                  </div>
                )}

                {/* Reasoning & Risk Badges */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-xs">
                  <div>
                    <span className="font-semibold text-muted-foreground block mb-1">
                      Agent Stated Reasoning
                    </span>
                    <p className="p-2.5 bg-muted/30 border border-border rounded text-foreground">
                      {intent.reasoning || intent.description || 'No reasoning provided by agent.'}
                    </p>
                  </div>

                  <div>
                    <span className="font-semibold text-muted-foreground block mb-1">
                      AI Risk Layer Inspection
                    </span>
                    <div className="p-2.5 bg-muted/30 border border-border rounded space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Honeypot Canary:</span>
                        {canary ? (
                          <span className={`font-mono ${canary.tripped ? 'text-rose-400 font-semibold' : 'text-emerald-400'}`}>
                            {canary.tripped ? 'TRIPPED' : 'CLEAR'} ({canary.segments} segments)
                          </span>
                        ) : (
                          <span className="text-muted-foreground">Bypassed / Disabled</span>
                        )}
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">AI Judge Verdict:</span>
                        {judge ? (
                          <span className="font-mono">
                            <span className={judge.safe ? 'text-emerald-400' : 'text-amber-400'}>
                              {judge.verdict.toUpperCase()}
                            </span>{' '}
                            (conf: {(judge.confidence * 100).toFixed(0)}%)
                          </span>
                        ) : (
                          <span className="text-muted-foreground">Bypassed / Disabled</span>
                        )}
                      </div>

                      {judge?.reasons && judge.reasons.length > 0 && (
                        <div className="pt-1 text-[11px] text-muted-foreground">
                          Reasons: {judge.reasons.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Collapsible Source Context Excerpt */}
                <div className="mt-4 pt-3 border-t border-border">
                  <button
                    onClick={() => toggleContext(intent.id)}
                    className="flex items-center space-x-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <span>Untrusted Source Context</span>
                    {expandedContext[intent.id] ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>

                  {expandedContext[intent.id] && (
                    <div className="mt-2 p-3 bg-muted/20 border border-border rounded font-mono text-[11px] whitespace-pre-wrap max-h-48 overflow-y-auto">
                      {typeof (intent as any).source_context === 'string'
                        ? (intent as any).source_context
                        : JSON.stringify((intent as any).source_context || 'No untrusted source context attached.', null, 2)}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
