'use client'

import { useEffect, useState, useMemo } from 'react'
import { api } from '@/lib/api'
import { IntentItem } from '@/types'
import { formatCents, formatDate, getStatusBadge } from '@/lib/utils'
import { useRealtime } from '@/hooks/useRealtime'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { X, ExternalLink, ShieldAlert, CheckCircle, Clock } from 'lucide-react'

export default function IntentsPage() {
  const [intents, setIntents] = useState<IntentItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [selectedIntent, setSelectedIntent] = useState<any | null>(null)
  const [showRawJson, setShowRawJson] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadIntents = async () => {
    try {
      const res = await api.getIntents({
        page,
        page_size: 25,
        status: statusFilter || undefined,
      })
      setIntents(res.items)
      setTotal(res.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useRealtime((event) => {
    if (event.type === 'intent_status_changed' || event.type === 'intent_created') {
      loadIntents()
    }
  })

  useEffect(() => {
    loadIntents()
  }, [page, statusFilter])

  const openDrawer = async (id: string) => {
    try {
      const detail = await api.getIntent(id)
      setSelectedIntent(detail)
      setShowRawJson(false)
    } catch (err: any) {
      alert(`Could not fetch intent details: ${err.message}`)
    }
  }

  const columnDefs = useMemo<ColDef[]>(
    () => [
      {
        headerName: 'Intent ID',
        field: 'id',
        width: 140,
        cellRenderer: (params: any) => (
          <span className="font-mono text-xs text-accent underline cursor-pointer">
            {params.value ? `${params.value.slice(0, 8)}...` : '-'}
          </span>
        ),
      },
      {
        headerName: 'Amount',
        field: 'amount',
        width: 110,
        valueFormatter: (p) => formatCents(p.value),
        cellStyle: { fontWeight: '600' },
      },
      {
        headerName: 'Currency',
        field: 'currency',
        width: 90,
      },
      {
        headerName: 'Merchant',
        field: 'merchant',
        width: 180,
      },
      {
        headerName: 'Status',
        field: 'status',
        width: 130,
        cellRenderer: (params: any) => {
          const { bg, label } = getStatusBadge(params.value || '')
          return (
            <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase ${bg}`}>
              {label}
            </span>
          )
        },
      },
      {
        headerName: 'Mandate ID',
        field: 'mandate_id',
        width: 140,
        cellRenderer: (p: any) => (
          <span className="font-mono text-xs text-muted-foreground">
            {p.value ? `${p.value.slice(0, 8)}...` : '-'}
          </span>
        ),
      },
      {
        headerName: 'Created At',
        field: 'created_at',
        flex: 1,
        valueFormatter: (p) => formatDate(p.value),
      },
    ],
    []
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Payment Intents</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit log of all autonomous payment attempts, risk evaluations, and execution states.
          </p>
        </div>

        {/* Filter controls */}
        <div className="flex items-center space-x-2">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            className="px-3 py-1.5 text-xs bg-card border border-border rounded focus:outline-none focus:border-accent"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="escalated">Escalated</option>
            <option value="executing">Executing</option>
            <option value="executed">Executed</option>
            <option value="denied">Denied</option>
            <option value="failed">Failed</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {/* AG Grid Table */}
      <div className="ag-theme-alpine-dark w-full h-[520px] rounded-lg border border-border overflow-hidden">
        <AgGridReact
          rowData={intents}
          columnDefs={columnDefs}
          onRowClicked={(event) => event.data?.id && openDrawer(event.data.id)}
          headerHeight={38}
          rowHeight={36}
          suppressCellFocus={true}
        />
      </div>

      {/* Pagination Footer */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Showing {intents.length} of {total} intents</span>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            Previous
          </button>
          <span>Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={intents.length < 25}
            className="px-3 py-1 border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      {/* Side Drawer for Details */}
      {selectedIntent && (
        <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-card border-l border-border shadow-2xl p-6 overflow-y-auto z-50">
          <div className="flex items-center justify-between pb-4 border-b border-border">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold">{formatCents(selectedIntent.amount)}</span>
                <span className="text-xs font-mono text-muted-foreground">{selectedIntent.currency}</span>
              </div>
              <span className="text-xs text-muted-foreground font-mono">ID: {selectedIntent.id}</span>
            </div>
            <button
              onClick={() => setSelectedIntent(null)}
              className="p-1.5 hover:bg-muted rounded"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-4 space-y-4 text-xs">
            {/* Status & Decision */}
            <div className="p-3 bg-muted/40 border border-border rounded flex justify-between items-center">
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Status</span>
                <span className="font-semibold uppercase text-sm mt-0.5 block">{selectedIntent.status}</span>
              </div>
              {selectedIntent.paypal_ref && (
                <div className="text-right">
                  <span className="text-muted-foreground block text-[10px] uppercase font-semibold">PayPal Batch ID</span>
                  <span className="font-mono text-xs">{selectedIntent.paypal_ref}</span>
                </div>
              )}
            </div>

            {/* Merchant & Reasoning */}
            <div className="space-y-1">
              <span className="font-semibold text-muted-foreground">Recipient Merchant:</span>
              <p className="font-mono bg-background p-2 border border-border rounded">{selectedIntent.merchant}</p>
            </div>

            <div className="space-y-1">
              <span className="font-semibold text-muted-foreground">Agent Reasoning:</span>
              <p className="bg-background p-2 border border-border rounded">
                {selectedIntent.reasoning || selectedIntent.description || 'None provided'}
              </p>
            </div>

            {/* AI Risk details */}
            <div className="space-y-2 pt-2 border-t border-border">
              <span className="font-semibold text-muted-foreground block">AI Risk Inspection Details:</span>
              <div className="p-3 bg-muted/30 border border-border rounded space-y-2">
                <div>
                  <span className="font-medium text-muted-foreground">Canary Honeypot:</span>
                  <div className="font-mono mt-0.5">
                    {selectedIntent.risk_details?.canary ? (
                      <span className={selectedIntent.risk_details.canary.tripped ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                        {selectedIntent.risk_details.canary.tripped ? 'TRIPPED (Honeypot Triggered)' : 'CLEAN'}
                      </span>
                    ) : (
                      'N/A'
                    )}
                  </div>
                </div>

                <div>
                  <span className="font-medium text-muted-foreground">Judge Evaluation:</span>
                  <div className="mt-0.5">
                    {selectedIntent.risk_details?.judge ? (
                      <div className="space-y-1">
                        <div>
                          Verdict: <span className="font-mono font-bold uppercase">{selectedIntent.risk_details.judge.verdict}</span> (Conf: {(selectedIntent.risk_details.judge.confidence * 100).toFixed(0)}%)
                        </div>
                        {selectedIntent.risk_details.judge.reasons?.length > 0 && (
                          <div className="text-muted-foreground">
                            Reasons: {selectedIntent.risk_details.judge.reasons.join(', ')}
                          </div>
                        )}
                      </div>
                    ) : (
                      'N/A'
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Cryptographic Audit Events Timeline */}
            <div className="space-y-2 pt-2 border-t border-border">
              <span className="font-semibold text-muted-foreground block">Linked Audit Trail:</span>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {(selectedIntent.audit_events || []).map((ev: any, idx: number) => (
                  <div key={idx} className="p-2 border border-border bg-background rounded font-mono text-[11px]">
                    <div className="flex justify-between text-muted-foreground">
                      <span className="text-accent font-semibold">{ev.event}</span>
                      <span>{formatDate(ev.created_at)}</span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1 truncate">Hash: {ev.hash}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Raw JSON toggle */}
            <div className="pt-2 border-t border-border">
              <button
                onClick={() => setShowRawJson(!showRawJson)}
                className="text-xs text-accent underline"
              >
                {showRawJson ? 'Hide Raw JSON' : 'View Raw JSON'}
              </button>
              {showRawJson && (
                <pre className="mt-2 p-3 bg-muted/60 border border-border rounded font-mono text-[10px] overflow-x-auto">
                  {JSON.stringify(selectedIntent, null, 2)}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
