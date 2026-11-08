'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect, useRef } from 'react'
import { useRealtime } from '@/hooks/useRealtime'
import { activeApi, isDemoMode } from '@/lib/activeApi'
import {
  FULL_TELEMETRY_ITEMS,
  FULL_GOVERNANCE_ITEMS,
  NavItemConfig,
} from '@/lib/navConfig'
import { ChevronRight, ChevronLeft } from 'lucide-react'

export function ConsoleSidebar({ escalationCount = 0 }: { escalationCount?: number }) {
  const pathname = usePathname()
  const [hasFrozen, setHasFrozen] = useState(false)
  const [protectionsOff, setProtectionsOff] = useState(false)
  const [pendingCount, setPendingCount] = useState(escalationCount)
  const [isTabletExpanded, setIsTabletExpanded] = useState(false)
  const railRef = useRef<HTMLDivElement>(null)

  // Never render sidebar on login screens
  if (pathname === '/login' || pathname === '/console/login' || pathname?.endsWith('/login')) {
    return null
  }

  useEffect(() => {
    checkStatus()
  }, [pathname])

  useRealtime((event) => {
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
      activeApi
        .getRiskConfig()
        .then((cfg) =>
          setProtectionsOff(!cfg.canary_enabled || !cfg.judge_enabled)
        )
        .catch(() => {})
    }
  }, [])

  // Close tablet expanded sidebar on outside click
  useEffect(() => {
    if (!isTabletExpanded) return
    const handleClickOutside = (e: MouseEvent) => {
      if (railRef.current && !railRef.current.contains(e.target as Node)) {
        setIsTabletExpanded(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isTabletExpanded])

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + '/')

  const renderNavSection = (items: NavItemConfig[], title?: string, isExpanded = true) => (
    <div className="space-y-0.5">
      {title && isExpanded && (
        <div className="px-3 pt-3 pb-1">
          <p className="font-sans text-xs font-semibold text-ink-muted/80">{title}</p>
        </div>
      )}
      {items.map(({ href, label, icon: Icon, exact, badgeKey }) => {
        const active = isActive(href, exact)
        const hasEscalations = badgeKey === 'escalations' && pendingCount > 0
        const isMandatesFrozen = badgeKey === 'frozen' && hasFrozen

        return (
          <Link
            key={href}
            href={href}
            onClick={() => setIsTabletExpanded(false)}
            title={!isExpanded ? label : undefined}
            className={`flex items-center ${
              isExpanded ? 'justify-between px-3' : 'justify-center px-2'
            } py-2.5 rounded-md text-xs font-medium transition-all relative ${
              active
                ? 'bg-paper-high text-ink font-semibold shadow-2xs'
                : 'text-ink-muted hover:bg-paper-low hover:text-ink'
            }`}
            aria-current={active ? 'page' : undefined}
          >
            {active && (
              <span className="absolute left-1 top-2 bottom-2 w-1 bg-vermilion rounded-full" />
            )}
            <span className={`flex items-center gap-2.5 ${active && isExpanded ? 'pl-1' : ''}`}>
              <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-vermilion' : 'text-ink-muted'}`} />
              {isExpanded && <span>{label}</span>}
            </span>

            {isExpanded && hasEscalations && (
              <span className="px-1.5 py-0.5 rounded-full bg-amber/15 border border-amber/30 text-amber font-mono text-2xs font-bold">
                {pendingCount}
              </span>
            )}

            {isExpanded && isMandatesFrozen && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-vermilion/10 text-vermilion font-mono text-2xs font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-vermilion animate-pulse" />
                1 frozen
              </span>
            )}

            {!isExpanded && (hasEscalations || isMandatesFrozen) && (
              <span
                className={`absolute top-1.5 right-1.5 w-2 h-2 rounded-full ${
                  isMandatesFrozen ? 'bg-vermilion' : 'bg-amber'
                }`}
              />
            )}
          </Link>
        )
      })}
    </div>
  )

  return (
    <>
      {/* Tablet Rail (768px - 1023px, md:flex lg:hidden) */}
      <aside
        ref={railRef}
        aria-label="Sidebar navigation"
        className={`hidden md:flex lg:hidden flex-col bg-paper border-r border-border h-screen sticky top-0 transition-all duration-200 z-header ${
          isTabletExpanded ? 'w-56 shadow-xl' : 'w-16'
        }`}
      >
        {/* Rail Header with Toggle */}
        <div className="h-14 px-3 border-b border-border flex items-center justify-between shrink-0">
          <Link
            href="/console"
            className={`flex items-center gap-2.5 min-w-0 ${!isTabletExpanded ? 'mx-auto' : ''}`}
          >
            <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 shrink-0" aria-hidden>
              <rect width="24" height="24" rx="3" fill="#E5391B" />
              <path d="M12 4 L20 7 V13 C20 17.5 16.5 20.5 12 22 C7.5 20.5 4 17.5 4 13 Z" fill="white" />
              <path d="M12 7.5 L17.5 9.5 V12.5 C17.5 15.5 15 17.5 12 18.5 C9 17.5 6.5 15.5 6.5 12.5 V9.5 Z" fill="#E5391B" />
              <line x1="12" y1="10.5" x2="12" y2="13.5" stroke="white" strokeWidth="1.5" strokeLinecap="square" />
              <circle cx="12" cy="15.5" r="0.75" fill="white" />
            </svg>
            {isTabletExpanded && (
              <div className="min-w-0">
                <p className="font-sans font-bold text-sm tracking-tight text-ink truncate">Gatekeeper</p>
                <p className="font-sans text-xs text-ink-muted truncate">Console</p>
              </div>
            )}
          </Link>
          <button
            type="button"
            onClick={() => setIsTabletExpanded(!isTabletExpanded)}
            className="p-1 text-ink-muted hover:text-ink rounded min-h-[32px] min-w-[32px] flex items-center justify-center"
            aria-label={isTabletExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {isTabletExpanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {/* Rail navigation */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-2">
          {renderNavSection(FULL_TELEMETRY_ITEMS, 'Telemetry', isTabletExpanded)}
          {renderNavSection(FULL_GOVERNANCE_ITEMS, 'Governance', isTabletExpanded)}
        </nav>

        {protectionsOff && (
          <div className="p-2 bg-amber/10 border-t border-amber/20 text-center">
            <span className="text-xs text-amber font-medium" title="Risk layers disabled">
              ⚠{isTabletExpanded && ' Risk layers disabled'}
            </span>
          </div>
        )}

        <div className="p-3 border-t border-border flex items-center justify-center bg-paper-low/40 shrink-0 text-xs">
          <span className="w-2 h-2 rounded-full bg-forest animate-pulse" />
          {isTabletExpanded && (
            <span className="ml-2 font-mono text-2xs text-ink-muted font-medium">Armed</span>
          )}
        </div>
      </aside>

      {/* Desktop Sidebar (1024px and up: hidden lg:flex) */}
      <aside
        className="hidden lg:flex flex-col w-56 shrink-0 bg-paper border-r border-border h-screen sticky top-0"
        aria-label="Sidebar navigation"
      >
        {/* Brand header */}
        <div className="h-14 px-4 border-b border-border flex items-center justify-between shrink-0">
          <Link href="/console" className="flex items-center gap-2.5 min-w-0">
            <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 shrink-0" aria-hidden>
              <rect width="24" height="24" rx="3" fill="#E5391B" />
              <path d="M12 4 L20 7 V13 C20 17.5 16.5 20.5 12 22 C7.5 20.5 4 17.5 4 13 Z" fill="white" />
              <path d="M12 7.5 L17.5 9.5 V12.5 C17.5 15.5 15 17.5 12 18.5 C9 17.5 6.5 15.5 6.5 12.5 V9.5 Z" fill="#E5391B" />
              <line x1="12" y1="10.5" x2="12" y2="13.5" stroke="white" strokeWidth="1.5" strokeLinecap="square" />
              <circle cx="12" cy="15.5" r="0.75" fill="white" />
            </svg>
            <div className="min-w-0">
              <p className="font-sans font-bold text-sm tracking-tight text-ink truncate">Gatekeeper</p>
              <p className="font-sans text-xs text-ink-muted truncate">Operator console</p>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-2">
          {renderNavSection(FULL_TELEMETRY_ITEMS, 'Telemetry', true)}
          {renderNavSection(FULL_GOVERNANCE_ITEMS, 'Governance', true)}
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
      </aside>
    </>
  )
}
