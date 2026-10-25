'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { Shield, Key } from 'lucide-react'

export default function LoginPage() {
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    const cleanToken = token.trim()
    if (!cleanToken) return

    setLoading(true)
    setError(null)

    // Save token immediately
    api.setToken(cleanToken)

    try {
      // Lightweight verification using fast endpoint
      await api.getStats()
      // Instant transition
      router.replace('/')
    } catch (err: any) {
      api.setToken(null)
      setError('Invalid operator bearer token or backend unreachable.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md p-8 border border-border bg-card rounded-lg shadow-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
            <Shield className="w-6 h-6 text-accent" />
          </div>
          <h1 className="text-lg font-semibold tracking-tight">Operator Authentication</h1>
          <p className="text-xs text-muted-foreground mt-1 text-center">
            Enter your secret firewall operator token to access the real-time governance console.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 text-xs bg-rose-950 text-rose-200 border border-rose-800 rounded">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">
              Operator Bearer Token
            </label>
            <div className="relative">
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste operator token (64-character hex)"
                className="w-full px-3 py-2 text-xs bg-background border border-border rounded focus:outline-none focus:border-accent font-mono"
                required
                autoFocus
              />
              <Key className="w-4 h-4 text-muted-foreground absolute right-2.5 top-2.5" />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {loading ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>Sign In to Console</span>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
