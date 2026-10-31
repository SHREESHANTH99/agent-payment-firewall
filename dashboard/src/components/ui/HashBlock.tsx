'use client'

import React, { useState } from 'react'
import { formatShortHash } from '@/lib/utils'
import { Check, Copy } from 'lucide-react'
import { cn } from '@/lib/utils'

export function HashBlock({ hash, label, className }: { hash: string; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!hash) return
    navigator.clipboard.writeText(hash)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      onClick={handleCopy}
      className={cn(
        'group inline-flex items-center gap-1.5 px-2 py-0.5 bg-paper-high border border-border cursor-pointer select-none hover:border-ink transition-colors',
        className
      )}
      title="Click to copy full SHA-256 hash"
    >
      {label && <span className="font-sans text-2xs uppercase text-ink-muted">{label}:</span>}
      <span className="font-mono text-2xs text-ink">{formatShortHash(hash)}</span>
      {copied ? (
        <Check className="w-3 h-3 text-forest" />
      ) : (
        <Copy className="w-3 h-3 text-ink-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </div>
  )
}
