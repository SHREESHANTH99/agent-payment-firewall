'use client'

import { useMemo, useState } from 'react'
import { AlertTriangle, Check, ChevronDown, ChevronRight, Copy, Loader2, Play, RotateCcw, Shield, WifiOff } from 'lucide-react'
import { Banner, Button, Stamp } from '@/components/ui'
import { useJudgePlayground } from '@/hooks/useJudgePlayground'
import { generateApiSnippets } from '@/lib/demoClient'
import type { AttackPreset, DemoAgentId, IntentRequest, IntentResult } from '@/lib/demoApi.types'
import { formatCents } from '@/lib/utils'

type Panel = 'setup' | 'attack' | 'firewall'
const fallbackIntent = (agent: DemoAgentId, mandateId: string): IntentRequest => ({
  agent_id: agent, mandate_id: mandateId, idempotency_key: `playground-${Date.now()}`,
  amount: '25.00', currency: 'USD', merchant: 'seller-one@example.test',
  description: 'Purchase requested by the user.',
  reasoning: 'The item and seller match the user task.',
  user_task: 'Buy the listed item from seller one.',
  source_context: 'The page lists the requested item from seller one.',
})

function SectionTitle({ children, eyebrow }: { children: React.ReactNode; eyebrow: string }) {
  return <div className="mb-4"><p className="font-mono text-xs uppercase tracking-widest text-vermilion">{eyebrow}</p><h2 className="font-serif text-2xl text-ink">{children}</h2></div>
}

function AgentCard({ agent, selected, onSelect }: { agent: NonNullable<ReturnType<typeof useJudgePlayground>['session']>['agents'][number]; selected: boolean; onSelect: () => void }) {
  return <button type="button" onClick={onSelect} className={`w-full text-left p-3 border ${selected ? 'border-vermilion bg-vermilion/5' : 'border-border bg-paper-low hover:border-ink/40'}`} aria-pressed={selected}>
    <div className="flex items-center justify-between"><span className="font-mono text-sm font-bold">AGENT {agent.id}</span><span className="text-xs text-ink-muted">{agent.mandate.status}</span></div>
    <p className="text-sm font-semibold mt-1">{agent.name}</p><p className="text-xs text-ink-muted">{agent.description}</p>
    <p className="text-xs text-ink-muted mt-2">Mandate <span className="font-mono text-ink">{agent.mandate.mandate_id}</span></p>
  </button>
}

function CheckpointStrip({ result }: { result: IntentResult | null }) {
  const canary = result?.risk.canary
  const judge = result?.risk.judge
  const verdicts = [
    ['Idempotency', 'NOT RECORDED'], ['Mandate & rules', result ? (result.reasons.some((r) => r.code === 'MANDATE_NOT_FOUND') ? 'DENIED' : 'PASS') : 'WAITING'],
    ['Atomic budget', result ? 'PASS' : 'WAITING'], ['Canary scan', canary ? (canary.tripped ? 'TRIPPED' : 'PASS') : 'NOT RECORDED'],
    ['Risk judge', judge ? judge.verdict.toUpperCase() : 'NOT RECORDED'], ['Decision & payout', result ? result.decision.toUpperCase() : 'WAITING'],
  ]
  return <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">{verdicts.map(([name, verdict], i) => <div key={name} className="border border-border bg-paper p-3 min-h-[86px]">
    <div className="flex justify-between"><span className="font-mono text-xs text-vermilion">0{i + 1}</span><Stamp verdict={verdict} /></div><p className="font-semibold text-sm mt-2">{name}</p>
  </div>)}</div>
}

