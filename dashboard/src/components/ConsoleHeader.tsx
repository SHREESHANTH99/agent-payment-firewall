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
    <header className="h-14 border-b border-border bg-paper/95 backdrop-blur-sm px-4 md:px-6 flex items-center justify-between shrink-0 z-20">
      {/* Left: Breadcrumbs */}
      <div className="flex items-center gap-2 min-w-0">
        <Link
          href="/console"
          className="font-sans text-xs font-medium text-ink-muted hover:text-ink transition-colors"
        >
          Console
        </Link>
        <span className="text-ink-muted/40 text-xs font-mono">/</span>
        <span className="font-sans text-xs font-semibold text-ink truncate">
          {pageTitle}
        </span>
      </div>

      {/* Right: Environment & Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Environment badge */}
        {mounted && (
          demo ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber/10 border border-amber/30 text-amber">
              <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
              Demo data
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-forest/10 border border-forest/30 text-forest">
              <span className="w-1.5 h-1.5 rounded-full bg-forest" />
              Live sandbox
            </span>
          )
        )}

        {/* Realtime status */}
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

        <div className="h-4 w-px bg-border/40 hidden sm:block mx-1" />

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="w-8 h-8 rounded-md hover:bg-paper-high text-ink-muted hover:text-ink flex items-center justify-center transition-colors"
          aria-label="Toggle color theme"
        >
          {mounted && theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>

        {/* Back to site */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md hover:bg-paper-high text-xs font-medium text-ink-muted hover:text-ink transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Back to site</span>
        </Link>

        {/* Sign out (if mounted and not demo mode) */}
        {mounted && !demo && (
          <button
            onClick={handleLogout}
            className="w-8 h-8 rounded-md hover:bg-vermilion/10 text-ink-muted hover:text-vermilion flex items-center justify-center transition-colors"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </header>
  )
}
