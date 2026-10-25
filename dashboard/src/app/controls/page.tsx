'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { RiskConfig } from '@/types'
import { useRealtime } from '@/hooks/useRealtime'
import { Shield, ShieldAlert, Cpu, Eye, Check } from 'lucide-react'

export default function ControlsPage() {
  const [config, setConfig] = useState<RiskConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const loadConfig = async () => {
    try {
      const cfg = await api.getRiskConfig()
      setConfig(cfg)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useRealtime((event) => {
    if (event.type === 'risk_config_changed') {
      setConfig({
        canary_enabled: event.data.canary_enabled,
        judge_enabled: event.data.judge_enabled,
      })
    }
  })

  useEffect(() => {
    loadConfig()
  }, [])

  const handleToggle = async (key: 'canary' | 'judge') => {
    if (!config) return
    const updatedCanary = key === 'canary' ? !config.canary_enabled : config.canary_enabled
    const updatedJudge = key === 'judge' ? !config.judge_enabled : config.judge_enabled

    setSaving(true)
    try {
      const newCfg = await api.updateRiskConfig(updatedCanary, updatedJudge)
      setConfig(newCfg)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: any) {
      alert(`Failed to update risk config: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-xs text-muted-foreground">Loading risk controls...</div>
  }

  const isProtectionsOff = !config?.canary_enabled || !config?.judge_enabled

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold tracking-tight">AI Risk & Security Controls</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Runtime switches for prompt-injection canary scanners and contextual LLM judge policies.
        </p>
      </div>

      {isProtectionsOff && (
        <div className="p-4 bg-amber-950/40 border border-amber-800 rounded-lg flex items-center space-x-3 text-xs text-amber-200">
          <ShieldAlert className="w-5 h-5 text-amber-400 flex-shrink-0" />
          <div>
            <span className="font-bold block">PROTECTIONS PARTIALLY OR FULLY DISABLED</span>
            <span className="text-[11px] text-amber-300">
              One or more AI risk inspection engines are turned off. Intent payloads will bypass respective guardrails.
            </span>
          </div>
        </div>
      )}

      {saveSuccess && (
        <div className="p-3 bg-emerald-950/40 border border-emerald-800 rounded-lg flex items-center space-x-2 text-xs text-emerald-200">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>Risk configuration updated and recorded to immutable audit log.</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Canary Switch */}
        <div className="p-5 border border-border bg-card rounded-lg space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-accent" />
              <h2 className="text-sm font-semibold">Honeypot Canary Scanner</h2>
            </div>
            <button
              onClick={() => handleToggle('canary')}
              disabled={saving}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                config?.canary_enabled ? 'bg-accent' : 'bg-muted'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  config?.canary_enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <p className="text-xs text-muted-foreground">
            Scans untrusted source text by exposing harmless honeypot tool traps. Any execution attempts trip the canary and freeze the mandate.
          </p>

          <div className="pt-3 border-t border-border flex justify-between text-[11px] text-muted-foreground">
            <span>Status:</span>
            <span className={`font-semibold ${config?.canary_enabled ? 'text-emerald-400' : 'text-amber-400'}`}>
              {config?.canary_enabled ? 'ACTIVE & PROTECTING' : 'BYPASSED'}
            </span>
          </div>
        </div>

        {/* Judge Switch */}
        <div className="p-5 border border-border bg-card rounded-lg space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Eye className="w-5 h-5 text-accent" />
              <h2 className="text-sm font-semibold">Contextual LLM Judge</h2>
            </div>
            <button
              onClick={() => handleToggle('judge')}
              disabled={saving}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                config?.judge_enabled ? 'bg-accent' : 'bg-muted'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  config?.judge_enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <p className="text-xs text-muted-foreground">
            Evaluates goal drift, urgency/coercion markers, and intent-merchant semantic alignment before approving payouts.
          </p>

          <div className="pt-3 border-t border-border flex justify-between text-[11px] text-muted-foreground">
            <span>Status:</span>
            <span className={`font-semibold ${config?.judge_enabled ? 'text-emerald-400' : 'text-amber-400'}`}>
              {config?.judge_enabled ? 'ACTIVE & PROTECTING' : 'BYPASSED'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