function RiskDetails({ result }: { result: IntentResult | null }) {
  const [open, setOpen] = useState(false)
  if (!result) return <p className="text-sm text-ink-muted">Send an intent to inspect canary and judge evidence.</p>
  const reasons = [...(result.risk.judge?.reasons || []), ...(result.risk.judge?.mismatch_reasons || []), ...result.reasons.map((reason) => reason.message)]
  return <div className="border border-border">
    <button type="button" className="w-full flex items-center justify-between p-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}><span className="font-semibold text-sm">Risk details</span>{open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</button>
    {open && <div className="border-t border-border p-3 space-y-3">
      <div className="grid grid-cols-2 gap-3 text-xs"><div><p className="text-ink-muted">Canary</p><p className="font-mono">{result.risk.canary?.tripped ? 'TRIPPED' : result.risk.canary ? 'PASS' : 'NOT RECORDED'}</p></div><div><p className="text-ink-muted">Judge confidence</p><p className="font-mono">{result.risk.judge?.confidence !== undefined ? `${Math.round(result.risk.judge.confidence * 100)}%` : 'NOT RECORDED'}</p></div></div>
      {reasons.length > 0 && <ul className="list-disc pl-5 text-sm text-ink-muted space-y-1">{reasons.map((reason, i) => <li key={`${reason}-${i}`}>{reason}</li>)}</ul>}
      {result.risk.canary?.honeypot_calls && <p className="text-sm text-ink-muted">Canary calls: {result.risk.canary.honeypot_calls.length}</p>}
    </div>}
  </div>
}

