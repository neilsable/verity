'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/auth-context'
import { LoginPage } from '@/components/LoginPage'
import { Dashboard } from '@/components/Dashboard'
import { ReportViewer } from '@/components/ReportViewer'
import type { ResearchJob } from '@/types'

export type AppView = 'dashboard' | 'report'

export function AppShell() {
  const { isAuthenticated, isLoading } = useAuth()
  const [view, setView] = useState<AppView>('dashboard')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'var(--paper)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--font-serif)', fontSize: 24,
            color: 'var(--ink)', marginBottom: 8,
          }}>VERITY</div>
          <div style={{ fontSize: 13, color: 'var(--ink3)' }}>Loading...</div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) return <LoginPage />

  if (view === 'report' && selectedJobId) {
    return (
      <ReportViewer
        jobId={selectedJobId}
        onBack={() => { setView('dashboard'); setSelectedJobId(null) }}
      />
    )
  }

  return (
    <Dashboard
      onViewReport={(jobId: string) => { setSelectedJobId(jobId); setView('report') }}
    />
  )
}
