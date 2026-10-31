'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { AuditItem } from '@/types'
import { formatDate, formatShortHash } from '@/lib/utils'
import { Button, Banner, Skeleton, EmptyState } from '@/components/ui'
import { HashBlock } from '@/components/ui/HashBlock'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { CheckCircle2, AlertOctagon, Loader2, Link2 } from 'lucide-react'

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<any | null>(null)
  const [animating, setAnimating] = useState(false)
  const demo = typeof window !== 'undefined' && isDemoMode()
  const LIMIT = 50

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await activeApi.getAudit(LIMIT, offset)
      setLogs(res.items)
      setTotal(res.total)
    } catch {}
    finally { setLoading(false) }
  }, [offset])

  useEffect(() => { load() }, [load])

  const handleVerify = async () => {
    setVerifying(true)
    setAnimating(true)
    try {
      const res = await activeApi.verifyChain()
      setVerifyResult(res)
    } catch (e: any) {
      setVerifyResult({ valid: false, error: e.message })
    }
    setVerifying(false)
    setTimeout(() => setAnimating(false), 1000)
  }

  const colDefs = useMemo<ColDef<AuditItem>[]>(() => [
    {
      headerName: 'ID', field: 'id', width: 100,
      cellRenderer: (p: any) => <span className="font-mono text-2xs">{p.value?.slice(0, 8)}…</span>,
    },
    { headerName: 'Event', field: 'event', flex: 1, minWidth: 140,
      cellRenderer: (p: any) => <span className="font-sans text-xs capitalize">{(p.value || '').replace(/_/g, ' ')}</span>,
    },
    {
      headerName: 'Intent', field: 'intent_id', width: 130,
      cellRenderer: (p: any) => <span className="font-mono text-2xs text-ink-muted">{p.value ? `${p.value.slice(0, 10)}…` : '—'}</span>,
    },
    {
      headerName: 'Hash', field: 'hash', width: 160,
      cellRenderer: (p: any) => <HashBlock hash={p.value} />,
    },
    {
      headerName: 'Prev hash', field: 'prev_hash', width: 160,
      cellRenderer: (p: any) => p.value ? <HashBlock hash={p.value} label="prev" /> : <span className="font-mono text-2xs text-ink-muted">genesis</span>,
    },
    {
      headerName: 'Created', field: 'created_at', width: 160,
      cellRenderer: (p: any) => <span className="font-mono text-2xs">{formatDate(p.value)}</span>,
    },
  ], [])

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-serif text-2xl text-ink">Audit chain</h1>
          <p className="font-sans text-xs text-ink-muted mt-0.5">
            SHA-256 hash-chained audit log stored in Postgres. Each entry references the previous entry's hash.
          </p>
        </div>
        <Button onClick={handleVerify} variant="secondary" className="flex items-center gap-2">
          {verifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />}
          Verify chain
        </Button>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">Sample audit entries — no real ledger data.</Banner>
      )}

      {/* Verify result */}
      {verifyResult && (
        <div className={`flex items-center gap-3 p-3 border text-sm ${verifyResult.valid ? 'border-forest bg-forest/5 text-forest' : 'border-vermilion bg-vermilion/5 text-vermilion'}`}>
          {verifyResult.valid
            ? <CheckCircle2 className="w-4 h-4 shrink-0" />
            : <AlertOctagon className="w-4 h-4 shrink-0" />}
          <span className="font-sans text-xs">
            {verifyResult.valid
              ? `Chain integrity verified — ${verifyResult.checked_count ?? logs.length} entries checked, all valid.`
              : `Chain integrity violation — first broken link at index ${verifyResult.first_broken_index ?? 'unknown'}.`}
          </span>
        </div>
      )}

      {/* Hash chain visualization */}
      {logs.length > 0 && (
        <div className="overflow-x-auto">
          <div className="flex items-center gap-0 pb-2 min-w-max">
            {logs.slice(0, 8).map((entry, i) => (
              <div key={entry.id} className="flex items-center">
                <div
                  className={`p-2 border ${animating ? 'border-forest bg-forest/5 transition-colors' : 'border-border bg-paper-low'} text-center min-w-[96px] transition-all duration-200`}
                  style={{ transitionDelay: animating ? `${i * 80}ms` : '0ms' }}
                >
                  <p className="font-mono text-2xs text-ink-muted truncate">{(entry.event || '').replace(/_/g, ' ')}</p>
                  <p className="font-mono text-2xs font-bold text-ink mt-0.5">{formatShortHash(entry.hash)}</p>
                </div>
                {i < Math.min(logs.length, 8) - 1 && (
                  <div className={`w-6 h-px ${animating ? 'bg-forest' : 'bg-border'} transition-colors`} style={{ transitionDelay: `${i * 80 + 40}ms` }} />
                )}
              </div>
            ))}
            {logs.length > 8 && (
              <div className="pl-2 font-mono text-2xs text-ink-muted">+{logs.length - 8} more</div>
            )}
          </div>
        </div>
      )}

      {/* AG Grid ledger */}
      {loading ? (
        <Skeleton className="h-64" />
      ) : logs.length === 0 ? (
        <EmptyState icon={Link2} title="No audit entries" description="The audit ledger is empty." />
      ) : (
        <div className="ag-theme-alpine border border-border" style={{ height: '400px' }}>
          <AgGridReact
            rowData={logs}
            columnDefs={colDefs}
            defaultColDef={{ resizable: true }}
          />
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs font-sans text-ink-muted">
        <span className="font-mono">{total} total entries</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
            disabled={offset === 0}
            className="px-2 py-1 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors"
          >
            Previous
          </button>
          <button
            onClick={() => setOffset((o) => o + LIMIT)}
            disabled={logs.length < LIMIT}
            className="px-2 py-1 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