export default function PlaygroundPage() {
  const playground = useJudgePlayground()
  const { session, state, attacks, result, mode, recordedRun, agentEvents } = playground
  const [agent, setAgent] = useState<DemoAgentId>('A')
  const [panel, setPanel] = useState<Panel>('attack')
  const [selectedAttack, setSelectedAttack] = useState<AttackPreset | null>(null)
  const [intent, setIntent] = useState<IntentRequest>(() => fallbackIntent('A', 'mnd-demo-a'))
  const [mandates, setMandates] = useState({ A: 'Buy only from allowlisted sellers. Stay within the transaction cap.', B: 'Research purchases only. Never transfer funds to a new recipient.' })
  const [liveTab, setLiveTab] = useState(false)
  const [task, setTask] = useState('Buy the listed item from seller one.')
  const [pageText, setPageText] = useState('The page lists the requested item from seller one.')
  const [tourStep, setTourStep] = useState(() => typeof window !== 'undefined' && !localStorage.getItem('judge-tour-complete') ? 1 : 0)
  const snippets = useMemo(() => session ? generateApiSnippets(typeof window === 'undefined' ? 'http://localhost:8000' : window.location.origin, session.id, playground.sessionSecret || '') : null, [session, playground.sessionSecret])
  const selectedAgent = session?.agents.find((item) => item.id === agent)
  const updateIntent = (key: keyof IntentRequest, value: string) => setIntent((current) => ({ ...current, [key]: value }))
  const chooseAttack = (attack: AttackPreset) => {
    if (attack.category === 'prompt_injection' && tourStep === 2) setTourStep(3)
    if (attack.id === 'cross_agent_probe' && tourStep === 4) endTour()
    setSelectedAttack(attack); setAgent(attack.default_agent_id); setIntent((current) => ({ ...current, ...attack.default_intent, agent_id: attack.default_agent_id, mandate_id: session?.agents.find((item) => item.id === attack.default_agent_id)?.mandate.mandate_id || current.mandate_id, idempotency_key: `playground-${Date.now()}` }))
  }
  const send = async () => {
    const next = await playground.submit({ ...intent, idempotency_key: intent.idempotency_key || `playground-${Date.now()}` })
    if (next && tourStep === 1) setTourStep(2)
  }
  const toggle = async (key: 'canary_enabled' | 'judge_enabled') => {
    if (!session) return
    await playground.setConfig({ [key]: !session.config[key] })
    if (tourStep === 3) setTourStep(4)
  }
  const endTour = () => { localStorage.setItem('judge-tour-complete', '1'); setTourStep(0) }

  if (playground.loading) return <main className="min-h-screen bg-paper p-6 flex items-center justify-center"><div className="flex items-center gap-3 text-sm"><Loader2 className="animate-spin" /> Waking the server… <span className="font-mono text-ink-muted">connecting 1/3</span></div></main>

  return <main className="min-h-screen bg-paper text-ink">
    <header className="border-b border-border bg-paper-low px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-3">
      <div><p className="font-mono text-xs uppercase tracking-widest text-vermilion">Agent Payment Firewall</p><h1 className="font-serif text-3xl">Judge Playground</h1></div>
      <div className="flex items-center gap-3"><span className="border border-amber/40 bg-amber/10 text-amber px-3 py-1 text-xs font-mono">{mode === 'RECORDED' ? 'RECORDED MODE' : 'LIVE MODE'}</span>{session && <span className="font-mono text-xs text-ink-muted">{state?.quota.remaining ?? session.quota.remaining} demo runs remaining</span>}</div>
    </header>
    <div className="px-4 sm:px-6 pt-4 space-y-3">
      <Banner variant="warning" title="Sandbox only">No real money. Demo mandates are forced to dry-run.</Banner>
      {mode === 'RECORDED' && <Banner variant="info" title="Recorded example"><span className="inline-flex items-center gap-1"><WifiOff size={14} /> {recordedRun?.title || 'Live demo unavailable'} — this page remains interactive with recorded evidence.</span></Banner>}
      {playground.error && mode !== 'RECORDED' && <Banner variant="danger" title="Demo unavailable">{playground.error}</Banner>}
    </div>
    <nav className="flex sm:hidden gap-1 px-4 pt-4" aria-label="Playground panels">{(['setup', 'attack', 'firewall'] as Panel[]).map((item) => <button key={item} type="button" onClick={() => setPanel(item)} className={`flex-1 border px-2 py-2 text-xs uppercase ${panel === item ? 'bg-ink text-paper' : 'border-border'}`}>{item}</button>)}</nav>
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(210px,0.8fr)_minmax(360px,1.5fr)_minmax(280px,1fr)] gap-4 p-4 sm:p-6">
      <aside className={`${panel !== 'setup' ? 'hidden sm:block' : ''} space-y-4`}>
        <SectionTitle eyebrow="01 / Setup">Who is paying?</SectionTitle>
        <div className="space-y-2">{session?.agents.map((item) => <AgentCard key={item.id} agent={item} selected={agent === item.id} onSelect={() => { setAgent(item.id); updateIntent('agent_id', item.id); updateIntent('mandate_id', item.mandate.mandate_id) }} />)}</div>
        <div className="border border-border bg-paper-low p-3 space-y-3"><div className="flex justify-between"><label htmlFor="mandate-a" className="font-semibold text-sm">Mandate editor</label><span className="text-xs text-ink-muted">local draft</span></div><textarea id="mandate-a" value={mandates[agent]} onChange={(event) => setMandates((current) => ({ ...current, [agent]: event.target.value }))} rows={4} className="w-full bg-paper border border-border p-2 text-sm" aria-label={`Mandate for agent ${agent}`} /><p className="text-xs text-ink-muted">The live API currently exposes mandate policy as read-only; this draft helps frame the judge task.</p></div>
        <div className="border border-border bg-paper-low p-3 space-y-3"><p className="font-semibold text-sm">Protections</p>{(['canary_enabled', 'judge_enabled'] as const).map((key) => <label key={key} className="flex items-center justify-between text-sm"><span>{key === 'canary_enabled' ? 'Canary scan' : 'Risk judge'}</span><input type="checkbox" checked={session?.config[key] ?? true} onChange={() => toggle(key)} aria-label={key} /></label>)}</div>
        <Button variant="secondary" size="sm" onClick={playground.reset}><RotateCcw size={14} className="mr-2" /> Reset session</Button>
      </aside>

      <section className={`${panel !== 'attack' ? 'hidden sm:block' : ''}`}>
        <div className="flex items-start justify-between gap-3"><SectionTitle eyebrow="02 / Try an attack">Make a payment request</SectionTitle><div className="flex border border-border"><button type="button" onClick={() => setLiveTab(false)} className={`px-3 py-2 text-xs ${!liveTab ? 'bg-ink text-paper' : ''}`}>Intent</button><button type="button" onClick={() => setLiveTab(true)} className={`px-3 py-2 text-xs ${liveTab ? 'bg-ink text-paper' : ''}`}>Live agent</button></div></div>
        {!liveTab ? <div className="space-y-4">
          <div className="flex flex-wrap gap-2" aria-label="Attack library">{['policy', 'prompt_injection', 'exfiltration', 'authorization', 'semantic_drift'].map((category) => <div key={category} className="contents">{attacks.filter((attack) => attack.category === category).map((attack) => <button type="button" key={attack.id} onClick={() => chooseAttack(attack)} className={`border px-3 py-2 text-xs ${selectedAttack?.id === attack.id ? 'border-vermilion bg-vermilion/10 text-vermilion' : 'border-border bg-paper-low hover:border-ink'}`}>{attack.name}</button>)}</div>)}</div>
          <div className="border border-border bg-paper-low p-4 space-y-3">
            <div className="grid sm:grid-cols-2 gap-3"><label className="text-sm">Amount<input value={intent.amount} onChange={(e) => updateIntent('amount', e.target.value)} className="field" inputMode="decimal" /></label><label className="text-sm">Currency<input value={intent.currency} onChange={(e) => updateIntent('currency', e.target.value)} className="field" /></label><label className="text-sm">Merchant<input value={intent.merchant} onChange={(e) => updateIntent('merchant', e.target.value)} className="field" /></label><label className="text-sm">Idempotency key<input value={intent.idempotency_key} onChange={(e) => updateIntent('idempotency_key', e.target.value)} className="field" /></label></div>
            <label className="text-sm block">Description<input value={intent.description} onChange={(e) => updateIntent('description', e.target.value)} className="field" /></label><label className="text-sm block">Reasoning<textarea value={intent.reasoning} onChange={(e) => updateIntent('reasoning', e.target.value)} rows={2} className="field" /></label><label className="text-sm block">User task<textarea value={intent.user_task} onChange={(e) => updateIntent('user_task', e.target.value)} rows={2} className="field" /></label><label className="text-sm block">Source context / untrusted page text<textarea value={intent.source_context} onChange={(e) => updateIntent('source_context', e.target.value)} rows={3} className="field" /></label>
            <fieldset><legend className="text-sm font-semibold mb-2">Target mandate</legend><div className="flex gap-2">{session?.agents.map((item) => <label key={item.id} className={`flex-1 border p-2 text-sm ${agent === item.id ? 'border-vermilion' : 'border-border'}`}><input type="radio" name="target-agent" checked={agent === item.id} onChange={() => { setAgent(item.id); updateIntent('agent_id', item.id); updateIntent('mandate_id', selectedAgent?.mandate.mandate_id || item.mandate.mandate_id) }} /> <span className="ml-2">Agent {item.id}{item.id !== intent.agent_id ? ' (other)' : ' (own)'}</span></label>)}</div></fieldset>
            <Button onClick={send} disabled={!session || mode === 'RECORDED'}><Play size={14} className="mr-2" /> Send intent</Button>
          </div>
        </div> : <div className="border border-border bg-paper-low p-4 space-y-4"><p className="text-sm text-ink-muted">Watch a sandbox agent browse a page, propose a payment, and receive the firewall verdict.</p><label className="text-sm block">Task<textarea value={task} onChange={(e) => setTask(e.target.value)} rows={3} className="field" /></label><label className="text-sm block">Store variant<select className="field" onChange={(e) => { const attack = attacks.find((item) => item.id === e.target.value); if (attack) { setSelectedAttack(attack); setPageText(attack.default_intent.source_context) } }}><option value="">Choose an attack variant</option>{attacks.map((attack) => <option value={attack.id} key={attack.id}>{attack.title}</option>)}</select></label><label className="text-sm block">Or type poisoned page text<textarea value={pageText} onChange={(e) => setPageText(e.target.value)} rows={5} className="field" /></label><Button onClick={() => playground.runAgent({ agent_id: agent, attack_id: selectedAttack?.id || 'prompt_injection', user_task: task, page_text: pageText })} disabled={!session || mode === 'RECORDED'}><Play size={14} className="mr-2" /> Watch agent</Button>{agentEvents.length > 0 && <ol className="border-t border-border pt-3 space-y-2">{agentEvents.map((event) => <li key={event.sequence} className="flex gap-2 text-sm"><span className="font-mono text-vermilion">{event.sequence}</span><span>{event.message}</span></li>)}</ol>}</div>}
      </section>

      <aside className={`${panel !== 'firewall' ? 'hidden sm:block' : ''} space-y-4`}>
        <SectionTitle eyebrow="03 / What the firewall did">Evidence, not guesses</SectionTitle>
        <CheckpointStrip result={result} />
        <div className="border border-border bg-paper-low p-4 flex items-center justify-between"><div><p className="text-xs text-ink-muted">Decision</p><p className="font-serif text-2xl">{result?.decision || 'WAITING'}</p></div><Stamp verdict={result?.decision === 'approved' ? 'APPROVED' : result?.decision === 'escalated' ? 'ESCALATED' : result ? 'BLOCKED' : 'WAITING'} /></div>
        {selectedAgent?.mandate.status === 'frozen' && <Banner variant="danger" title="Mandate frozen">{selectedAgent.mandate.freeze_reason || 'This mandate cannot make payments.'}</Banner>}
        {result?.decision === 'escalated' && <div className="border border-amber/40 bg-amber/10 p-3 flex gap-2"><Button size="sm" onClick={() => playground.escalation('approve')}>Approve</Button><Button size="sm" variant="danger" onClick={() => playground.escalation('reject')}>Reject</Button></div>}
        <RiskDetails result={result} />
        <div className="border border-border bg-paper-low p-3 space-y-2"><p className="font-semibold text-sm">Budget</p>{(selectedAgent ? [selectedAgent.mandate] : []).map((mandate) => <div key={mandate.mandate_id}><div className="flex justify-between text-xs"><span>Remaining</span><span className="font-mono">{formatCents(mandate.remaining_cents)}</span></div><div className="h-2 bg-paper-high mt-1"><div className="h-full bg-forest" style={{ width: `${Math.min(100, (mandate.remaining_cents / mandate.budget_total_cents) * 100)}%` }} /></div></div>)}</div>
        <div className="border border-border bg-paper-low p-3"><div className="flex justify-between items-center mb-2"><p className="font-semibold text-sm">Audit chain</p><button type="button" className="text-xs underline" onClick={() => alert('Chain verification is available from the live audit endpoint.')}>Verify chain</button></div>{result?.operatorView.new_audit_entries.map((entry) => <p key={entry.hash} className="font-mono text-xs break-all">{entry.event} · {entry.hash}</p>) || <p className="text-sm text-ink-muted">No response entries yet.</p>}</div>
      </aside>
    </div>
    <section className="border-t border-border px-4 sm:px-6 py-8 bg-paper-high"><div className="max-w-6xl mx-auto"><SectionTitle eyebrow="04 / Integrate">Use it as an API</SectionTitle><div className="grid lg:grid-cols-2 gap-4">{(['curl', 'python'] as const).map((kind) => <div key={kind} className="relative border border-border bg-ink text-paper p-4"><p className="font-mono text-xs text-paper/70 mb-2">{kind}</p><pre className="whitespace-pre-wrap break-words text-xs leading-relaxed">{snippets?.[kind] || 'Create a session to generate a snippet.'}</pre>{snippets && <button type="button" className="absolute top-3 right-3 text-paper/70 hover:text-paper" aria-label={`Copy ${kind} snippet`} onClick={() => navigator.clipboard?.writeText(snippets[kind])}><Copy size={15} /></button>}</div>)}</div><a className="inline-block mt-4 text-sm underline" href="/docs" target="_blank" rel="noreferrer">OpenAPI docs <ChevronRight className="inline" size={15} /></a></div></section>
    {tourStep > 0 && <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-6 sm:max-w-sm border border-vermilion bg-paper-low shadow-lg p-4 z-20"><div className="flex items-start gap-3"><Shield className="text-vermilion shrink-0" size={18} /><div><p className="font-semibold text-sm">Guided tour · step {tourStep} of 4</p><p className="text-sm text-ink-muted mt-1">{tourStep === 1 ? 'Send a normal purchase.' : tourStep === 2 ? 'Now send an injection from the attack library.' : tourStep === 3 ? 'Toggle protections off and repeat.' : 'Try agent A on agent B’s mandate.'}</p><button type="button" onClick={endTour} className="text-xs underline mt-3">Skip tour</button></div></div></div>}
  </main>
}
