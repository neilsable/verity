'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth-context'
import { researchApi } from '@/lib/api'
import type { ResearchReport, Citation, CritiqueFlag } from '@/types'

interface ReportViewerProps {
  jobId: string
  onBack: () => void
}

export function ReportViewer({ jobId, onBack }: ReportViewerProps) {
  const { token } = useAuth()
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeSection, setActiveSection] = useState('summary')

  useEffect(() => {
    if (!token) return
    researchApi.getReport(jobId, token)
      .then(r => { setReport(r); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [jobId, token])

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--paper)' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: 'var(--font-serif)', fontSize: 20, color: 'var(--ink)', marginBottom: 8 }}>Loading report...</div>
      </div>
    </div>
  )

  if (error || !report) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--paper)' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 16, color: 'var(--red)', marginBottom: 16 }}>{error || 'Report not found'}</div>
        <button onClick={onBack} style={{ fontSize: 14, color: 'var(--accent2)', background: 'none', border: 'none', cursor: 'pointer' }}>← Back</button>
      </div>
    </div>
  )

  const sections = [
    { id: 'summary', label: 'Summary' },
    { id: 'bull', label: 'Bull Case' },
    { id: 'bear', label: 'Bear Case' },
    { id: 'valuation', label: 'Valuation' },
    { id: 'risks', label: 'Risks' },
    { id: 'citations', label: `Citations (${report.citations.length})` },
  ]

  return (
    <div style={{ minHeight: '100vh', background: 'var(--paper)', fontFamily: 'var(--font-sans)' }}>

      {/* Nav */}
      <nav style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        display: 'flex', alignItems: 'center', gap: 20,
        padding: '0 40px', height: 60,
        background: 'rgba(248,247,244,0.95)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--paper3)',
      }}>
        <button onClick={onBack} style={{
          fontSize: 13, color: 'var(--ink2)', background: 'none',
          border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>← Back</button>
        <div style={{ width: 1, height: 20, background: 'var(--paper3)' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 500, color: 'var(--ink)', letterSpacing: '0.04em' }}>
          {report.ticker}
        </span>
        <span style={{ fontSize: 14, fontWeight: 300, color: 'var(--ink3)' }}>{report.company_name}</span>
        <div style={{ flex: 1 }} />
        <div style={{
          fontSize: 12, fontWeight: 500, padding: '4px 12px',
          background: `rgba(42,155,106,${report.overall_confidence})`,
          color: 'var(--emerald2)', borderRadius: 100,
          border: '1px solid rgba(42,155,106,0.2)',
        }}>
          {Math.round(report.overall_confidence * 100)}% confidence
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink3)', fontFamily: 'var(--font-mono)' }}>
          ${report.total_cost_usd.toFixed(3)}
        </div>
      </nav>

      <div style={{ paddingTop: 80, maxWidth: 900, margin: '0 auto', padding: '80px 40px 80px' }}>

        {/* Title */}
        <div style={{ marginBottom: 40 }}>
          <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 10 }}>
            Equity Research — {new Date(report.generated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
          </div>
          <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: 'clamp(32px,5vw,52px)', lineHeight: 1.05, letterSpacing: '-0.02em', color: 'var(--ink)' }}>
            {report.company_name}
          </h1>

          {/* Critique flags */}
          {report.critique_flags.length > 0 && (
            <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(201,168,76,0.08)', border: '1px solid rgba(201,168,76,0.2)', borderRadius: 'var(--radius)', fontSize: 13, color: 'var(--ink2)' }}>
              ⚠ {report.critique_flags.length} claim{report.critique_flags.length !== 1 ? 's' : ''} flagged for review by the Critique Agent
            </div>
          )}
        </div>

        {/* Section tabs */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 32, borderBottom: '1px solid var(--paper3)', paddingBottom: 0 }}>
          {sections.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              style={{
                fontSize: 13, fontWeight: activeSection === s.id ? 500 : 400,
                fontFamily: 'var(--font-sans)',
                color: activeSection === s.id ? 'var(--ink)' : 'var(--ink3)',
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '10px 16px 12px',
                borderBottom: `2px solid ${activeSection === s.id ? 'var(--ink)' : 'transparent'}`,
                marginBottom: -1, transition: 'all 0.15s',
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Section content */}
        <div style={{ maxWidth: 720 }}>
          {activeSection === 'summary' && <ReportSection title="Executive Summary" content={report.executive_summary} />}
          {activeSection === 'bull' && <ReportSection title="Bull Thesis" content={report.bull_thesis} accent="var(--emerald2)" />}
          {activeSection === 'bear' && <ReportSection title="Bear Thesis" content={report.bear_thesis} accent="var(--red)" />}
          {activeSection === 'valuation' && <ReportSection title="Valuation" content={report.valuation_section} />}
          {activeSection === 'risks' && (
            <div>
              <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 28, color: 'var(--ink)', marginBottom: 20 }}>Key Risks</h2>
              {report.key_risks.map((risk, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 14, padding: '12px 16px', background: 'var(--white)', border: '1px solid var(--paper3)', borderLeft: '2px solid var(--red)', borderRadius: 'var(--radius)' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--red)', fontWeight: 500, flexShrink: 0, marginTop: 2 }}>{String(i+1).padStart(2,'0')}</span>
                  <span style={{ fontSize: 14, fontWeight: 300, color: 'var(--ink2)', lineHeight: 1.6 }}>{risk}</span>
                </div>
              ))}
            </div>
          )}
          {activeSection === 'citations' && <CitationsPanel citations={report.citations} flags={report.critique_flags} />}
        </div>

        {/* Footer stats */}
        <div style={{ marginTop: 60, paddingTop: 24, borderTop: '1px solid var(--paper3)', display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          {[
            { label: 'Input tokens', value: report.total_input_tokens.toLocaleString() },
            { label: 'Output tokens', value: report.total_output_tokens.toLocaleString() },
            { label: 'Total cost', value: `$${report.total_cost_usd.toFixed(4)}` },
            { label: 'Citations', value: String(report.citations.length) },
            { label: 'Confidence', value: `${Math.round(report.overall_confidence * 100)}%` },
          ].map(stat => (
            <div key={stat.label}>
              <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 4 }}>{stat.label}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, color: 'var(--ink)' }}>{stat.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ReportSection({ title, content, accent }: { title: string; content: string; accent?: string }) {
  return (
    <div>
      <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 28, color: 'var(--ink)', marginBottom: 20, paddingLeft: accent ? 16 : 0, borderLeft: accent ? `3px solid ${accent}` : 'none' }}>
        {title}
      </h2>
      <div style={{ fontSize: 15, fontWeight: 300, lineHeight: 1.85, color: 'var(--ink2)', whiteSpace: 'pre-wrap' }}>
        {content || 'No content available for this section.'}
      </div>
    </div>
  )
}

