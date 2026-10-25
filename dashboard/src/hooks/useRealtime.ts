'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { api } from '@/lib/api'

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'

export interface RealtimeEvent {
  type: string
  ts: string
  data: Record<string, any>
}

export function useRealtime(onEvent?: (event: RealtimeEvent) => void) {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isMountedRef = useRef<boolean>(true)

  const connect = useCallback(async () => {
    if (!api.getToken()) {
      setStatus('disconnected')
      return
    }

    setStatus('connecting')

    try {
      const { ticket } = await api.getWsTicket()
      if (!isMountedRef.current) return

      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const wsUrl = apiBase.replace(/^http/, 'ws') + `/ws/dashboard?ticket=${ticket}`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!isMountedRef.current) return
        setStatus('connected')
      }

      ws.onmessage = (e) => {
        if (!isMountedRef.current) return
        try {
          const parsed = JSON.parse(e.data)
          if (parsed.type === 'ping') return
          setLastEvent(parsed)
          if (onEvent) onEvent(parsed)
        } catch (err) {
          // ignore non-json
        }
      }

      ws.onclose = () => {
        if (!isMountedRef.current) return
        setStatus('disconnected')
        // Auto-reconnect after backoff
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) connect()
        }, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch (err) {
      if (!isMountedRef.current) return
      setStatus('disconnected')
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) connect()
      }, 5000)
    }
  }, [onEvent])

  useEffect(() => {
    isMountedRef.current = true
    connect()

    return () => {
      isMountedRef.current = false
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  return { status, lastEvent }
}
