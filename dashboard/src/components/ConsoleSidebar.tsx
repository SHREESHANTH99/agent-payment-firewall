'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState, useEffect } from 'react'
import { useRealtime } from '@/hooks/useRealtime'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import {
  LayoutDashboard, CheckSquare, ListOrdered, Scale, Link2, Shield, X
} from 'lucide-react'

const NAV_TELEMETRY = [
  { href: '/console', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/console/approvals', label: 'Approvals', icon: CheckSquare, badge: true },
  { href: '/console/intents', label: 'Intents', icon: ListOrdered },
]

const NAV_GOVERNANCE = [
  { href: '/console/mandates', label: 'Mandates', icon: Scale },
  { href: '/console/audit', label: 'Audit chain', icon: Link2 },
  { href: '/console/controls', label: 'Risk controls', icon: Shield },
]

export function ConsoleSidebar({ escalationCount = 0 }: { escalationCount?: number }) {
  const pathname = usePathname()
  const router = useRouter()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [hasFrozen, setHasFrozen] = useState(false)
  const [protectionsOff, setProtectionsOff] = useState(false)
  const [pendingCount, setPendingCount] = useState(escalationCount)

  useEffect(() => {
    checkStatus()
  }, [pathname])

  const { status } = useRealtime((event) => {
    if (event.type === 'mandate_frozen') setHasFrozen(true)
    if (event.type === 'mandate_unfrozen') checkStatus()
    if (event.type === 'intent_escalated') setPendingCount((c) => c + 1)
    if (event.type === 'risk_config_changed') {
      setProtectionsOff(!event.data.canary_enabled || !event.data.judge_enabled)
    }
  })

  const checkStatus = async () => {
    try {
      const s = await activeApi.getStats()
      setHasFrozen((s.frozen_mandates ?? 0) > 0)
      if (s.escalations_pending !== undefined) {
        setPendingCount(s.escalations_pending)
      }
    } catch {}
  }

  useEffect(() => {
    if (activeApi.getToken() || isDemoMode()) {
      checkStatus()
      activeApi.getRiskConfig().then((cfg) =>
        setProtectionsOff(!cfg.canary_enabled || !cfg.judge_enabled)
      ).catch(() => {})
    }
  }, [])

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
            <p className="font-sans font-bold text-sm tracking-tight text-ink truncate">Gatekeeper</p>
            <p className="font-sans text-xs text-ink-muted truncate">Operator console</p>
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

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-0.5" aria-label="Console navigation">
        <div className="px-2 pt-1 pb-1">
          <p className="font-sans text-xs font-semibold text-ink-muted/80">Telemetry</p>
        </div>
        {NAV_TELEMETRY.map(({ href, label, icon: Icon, exact, badge }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-all relative ${
                active
                  ? 'bg-paper-high text-ink font-semibold shadow-2xs'
                  : 'text-ink-muted hover:bg-paper-low hover:text-ink'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              {active && (
                <span className="absolute left-1 top-2 bottom-2 w-1 bg-vermilion rounded-full" />
              )}
              <span className={`flex items-center gap-2.5 ${active ? 'pl-1' : ''}`}>
                <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-vermilion' : 'text-ink-muted'}`} />
                <span>{label}</span>
              </span>
              {badge && pendingCount > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-amber/15 border border-amber/30 text-amber font-mono text-2xs font-bold">
                  {pendingCount}
                </span>
              )}
            </Link>
          )
        })}

        <div className="px-2 pt-4 pb-1">
          <p className="font-sans text-xs font-semibold text-ink-muted/80">Governance</p>
        </div>
        {NAV_GOVERNANCE.map(({ href, label, icon: Icon }) => {
          const active = isActive(href)
          const isMandates = href === '/console/mandates'
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-all relative ${
                active
                  ? 'bg-paper-high text-ink font-semibold shadow-2xs'
                  : 'text-ink-muted hover:bg-paper-low hover:text-ink'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              {active && (
                <span className="absolute left-1 top-2 bottom-2 w-1 bg-vermilion rounded-full" />
              )}
              <span className={`flex items-center gap-2.5 ${active ? 'pl-1' : ''}`}>
                <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-vermilion' : 'text-ink-muted'}`} />
                <span>{label}</span>
              </span>
              {isMandates && hasFrozen && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-vermilion/10 text-vermilion font-mono text-2xs font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-vermilion animate-pulse" />
                  1 frozen
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Protections off banner */}
      {protectionsOff && (
        <div className="px-3 py-2 bg-amber/10 border-t border-amber/20 text-xs">
          <p className="font-sans text-xs text-amber font-medium">
            ⚠ Risk layers disabled
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="p-3 border-t border-border flex items-center justify-between bg-paper-low/40 shrink-0 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-forest animate-pulse" />
          <span className="font-mono text-2xs text-ink-muted font-medium">Firewall armed</span>
        </div>
        <span className="font-mono text-2xs text-ink-muted/70">v0.1.0</span>
      </div>
    </>
  )

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={`lg:hidden fixed inset-y-0 left-0 z-50 w-60 bg-paper border-r border-border flex flex-col transition-transform duration-200 ${
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
