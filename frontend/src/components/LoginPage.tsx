'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/auth-context'

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email, password)
    } catch {
      setError('Invalid credentials. Try any email/password for demo.')
    } finally {
      setLoading(false)
    }
  }

  // Auto-login for demo
  const demoLogin = async () => {
    setLoading(true)
    try { await login('demo@verity.ai', 'demo1234') } catch {}
    setLoading(false)
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'var(--paper)',
      fontFamily: 'var(--font-sans)',
    }}>
      <div style={{ width: '100%', maxWidth: 400, padding: '0 24px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--gold)', display: 'inline-block' }} />
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: 28, color: 'var(--ink)' }}>VERITY</span>
          </div>
          <p style={{ fontSize: 14, color: 'var(--ink3)', fontWeight: 300 }}>Autonomous equity research</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--ink2)', marginBottom: 6, letterSpacing: '0.04em' }}>
              EMAIL
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              style={{
                width: '100%', padding: '11px 14px',
                fontSize: 14, fontFamily: 'var(--font-sans)',
                background: 'var(--white)', border: '1px solid var(--paper3)',
                borderRadius: 'var(--radius)', outline: 'none', color: 'var(--ink)',
              }}
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--ink2)', marginBottom: 6, letterSpacing: '0.04em' }}>
              PASSWORD
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                width: '100%', padding: '11px 14px',
                fontSize: 14, fontFamily: 'var(--font-sans)',
                background: 'var(--white)', border: '1px solid var(--paper3)',
                borderRadius: 'var(--radius)', outline: 'none', color: 'var(--ink)',
              }}
            />
          </div>

          {error && (
            <div style={{ fontSize: 13, color: 'var(--red)', marginBottom: 16 }}>{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '12px',
              fontSize: 14, fontWeight: 500, fontFamily: 'var(--font-sans)',
              background: loading ? 'var(--ink3)' : 'var(--ink)',
              color: 'var(--white)', border: 'none',
              borderRadius: 'var(--radius)', cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <button
            onClick={demoLogin}
            disabled={loading}
            style={{
              fontSize: 13, color: 'var(--accent2)', background: 'none',
              border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)',
              textDecoration: 'underline',
            }}
          >
            Skip — use demo account
          </button>
        </div>
      </div>
    </div>
  )
}
