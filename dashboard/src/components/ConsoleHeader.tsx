'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { isDemoMode, activeApi } from '@/lib/activeApi'
import { useRealtime } from '@/hooks/useRealtime'
import { Sun, Moon, ArrowLeft, Loader2, LogOut } from 'lucide-react'

const PAGE_NAMES: Record<string, string> = {
  '/console': 'Overview',
  '/console/approvals': 'Approvals',
  '/console/intents': 'Intents',
  '/console/mandates': 'Mandates',
  '/console/audit': 'Audit chain',
  '/console/controls': 'Risk controls',
  '/console/login': 'Sign in',
}

export function ConsoleHeader() {
  const pathname = usePathname()
  const router = useRouter()
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [demo, setDemo] = useState(false)
  const [mounted, setMounted] = useState(false)

  // Never render header on login screens
  if (pathname === '/login' || pathname === '/console/login' || pathname?.endsWith('/login')) {
    return null
  }

  useEffect(() => {
    setMounted(true)
    setDemo(isDemoMode())
    const saved = (localStorage.getItem('apf_theme') as 'light' | 'dark') || 'light'
    setTheme(saved)
  }, [pathname])

  const { status } = useRealtime()

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('apf_theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
  }

  const handleLogout = () => {
    activeApi.setToken(null)
    sessionStorage.removeItem('apf_demo_mode')
    sessionStorage.removeItem('apf_token')
    router.push('/console/login')
  }

  const pageTitle = PAGE_NAMES[pathname] || 'Overview'

  return (
    <header className="h-14 border-b border-border bg-paper/95 backdrop-blur-sm px-4 md:px-6 flex items-center justify-between shrink-0 z-header">
      {/* Left: Breadcrumbs / Title */}
      <div className="flex items-center gap-2 min-w-0">
        <Link
          href="/console"
          className="hidden sm:inline font-sans text-xs font-medium text-ink-muted hover:text-ink transition-colors"
        >
          Console
        </Link>
        <span className="hidden sm:inline text-ink-muted/40 text-xs font-mono">/</span>
        <h1 className="font-sans text-sm md:text-xs font-semibold text-ink truncate">
          {pageTitle}
        </h1>
      </div>

      {/* Right: Environment & Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Environment badge & Exit sample mode */}
        {mounted && (
          demo ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber/10 border border-amber/30 text-amber">
                <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
                Sample mode
              </span>
              <button
                type="button"
                onClick={() => {
                  sessionStorage.removeItem('apf_demo_mode')
                  setDemo(false)
                  router.push('/console/login')
                }}
                className="hidden sm:inline text-xs text-ink-muted hover:text-vermilion underline transition-colors"
              >
                Exit sample mode
              </button>
            </div>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-forest/10 border border-forest/30 text-forest">
              <span className="w-1.5 h-1.5 rounded-full bg-forest" />
              Live sandbox
            </span>
          )
        )}

        {/* Realtime status (only shown on md+ and only if not in demo mode) */}
        {!demo && (
          <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded text-xs font-mono text-ink-muted">
            {status === 'connected' ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-forest" />
                <span>Live</span>
              </>
            ) : status === 'connecting' ? (
              <>
                <Loader2 className="w-3 h-3 text-amber animate-spin" />
                <span>Connecting</span>
              </>
            ) : (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-ink-muted opacity-40" />
                <span>Offline</span>
              </>
            )}
          </div>
        )}

        <div className="h-4 w-px bg-border/40 hidden sm:block mx-1" />

        {/* Theme toggle (hidden on phone, available in More bottom sheet) */}
        <button
          onClick={toggleTheme}
          className="hidden sm:flex w-8 h-8 rounded-md hover:bg-paper-high text-ink-muted hover:text-ink items-center justify-center transition-colors min-h-[44px] min-w-[44px]"
          aria-label="Toggle color theme"
        >
          {mounted && theme === 'dark' ? <Sun className="w-4 h-4 text-amber" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Back to site (hidden on phone, available in More bottom sheet) */}
        <Link
          href="/"
          className="hidden sm:inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md hover:bg-paper-high text-xs font-medium text-ink-muted hover:text-ink transition-colors min-h-[44px]"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to site</span>
        </Link>

        {/* Sign out (desktop/tablet only if mounted and not demo mode) */}
        {mounted && !demo && (
          <button
            onClick={handleLogout}
            className="hidden sm:flex w-8 h-8 rounded-md hover:bg-vermilion/10 text-ink-muted hover:text-vermilion items-center justify-center transition-colors min-h-[44px] min-w-[44px]"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        )}
      </div>
    </header>
  )
}
