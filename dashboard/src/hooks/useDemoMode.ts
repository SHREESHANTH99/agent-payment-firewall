'use client'

import { useState, useEffect } from 'react'
import { isDemoMode } from '@/lib/activeApi'

/**
 * SSR-safe hook for demo mode status.
 * Returns false on initial SSR/hydration render to guarantee match,
 * then updates after client mount.
 */
export function useDemoMode(): boolean {
  const [demo, setDemo] = useState(false)

  useEffect(() => {
    setDemo(isDemoMode())
  }, [])

  return demo
}
