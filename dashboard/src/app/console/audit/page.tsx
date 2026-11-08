'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { activeApi } from '@/lib/activeApi'
import { useDemoMode } from '@/hooks/useDemoMode'
import { AuditItem } from '@/types'
import { formatDate, formatShortHash } from '@/lib/utils'
import { Button, Banner, Skeleton, EmptyState } from '@/components/ui'
import { HashBlock } from '@/components/ui/HashBlock'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { CheckCircle2, AlertOctagon, Loader2, Link2, Copy, Check } from 'lucide-react'

function CopyHash({ hash }: { hash?: string | null }) {
  const [copied, setCopied] = useState(false)
  if (!hash) return <span className="font-mono text-2xs text-ink-muted">genesis</span>

  const handleCopy = () => {
    navigator.clipboard.writeText(hash)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex items-center gap-1 font-mono text-xs text-ink">
      <span>{hash.slice(0, 10)}…{hash.slice(-6)}</span>
      <button
        onClick={handleCopy}
        className="p-1 text-ink-muted hover:text-ink min-h-[36px] min-w-[36px] flex items-center justify-center"
        aria-label="Copy full hash"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-forest" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </div>
  )
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<any | null>(null)
  const [animating, setAnimating] = useState(false)
  const demo = useDemoMode()
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
        <Button onClick={handleVerify} variant="secondary" className="flex items-center gap-2 min-h-[44px]">
          {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
          <span>Verify chain</span>
        </Button>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">Sample audit entries &mdash; no real ledger data.</Banner>
      )}

      {/* Verify result */}
      {verifyResult && (
        <div className={`flex items-center gap-3 p-3 border text-sm ${verifyResult.valid ? 'border-forest bg-forest/5 text-forest' : 'border-vermilion bg-vermilion/5 text-vermilion'}`}>
          {verifyResult.valid
            ? <CheckCircle2 className="w-4 h-4 shrink-0" />
            : <AlertOctagon className="w-4 h-4 shrink-0" />}
          <span className="font-sans font-medium">
            {verifyResult.valid
              ? `Chain verified valid (${verifyResult.entries_checked ?? logs.length} blocks checked, 0 broken links)`
              : `Chain verification failed: ${verifyResult.error ?? 'Broken hash link detected'}`}
          </span>
        </div>
      )}

      {loading ? (
        <Skeleton className="h-64" />
      ) : logs.length === 0 ? (
        <EmptyState icon={Link2} title="No audit entries" description="The hash chain is currently empty." />
      ) : (
        <>
          {/* Mobile Card List View (< 768px) */}
          <div className="md:hidden space-y-3">
            {logs.map((item) => (
              <div
                key={item.id}
                className="p-4 bg-paper-low border border-border rounded-lg space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-sans text-sm font-semibold capitalize text-ink">
                    {(item.event || '').replace(/_/g, ' ')}
                  </span>
                  <span className="font-mono text-2xs text-ink-muted">
                    {formatDate(item.created_at)}
                  </span>
                </div>
                {item.intent_id && (
                  <p className="font-mono text-2xs text-ink-muted truncate">
                    Intent: {item.intent_id}
                  </p>
                )}
                <div className="pt-2 border-t border-border/50 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-2xs font-mono uppercase text-ink-muted">Hash:</span>
                    <CopyHash hash={item.hash} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-2xs font-mono uppercase text-ink-muted">Prev:</span>
                    <CopyHash hash={item.prev_hash} />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop AG Grid (>= 768px) */}
          <div className="hidden md:block ag-theme-alpine border border-border" style={{ height: '480px' }}>
            <AgGridReact
              rowData={logs}
              columnDefs={colDefs}
              defaultColDef={{ resizable: true, sortable: true }}
              suppressCellFocus={false}
            />
          </div>
        </>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs font-sans text-ink-muted pt-2">
        <span className="font-mono">{total} total entries</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
            disabled={offset === 0}
            className="px-3 py-2 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors rounded min-h-[44px]"
          >
            Previous
          </button>
          <button
            onClick={() => setOffset((o) => o + LIMIT)}
            disabled={offset + LIMIT >= total}
            className="px-3 py-2 border border-border hover:bg-paper-high disabled:opacity-40 transition-colors rounded min-h-[44px]"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
