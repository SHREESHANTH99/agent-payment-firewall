'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useRealtime, ConnectionStatus } from '@/hooks/useRealtime'
import { Shield, ShieldAlert, Activity, CheckSquare, ListOrdered, Scale, Lock, Moon, Sun, LogOut } from 'lucide-react'

export function AppHeader() {
  const pathname = usePathname()
  const router = useRouter()
  const [theme, setTheme] = useState<'light' | 'dark'>('dark')
  const [hasFrozen, setHasFrozen] = useState<boolean>(false)
  const [protectionsOff, setProtectionsOff] = useState<boolean>(false)

  const { status } = useRealtime((event) => {
    if (event.type === 'mandate_frozen') {
      setHasFrozen(true)
    } else if (event.type === 'mandate_unfrozen') {
      checkFrozenState()
    } else if (event.type === 'risk_config_changed') {
      const data = event.data
      setProtectionsOff(!data.canary_enabled || !data.judge_enabled)
    }
  })

  const checkFrozenState = async () => {
    try {
      const stats = await api.getStats()
      setHasFrozen(stats.frozen_mandates > 0)
    } catch {
      // ignore
    }
  }

  const checkRiskConfig = async () => {
    try {
      const cfg = await api.getRiskConfig()
      setProtectionsOff(!cfg.canary_enabled || !cfg.judge_enabled)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    // Sync dark class on mount
    document.documentElement.classList.add('dark')
    checkFrozenState()
    checkRiskConfig()
  }, [])

  const toggleTheme = () => {
    if (theme === 'dark') {
      document.documentElement.classList.remove('dark')
      setTheme('light')
    } else {
      document.documentElement.classList.add('dark')
      setTheme('dark')
    }
  }

  const handleLogout = () => {
    api.setToken(null)
    router.push('/login')
  }

  const navLinks = [
    { href: '/', label: 'Overview', icon: Activity },
    { href: '/approvals', label: 'Approvals', icon: CheckSquare },
    { href: '/intents', label: 'Intents', icon: ListOrdered },
    { href: '/mandates', label: 'Mandates', icon: Scale },
    { href: '/audit', label: 'Audit Chain', icon: Lock },
    { href: '/controls', label: 'Risk Controls', icon: Shield },
  ]

  if (pathname === '/login') return null

  return (
    <header className="border-b border-border bg-card">
      {/* Global alert: frozen mandates */}
      {hasFrozen && (
        <div className="bg-rose-950 text-rose-200 border-b border-rose-800 px-4 py-2 text-xs font-semibold flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <span>MANDATE FROZEN: One or more spending mandates have tripped the circuit breaker. Autonomous actions blocked.</span>
          </div>
          <Link href="/mandates" className="underline hover:text-white">Review Mandates</Link>
        </div>
      )}

      {/* Global alert: protections off */}
      {protectionsOff && (
        <div className="bg-amber-950 text-amber-200 border-b border-amber-800 px-4 py-1.5 text-xs font-medium flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span>PROTECTIONS OFF: One or more AI risk inspection layers (Canary / Judge) are currently disabled.</span>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <div className="flex items-center space-x-8">
          <div className="flex items-center space-x-2">
            <Shield className="w-5 h-5 text-accent" />
            <span className="font-semibold text-sm tracking-tight">Agent Payment Firewall</span>
          </div>
          <nav className="hidden md:flex space-x-1">
            {navLinks.map((item) => {
              const Icon = item.icon
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center space-x-1.5 transition-colors ${
                    active
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
        </div>

        <div className="flex items-center space-x-4 text-xs">
          {/* Connection status indicator */}
          <div className="flex items-center space-x-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                status === 'connected'
                  ? 'bg-emerald-500'
                  : status === 'connecting'
                  ? 'bg-amber-500 animate-ping'
                  : 'bg-rose-500'
              }`}
            />
            <span className="text-muted-foreground capitalize">{status}</span>
          </div>

          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          <button
            onClick={handleLogout}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
            aria-label="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
