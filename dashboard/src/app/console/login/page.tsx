'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { Shield } from 'lucide-react'
import { Button } from '@/components/ui'
import { isDemoMode, setDemoMode } from '@/lib/activeApi'

export default function ConsoleLoginPage() {
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (isDemoMode() || api.getToken()) router.replace('/console')
  }, [])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    const clean = token.trim()
    if (!clean) return
    setLoading(true)
    setError(null)
    setDemoMode(false)
    api.setToken(clean)
    try {
      await api.getStats()
      router.replace('/console?demo=0')
    } catch {
      api.setToken(null)
      setError('Invalid operator bearer token or backend unreachable.')
      setLoading(false)
    }
  }

  const handleDemo = () => {
    setDemoMode(true)
    router.push('/console?demo=1')
  }

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Mark */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-vermilion flex items-center justify-center mb-3">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <h1 className="font-serif text-2xl text-ink">Operator authentication</h1>
          <p className="font-sans text-xs text-ink-muted mt-1 text-center">
            Enter your secret firewall operator token to access the governance console.
          </p>
        </div>

        {error && (
          <div className="mb-4 px-3 py-2 bg-vermilion/10 border border-vermilion/30 text-vermilion text-xs font-sans">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-3">
          <div>
            <label className="font-sans text-2xs uppercase tracking-wider text-ink-muted mb-1.5 block">
              Bearer token
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="64-character hex token"
              className="w-full px-3 py-2 text-xs font-mono bg-paper-low border border-border text-ink placeholder-ink-muted focus:outline-none focus:border-ink transition-colors"
              required
              autoFocus
            />
          </div>
          <Button type="submit" className="w-full justify-center" disabled={loading}>
            {loading ? 'Verifying…' : 'Sign in to console'}
          </Button>
        </form>

        <div className="mt-4 flex items-center gap-2">
          <div className="flex-1 h-px bg-border" />
          <span className="font-sans text-2xs text-ink-muted uppercase">or</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        <Button variant="secondary" className="w-full justify-center mt-4" onClick={handleDemo}>
          Explore in demo mode
        </Button>

        <p className="font-sans text-2xs text-ink-muted text-center mt-4">
          Demo mode uses sample data only. No network calls are made.
        </p>
      </div>
    </div>
  )
}
