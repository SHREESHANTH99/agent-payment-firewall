'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { activeApi } from '@/lib/activeApi'
import { useDemoMode } from '@/hooks/useDemoMode'
import { useRealtime } from '@/hooks/useRealtime'
import { IntentItem } from '@/types'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'
import { Drawer, Banner, Skeleton, EmptyState, Stamp } from '@/components/ui'
import { HashBlock } from '@/components/ui/HashBlock'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { ListOrdered, ChevronRight, Filter, X } from 'lucide-react'

type StatusFilter = '' | 'executed' | 'escalated' | 'denied' | 'executing'

export default function IntentsPage() {
  const [intents, setIntents] = useState<IntentItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<StatusFilter>('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<IntentItem | null>(null)
  const [filterSheetOpen, setFilterSheetOpen] = useState(false)
  const demo = useDemoMode()

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
    if (detail) { setSelected(detail) }
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
        <button onClick={() => openDrawer(p.data.id)} className="text-ink-muted hover:text-ink min-h-[44px] min-w-[44px] flex items-center justify-center" aria-label="Open detail">
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

        {/* Desktop Filter Select */}
        <div className="hidden md:block">
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value as StatusFilter); setPage(1) }}
            className="field font-sans text-xs bg-paper-low border border-border text-ink px-3 py-2 focus:outline-none focus:border-ink rounded"
          >
            {statusOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Mobile Filter Button */}
        <div className="md:hidden">
          <button
            type="button"
            onClick={() => setFilterSheetOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-paper-high border border-border text-xs font-semibold rounded min-h-[44px]"
          >
            <Filter className="w-4 h-4" />
            <span>Filter{status ? `: ${status}` : ''}</span>
          </button>
        </div>
      </div>

      {/* Filter Bottom Sheet for Mobile */}
      {filterSheetOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="md:hidden fixed inset-0 z-sheet flex flex-col justify-end"
        >
          <div
            className="fixed inset-0 bg-black/50"
            onClick={() => setFilterSheetOpen(false)}
          />
          <div className="relative z-10 bg-paper border-t border-border rounded-t-2xl p-5 pb-safe-bottom space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h2 className="font-sans font-bold text-sm text-ink">Filter intents</h2>
              <button
                onClick={() => setFilterSheetOpen(false)}
                className="p-2 text-ink-muted hover:text-ink min-h-[44px] min-w-[44px] flex items-center justify-center"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-1">
              {statusOptions.map((o) => (
                <button
                  key={o.value}
                  onClick={() => {
                    setStatus(o.value)
                    setPage(1)
                    setFilterSheetOpen(false)
                  }}
                  className={`w-full text-left px-3 py-3 rounded text-sm min-h-[44px] flex items-center justify-between ${
                    status === o.value ? 'bg-vermilion/10 text-vermilion font-semibold' : 'text-ink hover:bg-paper-high'
                  }`}
                >
                  <span>{o.label}</span>
                  {status === o.value && <span className="font-bold text-xs">✓</span>}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {demo && (
        <Banner variant="info" title="Sample data">Sample payment intents. No real transactions.</Banner>
      )}

      {loading ? (
        <Skeleton className="flex-1 h-64" />
      ) : intents.length === 0 ? (
        <EmptyState icon={ListOrdered} title="No intents found" description="Try adjusting the status filter." />
      ) : (
        <>
          {/* Mobile Card List View (< 768px) */}
          <div className="md:hidden space-y-3">
            {intents.map((item) => {
              const { bg, label } = getStatusBadge(item.status || '')
              return (
                <div
                  key={item.id}
                  onClick={() => openDrawer(item.id)}
                  className="p-4 bg-paper-low border border-border rounded-lg space-y-2 cursor-pointer hover:border-ink/20 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-vermilion font-bold">
                      {item.id.slice(0, 10)}…
                    </span>
                    <span className={`px-1.5 py-0.5 border text-2xs font-semibold uppercase ${bg}`}>
                      {label}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="font-sans text-sm font-semibold text-ink truncate pr-2">
                      {item.merchant}
                    </span>
                    <span className="font-mono text-sm font-bold text-ink shrink-0">
                      {formatCents(item.amount)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-2xs text-ink-muted pt-1 border-t border-border/50">
                    <span className="truncate">Mandate: {item.mandate_id?.slice(0, 8) || '—'}</span>
                    <span className="font-mono">{formatDate(item.created_at)}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Desktop AG Grid (>= 768px) */}
          <div className="hidden md:block ag-theme-alpine flex-1 min-h-0 border border-border" style={{ height: '480px' }}>
            <AgGridReact
              rowData={intents}
              columnDefs={colDefs}
              defaultColDef={{ resizable: true, sortable: true }}
              suppressCellFocus={false}
            />
          </div>
        </>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs font-sans text-ink-muted pt-2">
        <span className="font-mono">{total} total intents</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-2 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors rounded min-h-[44px]"
          >
            Previous
          </button>
          <span className="font-mono px-2">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={intents.length < 25}
            className="px-3 py-2 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors rounded min-h-[44px]"
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
                      ? 'TRIPPED'
                      : 'PASS'
                  } />
                </div>
              </div>
            )}
          </div>
        </Drawer>
      )}
    </div>
  )
}
