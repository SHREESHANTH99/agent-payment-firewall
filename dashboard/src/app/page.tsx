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
    <div className="border border-border bg-paper-low p-4 font-mono text-xs select-none" aria-label="Example: intent blocked by firewall">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-border">
        <div>
          <p className="font-sans text-2xs uppercase text-ink-muted">Example transaction</p>
          <p className="font-bold text-sm text-ink">$850.00 → dark-escrow-node.org</p>
        </div>
        <span className="px-1.5 py-0.5 bg-amber/10 border border-amber/30 text-amber text-2xs font-bold">INTERCEPTED</span>
      </div>
      <div className="space-y-2">
        {HERO_CHECKPOINTS.map((cp, i) => (
          <div
            key={cp.name}
            className={`flex items-center justify-between transition-all duration-200 ${i < visible ? 'opacity-100' : 'opacity-0'}`}
          >
            <span className="text-ink-muted text-2xs">{cp.name}</span>
            <StatusChip status={i < visible ? cp.status : 'pending'} />
          </div>
        ))}
      </div>
      {done && (
        <div className="mt-3 pt-2 border-t border-border flex items-center justify-between">
          <span className="text-2xs text-ink-muted">Settlement</span>
          <span className="px-2 py-0.5 border-2 border-vermilion text-vermilion font-bold text-sm tracking-widest">BLOCKED</span>
        </div>
      )}
      <p className="mt-2 text-2xs text-ink-muted font-sans">This is a recorded example. No real funds involved.</p>
    </div>
  )
}

