'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth-context'
import { researchApi } from '@/lib/api'
import type { ResearchJob } from '@/types'

interface JobHistoryProps {
  onViewReport: (jobId: string) => void
}

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  completed: { bg: 'rgba(42,155,106,0.08)', color: 'var(--emerald2)', label: 'Complete' },
  running:   { bg: 'rgba(201,168,76,0.10)', color: 'var(--gold)',     label: 'Running'  },
  pending:   { bg: 'var(--paper2)',          color: 'var(--ink3)',     label: 'Queued'   },
  failed:    { bg: 'rgba(184,50,50,0.08)',   color: 'var(--red)',      label: 'Failed'   },
  cancelled: { bg: 'var(--paper2)',          color: 'var(--ink3)',     label: 'Cancelled'},
}

export function JobHistory({ onViewReport }: JobHistoryProps) {
  const { token } = useAuth()
  const [jobs, setJobs] = useState<ResearchJob[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    researchApi.getHistory(token).then(r => {
      setJobs(r.items as ResearchJob[])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [token])

  if (loading) return (
    <div style={{ fontSize: 13, color: 'var(--ink3)', padding: '20px 0' }}>Loading history...</div>
  )

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 20,
      }}>
        <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink3)' }}>
          Research History
        </div>
        <span style={{ fontSize: 12, color: 'var(--ink3)' }}>{jobs.length} jobs</span>
      </div>

      {jobs.length === 0 ? (
        <div style={{
          padding: '40px 24px', textAlign: 'center',
          background: 'var(--white)', border: '1px solid var(--paper3)',
          borderRadius: 'var(--radius-lg)',
        }}>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: 20, color: 'var(--ink3)', marginBottom: 8 }}>
            No research jobs yet
          </div>
          <div style={{ fontSize: 14, fontWeight: 300, color: 'var(--ink3)' }}>
            Enter a ticker above to run your first analysis.
          </div>
        </div>
      ) : (
        <div style={{
          background: 'var(--white)', border: '1px solid var(--paper3)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          {jobs.map((job, i) => {
            const s = STATUS_STYLE[job.status] || STATUS_STYLE.pending
            return (
              <div
                key={job.id}
                onClick={() => job.status === 'completed' && onViewReport(job.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 16,
                  padding: '14px 20px',
                  borderBottom: i < jobs.length - 1 ? '1px solid var(--paper3)' : 'none',
                  cursor: job.status === 'completed' ? 'pointer' : 'default',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => job.status === 'completed' && ((e.currentTarget as HTMLElement).style.background = 'var(--paper)')}
                onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
              >
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 500,
                  color: 'var(--ink)', minWidth: 60, letterSpacing: '0.04em',
                }}>{job.ticker}</span>

                <span style={{
                  fontSize: 13, fontWeight: 300, color: 'var(--ink2)',
                  flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{job.research_brief}</span>

                <span style={{
                  fontSize: 11, fontWeight: 500, letterSpacing: '0.04em',
                  padding: '3px 10px', borderRadius: 100,
                  background: s.bg, color: s.color, flexShrink: 0,
                }}>{s.label}</span>

                {job.cost_usd != null && (
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12,
                    color: 'var(--ink3)', minWidth: 48, textAlign: 'right',
                  }}>${job.cost_usd.toFixed(3)}</span>
                )}

                {job.status === 'completed' && (
                  <span style={{ fontSize: 13, color: 'var(--accent2)', flexShrink: 0 }}>→</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
