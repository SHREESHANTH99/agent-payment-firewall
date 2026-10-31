'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState, useEffect } from 'react'
import { useRealtime, ConnectionStatus } from '@/hooks/useRealtime'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import { Banner } from '@/components/ui'
import {
  LayoutDashboard, CheckSquare, ListOrdered, Scale, Link2, Shield,
  LogOut, Sun, Moon, Menu, X, Wifi, WifiOff, Loader2
} from 'lucide-react'

const NAV = [
  { href: '/console', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/console/approvals', label: 'Approvals', icon: CheckSquare, badge: true },
  { href: '/console/intents', label: 'Intents', icon: ListOrdered },
  { href: '/console/mandates', label: 'Mandates', icon: Scale },
  { href: '/console/audit', label: 'Audit chain', icon: Link2 },
  { href: '/console/controls', label: 'Risk controls', icon: Shield },
]

function ConnectionDot({ status }: { status: ConnectionStatus }) {
  if (status === 'connected') return <Wifi className="w-3.5 h-3.5 text-forest" aria-label="Live" />
  if (status === 'connecting') return <Loader2 className="w-3.5 h-3.5 text-amber animate-spin" aria-label="Connecting" />
  return <WifiOff className="w-3.5 h-3.5 text-ink-muted" aria-label="Disconnected" />
}

export function ConsoleSidebar({ escalationCount = 0 }: { escalationCount?: number }) {
  const pathname = usePathname()
  const router = useRouter()
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [hasFrozen, setHasFrozen] = useState(false)
  const [protectionsOff, setProtectionsOff] = useState(false)
  const [demo, setDemo] = useState(false)

  useEffect(() => {
    setDemo(isDemoMode())
  }, [pathname])

  const { status } = useRealtime((event) => {
    if (event.type === 'mandate_frozen') setHasFrozen(true)
    if (event.type === 'mandate_unfrozen') checkFrozen()
    if (event.type === 'risk_config_changed') {
      setProtectionsOff(!event.data.canary_enabled || !event.data.judge_enabled)
    }
  })

  const checkFrozen = async () => {
    try {
      const s = await activeApi.getStats()
      setHasFrozen((s.frozen_mandates ?? 0) > 0)
    } catch {}
  }

  useEffect(() => {
    const savedTheme = (localStorage.getItem('apf_theme') as 'light' | 'dark') || 'light'
    setTheme(savedTheme)
    document.documentElement.classList.toggle('dark', savedTheme === 'dark')
    if (activeApi.getToken()) {
      checkFrozen()
      activeApi.getRiskConfig().then((cfg) =>
        setProtectionsOff(!cfg.canary_enabled || !cfg.judge_enabled)
      ).catch(() => {})
    }
  }, [])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('apf_theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
  }

  const handleLogout = () => {
    activeApi.setToken(null)
    router.push('/console/login')
  }

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + '/')

  const SidebarContent = () => (
    <>
      {/* Brand header */}
      <div className="h-14 px-4 border-b border-border flex items-center justify-between shrink-0">
        <Link href="/console" className="flex items-center gap-2.5 min-w-0">
          <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 shrink-0" aria-hidden>
            <rect width="24" height="24" rx="3" fill="#E5391B" />
            <path d="M12 4 L20 7 V13 C20 17.5 16.5 20.5 12 22 C7.5 20.5 4 17.5 4 13 V7 Z" fill="white" />
            <path d="M12 7.5 L17.5 9.5 V12.5 C17.5 15.5 15 17.5 12 18.5 C9 17.5 6.5 15.5 6.5 12.5 V9.5 Z" fill="#E5391B" />
            <line x1="12" y1="10.5" x2="12" y2="13.5" stroke="white" strokeWidth="1.5" strokeLinecap="square" />
            <circle cx="12" cy="15.5" r="0.75" fill="white" />
          </svg>
          <div className="min-w-0">
            <p className="font-sans font-bold text-xs uppercase tracking-wider text-ink truncate">Gatekeeper</p>
            <p className="font-mono text-2xs text-ink-muted uppercase tracking-widest truncate">
              {demo ? 'Demo mode' : 'Operator console'}
            </p>
          </div>
        </Link>
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1 text-ink-muted hover:text-ink"
          aria-label="Close menu"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Demo badge */}
      {demo && (
        <div className="px-4 py-1.5 bg-amber/10 border-b border-amber/20">
          <p className="font-mono text-2xs text-amber font-semibold uppercase tracking-wider">
            Sample data — no real transactions
          </p>
        </div>
      )}

      {/* Alert banners */}
      {hasFrozen && (
        <Link href="/console/mandates">
          <div className="px-4 py-2 bg-vermilion/10 border-b border-vermilion/20 flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-vermilion rounded-none animate-pulse shrink-0" />
            <p className="font-sans text-2xs text-vermilion">Mandate frozen — review required</p>
          </div>
        </Link>
      )}

      {/* Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto" aria-label="Console navigation">
        <div className="px-3 mb-1">
          <p className="font-sans text-2xs text-ink-muted uppercase tracking-widest px-1 mb-1">Telemetry</p>
        </div>
        {NAV.slice(0, 3).map(({ href, label, icon: Icon, exact, badge }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center justify-between px-4 py-2 text-xs font-medium transition-colors border-l-2 ${
                active
                  ? 'border-vermilion bg-paper-high text-ink font-semibold'
                  : 'border-transparent text-ink-muted hover:bg-paper-low hover:text-ink'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </span>
              {badge && escalationCount > 0 && (
                <span className="px-1.5 py-0.5 bg-vermilion text-white font-mono text-2xs font-bold">
                  {escalationCount}
                </span>
              )}
            </Link>
          )
        })}

        <div className="px-3 mt-4 mb-1">
          <p className="font-sans text-2xs text-ink-muted uppercase tracking-widest px-1 mb-1">Governance</p>
        </div>
        {NAV.slice(3).map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-2.5 px-4 py-2 text-xs font-medium transition-colors border-l-2 ${
                active
                  ? 'border-vermilion bg-paper-high text-ink font-semibold'
                  : 'border-transparent text-ink-muted hover:bg-paper-low hover:text-ink'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Protections off banner */}
      {protectionsOff && (
        <div className="px-4 py-2 bg-amber/10 border-t border-amber/20">
          <p className="font-mono text-2xs text-amber font-semibold uppercase">
            ⚠ Protections off — risk layers disabled
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="p-3 border-t border-border flex items-center justify-between bg-paper-low shrink-0">
        <div className="flex items-center gap-1.5">
          <ConnectionDot status={status} />
          <span className="font-mono text-2xs text-ink-muted uppercase tracking-wider">
            {status === 'connected' ? 'Live' : status === 'connecting' ? 'Connecting…' : 'Offline'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleTheme}
            className="p-1.5 text-ink-muted hover:text-ink hover:bg-paper-high transition-colors"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>
          {!demo && (
            <button
              onClick={handleLogout}
              className="p-1.5 text-ink-muted hover:text-vermilion hover:bg-paper-high transition-colors"
              aria-label="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </>
  )

  return (
    <>
      {/* Mobile toggle button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-3 left-3 z-40 p-2 bg-paper-low border border-border text-ink-muted hover:text-ink"
        aria-label="Open menu"
      >
        <Menu className="w-4 h-4" />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={`lg:hidden fixed inset-y-0 left-0 z-50 w-64 bg-paper border-r border-border flex flex-col transition-transform duration-200 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Sidebar"
      >
        <SidebarContent />
      </aside>

      {/* Desktop sidebar */}
      <aside
        className="hidden lg:flex flex-col w-56 shrink-0 bg-paper border-r border-border h-screen sticky top-0"
        aria-label="Sidebar"
      >
        <SidebarContent />
      </aside>
    </>
  )
}
