'use client'

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  MAIN_BOTTOM_NAV_ITEMS,
  MORE_SHEET_ITEMS,
  NavItemConfig,
} from '@/lib/navConfig'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { useRealtime } from '@/hooks/useRealtime'
import {
  MoreHorizontal,
  X,
  Sun,
  Moon,
  ArrowLeft,
  LogOut,
} from 'lucide-react'

export function ConsoleBottomBar() {
  const pathname = usePathname()
  const router = useRouter()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [escalationsCount, setEscalationsCount] = useState<number>(0)
  const [hasFrozen, setHasFrozen] = useState<boolean>(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [demo, setDemo] = useState(false)
  const [mounted, setMounted] = useState(false)

  const sheetRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  // Do not render on login page
  if (
    pathname === '/login' ||
    pathname === '/console/login' ||
    pathname?.endsWith('/login')
  ) {
    return null
  }

  useEffect(() => {
    setMounted(true)
    setDemo(isDemoMode())
    const saved =
      (localStorage.getItem('apf_theme') as 'light' | 'dark') || 'light'
    setTheme(saved)
  }, [pathname])

  const fetchStats = async () => {
    try {
      const stats = await activeApi.getStats()
      if (stats.escalations_pending !== undefined) {
        setEscalationsCount(stats.escalations_pending)
      }
      setHasFrozen((stats.frozen_mandates ?? 0) > 0)
    } catch {}
  }

  useEffect(() => {
    if (activeApi.getToken() || isDemoMode()) {
      fetchStats()
    }
  }, [pathname])

  useRealtime((event) => {
    if (event.type === 'intent_escalated') {
      setEscalationsCount((c) => c + 1)
    }
    if (event.type === 'mandate_frozen') {
      setHasFrozen(true)
    }
    if (event.type === 'mandate_unfrozen') {
      fetchStats()
    }
  })

  // Keyboard trap and ESC handling for sheet
  useEffect(() => {
    if (!sheetOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSheetOpen(false)
        return
      }

      if (e.key === 'Tab' && sheetRef.current) {
        const focusableElements = sheetRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        const first = focusableElements[0]
        const last = focusableElements[focusableElements.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === first) {
            last?.focus()
            e.preventDefault()
          }
        } else {
          if (document.activeElement === last) {
            first?.focus()
            e.preventDefault()
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    closeButtonRef.current?.focus()
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [sheetOpen])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('apf_theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
  }

  const handleExitSampleMode = () => {
    sessionStorage.removeItem('apf_demo_mode')
    setSheetOpen(false)
    router.push('/console/login')
  }

  const handleLogout = () => {
    activeApi.setToken(null)
    sessionStorage.removeItem('apf_demo_mode')
    sessionStorage.removeItem('apf_token')
    setSheetOpen(false)
    router.push('/console/login')
  }

  const isTabActive = (item: NavItemConfig) => {
    if (item.exact) return pathname === item.href
    return pathname === item.href || pathname.startsWith(item.href + '/')
  }

  const isMoreActive = MORE_SHEET_ITEMS.some((item) =>
    pathname === item.href || pathname.startsWith(item.href + '/')
  )

  return (
    <>
      {/* Mobile Bottom Tab Bar (visible only below 768px: md:hidden) */}
      <nav
        aria-label="Mobile console navigation"
        className="md:hidden fixed bottom-0 left-0 right-0 z-bottom-bar bg-paper/98 backdrop-blur-md border-t border-border pb-safe-bottom"
      >
        <div className="grid grid-cols-5 h-16 items-center px-1">
          {MAIN_BOTTOM_NAV_ITEMS.map((item) => {
            const active = isTabActive(item)
            const Icon = item.icon
            const hasEscalations = item.badgeKey === 'escalations' && escalationsCount > 0
            const hasFrozenBadge = item.badgeKey === 'frozen' && hasFrozen

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative flex flex-col items-center justify-center h-full min-h-[44px] transition-colors ${
                  active
                    ? 'border-t-2 border-vermilion text-ink font-semibold'
                    : 'text-ink-muted hover:text-ink'
                }`}
                aria-current={active ? 'page' : undefined}
              >
                <div className="relative">
                  <Icon
                    className={`w-5 h-5 ${active ? 'text-vermilion' : 'text-ink-muted'}`}
                    aria-hidden
                  />
                  {hasEscalations && (
                    <span
                      aria-label={`${escalationsCount} pending approvals`}
                      className="absolute -top-1.5 -right-2 px-1 py-0.2 bg-amber text-paper font-mono text-[10px] font-bold rounded-full min-w-[14px] text-center"
                    >
                      {escalationsCount}
                    </span>
                  )}
                  {hasFrozenBadge && (
                    <span
                      aria-label="Frozen mandate"
                      className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-vermilion"
                    />
                  )}
                </div>
                <span className="text-[11px] mt-1 leading-tight tracking-tight">
                  {item.label}
                </span>
              </Link>
            )
          })}

          {/* 5th Tab: More */}
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            aria-expanded={sheetOpen}
            aria-haspopup="dialog"
            aria-label="Open more navigation options"
            className={`relative flex flex-col items-center justify-center h-full min-h-[44px] transition-colors ${
              isMoreActive || sheetOpen
                ? 'border-t-2 border-vermilion text-ink font-semibold'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <MoreHorizontal
              className={`w-5 h-5 ${isMoreActive || sheetOpen ? 'text-vermilion' : 'text-ink-muted'}`}
              aria-hidden
            />
            <span className="text-[11px] mt-1 leading-tight tracking-tight">
              More
            </span>
          </button>
        </div>
      </nav>

      {/* Accessible Bottom Sheet for More */}
      {sheetOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="more-sheet-title"
          className="md:hidden fixed inset-0 z-sheet flex flex-col justify-end"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity"
            onClick={() => setSheetOpen(false)}
            aria-hidden="true"
          />

          {/* Sheet panel */}
          <div
            ref={sheetRef}
            className="relative z-10 bg-paper border-t border-border rounded-t-2xl shadow-xl max-h-[85dvh] overflow-y-auto pb-safe-bottom"
          >
            {/* Grab handle */}
            <div className="w-12 h-1.5 bg-border/80 rounded-full mx-auto my-3" />

            <div className="px-5 pb-3 pt-1 flex items-center justify-between border-b border-border">
              <h2
                id="more-sheet-title"
                className="font-sans font-bold text-base text-ink"
              >
                More options
              </h2>
              <button
                ref={closeButtonRef}
                type="button"
                onClick={() => setSheetOpen(false)}
                className="p-2 text-ink-muted hover:text-ink min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="Close sheet"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-1">
              {MORE_SHEET_ITEMS.map((item) => {
                const active = pathname === item.href
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setSheetOpen(false)}
                    className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium min-h-[44px] transition-colors ${
                      active
                        ? 'bg-paper-high text-ink font-semibold'
                        : 'text-ink-muted hover:bg-paper-low hover:text-ink'
                    }`}
                  >
                    <Icon
                      className={`w-5 h-5 ${active ? 'text-vermilion' : 'text-ink-muted'}`}
                    />
                    <span>{item.label}</span>
                  </Link>
                )
              })}

              <hr className="my-2 border-border" />

              {/* Theme toggle */}
              <button
                type="button"
                onClick={toggleTheme}
                className="w-full flex items-center justify-between px-3 py-3 rounded-lg text-sm font-medium text-ink-muted hover:bg-paper-low hover:text-ink min-h-[44px] transition-colors"
              >
                <span className="flex items-center gap-3">
                  {theme === 'dark' ? (
                    <Sun className="w-5 h-5 text-amber" />
                  ) : (
                    <Moon className="w-5 h-5 text-ink-muted" />
                  )}
                  <span>Theme: {theme === 'dark' ? 'Dark' : 'Light'}</span>
                </span>
                <span className="text-xs font-mono text-ink-muted">Switch</span>
              </button>

              {/* Back to site */}
              <Link
                href="/"
                onClick={() => setSheetOpen(false)}
                className="flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-ink-muted hover:bg-paper-low hover:text-ink min-h-[44px] transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-ink-muted" />
                <span>Back to site</span>
              </Link>

              {/* Sample mode exit or sign out */}
              {demo ? (
                <button
                  type="button"
                  onClick={handleExitSampleMode}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-amber hover:bg-amber/10 min-h-[44px] transition-colors"
                >
                  <LogOut className="w-5 h-5 text-amber" />
                  <span>Exit sample mode</span>
                </button>
              ) : (
                mounted && (
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-vermilion hover:bg-vermilion/10 min-h-[44px] transition-colors"
                  >
                    <LogOut className="w-5 h-5 text-vermilion" />
                    <span>Sign out</span>
                  </button>
                )
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
