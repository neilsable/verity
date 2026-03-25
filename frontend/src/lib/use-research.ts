'use client'

import { useState, useRef, useCallback } from 'react'
import { researchApi } from '@/lib/api'
import type { ResearchJob, ProgressEvent, AgentName } from '@/types'

export type AgentStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface AgentState {
  name: AgentName
  status: AgentStatus
  durationMs?: number
  error?: string
}

export interface ResearchSession {
  job: ResearchJob | null
  agentStates: AgentState[]
  isRunning: boolean
  isComplete: boolean
  error: string | null
  totalCost: number | null
}

const ALL_AGENTS: AgentName[] = [
  'orchestrator', 'filing', 'earnings', 'comps',
  'news', 'synthesis', 'critique', 'citation',
]

function makeInitialAgents(): AgentState[] {
  return ALL_AGENTS.map(name => ({ name, status: 'queued' as AgentStatus }))
}

export function useResearch(token: string | null) {
  const [session, setSession] = useState<ResearchSession>({
    job: null,
    agentStates: makeInitialAgents(),
    isRunning: false,
    isComplete: false,
    error: null,
    totalCost: null,
  })

  const esRef = useRef<(() => void) | null>(null)

  const updateAgent = useCallback((name: AgentName, update: Partial<AgentState>) => {
    setSession(s => ({
      ...s,
      agentStates: s.agentStates.map(a => a.name === name ? { ...a, ...update } : a),
    }))
  }, [])

  const startResearch = useCallback(async (ticker: string, brief: string) => {
    if (!token) throw new Error('Not authenticated')

    // Reset state
    setSession({
      job: null,
      agentStates: makeInitialAgents(),
      isRunning: true,
      isComplete: false,
      error: null,
      totalCost: null,
    })

    // Create job
    const job = await researchApi.createJob(ticker, brief, token)

    setSession(s => ({ ...s, job }))

    // Subscribe to SSE stream
    const cleanup = researchApi.streamProgress(
      job.id,
      token,
      (rawEvent: unknown) => {
        const event = rawEvent as ProgressEvent

        if (event.event === 'agent_started') {
          updateAgent(event.agent, { status: 'running' })
        } else if (event.event === 'agent_completed') {
          updateAgent(event.agent, { status: 'completed', durationMs: event.duration_ms })
        } else if (event.event === 'agent_failed') {
          updateAgent(event.agent, { status: 'failed', error: event.error })
        } else if (event.event === 'job_completed') {
          setSession(s => ({
            ...s,
            isRunning: false,
            isComplete: true,
            totalCost: event.cost_usd,
          }))
          cleanup()
        } else if (event.event === 'job_failed') {
          setSession(s => ({
            ...s,
            isRunning: false,
            error: event.error,
          }))
          cleanup()
        }
      },
    )

    esRef.current = cleanup

    return job
  }, [token, updateAgent])

  const cancel = useCallback(() => {
    esRef.current?.()
    setSession(s => ({ ...s, isRunning: false }))
  }, [])

  return { session, startResearch, cancel }
}
