'use client'

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { api } from '@/lib/api'

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'

export interface RealtimeEvent {
  type: string
  ts: string
  data: Record<string, any>
}

type EventListener = (event: RealtimeEvent) => void

interface RealtimeContextValue {
  status: ConnectionStatus
  lastEvent: RealtimeEvent | null
  subscribe: (listener: EventListener) => () => void
}

const RealtimeContext = createContext<RealtimeContextValue>({
  status: 'disconnected',
  lastEvent: null,
  subscribe: () => () => {},
})

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null)
  const listenersRef = useRef<Set<EventListener>>(new Set())
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isConnectingRef = useRef<boolean>(false)
  const isMountedRef = useRef<boolean>(true)

  const connect = useCallback(async () => {
    // Only connect if client has token and is in browser
    if (typeof window === 'undefined') return
    const token = api.getToken()
    if (!token) {
      setStatus('disconnected')
      return
    }

    if (isConnectingRef.current || (wsRef.current && wsRef.current.readyState === WebSocket.OPEN)) {
      return
    }

    isConnectingRef.current = true
    setStatus('connecting')

    try {
      const { ticket } = await api.getWsTicket()
      if (!isMountedRef.current) return

      // Determine correct WS host/port from current window location if API_URL not explicitly set
      const apiHost = window.location.hostname
      const wsUrl = `ws://${apiHost}:8000/ws/dashboard?ticket=${ticket}`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!isMountedRef.current) return
        isConnectingRef.current = false
        setStatus('connected')
      }

      ws.onmessage = (e) => {
        if (!isMountedRef.current) return
        try {
          const parsed = JSON.parse(e.data)
          if (parsed.type === 'ping') return
          setLastEvent(parsed)
          listenersRef.current.forEach((fn) => {
            try {
              fn(parsed)
            } catch (err) {
              console.error('Error in WS subscriber callback:', err)
            }
          })
        } catch {
          // ignore
        }
      }

      ws.onclose = () => {
        if (!isMountedRef.current) return
        isConnectingRef.current = false
        setStatus('disconnected')
        wsRef.current = null

        // Reconnect after 5s backoff to prevent fast spin/flicker
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) connect()
        }, 5000)
      }

      ws.onerror = (e) => {
        // ws.onclose will fire after onerror
      }
    } catch (err) {
      if (!isMountedRef.current) return
      isConnectingRef.current = false
      setStatus('disconnected')
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) connect()
      }, 5000)
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true
    connect()

    return () => {
      // Do not aggressively close on fast sub-renders; only if unmounted
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
    }
  }, [connect])

  const subscribe = useCallback((listener: EventListener) => {
    listenersRef.current.add(listener)
    return () => {
      listenersRef.current.delete(listener)
    }
  }, [])

  return (
    <RealtimeContext.Provider value={{ status, lastEvent, subscribe }}>
      {children}
    </RealtimeContext.Provider>
  )
}

export function useRealtime(onEvent?: EventListener) {
  const context = useContext(RealtimeContext)

  useEffect(() => {
    if (!onEvent) return
    const unsubscribe = context.subscribe(onEvent)
    return () => unsubscribe()
  }, [onEvent, context])

  return {
    status: context.status,
    lastEvent: context.lastEvent,
  }
}
