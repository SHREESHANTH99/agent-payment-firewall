'use client'

import { useEffect, useState, useMemo } from 'react'
import { api } from '@/lib/api'
import { AuditItem } from '@/types'
import { formatDate } from '@/lib/utils'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { CheckCircle2, AlertOctagon, RefreshCw } from 'lucide-react'

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditItem[]>([])
  const [total, setTotal] = useState(0)
  const [limit, setLimit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<any | null>(null)

  const loadAudit = async () => {
    try {
      const res = await api.getAudit(limit, offset)
      setLogs(res.items)
      setTotal(res.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAudit()
  }, [offset, limit])

  const handleVerify = async () => {
    setVerifying(true)
    try {
      const res = await api.verifyChain()
      setVerifyResult(res)
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`)
    } finally {
      setVerifying(false)
    }
  }

  const columnDefs = useMemo<ColDef[]>(
    () => [
      {
        headerName: 'Event Type',
        field: 'event',
        width: 170,
        cellRenderer: (p: any) => (
          <span className="font-mono text-xs font-semibold text-accent">{p.value}</span>
        ),
      },
      {
        headerName: 'Intent ID',
        field: 'intent_id',
        width: 140,
        cellRenderer: (p: any) => (
          <span className="font-mono text-xs text-muted-foreground">
            {p.value ? `${p.value.slice(0, 8)}...` : '-'}
          </span>
        ),
      },
      {
        headerName: 'Block Hash',
        field: 'hash',
        width: 140,
        cellRenderer: (p: any) => (
          <span className="font-mono text-xs text-emerald-400">
            {p.value ? `${p.value.slice(0, 12)}...` : '-'}
          </span>
        ),
      },
      {
        headerName: 'Prev Hash',
        field: 'prev_hash',
        width: 140,
        cellRenderer: (p: any) => (
          <span className="font-mono text-xs text-muted-foreground">
            {p.value ? `${p.value.slice(0, 12)}...` : '-'}
          </span>
        ),
      },
      {
        headerName: 'Payload',
        field: 'payload',
        flex: 1,
        cellRenderer: (p: any) => (
          <span className="font-mono text-[11px] text-muted-foreground truncate block">
            {JSON.stringify(p.value)}
          </span>
        ),
      },
      {
        headerName: 'Timestamp',
        field: 'created_at',
        width: 170,
        valueFormatter: (p) => formatDate(p.value),
      },
    ],
    []
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Cryptographic Audit Chain</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Tamper-evident, linearly chained hash ledger verifying historical event sequencing and integrity.
          </p>
        </div>

        <button
          onClick={handleVerify}
          disabled={verifying}
          className="px-3.5 py-1.5 bg-accent text-accent-foreground text-xs font-semibold rounded flex items-center space-x-1.5 hover:opacity-90 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
          <span>{verifying ? 'Verifying Hashes...' : 'Verify Chain Integrity'}</span>
        </button>
      </div>

      {/* Verification Result Banner */}
      {verifyResult && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
            verifyResult.valid
              ? 'bg-emerald-950/40 text-emerald-200 border-emerald-800'
              : 'bg-rose-950/40 text-rose-200 border-rose-800'
          }`}
        >
          <div className="flex items-center space-x-2">
            {verifyResult.valid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertOctagon className="w-4 h-4 text-rose-400" />
            )}
            <span className="font-medium">
              {verifyResult.valid
                ? `Cryptographic chain valid! Verified ${verifyResult.checked} consecutive block hashes without discontinuity.`
                : `CHAIN INTEGRITY FAILURE: Discontinuity or tamper detected at block index ${verifyResult.first_broken_index}!`}
            </span>
          </div>
          <button onClick={() => setVerifyResult(null)} className="text-[11px] underline">Dismiss</button>
        </div>
      )}

      {/* AG Grid Hash Table */}
      <div className="ag-theme-alpine-dark w-full h-[520px] rounded-lg border border-border overflow-hidden">
        <AgGridReact
          rowData={logs}
          columnDefs={columnDefs}
          headerHeight={38}
          rowHeight={36}
          suppressCellFocus={true}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Total Logged Blocks: {total}</span>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setOffset((o) => Math.max(0, o - limit))}
            disabled={offset === 0}
            className="px-3 py-1 border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            Previous
          </button>
          <span>Offset {offset}</span>
          <button
            onClick={() => setOffset((o) => o + limit)}
            disabled={offset + limit >= total}
            className="px-3 py-1 border border-border rounded hover:bg-muted disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