// -- Interactive simulator ---------------------------------------------------
function Simulator({ scenarios }: { scenarios: Scenario[] }) {
  const [selected, setSelected] = useState(scenarios[0]?.id ?? '')
  const [firewallOn, setFirewallOn] = useState(true)
  const [running, setRunning] = useState(false)
  const [step, setStep] = useState(-1)
  const [done, setDone] = useState(false)

  const scenario = scenarios.find((s) => s.id === selected) ?? scenarios[0]
  const checkpoints = scenario?.firewall_on_checkpoints ?? []

  const run = useCallback(() => {
    if (running) return
    setRunning(true); setStep(-1); setDone(false)
    checkpoints.forEach((_, i) => {
      setTimeout(() => {
        setStep(i)
        if (i === checkpoints.length - 1) setTimeout(() => { setDone(true); setRunning(false) }, 350)
      }, i * 450)
    })
  }, [checkpoints, running])

  const reset = () => { setStep(-1); setDone(false); setRunning(false) }

  return (
    <div className="border border-border bg-paper-low p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="font-sans text-2xs uppercase text-ink-muted block mb-1">Scenario</label>
          <select
            value={selected}
            onChange={(e) => { setSelected(e.target.value); reset() }}
            className="font-sans text-xs bg-paper border border-border text-ink px-2 py-1.5 focus:outline-none"
          >
            {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name} — {s.tag}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="font-sans text-2xs uppercase text-ink-muted">Firewall</label>
          <button
            onClick={() => { setFirewallOn(!firewallOn); reset() }}
            className={`w-10 h-5 border relative transition-colors ${firewallOn ? 'bg-forest border-forest' : 'bg-paper-highest border-border'}`}
            role="switch"
            aria-checked={firewallOn}
          >
            <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white transition-transform ${firewallOn ? 'translate-x-5' : 'translate-x-0'}`} />
          </button>
          <span className="font-mono text-2xs text-ink-muted">{firewallOn ? 'On' : 'Off'}</span>
        </div>
        <button
          onClick={run}
          disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-vermilion text-white font-sans text-xs font-semibold hover:bg-ink transition-colors disabled:opacity-50"
        >
          <Play className="w-3 h-3" />
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
                  className={`flex items-center justify-between px-3 py-1.5 border transition-all duration-200 ${
                    i <= step ? 'border-border bg-paper' : 'border-dashed border-border/50 opacity-40'
                  }`}
                >
                  <span className={`font-sans text-xs ${i <= step ? 'text-ink' : 'text-ink-muted'}`}>{cp.name}</span>
                  <div className="flex items-center gap-2">
                    {i <= step && <StatusChip status={cp.status} />}
                    {i <= step && <span className="font-sans text-2xs text-ink-muted max-w-[200px] truncate">{cp.detail}</span>}
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
          { label: 'Combined detection rate', value: m ? `${(m.overall_detection_rates?.combined_defense * 100).toFixed(1)}%` : undefined },
          { label: 'False positive rate', value: m ? `${(m.false_positive_rates?.canary * 100).toFixed(1)}%` : undefined },
          { label: 'Benign cases', value: m?.sample_sizes?.benign_cases },
          { label: 'Injection cases', value: m?.sample_sizes?.injection_cases },
        ].map(({ label, value }) => (
          <div key={label} className="p-3 bg-paper-low border border-border">
            <p className="font-sans text-2xs uppercase text-ink-muted">{label}</p>
            <p className="font-mono text-lg font-bold text-ink mt-1">
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
                <span className="font-sans text-xs text-ink-muted w-40 shrink-0 capitalize">{cat.replace(/_/g, ' ')}</span>
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

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
    setMenuOpen(false)
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* Sticky nav */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-paper/95 backdrop-blur border-b border-border h-14 flex items-center">
        <div className="max-w-7xl mx-auto px-4 md:px-8 w-full flex items-center justify-between gap-4">
          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5">
            <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 shrink-0">
              <rect width="24" height="24" rx="3" fill="#E5391B" />
              <path d="M12 4 L20 7 V13 C20 17.5 16.5 20.5 12 22 C7.5 20.5 4 17.5 4 13 V7 Z" fill="white" />
              <path d="M12 7.5 L17.5 9.5 V12.5 C17.5 15.5 15 17.5 12 18.5 C9 17.5 6.5 15.5 6.5 12.5 V9.5 Z" fill="#E5391B" />
              <line x1="12" y1="10.5" x2="12" y2="13.5" stroke="white" strokeWidth="1.5" strokeLinecap="square" />
              <circle cx="12" cy="15.5" r="0.75" fill="white" />
            </svg>
            <div>
              <p className="font-sans font-bold text-xs uppercase tracking-wider text-ink">Gatekeeper</p>
              <p className="font-mono text-2xs text-ink-muted hidden sm:block">Payment firewall for AI</p>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden xl:flex items-center gap-5" aria-label="Sections">
            {SECTIONS.slice(1).map((id) => (
              <button
                key={id}
                onClick={() => scrollTo(id)}
                className={`font-sans text-xs uppercase tracking-wide transition-colors ${active === id ? 'text-vermilion font-semibold' : 'text-ink-muted hover:text-ink'}`}
              >
                {SECTION_LABELS[id]}
              </button>
            ))}
          </nav>

          {/* CTA */}
          <div className="flex items-center gap-2">
            <button onClick={toggle} className="p-2 text-ink-muted hover:text-ink transition-colors" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <a
              href="https://github.com/SHREESHANTH99/agent-payment-firewall"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 border border-border text-ink font-sans text-xs hover:bg-paper-high transition-colors"
            >
              <Github className="w-3.5 h-3.5" />
              GitHub
            </a>
            <Link
              href="/console?demo=1"
              className="px-3 py-1.5 border border-border bg-paper-high text-ink font-sans text-xs font-semibold hover:bg-paper-highest transition-colors"
            >
              Demo mode
            </Link>
            <Link
              href="/console/login"
              className="px-3 py-1.5 bg-vermilion text-white font-sans text-xs font-semibold hover:bg-ink transition-colors"
            >
              Sign in with token
            </Link>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="xl:hidden p-2 text-ink-muted hover:text-ink"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            >
              {menuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="xl:hidden fixed inset-0 z-40 bg-paper pt-14">
          <nav className="flex flex-col p-4 gap-1">
            {SECTIONS.map((id) => (
              <button
                key={id}
                onClick={() => scrollTo(id)}
                className="text-left px-3 py-2 font-sans text-sm text-ink hover:bg-paper-high transition-colors"
              >
                {SECTION_LABELS[id]}
              </button>
            ))}
          </nav>
        </div>
      )}

      <main className="pt-14">
        {/* 01 Hero */}
        <section id="hero" className="max-w-7xl mx-auto px-4 md:px-8 py-16 md:py-24">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left */}
            <div className="lg:col-span-6 flex flex-col gap-6">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-vermilion" />
                <span className="font-mono text-2xs uppercase tracking-widest text-ink-muted">Open source — MIT</span>
              </div>
              <h1 className="font-serif text-4xl md:text-5xl text-ink leading-tight">
                Let agents pay.<br />Not blindly.
              </h1>
              <p className="font-sans text-base text-ink-muted max-w-lg leading-relaxed">
                The open-source, deterministic payment firewall that intercepts autonomous agent transactions
                before settlement — through policy rules, atomic budget accounting, honeypot canary scanning, and LLM-based risk adjudication.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/console?demo=1"
                  className="inline-flex items-center gap-2 px-4 py-2.5 border border-border bg-paper-high text-ink font-sans text-sm font-semibold hover:bg-paper-highest transition-colors"
                >
                  Explore demo
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href="/console/login"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-vermilion text-white font-sans text-sm font-semibold hover:bg-ink transition-colors"
                >
                  Sign in with token
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
                <a
                  href="https://github.com/SHREESHANTH99/agent-payment-firewall"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2.5 border border-border text-ink font-sans text-sm hover:bg-paper-high transition-colors"
                >
                  <Github className="w-3.5 h-3.5" />
                  GitHub
                </a>
              </div>
            </div>

            {/* Right — animated ledger */}
            <div className="lg:col-span-6">
              <AnimatedLedger />
            </div>
          </div>
        </section>

        {/* Hairline divider */}
        <div className="border-t border-border" />

        {/* 02 Problem */}
        <section id="problem" className="bg-paper-low py-16">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-8">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">Why this exists</p>
              <h2 className="font-serif text-3xl text-ink">Autonomous payments fail silently.</h2>
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
                      <rect x="12" y="14" width="40" height="6" rx="1" fill="currentColor" className="text-ink-muted opacity-40" />
                      <rect x="12" y="24" width="56" height="4" rx="1" fill="currentColor" className="text-ink-muted opacity-25" />
                      <rect x="12" y="32" width="48" height="4" rx="1" fill="currentColor" className="text-ink-muted opacity-25" />
                      <rect x="12" y="42" width="56" height="8" rx="1" fill="currentColor" className="text-vermilion opacity-60" />
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
                      <circle cx="40" cy="30" r="8" fill="currentColor" className="text-vermilion opacity-30" />
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
                    <span className="font-mono text-3xl font-bold text-ink-muted opacity-30">{n}</span>
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
        <section id="attack" className="py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-8">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">Attack anatomy</p>
              <h2 className="font-serif text-3xl text-ink">How a prompt injection attack unfolds.</h2>
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
        <section id="simulator" className="bg-paper-low py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">Interactive</p>
              <h2 className="font-serif text-3xl text-ink">Run a scenario.</h2>
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
        <section id="architecture" className="py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">How it works</p>
              <h2 className="font-serif text-3xl text-ink">Six deterministic checkpoints.</h2>
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
        <section id="evidence" className="bg-paper-low py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">Calibration results</p>
              <h2 className="font-serif text-3xl text-ink">Empirically measured, honestly presented.</h2>
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
        <section id="preview" className="py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">Operator console</p>
              <h2 className="font-serif text-3xl text-ink">Full real-time governance console.</h2>
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
            <div className="mt-6 flex gap-3">
              <Link
                href="/console?demo=1"
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-vermilion text-white font-sans text-sm font-semibold hover:bg-ink transition-colors"
              >
                Open demo console
                <ExternalLink className="w-3.5 h-3.5" />
              </Link>
              <Link
                href="/console/login"
                className="inline-flex items-center gap-2 px-4 py-2.5 border border-border text-ink font-sans text-sm hover:bg-paper-high transition-colors"
              >
                Sign in with token
              </Link>
            </div>
          </div>
        </section>

        {/* 08 Open source */}
        <section id="open-source" className="bg-paper-high py-16 border-t border-border">
          <div className="max-w-7xl mx-auto px-4 md:px-8">
            <div className="mb-6">
              <p className="font-mono text-2xs uppercase tracking-widest text-vermilion mb-2">Open source</p>
              <h2 className="font-serif text-3xl text-ink">Free, auditable, self-hosted.</h2>
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
                  className="inline-flex items-center gap-2 px-4 py-2.5 border border-border text-ink font-sans text-sm hover:bg-paper-high transition-colors"
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
      <footer className="border-t border-border bg-paper py-6">
        <div className="max-w-7xl mx-auto px-4 md:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-sans text-ink-muted">
          <span>Agent Payment Firewall — MIT License</span>
          <div className="flex items-center gap-4">
            <a href="https://github.com/SHREESHANTH99/agent-payment-firewall" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">GitHub</a>
            <Link href="/console?demo=1" className="hover:text-ink transition-colors">Demo</Link>
            <Link href="/console/login" className="hover:text-ink transition-colors">Console</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