function CitationsPanel({ citations, flags }: { citations: Citation[]; flags: CritiqueFlag[] }) {
  return (
    <div>
      <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 28, color: 'var(--ink)', marginBottom: 20 }}>
        Citation Index
      </h2>

      {flags.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--red)', marginBottom: 12 }}>Critique Flags</div>
          {flags.map(flag => (
            <div key={flag.flag_id} style={{ padding: '12px 16px', background: 'rgba(184,50,50,0.04)', border: '1px solid rgba(184,50,50,0.15)', borderRadius: 'var(--radius)', marginBottom: 10 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--red)', marginBottom: 4 }}>{flag.flag_type}</div>
              <div style={{ fontSize: 13, fontWeight: 300, color: 'var(--ink2)', marginBottom: 4 }}>{flag.claim_text}</div>
              <div style={{ fontSize: 12, color: 'var(--ink3)' }}>{flag.explanation}</div>
            </div>
          ))}
        </div>
      )}

      {citations.length === 0 ? (
        <p style={{ fontSize: 14, color: 'var(--ink3)' }}>No citations generated.</p>
      ) : (
        citations.map((cite, i) => (
          <div key={cite.citation_id} style={{ padding: '14px 16px', background: 'var(--white)', border: '1px solid var(--paper3)', borderRadius: 'var(--radius)', marginBottom: 10 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 500, background: 'rgba(201,168,76,0.15)', color: 'var(--gold)', borderRadius: 3, padding: '2px 6px', flexShrink: 0 }}>
                [{i + 1}]
              </span>
              <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--ink)', lineHeight: 1.5 }}>{cite.claim_text}</span>
            </div>
            <div style={{ paddingLeft: 32 }}>
              <div style={{ fontSize: 12, color: 'var(--accent2)', marginBottom: 4 }}>
                <a href={cite.source_url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>
                  {cite.source_document}
                  {cite.filing_date && ` · ${new Date(cite.filing_date).getFullYear()}`}
                </a>
              </div>
              <div style={{ fontSize: 12, fontWeight: 300, color: 'var(--ink3)', fontStyle: 'italic', lineHeight: 1.6, borderLeft: '2px solid var(--paper3)', paddingLeft: 10 }}>
                "{cite.passage}"
              </div>
              <div style={{ fontSize: 11, color: 'var(--ink3)', marginTop: 4 }}>
                Confidence: {Math.round(cite.confidence * 100)}%
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
