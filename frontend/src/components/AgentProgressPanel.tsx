'use client'

import type { ResearchSession, AgentState } from '@/lib/use-research'
import type { AgentName } from '@/types'

const AGENT_LABELS: Record<AgentName, string> = {
  orchestrator: 'Orchestrator',
  filing: 'Filing Agent',
  earnings: 'Earnings Agent',
  comps: 'Comps Agent',
  news: 'News Agent',
  synthesis: 'Synthesis Agent',
  critique: 'Critique Agent',
  citation: 'Citation Agent',
}

const AGENT_DESCRIPTIONS: Record<AgentName, string> = {
  orchestrator: 'Decomposes research brief into sub-tasks',
  filing: 'Ingests SEC 10-K, 10-Q, 8-K filings via RAG',
  earnings: 'Scores earnings call tone and guidance',
  comps: 'Builds peer comparison table with live data',
  news: 'Analyses recent news with temporal weighting',
  synthesis: 'Writes bull/bear/risk/valuation sections',
  critique: 'Red-teams report and assigns confidence score',
  citation: 'Maps every claim to its source document',
}

const STATUS_COLORS = {
  queued: 'var(--ink3)',
  running: 'var(--accent2)',
  completed: 'var(--emerald2)',
  failed: 'var(--red)',
}

interface AgentProgressPanelProps {
  session: ResearchSession
  onViewReport?: () => void
  onCancel?: () => void
}

export function AgentProgressPanel({ session, onViewReport, onCancel }: AgentProgressPanelProps) {
  const completed = session.agentStates.filter(a => a.status === 'completed').length
  const total = session.agentStates.length
  const pct = Math.round((completed / total) * 100)

  return (
    <div style={{
      background: 'var(--white)', border: '1px solid var(--paper3)',
      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '18px 24px', borderBottom: '1px solid var(--paper3)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 12,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink)', marginBottom: 2 }}>
            {session.job?.ticker} — Research pipeline
          </div>
          <div style={{ fontSize: 12, color: 'var(--ink3)' }}>
            {session.isComplete ? 'Complete' : session.isRunning ? 'Running' : 'Initialising'}
            {session.totalCost != null && ` · $${session.totalCost.toFixed(3)} total cost`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {onCancel && (
            <button onClick={onCancel} style={{
              fontSize: 13, fontFamily: 'var(--font-sans)',
              background: 'none', border: '1px solid var(--paper3)',
              borderRadius: 'var(--radius)', padding: '7px 16px',
              cursor: 'pointer', color: 'var(--ink2)',
            }}>Cancel</button>
          )}
          {onViewReport && (
            <button onClick={onViewReport} style={{
              fontSize: 13, fontWeight: 500, fontFamily: 'var(--font-sans)',
              background: 'var(--ink)', color: 'var(--white)',
              border: 'none', borderRadius: 'var(--radius)',
              padding: '7px 18px', cursor: 'pointer',
            }}>View report →</button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ padding: '16px 24px 0', borderBottom: '1px solid var(--paper3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--ink2)' }}>Overall progress</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink3)' }}>{pct}%</span>
        </div>
        <div style={{ height: 4, background: 'var(--paper2)', borderRadius: 100, marginBottom: 16, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 100,
            background: session.isComplete ? 'var(--emerald2)' : 'var(--accent2)',
            width: `${pct}%`, transition: 'width 0.6s ease',
          }} />
        </div>
      </div>

      {/* Agent list */}
      <div style={{ padding: 16 }}>
        {session.agentStates.map((agent, i) => (
          <AgentRow key={agent.name} agent={agent} index={i} />
        ))}
      </div>

      {/* Error */}
      {session.error && (
        <div style={{
          margin: '0 16px 16px', padding: '10px 14px',
          background: 'rgba(184,50,50,0.06)', borderRadius: 'var(--radius)',
          fontSize: 13, color: 'var(--red)',
        }}>
          Pipeline error: {session.error}
        </div>
      )}
    </div>
  )
}

function AgentRow({ agent, index }: { agent: AgentState; index: number }) {
  const color = STATUS_COLORS[agent.status]
  const isRunning = agent.status === 'running'
  const isCompleted = agent.status === 'completed'

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 12, padding: '9px 10px',
      borderRadius: 'var(--radius)',
      background: isRunning ? 'rgba(45,90,143,0.04)' : isCompleted ? 'rgba(42,155,106,0.03)' : 'transparent',
      transition: 'background 0.3s',
    }}>
      {/* Status dot */}
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: color, marginTop: 5, flexShrink: 0,
        boxShadow: isRunning ? `0 0 0 3px rgba(45,90,143,0.15)` : 'none',
        animation: isRunning ? 'pulse 1.5s infinite' : 'none',
      }} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{
            fontSize: 13, fontWeight: 500,
            color: agent.status === 'queued' ? 'var(--ink3)' : 'var(--ink)',
          }}>
            {AGENT_LABELS[agent.name]}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {agent.durationMs && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink3)' }}>
                {(agent.durationMs / 1000).toFixed(1)}s
              </span>
            )}
            <span style={{
              fontSize: 11, fontWeight: 500, letterSpacing: '0.04em',
              padding: '2px 8px', borderRadius: 100,
              background: isCompleted ? 'rgba(42,155,106,0.08)' : isRunning ? 'rgba(45,90,143,0.08)' : 'var(--paper2)',
              color,
            }}>
              {agent.status === 'running' ? 'running…' : agent.status}
            </span>
          </div>
        </div>
        <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--ink3)', marginTop: 1 }}>
          {AGENT_DESCRIPTIONS[agent.name]}
        </div>
        {agent.error && (
          <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 4 }}>{agent.error}</div>
        )}
      </div>
    </div>
  )
}
