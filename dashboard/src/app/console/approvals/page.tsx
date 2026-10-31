'use client'

import { useState, useEffect, useCallback } from 'react'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime } from '@/hooks/useRealtime'
import { IntentItem } from '@/types'
import { Stamp } from '@/components/ui/Stamp'
import { Button, Banner, EmptyState, Skeleton } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'
import { Clock, ChevronDown, ChevronUp, CheckSquare } from 'lucide-react'

function ExpiryCountdown({ expiresAt }: { expiresAt?: string }) {
  const [rem, setRem] = useState('')
  useEffect(() => {
    if (!expiresAt) return
    const tick = () => {
      const diff = new Date(expiresAt).getTime() - Date.now()
      if (diff <= 0) { setRem('Expired'); return }
      const m = Math.floor(diff / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setRem(`${m}m ${s}s`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [expiresAt])
  if (!rem) return null
  return (
    <span className={`font-mono text-2xs tabular-nums flex items-center gap-1 ${rem === 'Expired' ? 'text-vermilion' : 'text-amber'}`}>
      <Clock className="w-3 h-3" />
      {rem}
    </span>
  )
}

function EscalationCard({
  intent,
  highlight,
  onApprove,
  onReject,
}: {
  intent: IntentItem
  highlight: boolean
  onApprove: (id: string) => Promise<void>
  onReject: (id: string, reason: string) => Promise<void>
}) {
  const [contextOpen, setContextOpen] = useState(false)
  const [confirming, setConfirming] = useState<'approve' | 'reject' | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [acting, setActing] = useState(false)

  const canary = intent.risk_details?.canary_tripped ?? intent.risk_details?.canary?.tripped
  const judgeScore = intent.risk_details?.judge_score ?? intent.risk_details?.judge?.confidence
  const judgeOk = typeof judgeScore === 'number' ? judgeScore < 0.5 : intent.risk_details?.judge?.safe

  return (
    <div
      className={`border border-border bg-paper-low flex flex-col transition-colors ${highlight ? 'border-amber bg-amber/5' : ''}`}
      role="article"
      aria-label={`Escalated payment: ${intent.merchant}`}
    >
      {/* Card header */}
      <div className="px-4 py-3 border-b border-border flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <p className="font-mono text-xl font-bold text-ink tabular-nums">{formatCents(intent.amount)}</p>
          <div className="min-w-0">
            <p className="font-sans text-sm font-semibold text-ink truncate">{intent.merchant}</p>
            <p className="font-mono text-2xs text-ink-muted truncate">{intent.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <ExpiryCountdown expiresAt={intent.expires_at} />
          <span className="font-sans text-2xs text-ink-muted">{formatDate(intent.created_at)}</span>
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-3">
        {intent.description && (
          <p className="font-sans text-xs text-ink">{intent.description}</p>
        )}

        {intent.reasoning && (
          <div>
            <p className="font-sans text-2xs uppercase text-ink-muted tracking-wider mb-1">Agent reasoning</p>
            <p className="font-sans text-xs text-ink bg-paper-high border border-border p-2 leading-relaxed">
              {intent.reasoning}
            </p>
          </div>
        )}

        {/* Verdicts */}
        <div className="flex flex-wrap gap-2 items-center">
          <span className="font-sans text-2xs text-ink-muted uppercase">Canary:</span>
          <Stamp verdict={canary ? 'TRIPPED' : 'PASS'} />
          <span className="font-sans text-2xs text-ink-muted uppercase ml-2">Judge:</span>
          <Stamp verdict={judgeOk === false ? 'FLAGGED' : judgeOk === true ? 'PASS' : 'SKIP'} />
          {judgeScore !== undefined && (
            <span className="font-mono text-2xs text-ink-muted">score: {judgeScore.toFixed(2)}</span>
          )}
        </div>

        {/* Decision reasons */}
        {Array.isArray(intent.decision_reasons) && intent.decision_reasons.length > 0 && (
          <ul className="space-y-0.5">
            {(intent.decision_reasons as string[]).map((r, i) => (
              <li key={i} className="font-sans text-xs text-ink-muted flex items-start gap-1.5">
                <span className="w-1 h-1 bg-amber mt-1.5 shrink-0" />
                {typeof r === 'string' ? r : (r as any).message}
              </li>
            ))}
          </ul>
        )}

        {/* Collapsible source context */}
        {intent.source_context && (
          <div>
            <button
              onClick={() => setContextOpen(!contextOpen)}
              className="flex items-center gap-1 font-sans text-2xs text-ink-muted hover:text-ink uppercase tracking-wider transition-colors"
              aria-expanded={contextOpen}
            >
              {contextOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              Source context
            </button>
            {contextOpen && (
              <pre className="mt-2 p-2 bg-paper-high border border-border font-mono text-2xs text-ink leading-relaxed whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                {intent.source_context}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t border-border bg-paper">
        {confirming === null ? (
          <div className="flex gap-2">
            <Button
              onClick={() => setConfirming('approve')}
              className="flex items-center gap-1.5"
              variant="secondary"
            >
              <span className="w-2 h-2 bg-forest" />
              Approve payment
            </Button>
            <Button
              onClick={() => setConfirming('reject')}
              variant="danger"
            >
              Reject
            </Button>
          </div>
        ) : confirming === 'approve' ? (
          <div className="flex items-center gap-2">
            <p className="font-sans text-xs text-ink">Confirm approve {formatCents(intent.amount)} to {intent.merchant}?</p>
            <Button
              size="sm"
              className="bg-forest text-white hover:bg-forest/80"
              disabled={acting}
              onClick={async () => {
                setActing(true)
                await onApprove(intent.id)
              }}
            >
              {acting ? 'Approving…' : 'Confirm'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>Cancel</Button>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              placeholder="Reason for rejection (optional)"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="px-2 py-1.5 text-xs font-sans bg-paper-low border border-border focus:outline-none focus:border-vermilion transition-colors"
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="danger"
                disabled={acting}
                onClick={async () => {
                  setActing(true)
                  await onReject(intent.id, rejectReason)
                }}
              >
                {acting ? 'Rejecting…' : 'Confirm reject'}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>Cancel</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ApprovalsPage() {
  const [items, setItems] = useState<IntentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [highlightId, setHighlightId] = useState<string | null>(null)
  const demo = typeof window !== 'undefined' && isDemoMode()

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await activeApi.getIntents({ status: 'escalated', page_size: 50 })
      const full = await Promise.all(
        res.items.map(async (item: IntentItem) => {
          if (item.risk_details && item.reasoning) return item
          return (await activeApi.getIntent(item.id)) ?? item
        })
      )
      setItems(full)
    } catch {}
    finally { setLoading(false) }
  }, [])

  useRealtime((event) => {
    if (event.type === 'intent_escalated') {
      setHighlightId(event.data.intent_id)
      setTimeout(() => setHighlightId(null), 4000)
      load(true)
    }
    if (event.type === 'intent_status_changed') load(true)
  })

  useEffect(() => { load() }, [load])

  const handleApprove = async (id: string) => {
    await activeApi.approveIntent(id)
    setItems((prev) => prev.filter((i) => i.id !== id))
  }

  const handleReject = async (id: string, reason: string) => {
    await activeApi.rejectIntent(id, reason)
    setItems((prev) => prev.filter((i) => i.id !== id))
  }

  if (loading && items.length === 0) return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-48" />
      <Skeleton className="h-48" />
    </div>
  )

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-2xl text-ink">Escalations & approvals</h1>
        <p className="font-sans text-xs text-ink-muted mt-0.5">
          Transactions that exceeded deterministic policy thresholds and require human authorization.
        </p>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">
          These are scripted example escalations — no real transactions.
        </Banner>
      )}

      {items.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          title="Approval queue is clear"
          description="No transactions currently require human authorization. New escalations will appear in real time."
        />
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <EscalationCard
              key={item.id}
              intent={item}
              highlight={item.id === highlightId}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </div>
  )
}
