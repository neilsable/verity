'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/auth-context'
import { useResearch } from '@/lib/use-research'
import { AgentProgressPanel } from '@/components/AgentProgressPanel'
import { JobHistory } from '@/components/JobHistory'

const TICKER_CHIPS = ['AAPL', 'NVDA', 'MSFT', 'GOOGL', 'TSLA', 'META', 'AMZN']

interface DashboardProps {
  onViewReport: (jobId: string) => void
}

export function Dashboard({ onViewReport }: DashboardProps) {
  const { token, email, logout } = useAuth()
  const { session, startResearch, cancel } = useResearch(token)

  const [ticker, setTicker] = useState('')
  const [brief, setBrief] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker.trim()) return
    setSubmitting(true)
    setSubmitError('')
    try {
      await startResearch(
        ticker.trim().toUpperCase(),
        brief.trim() || `Provide a comprehensive equity research analysis for ${ticker.toUpperCase()}.`,
      )
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to start research job')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--paper)', fontFamily: 'var(--font-sans)' }}>

      {/* Nav */}
      <nav style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 40px', height: 60,
        background: 'rgba(248,247,244,0.95)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--paper3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--gold)', display: 'inline-block' }} />
          <span style={{ fontFamily: 'var(--font-serif)', fontSize: 20, color: 'var(--ink)' }}>VERITY</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 13, color: 'var(--ink3)' }}>{email}</span>
          <button onClick={logout} style={{
            fontSize: 13, color: 'var(--ink2)', background: 'none',
            border: '1px solid var(--paper3)', borderRadius: 'var(--radius)',
            padding: '6px 14px', cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>Sign out</button>
        </div>
      </nav>

      <div style={{ paddingTop: 80, maxWidth: 1100, margin: '0 auto', padding: '80px 40px 60px' }}>

        {/* Header */}
        <div style={{ marginBottom: 48 }}>
          <div style={{
            fontSize: 11, fontWeight: 500, letterSpacing: '0.1em',
            textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 12,
          }}>Research Engine</div>
          <h1 style={{
            fontFamily: 'var(--font-serif)', fontSize: 'clamp(32px,5vw,52px)',
            lineHeight: 1.1, letterSpacing: '-0.02em', color: 'var(--ink)', marginBottom: 10,
          }}>
            Enter a ticker.<br /><em style={{ fontStyle: 'italic', color: 'var(--accent2)' }}>Get a cited research note.</em>
          </h1>
          <p style={{ fontSize: 16, fontWeight: 300, color: 'var(--ink2)' }}>
            Eight specialised agents run in parallel and deliver a red-teamed, fully cited equity research report.
          </p>
        </div>

        {/* Search box */}
        <form onSubmit={handleSubmit}>
          <div style={{
            display: 'flex', gap: 12, alignItems: 'center',
            background: 'var(--white)', border: '1.5px solid var(--paper3)',
            borderRadius: 'var(--radius-lg)', padding: '8px 8px 8px 20px',
            marginBottom: 14, transition: 'border-color 0.2s',
          }}>
            <input
              value={ticker}
              onChange={e => setTicker(e.target.value.toUpperCase().slice(0, 6))}
              placeholder="AAPL"
              style={{
                fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 500,
                width: 100, background: 'none', border: 'none', outline: 'none',
                color: 'var(--ink)', letterSpacing: '0.05em',
              }}
            />
            <div style={{ width: 1, background: 'var(--paper3)', alignSelf: 'stretch', margin: '4px 0' }} />
            <input
              value={brief}
              onChange={e => setBrief(e.target.value)}
              placeholder="e.g. Focus on AI services revenue growth and margin expansion"
              style={{
                flex: 1, fontSize: 14, fontWeight: 300,
                background: 'none', border: 'none', outline: 'none',
                color: 'var(--ink2)', fontFamily: 'var(--font-sans)',
              }}
            />
            <button
              type="submit"
              disabled={submitting || session.isRunning || !ticker}
              style={{
                fontFamily: 'var(--font-sans)', fontSize: 14, fontWeight: 500,
                background: (submitting || session.isRunning || !ticker) ? 'var(--ink3)' : 'var(--ink)',
                color: 'var(--white)', border: 'none', borderRadius: 6,
                padding: '12px 24px', cursor: (submitting || session.isRunning || !ticker) ? 'not-allowed' : 'pointer',
                whiteSpace: 'nowrap', transition: 'background 0.2s',
              }}
            >
              {submitting ? 'Starting...' : session.isRunning ? 'Running...' : 'Run research →'}
            </button>
          </div>

          {/* Ticker chips */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {TICKER_CHIPS.map(t => (
              <button
                key={t}
                type="button"
                onClick={() => setTicker(t)}
                style={{
                  fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500,
                  letterSpacing: '0.04em', background: 'var(--paper)',
                  border: `1px solid ${ticker === t ? 'var(--accent2)' : 'var(--paper3)'}`,
                  color: ticker === t ? 'var(--accent2)' : 'var(--ink2)',
                  borderRadius: 100, padding: '5px 14px', cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </form>

        {submitError && (
          <div style={{ marginTop: 12, fontSize: 13, color: 'var(--red)', padding: '10px 14px', background: 'rgba(184,50,50,0.06)', borderRadius: 'var(--radius)' }}>
            {submitError}
          </div>
        )}

        {/* Agent progress panel */}
        {(session.isRunning || session.isComplete || session.agentStates.some(a => a.status !== 'queued')) && (
          <div style={{ marginTop: 48 }}>
            <AgentProgressPanel
              session={session}
              onViewReport={session.isComplete && session.job ? () => onViewReport(session.job!.id) : undefined}
              onCancel={session.isRunning ? cancel : undefined}
            />
          </div>
        )}

        {/* Job history */}
        <div style={{ marginTop: 64 }}>
          <JobHistory onViewReport={onViewReport} />
        </div>
      </div>
    </div>
  )
}
