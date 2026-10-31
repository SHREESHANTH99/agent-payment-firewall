'use client'

import { useState, useEffect } from 'react'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime } from '@/hooks/useRealtime'
import { RiskConfig } from '@/types'
import { Button, Banner, Skeleton } from '@/components/ui'
import { Shield, Eye, Check } from 'lucide-react'

function ToggleCard({
  label,
  description,
  enabled,
  onToggle,
  saving,
}: {
  label: string
  description: string
  enabled: boolean
  onToggle: () => void
  saving: boolean
}) {
  return (
    <div className={`border ${enabled ? 'border-border' : 'border-amber/40'} bg-paper-low p-4 flex items-center justify-between gap-4`}>
      <div className="min-w-0">
        <p className="font-sans font-semibold text-sm text-ink">{label}</p>
        <p className="font-sans text-xs text-ink-muted mt-0.5">{description}</p>
      </div>
      <button
        onClick={onToggle}
        disabled={saving}
        className={`relative w-12 h-6 shrink-0 border transition-colors focus:outline-none focus:ring-1 focus:ring-ink ${
          enabled ? 'bg-forest border-forest' : 'bg-paper-highest border-border'
        }`}
        role="switch"
        aria-checked={enabled}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-0'}`}
        />
      </button>
    </div>
  )
}

export default function ControlsPage() {
  const [config, setConfig] = useState<RiskConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const demo = typeof window !== 'undefined' && isDemoMode()

  useRealtime((event) => {
    if (event.type === 'risk_config_changed') {
      setConfig({ canary_enabled: event.data.canary_enabled, judge_enabled: event.data.judge_enabled })
    }
  })

  useEffect(() => {
    activeApi.getRiskConfig()
      .then(setConfig)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleToggle = async (key: 'canary' | 'judge') => {
    if (!config) return
    const updated = {
      canary_enabled: key === 'canary' ? !config.canary_enabled : config.canary_enabled,
      judge_enabled: key === 'judge' ? !config.judge_enabled : config.judge_enabled,
    }
    setSaving(true)
    try {
      const res = await activeApi.updateRiskConfig(updated.canary_enabled, updated.judge_enabled)
      setConfig(res)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {}
    setSaving(false)
  }

  if (loading) return <Skeleton className="h-64" />

  const protectionsOff = !config?.canary_enabled || !config?.judge_enabled

  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h1 className="font-serif text-2xl text-ink">Risk controls</h1>
        <p className="font-sans text-xs text-ink-muted mt-0.5">
          Enable or disable the AI risk detection layers. Disabling either layer reduces detection coverage.
        </p>
      </div>

      {demo && (
        <Banner variant="info" title="Sample data">Changes apply to demo state only.</Banner>
      )}

      {protectionsOff && (
        <Banner variant="warning" title="Protections off">
          One or more AI risk inspection layers are currently disabled. Adversarial payment injection attacks may not be detected.
        </Banner>
      )}

      <div className="space-y-3">
        <ToggleCard
          label="Canary scanner"
          description="Injects honeypot tool definitions into the LLM context. If the agent calls them, it signals adversarial prompt injection. Fast and deterministic."
          enabled={config?.canary_enabled ?? true}
          onToggle={() => handleToggle('canary')}
          saving={saving}
        />
        <ToggleCard
          label="Risk judge"
          description="Sends the payment context to a secondary LLM with a structured adversarial injection detection prompt. Provides semantic analysis complementing the canary."
          enabled={config?.judge_enabled ?? true}
          onToggle={() => handleToggle('judge')}
          saving={saving}
        />
      </div>

      {saved && (
        <div className="flex items-center gap-2 text-xs text-forest font-sans">
          <Check className="w-3.5 h-3.5" />
          Configuration saved
        </div>
      )}

      <div className="border border-border bg-paper-low p-4 space-y-2 mt-4">
        <p className="font-sans font-semibold text-sm text-ink">About these controls</p>
        <p className="font-sans text-xs text-ink-muted leading-relaxed">
          The canary scanner is the primary fast-path defense. It costs one extra LLM tool slot per intent and
          adds negligible latency. The risk judge makes a separate LLM API call and adds latency proportional
          to the LLM response time. Together they provide layered defense: the canary catches direct token
          injection, the judge catches semantic manipulation. Both layers fail closed — if either is unavailable,
          the intent escalates rather than proceeding.
        </p>
      </div>
    </div>
  )
}
