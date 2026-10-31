'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime } from '@/hooks/useRealtime'
import { IntentItem } from '@/types'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'
import { Drawer, Banner, Skeleton, EmptyState, Stamp } from '@/components/ui'
import { HashBlock } from '@/components/ui/HashBlock'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { ListOrdered, ChevronRight } from 'lucide-react'

type StatusFilter = '' | 'executed' | 'escalated' | 'denied' | 'executing'

export default function IntentsPage() {
  const [intents, setIntents] = useState<IntentItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<StatusFilter>('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<IntentItem | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const demo = typeof window !== 'undefined' && isDemoMode()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await activeApi.getIntents({ page, page_size: 25, status: status || undefined })
      setIntents(res.items)
      setTotal(res.total)
    } catch {}
    finally { setLoading(false) }
  }, [page, status])

  useRealtime((event) => {
    if (['intent_status_changed', 'intent_created'].includes(event.type)) load()
  })

  useEffect(() => { load() }, [load])

  const openDrawer = async (id: string) => {
    const detail = await activeApi.getIntent(id)
    if (detail) { setSelected(detail); setShowRaw(false) }
  }

  const colDefs = useMemo<ColDef<IntentItem>[]>(() => [
    {
      headerName: 'ID', field: 'id', width: 130,
      cellRenderer: (p: any) => (
        <span className="font-mono text-2xs text-vermilion cursor-pointer underline">
          {p.value?.slice(0, 8)}…
        </span>
      ),
      onCellClicked: (p: any) => openDrawer(p.data.id),
    },
    {
      headerName: 'Amount', field: 'amount', width: 110,
      cellRenderer: (p: any) => <span className="font-mono text-xs tabular-nums">{formatCents(p.value)}</span>,
    },
    { headerName: 'Currency', field: 'currency', width: 80 },
    { headerName: 'Merchant', field: 'merchant', flex: 1, minWidth: 140 },
    {
      headerName: 'Status', field: 'status', width: 120,
      cellRenderer: (p: any) => {
        const { bg, label } = getStatusBadge(p.value || '')
        return <span className={`px-1.5 py-0.5 border text-2xs font-semibold uppercase ${bg}`}>{label}</span>
      },
    },
    {
      headerName: 'Mandate', field: 'mandate_id', width: 130,
      cellRenderer: (p: any) => <span className="font-mono text-2xs text-ink-muted">{p.value ? `${p.value.slice(0, 10)}…` : '—'}</span>,
    },
    {
      headerName: 'Created', field: 'created_at', width: 160,
      cellRenderer: (p: any) => <span className="font-mono text-2xs">{formatDate(p.value)}</span>,
    },
    {
      headerName: '', width: 40,
      cellRenderer: (p: any) => (
        <button onClick={() => openDrawer(p.data.id)} className="text-ink-muted hover:text-ink" aria-label="Open detail">
          <ChevronRight className="w-4 h-4" />
        </button>
      ),
    },
  ], [])

  const statusOptions: { value: StatusFilter; label: string }[] = [
    { value: '', label: 'All statuses' },
    { value: 'executed', label: 'Executed' },
    { value: 'escalated', label: 'Escalated' },
    { value: 'denied', label: 'Blocked' },
    { value: 'executing', label: 'Settling' },
  ]

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl text-ink">Payment intents</h1>
          <p className="font-sans text-xs text-ink-muted mt-0.5">All payment intents processed by the firewall.</p>
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value as StatusFilter); setPage(1) }}
          className="font-sans text-xs bg-paper-low border border-border text-ink px-2 py-1.5 focus:outline-none focus:border-ink"
        >
          {statusOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">Sample payment intents. No real transactions.</Banner>
      )}

      {loading ? (
        <Skeleton className="flex-1 h-64" />
      ) : intents.length === 0 ? (
        <EmptyState icon={ListOrdered} title="No intents found" description="Try adjusting the status filter." />
      ) : (
        <div className="ag-theme-alpine flex-1 min-h-0 border border-border" style={{ height: '480px' }}>
          <AgGridReact
            rowData={intents}
            columnDefs={colDefs}
            defaultColDef={{ resizable: true, sortable: true }}
            suppressCellFocus={false}
          />
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs font-sans text-ink-muted">
        <span className="font-mono">{total} total intents</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-2 py-1 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors"
          >
            Previous
          </button>
          <span className="font-mono px-2">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={intents.length < 25}
            className="px-2 py-1 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors"
          >
            Next
          </button>
        </div>
      </div>

      {/* Detail drawer */}
      {selected && (
        <Drawer
          isOpen={!!selected}
          onClose={() => setSelected(null)}
          title={`Intent — ${selected.merchant}`}
          subtitle={selected.id}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted">Amount</p>
                <p className="font-mono text-lg font-bold tabular-nums">{formatCents(selected.amount)} {selected.currency}</p>
              </div>
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted">Status</p>
                <p className="font-sans text-xs font-semibold mt-0.5">{selected.status}</p>
              </div>
            </div>

            {selected.description && (
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted mb-1">Description</p>
                <p className="font-sans text-xs text-ink">{selected.description}</p>
              </div>
            )}

            {selected.decision_reasons && Array.isArray(selected.decision_reasons) && selected.decision_reasons.length > 0 && (
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted mb-1">Decision reasons</p>
                <ul className="space-y-1">
                  {(selected.decision_reasons as string[]).map((r, i) => (
                    <li key={i} className="font-sans text-xs text-ink flex items-start gap-1.5">
                      <span className="w-1 h-1 bg-ink-muted mt-1.5 shrink-0" />
                      {typeof r === 'string' ? r : (r as any).message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selected.risk_details && (
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted mb-1">Risk assessment</p>
                <div className="flex gap-2 flex-wrap">
                  <Stamp verdict={
                    (selected.risk_details.canary_tripped ?? selected.risk_details.canary?.tripped)
                      ? 'TRIPPED' : 'PASS'
                  } />
                  {(selected.risk_details.judge_score ?? selected.risk_details.judge?.confidence) !== undefined && (
                    <Stamp
                      verdict={
                        (selected.risk_details.judge_score ?? 0) > 0.5 ||
                        selected.risk_details.judge?.injection_suspected
                          ? 'FLAGGED' : 'PASS'
                      }
                    />
                  )}
                </div>
                {selected.risk_details.judge_reasoning && (
                  <p className="font-sans text-xs text-ink-muted mt-2">{selected.risk_details.judge_reasoning}</p>
                )}
              </div>
            )}

            {selected.paypal_ref && (
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted mb-1">PayPal reference</p>
                <span className="font-mono text-xs text-ink">{selected.paypal_ref}</span>
              </div>
            )}

            <div className="flex items-center justify-between border-t border-border pt-3">
              <button
                onClick={() => setShowRaw(!showRaw)}
                className="font-mono text-2xs text-ink-muted hover:text-ink uppercase tracking-wider transition-colors"
              >
                {showRaw ? 'Hide' : 'Show'} raw JSON
              </button>
            </div>

            {showRaw && (
              <pre className="bg-paper-high border border-border p-3 font-mono text-2xs overflow-auto max-h-64 break-all whitespace-pre-wrap">
                {JSON.stringify(selected, null, 2)}
              </pre>
            )}
          </div>
        </Drawer>
      )}
    </div>
  )
}
