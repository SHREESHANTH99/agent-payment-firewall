'use client'

import { useEffect, useState } from 'react'

export type DeviceType = 'phone' | 'tablet' | 'desktop'

export function useBreakpoint(): {
  device: DeviceType
  isPhone: boolean
  isTablet: boolean
  isDesktop: boolean
  width: number
} {
  const [width, setWidth] = useState<number>(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1200,
  )

  useEffect(() => {
    if (typeof window === 'undefined') return
    const handleResize = () => setWidth(window.innerWidth)
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const isPhone = width < 768
  const isTablet = width >= 768 && width < 1024
  const isDesktop = width >= 1024

  const device: DeviceType = isPhone ? 'phone' : isTablet ? 'tablet' : 'desktop'

  return { device, isPhone, isTablet, isDesktop, width }
}
