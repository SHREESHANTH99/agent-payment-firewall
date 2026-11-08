'use client'

import Link from 'next/link'
import { useState, useEffect, useRef, useCallback } from 'react'
import { Sun, Moon, Menu, X, Github, ExternalLink, ChevronDown, Play, Square } from 'lucide-react'

// -- Types and helpers -------------------------------------------------
interface CalibrationData { metrics?: any; models?: any; timestamp?: string }
interface EvalData { metrics?: any; evaluated_model?: string; total_scenarios_evaluated?: number }
interface Scenario {
  id: string; name: string; tag: string; description: string
  firewall_on_checkpoints: Array<{ id: string; name: string; status: string; detail: string }>
  firewall_off_result: { status: string; amount_paid: string; detail: string }
  amount_cents: number; merchant: string; user_instruction?: string
}

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  useEffect(() => {
    const saved = (localStorage.getItem('apf_theme') as 'light' | 'dark') || 'light'
    setTheme(saved)
    document.documentElement.classList.toggle('dark', saved === 'dark')
  }, [])
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('apf_theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
  }
  return { theme, toggle }
}

function useScrollSpy(ids: string[]) {
  const [active, setActive] = useState(ids[0])
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setActive(e.target.id)
        }
      },
      { rootMargin: '-40% 0px -55% 0px' }
    )
    ids.forEach((id) => { const el = document.getElementById(id); if (el) obs.observe(el) })
    return () => obs.disconnect()
  }, [ids])
  return active
}

// -- CheckpointStatus chip --------------------------------------------------
function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    pass: 'text-forest bg-forest/10 border-forest/30',
    executed: 'text-forest bg-forest/10 border-forest/30',
    escalated: 'text-amber bg-amber/10 border-amber/30',
    blocked: 'text-vermilion bg-vermilion/10 border-vermilion/30',
    fail: 'text-vermilion bg-vermilion/10 border-vermilion/30',
    skip: 'text-ink-muted bg-paper-high border-border',
  }
  const cls = map[status] ?? 'text-ink-muted bg-paper-high border-border'
  return (
    <span className={`px-1.5 py-0.5 border font-mono text-2xs font-bold uppercase ${cls}`}>{status}</span>
  )
}

// -- Animated ledger card (hero right col) -----------------------------------
const HERO_CHECKPOINTS = [
  { name: '1. Idempotency', status: 'pass', ms: 400 },
  { name: '2. Mandate & rules', status: 'pass', ms: 800 },
  { name: '3. Atomic budget', status: 'pass', ms: 1200 },
  { name: '4. Canary scan', status: 'blocked', ms: 1600 },
  { name: '5. Risk judge', status: 'blocked', ms: 2000 },
]

function AnimatedLedger() {
  const [visible, setVisible] = useState(0)
  const [done, setDone] = useState(false)
  useEffect(() => {
    setVisible(0); setDone(false)
    const timers = HERO_CHECKPOINTS.map((cp, i) =>
      setTimeout(() => {
        setVisible((v) => v + 1)
        if (i === HERO_CHECKPOINTS.length - 1) setTimeout(() => setDone(true), 300)
      }, cp.ms)
    )
    const loop = setTimeout(() => { setVisible(0); setDone(false) }, 6000)
    return () => { timers.forEach(clearTimeout); clearTimeout(loop) }
  }, [])

  return (
    <div className="border border-border bg-paper-low p-4 font-mono text-xs select-none w-full overflow-hidden" aria-label="Example: intent blocked by firewall">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-border gap-2">
        <div className="min-w-0">
          <p className="font-sans text-2xs uppercase text-ink-muted truncate">Example transaction</p>
          <p className="font-bold text-sm text-ink truncate">$850.00 → dark-escrow-node.org</p>
        </div>
        <span className="px-1.5 py-0.5 bg-amber/10 border border-amber/30 text-amber text-2xs font-bold shrink-0">INTERCEPTED</span>
      </div>
      <div className="space-y-2">
        {HERO_CHECKPOINTS.map((cp, i) => (
          <div
            key={cp.name}
            className={`flex items-center justify-between py-1 transition-opacity duration-300 ${
              i < visible ? 'opacity-100' : 'opacity-20'
            }`}
          >
            <span className="text-ink-muted text-xs truncate mr-2">{cp.name}</span>
            {i < visible && <StatusChip status={cp.status} />}
          </div>
        ))}
      </div>
      {done && (
        <div className="mt-3 pt-2 border-t border-border flex items-center justify-between text-2xs text-vermilion">
          <span>STATUS: REJECTED</span>
          <span>CODE: CANARY_TRIGGERED</span>
        </div>
      )}
      <p className="mt-3 font-sans text-2xs text-ink-muted/70">
        This is a recorded example. No real funds involved.
      </p>
    </div>
  )
}

