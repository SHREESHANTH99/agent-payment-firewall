'use client'

import { useCallback, useEffect, useState } from 'react'
import type { DemoConfig, IntentRequest, IntentResult } from '@/lib/demoApi.types'
import {
  actOnEscalation, createDemoSession, getAttackPresets, getDemoState, loadRecordedRun,
  readAgentEvents, startAgentRun, submitDemoIntent, updateDemoConfig,
  type PlaygroundMode, type PlaygroundState, type RecordedRun,
} from '@/lib/demoClient'

const initialState: PlaygroundState = {
  mode: 'LIVE', session: null, sessionSecret: null, state: null, attacks: [],
  recordedRun: null, loading: true, waking: false, error: null,
}

export function useJudgePlayground() {
  const [playground, setPlayground] = useState<PlaygroundState>(initialState)
  const [result, setResult] = useState<IntentResult | null>(null)
  const [agentEvents, setAgentEvents] = useState<import('@/lib/demoApi.types').AgentRunEvent[]>([])

  const fallback = useCallback(async (error: unknown) => {
    const recordedRun = await loadRecordedRun()
    setPlayground((current) => ({ ...current, mode: 'RECORDED', waking: false, recordedRun, error: error instanceof Error ? error.message : 'Live demo unavailable.' }))
  }, [])

  const refresh = useCallback(async (id: string, secret: string) => {
    const state = await getDemoState(id, secret)
    setPlayground((current) => ({ ...current, state: state.session, session: state.session }))
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([createDemoSession({ scenario: 'clean_purchase' }), getAttackPresets()])
      .then(async ([created, attacks]) => {
        if (!active) return
        setPlayground((current) => ({ ...current, session: created.session, sessionSecret: created.session_secret, attacks, loading: false, waking: false }))
        await refresh(created.session.id, created.session_secret)
      })
      .catch(async (error) => {
        if (active) await fallback(error)
        if (active) setPlayground((current) => ({ ...current, loading: false }))
      })
    return () => { active = false }
  }, [fallback, refresh])

  const submit = useCallback(async (intent: IntentRequest) => {
    if (!playground.session || !playground.sessionSecret) return null
    try {
      const next = await submitDemoIntent(playground.session.id, playground.sessionSecret, intent)
      setResult(next)
      await refresh(playground.session.id, playground.sessionSecret)
      return next
    } catch (error) {
      await fallback(error)
      return null
    }
  }, [fallback, playground.session, playground.sessionSecret, refresh])

  const setConfig = useCallback(async (config: Partial<DemoConfig>) => {
    if (!playground.session || !playground.sessionSecret) return
    try {
      const nextConfig = await updateDemoConfig(playground.session.id, playground.sessionSecret, config)
      setPlayground((current) => ({ ...current, session: current.session ? { ...current.session, config: nextConfig } : null }))
    } catch (error) { await fallback(error) }
  }, [fallback, playground.session, playground.sessionSecret])

  const runAgent = useCallback(async (payload: { agent_id: string; attack_id: string; user_task: string; page_text: string }) => {
    if (!playground.session || !playground.sessionSecret) return
    try {
      const run = await startAgentRun(playground.session.id, playground.sessionSecret, payload)
      setAgentEvents(await readAgentEvents(playground.session.id, playground.sessionSecret, run.run_id))
    } catch (error) { await fallback(error) }
  }, [fallback, playground.session, playground.sessionSecret])

  const escalation = useCallback(async (action: 'approve' | 'reject') => {
    if (!result || !playground.session || !playground.sessionSecret) return
    const next = await actOnEscalation(playground.session.id, playground.sessionSecret, result.intent_id, action)
    setResult(next)
    await refresh(playground.session.id, playground.sessionSecret)
  }, [playground.session, playground.sessionSecret, refresh, result])

  const reset = useCallback(() => window.location.reload(), [])
  const refreshSession = useCallback(async () => {
    if (playground.session && playground.sessionSecret) {
      await refresh(playground.session.id, playground.sessionSecret)
    }
  }, [playground.session, playground.sessionSecret, refresh])
  return { ...playground, result, agentEvents, submit, setConfig, runAgent, escalation, reset, refreshSession }
}