// -- Interactive Simulator ---------------------------------------------------
function Simulator({ scenarios }: { scenarios: Scenario[] }) {
  const [selectedId, setSelectedId] = useState(scenarios[0]?.id || '')
  const [firewallOn, setFirewallOn] = useState(true)
  const [running, setRunning] = useState(false)
  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)

  const scenario = scenarios.find((s) => s.id === selectedId) || scenarios[0]
  const checkpoints = scenario?.firewall_on_checkpoints || []

  const run = useCallback(() => {
    if (running) return
    setRunning(true)
    setStep(0)
    setDone(false)

    const stepInterval = 400
    checkpoints.forEach((_, i) => {
      setTimeout(() => {
        setStep(i + 1)
        if (i === checkpoints.length - 1) {
          setTimeout(() => {
            setDone(true)
            setRunning(false)
          }, 300)
        }
      }, (i + 1) * stepInterval)
    })
  }, [running, checkpoints])

  return (
    <div className="border border-border bg-paper p-4 md:p-6 space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-border">
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="scenario-select" className="font-sans text-xs font-medium text-ink-muted">
            Scenario:
          </label>
          <select
            id="scenario-select"
            value={selectedId}
            onChange={(e) => {
              setSelectedId(e.target.value)
              setStep(0)
              setDone(false)
            }}
            className="field text-xs py-1 px-2 border border-border bg-paper text-ink rounded"
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.tag})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer font-sans text-xs text-ink-muted">
            <input
              type="checkbox"
              checked={firewallOn}
              onChange={(e) => setFirewallOn(e.target.checked)}
              className="accent-vermilion min-w-[20px] min-h-[20px]"
            />
            <span>Firewall active</span>
          </label>
        </div>

        <button
          onClick={run}
          disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-vermilion text-white font-sans text-xs font-semibold hover:bg-ink transition-colors disabled:opacity-50 min-h-[44px]"
        >
          <Play className="w-3.5 h-3.5" />
          Run
        </button>
      </div>

      {scenario && (
        <div>
          <p className="font-sans text-2xs text-ink-muted mb-2">{scenario.description}</p>
          {!firewallOn ? (
            <div className="border border-amber/40 bg-amber/5 p-3 text-xs font-sans text-amber">
              Firewall disabled — payment would proceed to {scenario.merchant} without inspection.
              <br />
              <span className="font-bold">{scenario.firewall_off_result.detail}</span>
            </div>
          ) : (
            <div className="space-y-1.5">
              {checkpoints.map((cp, i) => (
                <div
                  key={cp.id}
                  className={`flex items-center justify-between px-3 py-2 border transition-all duration-200 ${
                    i <= step ? 'border-border bg-paper' : 'border-dashed border-border opacity-40'
                  }`}
                >
                  <span className={`font-sans text-xs ${i <= step ? 'text-ink' : 'text-ink-muted'}`}>{cp.name}</span>
                  <div className="flex items-center gap-2">
                    {i <= step && <StatusChip status={cp.status} />}
                    {i <= step && <span className="font-sans text-2xs text-ink-muted max-w-[140px] sm:max-w-[200px] truncate">{cp.detail}</span>}
                  </div>
                </div>
              ))}
              {done && (
                <div className={`flex items-center justify-between px-3 py-2 border-2 mt-2 ${
                  checkpoints.some((c) => ['blocked', 'fail'].includes(c.status))
                    ? 'border-vermilion bg-vermilion/5 text-vermilion'
                    : checkpoints.some((c) => c.status === 'escalated')
                    ? 'border-amber bg-amber/5 text-amber'
                    : 'border-forest bg-forest/5 text-forest'
                }`}>
                  <span className="font-sans text-xs font-bold uppercase tracking-wide">
                    {checkpoints.some((c) => ['blocked', 'fail'].includes(c.status)) ? 'Payment blocked'
                      : checkpoints.some((c) => c.status === 'escalated') ? 'Escalated for approval'
                      : 'Payment executed'}
                  </span>
                  <span className="font-mono text-xs font-bold tracking-widest">
                    {checkpoints.some((c) => ['blocked', 'fail'].includes(c.status)) ? 'BLOCKED'
                      : checkpoints.some((c) => c.status === 'escalated') ? 'ESCALATED'
                      : 'APPROVED'}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <p className="font-sans text-2xs text-ink-muted">Recorded example. All checkpoint states and timings are pre-authored.</p>
    </div>
  )
}

// -- Evidence section --------------------------------------------------------
function EvidenceSection({ calibration, eval: evalData }: { calibration: CalibrationData; eval: EvalData }) {
  const m = calibration.metrics
  const categories = m?.category_breakdown ? Object.entries(m.category_breakdown) : []

  const metric = (val: any, fallback = 'Not measured yet') =>
    val !== undefined && val !== null ? val : fallback

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Combined detection rate',
            value: m?.sample_sizes?.injection_cases && m.sample_sizes.injection_cases >= 10
              ? `${(m.overall_detection_rates?.combined_defense * 100).toFixed(1)}%`
              : m?.sample_sizes?.injection_cases ? `${m.sample_sizes.injection_cases} observed (insufficient sample)` : 'Not measured yet',
          },
          {
            label: 'False positive rate',
            value: m?.sample_sizes?.benign_cases && m.sample_sizes.benign_cases >= 10
              ? `${(m.false_positive_rates?.canary * 100).toFixed(1)}%`
              : m?.sample_sizes?.benign_cases ? `${m.sample_sizes.benign_cases} observed (insufficient sample)` : 'Not measured yet',
          },
          { label: 'Benign cases', value: m?.sample_sizes?.benign_cases },
          { label: 'Injection cases', value: m?.sample_sizes?.injection_cases },
        ].map(({ label, value }) => (
          <div key={label} className="p-3 bg-paper-low border border-border">
            <p className="font-sans text-2xs uppercase text-ink-muted">{label}</p>
            <p className="font-mono text-sm font-bold text-ink mt-1">
              {metric(value)}
            </p>
          </div>
        ))}
      </div>

      {categories.length > 0 && (
        <div>
          <p className="font-sans text-xs uppercase text-ink-muted mb-2">Detection by attack category</p>
          <div className="space-y-1.5">
            {categories.map(([cat, vals]: [string, any]) => (
              <div key={cat} className="flex items-center gap-3">
                <span className="font-sans text-xs text-ink-muted w-36 sm:w-40 shrink-0 capitalize truncate">{cat.replace(/_/g, ' ')}</span>
                <div className="flex-1 h-2 bg-paper-high overflow-hidden">
                  <div
                    className="h-full bg-forest transition-all"
                    style={{ width: `${(vals.combined_rate ?? 0) * 100}%` }}
                  />
                </div>
                <span className="font-mono text-2xs text-ink w-10 text-right">{((vals.combined_rate ?? 0) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border border-border bg-paper-low p-3 text-xs font-sans text-ink-muted space-y-1">
        <p>Model: <span className="font-mono text-ink">{calibration.models?.canary ?? evalData.evaluated_model ?? 'Not recorded'}</span></p>
        <p>Timestamp: <span className="font-mono text-ink">{calibration.timestamp ? new Date(calibration.timestamp).toLocaleDateString() : 'Not recorded'}</span></p>
        <p>Sample size: <span className="font-mono text-ink">{m?.sample_sizes?.total_benign_evaluations ?? evalData.total_scenarios_evaluated ?? 'Not recorded'}</span> evaluations</p>
        <p className="text-ink-muted">Detection rates are probabilistic estimates over a small sample. Results vary by model and attack type. LLM detection is not deterministic.</p>
      </div>
    </div>
  )
}

// -- Main landing component --------------------------------------------------
const SECTIONS = ['hero', 'problem', 'attack', 'simulator', 'architecture', 'evidence', 'preview', 'open-source']
const SECTION_LABELS: Record<string, string> = {
  hero: 'Introduction', problem: 'Problem', attack: 'Attack', simulator: 'Simulator',
  architecture: 'Architecture', evidence: 'Evidence', preview: 'Console', 'open-source': 'Open source',
}

export default function LandingPage() {
  const { theme, toggle } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const active = useScrollSpy(SECTIONS)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [calibration, setCalibration] = useState<CalibrationData>({})
  const [evalData, setEvalData] = useState<EvalData>({})

  useEffect(() => {
    fetch('/data/scenarios.json').then(r => r.json()).then(setScenarios).catch(() => {})
    fetch('/data/calibration.json').then(r => r.json()).then(setCalibration).catch(() => {})
    fetch('/data/eval.json').then(r => r.json()).then(setEvalData).catch(() => {})
  }, [])

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [menuOpen])

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
    setMenuOpen(false)
  }

  return (
    <div className="min-h-screen bg-paper text-ink overflow-x-hidden">
      {/* Sticky nav */}
      <header className="fixed top-0 left-0 right-0 z-header bg-paper/95 backdrop-blur border-b border-border h-14 flex items-center">
        <div className="max-w-7xl mx-auto px-4 md:px-8 w-full flex items-center justify-between gap-4">
          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5 shrink-0">
            <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 shrink-0">
              <rect width="24" height="24" rx="3" fill="#E5391B" />
              <path d="M12 4 L20 7 V13 C20 17.5 16.5 20.5 12 22 C7.5 20.5 4 17.5 4 13 Z" fill="white" />
              <path d="M12 7.5 L17.5 9.5 V12.5 C17.5 15.5 15 17.5 12 18.5 C9 17.5 6.5 15.5 6.5 12.5 V9.5 Z" fill="#E5391B" />
              <line x1="12" y1="10.5" x2="12" y2="13.5" stroke="white" strokeWidth="1.5" strokeLinecap="square" />
              <circle cx="12" cy="15.5" r="0.75" fill="white" />
            </svg>
            <div className="flex flex-col justify-center">
              <span className="font-sans font-bold text-xs uppercase tracking-wider text-ink leading-tight">Spendlatch</span>
              <span className="font-mono text-2xs text-ink-muted leading-tight hidden sm:block whitespace-nowrap">Settlement Interception for AI</span>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden xl:flex items-center gap-0.5" aria-label="Sections">
            {SECTIONS.slice(1).map((id) => (
              <button
                key={id}
                onClick={() => scrollTo(id)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors font-medium whitespace-nowrap ${
                  active === id
                    ? 'bg-paper-high text-ink font-semibold'
                    : 'text-ink-muted hover:text-ink hover:bg-paper-high/60'
                }`}
              >
                {SECTION_LABELS[id]}
              </button>
            ))}
          </nav>

          {/* Header Controls */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Theme toggle always visible */}
            <button
              onClick={toggle}
              className="w-9 h-9 rounded-md hover:bg-paper-high text-ink-muted hover:text-ink flex items-center justify-center transition-colors min-h-[44px] min-w-[44px]"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber" /> : <Moon className="w-4 h-4" />}
            </button>

            {/* Desktop only links */}
            <a
              href="https://github.com/SHREESHANTH99/agent-payment-firewall"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md hover:bg-paper-high text-ink-muted hover:text-ink font-sans text-xs font-medium transition-colors whitespace-nowrap"
            >
              <Github className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
            <Link
              href="/playground"
              className="hidden md:inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-paper-high hover:bg-paper-highest text-ink font-sans text-xs font-medium border border-border transition-colors whitespace-nowrap"
            >
              <span>Playground</span>
            </Link>
            <Link
              href="/console?demo=1"
              className="hidden md:inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-amber/10 hover:bg-amber/20 text-amber font-sans text-xs font-medium border border-amber/30 transition-colors whitespace-nowrap"
            >
              <span>Sample console</span>
            </Link>
            <Link
              href="/console/login"
              className="hidden md:inline text-xs text-ink-muted hover:text-ink transition-colors whitespace-nowrap px-1"
            >
              Sign in with token
            </Link>

            {/* Menu toggle for mobile and tablet (< 1280px) */}
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="xl:hidden w-9 h-9 rounded-md hover:bg-paper-high text-ink-muted hover:text-ink flex items-center justify-center transition-colors min-h-[44px] min-w-[44px]"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Full-screen Mobile Sheet for Navigation & CTAs */}
      {menuOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Mobile navigation"
          className="xl:hidden fixed inset-0 z-modal bg-paper flex flex-col pt-14 pb-safe-bottom overflow-y-auto"
        >
          <div className="flex-1 px-6 py-6 flex flex-col justify-between">
            {/* Section links */}
            <div>
              <p className="font-mono text-2xs uppercase tracking-wider text-ink-muted mb-3 font-semibold">
                Navigation
              </p>
              <nav className="flex flex-col space-y-1">
                {SECTIONS.map((id) => (
                  <button
                    key={id}
                    onClick={() => scrollTo(id)}
                    className="text-left py-3 px-3 rounded-lg font-sans text-base text-ink hover:bg-paper-high transition-colors min-h-[44px] flex items-center"
                  >
                    {SECTION_LABELS[id]}
                  </button>
                ))}
              </nav>
            </div>

            {/* CTAs in mobile menu */}
            <div className="pt-6 border-t border-border space-y-3 mt-6">
              <p className="font-mono text-2xs uppercase tracking-wider text-ink-muted mb-2 font-semibold">
                Get started
              </p>
              <Link
                href="/playground"
                onClick={() => setMenuOpen(false)}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-vermilion text-white font-sans text-sm font-semibold rounded shadow-xs min-h-[44px]"
              >
                Try the Playground
                <ExternalLink className="w-4 h-4" />
              </Link>
              <Link
                href="/console?demo=1"
                onClick={() => setMenuOpen(false)}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-amber/40 bg-amber/10 text-amber font-sans text-sm font-semibold rounded min-h-[44px]"
              >
                View sample console
              </Link>
              <Link
                href="/console/login"
                onClick={() => setMenuOpen(false)}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-border text-ink font-sans text-sm font-medium rounded hover:bg-paper-high min-h-[44px]"
              >
                Sign in with token
              </Link>
              <a
                href="https://github.com/SHREESHANTH99/agent-payment-firewall"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setMenuOpen(false)}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-ink-muted font-sans text-sm hover:text-ink min-h-[44px]"
              >
                <Github className="w-4 h-4" />
                View on GitHub
              </a>
            </div>
          </div>
        </div>
      )}

      <main className="pt-14">
        {/* 01 Hero */}
        <section id="hero" className="max-w-7xl mx-auto px-4 md:px-8 py-12 md:py-24">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left */}
            <div className="lg:col-span-6 flex flex-col gap-6">
              <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl text-ink leading-tight">
                Let agents pay.<br />Not blindly.
              </h1>
              <p className="font-sans text-sm sm:text-base text-ink-muted max-w-lg leading-relaxed">
                The open-source, policy-driven payment firewall that intercepts autonomous agent transactions
                before settlement — through policy rules, atomic budget accounting, honeypot canary scanning, and LLM-based risk adjudication.
              </p>

              {/* CTAs: stacked full width on phone in exact order */}
              <div className="flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-center gap-3">
                <Link
                  href="/playground"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 bg-vermilion text-white font-sans text-sm font-semibold hover:bg-ink transition-colors shadow-xs min-h-[44px]"
                >
                  Try the Playground
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href="/console?demo=1"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-3 border border-border bg-paper-high text-ink font-sans text-sm font-semibold hover:bg-paper-highest transition-colors min-h-[44px]"
                >
                  View sample console
                </Link>
                <a
                  href="https://github.com/SHREESHANTH99/agent-payment-firewall"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 py-2.5 px-3 text-ink-muted hover:text-ink font-sans text-sm underline sm:no-underline sm:border sm:border-border sm:hover:bg-paper-high transition-colors min-h-[44px]"
                >
                  <Github className="w-4 h-4" />
                  GitHub
                </a>
              </div>

              {/* Clean non-jagged meta chips */}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-mono text-ink-muted pt-1">
                <span>MIT Licensed</span>
                <span className="text-ink-muted/40">•</span>
                <span>Python 3.12 &amp; Next.js</span>
                <span className="text-ink-muted/40">•</span>
                <span>Sandbox Settlement</span>
              </div>
            </div>

            {/* Right — animated ledger */}
            <div className="lg:col-span-6 w-full">
              <AnimatedLedger />
            </div>
          </div>
        </section>

        {/* Hairline divider */}
        <div className="border-t border-border" />

        {/* 02 Problem */}
        <section id="problem" className="bg-paper-low py-12 md:py-16">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-8">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">Autonomous payments fail silently.</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                {
                  n: '01',
                  title: 'Agents have no spending conscience',
                  body: 'An autonomous agent with a payment credential acts on its context window. Poisoned context means poisoned intent. There is no native mechanism to verify whether a payment instruction reflects the user\'s real goal.',
                  svg: (
                    <svg viewBox="0 0 80 60" className="w-20 h-15 shrink-0" aria-hidden>
                      <rect x="4" y="4" width="72" height="52" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-border" />
                      <rect x="12" y="14" width="40" height="6" rx="1" fill="currentColor" className="text-ink-muted opacity-60" />
                      <rect x="12" y="24" width="56" height="4" rx="1" fill="currentColor" className="text-ink-muted opacity-45" />
                      <rect x="12" y="32" width="48" height="4" rx="1" fill="currentColor" className="text-ink-muted opacity-45" />
                      <rect x="12" y="42" width="56" height="8" rx="1" fill="currentColor" className="text-vermilion opacity-75" />
                    </svg>
                  ),
                },
                {
                  n: '02',
                  title: 'Prompt injection targets payments',
                  body: 'Hidden text, base64-encoded instructions, and social engineering can all divert a payment to an attacker-controlled destination. The attack surface is any content the agent reads before initiating a transaction.',
                  svg: (
                    <svg viewBox="0 0 80 60" className="w-20 h-15 shrink-0" aria-hidden>
                      <rect x="4" y="4" width="72" height="52" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-border" />
                      <path d="M8 16 Q40 8 72 16" stroke="currentColor" strokeWidth="1" className="text-forest opacity-60" fill="none" />
                      <circle cx="40" cy="30" r="8" fill="currentColor" className="text-vermilion opacity-50" />
                      <path d="M36 26 L44 34 M44 26 L36 34" stroke="currentColor" strokeWidth="2" strokeLinecap="square" className="text-vermilion" />
                    </svg>
                  ),
                },
                {
                  n: '03',
                  title: 'No audit trail, no rollback',
                  body: 'Corporate card tokens and instant payouts leave no tamper-evident history. When an unauthorized payment completes, attribution and recovery are difficult. Every decision should be hashable, inspectable, and immutable.',
                  svg: (
                    <svg viewBox="0 0 80 60" className="w-20 h-15 shrink-0" aria-hidden>
                      <rect x="4" y="24" width="20" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-border" />
                      <rect x="30" y="20" width="20" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-border" />
                      <rect x="56" y="28" width="20" height="10" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-border" />
                      <line x1="24" y1="31" x2="30" y2="31" stroke="currentColor" strokeWidth="1" className="text-amber" />
                      <line x1="50" y1="31" x2="56" y2="31" stroke="currentColor" strokeWidth="1" className="text-amber" />
                      <path d="M60 16 L64 12 L72 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" fill="none" className="text-vermilion" />
                    </svg>
                  ),
                },
              ].map(({ n, title, body, svg }) => (
                <div key={n} className="p-5 border border-border bg-paper flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-3xl font-bold text-ink-muted/60">{n}</span>
                    {svg}
                  </div>
                  <h3 className="font-sans font-semibold text-sm text-ink">{title}</h3>
                  <p className="font-sans text-xs text-ink-muted leading-relaxed">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 03 Attack story */}
        <section id="attack" className="py-12 md:py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-8">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">How a prompt injection attack unfolds.</h2>
              <p className="font-sans text-sm text-ink-muted mt-2 max-w-xl">
                From a poisoned web page to a blocked settlement — the four stages of an intercept.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { step: '01', title: 'Poisoned page', caption: 'A page the agent fetches contains hidden malicious instructions in the DOM.', src: '/illustrations/step1-poisoned-page.svg', alt: 'SVG showing a web page with hidden malicious HTML text' },
                { step: '02', title: 'Agent reads it', caption: 'The injected text enters the agent context and overrides the user instruction.', src: '/illustrations/step2-agent-reads.svg', alt: 'SVG showing agent context window with injected prompt' },
                { step: '03', title: 'Canary trips', caption: 'The canary scanner detects delimiter-breaking tokens. The risk judge flags semantic diversion.', src: '/illustrations/step3-canary-trips.svg', alt: 'SVG showing canary honeypot alert triggered' },
                { step: '04', title: 'Payment blocked', caption: 'Settlement halted. Mandate auto-frozen. Event recorded in the hash-chained audit ledger.', src: '/illustrations/step4-payment-blocked.svg', alt: 'SVG showing blocked payment stamp in audit ledger' },
              ].map(({ step, title, caption, src, alt }) => (
                <div key={step} className="flex flex-col border border-border bg-paper-low overflow-hidden">
                  <img src={src} alt={alt} className="w-full h-auto border-b border-border" loading="lazy" />
                  <div className="p-4 flex flex-col gap-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-2xs text-vermilion font-bold">{step}</span>
                      <span className="h-px flex-1 bg-border" />
                    </div>
                    <h3 className="font-sans font-semibold text-sm text-ink">{title}</h3>
                    <p className="font-sans text-xs text-ink-muted leading-relaxed">{caption}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 04 Interactive simulator */}
        <section id="simulator" className="bg-paper-low py-12 md:py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">Run a scenario.</h2>
              <p className="font-sans text-sm text-ink-muted mt-2">
                Select an attack scenario, toggle the firewall, and watch the checkpoint pipeline animate in order.
              </p>
            </div>
            {scenarios.length > 0
              ? <Simulator scenarios={scenarios} />
              : <div className="p-8 text-center font-sans text-xs text-ink-muted border border-dashed border-border">Loading scenarios…</div>
            }
          </div>
        </section>

        {/* 05 Architecture */}
        <section id="architecture" className="py-12 md:py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">Six deterministic checkpoints.</h2>
              <p className="font-sans text-sm text-ink-muted mt-2 max-w-xl">
                Every payment intent passes through the full pipeline, in order. No shortcut. No bypass.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[
                { n: 1, name: 'Idempotency check', detail: 'Atomic Redis SETNX deduplication. Replays from crashed agents never create duplicate payments.' },
                { n: 2, name: 'Mandate & policy rules', detail: 'Deterministic checks: mandate status, merchant allowlist, currency, transaction cap, period budget, validity window.' },
                { n: 3, name: 'Atomic budget reservation', detail: 'Redis INCR/DECR with compare-and-swap ensures no two concurrent requests overdraw the same mandate budget.' },
                { n: 4, name: 'Canary scanner', detail: 'Honeypot tool definitions injected into the LLM tool list. If the agent calls them, prompt injection is confirmed. Zero LLM calls required.' },
                { n: 5, name: 'LLM risk judge', detail: 'Separate LLM call with a structured adversarial injection detection prompt. Provides semantic analysis beyond token-level canary detection.' },
                { n: 6, name: 'Decision & payout', detail: 'Approved: PayPal Payouts (sandbox). Escalated: held in Redis, sent to operator via WebSocket. Blocked: mandate may auto-freeze.' },
              ].map(({ n, name, detail }) => (
                <div key={n} className="p-4 border border-border bg-paper-low">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="w-7 h-7 border-2 border-vermilion text-vermilion font-mono text-xs font-bold flex items-center justify-center shrink-0">{n}</span>
                    <h3 className="font-sans font-semibold text-sm text-ink">{name}</h3>
                  </div>
                  <p className="font-sans text-xs text-ink-muted leading-relaxed">{detail}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 06 Evidence */}
        <section id="evidence" className="bg-paper-low py-12 md:py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">Empirically measured, honestly presented.</h2>
              <p className="font-sans text-sm text-ink-muted mt-2 max-w-xl">
                Results from the calibration harness. Detection is probabilistic. Sample sizes are shown. No figures are invented.
              </p>
            </div>
            {calibration.metrics
              ? <EvidenceSection calibration={calibration} eval={evalData} />
              : <div className="p-8 text-center font-sans text-xs text-ink-muted border border-dashed border-border">Evidence data not yet generated. Run the calibration harness to populate.</div>
            }
          </div>
        </section>

        {/* 07 Console preview */}
        <section id="preview" className="py-12 md:py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">Full real-time governance console.</h2>
              <p className="font-sans text-sm text-ink-muted mt-2 max-w-xl">
                Overview, approval queue, intent ledger, mandates, audit chain, and risk controls — all live over WebSocket.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { label: 'Overview', desc: '5 KPIs, live event feed, pipeline strip, decision chart.' },
                { label: 'Approvals queue', desc: 'Escalated intents with risk stamps, expiry countdowns, and Approve / Reject actions.' },
                { label: 'Audit chain', desc: 'SHA-256 hash-chained ledger with visual link verification.' },
              ].map(({ label, desc }) => (
                <div key={label} className="border border-border bg-paper-low p-5 flex flex-col gap-2">
                  <p className="font-sans font-semibold text-sm text-ink">{label}</p>
                  <p className="font-sans text-xs text-ink-muted leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <Link
                href="/playground"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-vermilion text-white font-sans text-sm font-semibold hover:bg-ink transition-colors min-h-[44px]"
              >
                Open demo console
                <ExternalLink className="w-3.5 h-3.5" />
              </Link>
              <Link
                href="/console/login"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 border border-border text-ink font-sans text-sm hover:bg-paper-high transition-colors min-h-[44px]"
              >
                Sign in with token
              </Link>
            </div>
          </div>
        </section>

        {/* 08 Open source */}
        <section id="open-source" className="bg-paper-high py-12 md:py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl sm:text-3xl text-ink">Free, auditable, self-hosted.</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-4">
                <p className="font-sans text-sm text-ink-muted leading-relaxed">
                  MIT licensed. Run entirely on your infrastructure. No vendor lock-in. The PayPal integration is sandbox-only by default — plug in production credentials when you are ready.
                </p>
                <a
                  href="https://github.com/SHREESHANTH99/agent-payment-firewall"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2.5 border border-border text-ink font-sans text-sm hover:bg-paper-high transition-colors min-h-[44px]"
                >
                  <Github className="w-4 h-4" />
                  View on GitHub
                </a>
              </div>
              <div>
                <p className="font-sans text-2xs uppercase text-ink-muted mb-2">Quick start</p>
                <pre className="bg-ink text-paper p-4 font-mono text-xs leading-relaxed overflow-x-auto">
{`git clone https://github.com/SHREESHANTH99/agent-payment-firewall
cd agent-payment-firewall
cp .env.example .env
docker compose up --build`}
                </pre>
                <p className="font-sans text-2xs text-ink-muted mt-2">
                  Sandbox only. The PayPal Payouts integration targets the sandbox endpoint by default. No real money is moved.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-paper py-6 pb-safe-bottom">
        <div className="max-w-7xl mx-auto px-4 md:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-sans text-ink-muted">
          <span>Spendlatch — MIT License</span>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <a href="https://github.com/SHREESHANTH99/agent-payment-firewall" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors min-h-[44px] flex items-center">GitHub</a>
            <Link href="/playground" className="hover:text-ink transition-colors min-h-[44px] flex items-center">Playground</Link>
            <Link href="/console?demo=1" className="hover:text-ink transition-colors min-h-[44px] flex items-center">Sample console</Link>
            <Link href="/console/login" className="hover:text-ink transition-colors min-h-[44px] flex items-center">Sign in with token</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
