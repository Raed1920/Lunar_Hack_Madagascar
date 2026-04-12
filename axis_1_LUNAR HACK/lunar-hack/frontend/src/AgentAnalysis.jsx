import { useState, useEffect, useCallback } from 'react'
import './AgentAnalysis.css'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// ─── Risk badge ───────────────────────────────────────────────
function RiskBadge({ level }) {
  const map = {
    CRITIQUE: { color: '#ff4d4d', bg: 'rgba(255,77,77,0.12)', icon: '🔴' },
    ÉLEVÉ: { color: '#ff9f43', bg: 'rgba(255,159,67,0.12)', icon: '🟠' },
    MODÉRÉ: { color: '#f7c948', bg: 'rgba(247,201,72,0.12)', icon: '🟡' },
    FAIBLE: { color: '#26d476', bg: 'rgba(38,212,118,0.12)', icon: '🟢' },
  }
  const safe = (level || 'MODÉRÉ').toUpperCase()
  const style = map[safe] || map['MODÉRÉ']
  return (
    <span
      className="risk-badge"
      style={{ color: style.color, background: style.bg, border: `1px solid ${style.color}33` }}
    >
      {style.icon} Risque {safe}
    </span>
  )
}

// ─── Priority pill ────────────────────────────────────────────
function PriorityPill({ priority }) {
  const map = { haute: '#ff4d4d', moyenne: '#f7c948', faible: '#26d476' }
  const key = (priority || 'moyenne').toLowerCase()
  const color = map[key] || map['moyenne']
  return (
    <span className="priority-pill" style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>
      {priority}
    </span>
  )
}

// ─── Collapsible JSON email card ──────────────────────────────
function EmailCard({ email, type }) {
  const [expanded, setExpanded] = useState(false)
  const isChurn = type === 'churn'
  const accentColor = isChurn ? '#ff6b6b' : '#26d476'
  return (
    <div className="email-card" style={{ borderLeft: `3px solid ${accentColor}` }}>
      <div className="email-card-header" onClick={() => setExpanded((v) => !v)}>
        <div>
          <span className="email-to">{email.customer_name || email.to}</span>
          <span className="email-subject">{email.subject}</span>
        </div>
        <div className="email-meta">
          <span className="email-type-badge" style={{ background: `${accentColor}22`, color: accentColor }}>
            {isChurn ? '⚠ Churn Risk' : '⭐ High Value'}
          </span>
          <span className="email-expand-icon">{expanded ? '↑' : '↓'}</span>
        </div>
      </div>

      {expanded && (
        <div className="email-body">
          <div className="email-field">
            <span className="ef-label">To:</span> <span className="ef-val">{email.to}</span>
          </div>
          <div className="email-field">
            <span className="ef-label">Campaign:</span> <span className="ef-val">{email.campaign_type}</span>
          </div>
          {email.body_html && (
            <div className="email-html-preview">
              <div dangerouslySetInnerHTML={{ __html: email.body_html }} />
            </div>
          )}
          {email.personalization_tokens && (
            <div className="email-tokens">
              <span className="ef-label">Tokens:</span>
              <pre>{JSON.stringify(email.personalization_tokens, null, 2)}</pre>
            </div>
          )}
          <details className="raw-json">
            <summary>JSON complet</summary>
            <pre>{JSON.stringify(email, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  )
}

// ─── External Factor Card ─────────────────────────────────────
function FactorCard({ factor }) {
  const score = Number(factor.relevance_score ?? 0)
  const scoreColor = score >= 7 ? '#ff4d4d' : score >= 4 ? '#f7c948' : '#26d476'
  return (
    <div className="factor-card">
      <div className="factor-header">
        <span className="factor-category">{factor.category}</span>
        <span className="factor-score" style={{ color: scoreColor }}>
          {score}/10
        </span>
      </div>
      <div className="factor-name">{factor.factor}</div>
      <p className="factor-explanation">{factor.explanation}</p>
      {factor.action_recommendation && (
        <div className="factor-action">💡 {factor.action_recommendation}</div>
      )}
      <div className="factor-score-bar">
        <div className="fsb-fill" style={{ width: `${score * 10}%`, background: scoreColor }} />
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────
export default function AgentAnalysis() {
  const [status, setStatus] = useState('idle') // idle | running | done | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('analyst')
  const [elapsed, setElapsed] = useState(0)
  const [timerInterval, setTimerInterval] = useState(null)

  // Load last cached result on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/agent-analysis/last`)
      .then((r) => r.json())
      .then((data) => {
        if (data?.analyst) setResult(data)
      })
      .catch(() => {})
  }, [])

  const triggerAnalysis = useCallback(async () => {
    setStatus('running')
    setError('')
    setElapsed(0)

    const iv = setInterval(() => setElapsed((e) => e + 1), 1000)
    setTimerInterval(iv)

    try {
      const res = await fetch(`${API_BASE}/api/agent-analysis`, { method: 'POST' })
      if (!res.ok) {
        const msg = await res.text()
        throw new Error(msg)
      }
      const data = await res.json()
      setResult(data)
      setStatus('done')
    } catch (err) {
      setError(err.message || 'Erreur inconnue')
      setStatus('error')
    } finally {
      clearInterval(iv)
      setTimerInterval(null)
    }
  }, [])

  // Cleanup timer on unmount
  useEffect(() => () => { if (timerInterval) clearInterval(timerInterval) }, [timerInterval])

  const analyst = result?.analyst ?? {}
  const profiler = result?.customer_profiler ?? {}
  const researcher = result?.market_researcher ?? {}
  const bizMarketing = result?.business_marketing ?? {}
  const highValueEmails = profiler?.high_value_emails ?? []
  const churnEmails = profiler?.churn_emails ?? []
  const externalFactors = researcher?.external_factors ?? []
  const topCorrelations = researcher?.top_correlations ?? []
  const recommendations = analyst?.recommendations ?? []
  const criticalIssues = analyst?.critical_issues ?? []
  const bizRecs = bizMarketing?.business_recommendations ?? []
  const mktPlan = bizMarketing?.marketing_plan ?? []

  const tabs = [
    { id: 'analyst', label: '📊 Analyse KPI', badge: criticalIssues.length },
    { id: 'emails', label: '✉️ Emails cibles', badge: highValueEmails.length + churnEmails.length },
    { id: 'research', label: '🔍 Recherche externe', badge: externalFactors.length },
    { id: 'bizmkt', label: '🎪 Business & Marketing', badge: bizRecs.length + mktPlan.length },
  ]

  return (
    <div className="aa-page">
      {/* ── Header ── */}
      <header className="aa-header">
        <div className="aa-header-left">
          <div className="aa-header-icon">🤖</div>
          <div>
            <h1>Intelligence Agents KPI</h1>
            <p>Analyse temps réel · Emails clients · Veille macro</p>
          </div>
        </div>
        <div className="aa-header-right">
          {result && <span className="aa-last-run">Dernière analyse: {result.generated_at?.slice(0, 19).replace('T', ' ')} UTC</span>}
          <button
            className={`aa-run-btn ${status === 'running' ? 'running' : ''}`}
            onClick={triggerAnalysis}
            disabled={status === 'running'}
          >
            {status === 'running' ? (
              <><span className="spinner" /> Agents en cours… {elapsed}s</>
            ) : (
              <>⚡ Lancer l'analyse multi‑agents</>
            )}
          </button>
        </div>
      </header>

      {/* ── Status banner ── */}
      {status === 'running' && (
        <div className="aa-banner running">
          <div className="aa-banner-dots">
            <span /><span /><span />
          </div>
          <div>
                      <strong>4 agents IA en cours d'exécution…</strong>
            <p>KPI Analyst → Customer Profiler → Market Researcher → Business &amp; Marketing · {elapsed}s écoulées</p>
          </div>
        </div>
      )}
      {status === 'error' && (
        <div className="aa-banner error">
          ❌ <strong>Erreur:</strong> {error}
        </div>
      )}
      {status === 'done' && (
        <div className="aa-banner success">
                    ✅ <strong>Analyse complète!</strong> 4 agents ont terminé leur travail.
        </div>
      )}

      {/* ── No result placeholder ── */}
      {!result && status === 'idle' && (
        <div className="aa-placeholder">
          <div className="aa-placeholder-icon">🤖</div>
          <h2>Aucune analyse disponible</h2>
                    <p>Cliquez sur <strong>«&nbsp;Lancer l'analyse multi-agents&nbsp;»</strong> pour démarrer les 4 agents IA.</p>
          <ul className="aa-agent-list">
            <li>🔬 <strong>KPI Analyst</strong> — Analyse profonde + recommandations</li>
            <li>👥 <strong>Customer Profiler</strong> — Emails acheteurs VIP &amp; churn</li>
            <li>🌐 <strong>Market Researcher</strong> — Causes business &amp; macro</li>
            <li>🎯 <strong>Business &amp; Marketing</strong> — Produits, pricing, plan marketing</li>
          </ul>
        </div>
      )}

      {/* ── Result area ── */}
      {result && (
        <>
          {/* Executive summary bar */}
          {analyst.executive_summary && (
            <div className="aa-exec-summary">
              <span className="exec-icon">📋</span>
              <p>{analyst.executive_summary}</p>
              {analyst.risk_level && <RiskBadge level={analyst.risk_level} />}
            </div>
          )}

          {/* Tabs */}
          <div className="aa-tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                className={`aa-tab ${activeTab === t.id ? 'active' : ''}`}
                onClick={() => setActiveTab(t.id)}
              >
                {t.label}
                {t.badge > 0 && <span className="tab-badge">{t.badge}</span>}
              </button>
            ))}
          </div>

          {/* ── Tab: KPI Analyst ── */}
          {activeTab === 'analyst' && (
            <div className="aa-tab-content">
              {/* Analysis narrative */}
              {analyst.analysis && (
                <div className="aa-card">
                  <h2>🔬 Analyse détaillée</h2>
                  <p className="aa-narrative">{analyst.analysis}</p>
                </div>
              )}

              {/* Critical issues */}
              {criticalIssues.length > 0 && (
                <div className="aa-card">
                  <h2>🚨 Problèmes critiques</h2>
                  <div className="issues-grid">
                    {criticalIssues.map((issue, idx) => (
                      <div className="issue-card" key={idx}>
                        <div className="issue-number">#{idx + 1}</div>
                        <div>
                          <strong>{issue.title}</strong>
                          <p>{issue.description}</p>
                          {issue.estimated_impact && (
                            <span className="impact-tag">💥 Impact: {issue.estimated_impact}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {recommendations.length > 0 && (
                <div className="aa-card">
                  <h2>💡 Recommandations</h2>
                  <div className="reco-list">
                    {recommendations.map((r, idx) => (
                      <div className="reco-item" key={idx}>
                        <div className="reco-index">{idx + 1}</div>
                        <div className="reco-body">
                          <div className="reco-action">
                            <PriorityPill priority={r.priority} />
                            <strong>{r.action}</strong>
                          </div>
                          {r.expected_result && <p className="reco-result">→ {r.expected_result}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw fallback */}
              {analyst.raw_output && (
                <div className="aa-card raw-output">
                  <h2>Sortie brute agent Analyst</h2>
                  <pre>{analyst.raw_output}</pre>
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Emails ── */}
          {activeTab === 'emails' && (
            <div className="aa-tab-content">
              {profiler.segmentation_summary && (
                <div className="aa-card">
                  <h2>📊 Stratégie de segmentation</h2>
                  <p className="aa-narrative">{profiler.segmentation_summary}</p>
                </div>
              )}

              <div className="aa-emails-split">
                <div className="aa-email-col">
                  <h2 className="col-title green">⭐ Clients haute valeur ({highValueEmails.length})</h2>
                  {highValueEmails.length === 0 ? (
                    <p className="empty-hint">Aucun email généré pour les gros acheteurs.</p>
                  ) : (
                    highValueEmails.map((email, idx) => (
                      <EmailCard key={`hv-${idx}`} email={email} type="high_value" />
                    ))
                  )}
                </div>
                <div className="aa-email-col">
                  <h2 className="col-title red">⚠️ Risque churn ({churnEmails.length})</h2>
                  {churnEmails.length === 0 ? (
                    <p className="empty-hint">Aucun email généré pour les clients à risque.</p>
                  ) : (
                    churnEmails.map((email, idx) => (
                      <EmailCard key={`ch-${idx}`} email={email} type="churn" />
                    ))
                  )}
                </div>
              </div>

              {profiler.raw_output && (
                <div className="aa-card raw-output">
                  <h2>Sortie brute agent Profiler</h2>
                  <pre>{profiler.raw_output}</pre>
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Research ── */}
          {activeTab === 'research' && (
            <div className="aa-tab-content">
              {researcher.research_summary && (
                <div className="aa-card">
                  <h2>🔍 Résumé de recherche</h2>
                  <p className="aa-narrative">{researcher.research_summary}</p>
                  {researcher.confidence_level && (
                    <span className="confidence-badge">
                      Confiance: <strong>{researcher.confidence_level}</strong>
                    </span>
                  )}
                </div>
              )}

              {topCorrelations.length > 0 && (
                <div className="aa-card">
                  <h2>🔗 Top corrélations KPI ↔ Facteurs externes</h2>
                  <ul className="correlations-list">
                    {topCorrelations.map((c, idx) => (
                      <li key={idx}>{typeof c === 'string' ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                </div>
              )}

              {externalFactors.length > 0 && (
                <div className="aa-card">
                  <h2>🌍 Facteurs externes identifiés ({externalFactors.length})</h2>
                  <div className="factors-grid">
                    {externalFactors.map((f, idx) => (
                      <FactorCard key={idx} factor={f} />
                    ))}
                  </div>
                </div>
              )}

              {researcher.raw_output && (
                <div className="aa-card raw-output">
                  <h2>Sortie brute agent Researcher</h2>
                  <pre>{researcher.raw_output}</pre>
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Business & Marketing ── */}
          {activeTab === 'bizmkt' && (
            <div className="aa-tab-content">
              {bizMarketing.strategy_summary && (
                <div className="aa-card">
                  <h2>🎯 Stratégie Business & Marketing</h2>
                  <p className="aa-narrative">{bizMarketing.strategy_summary}</p>
                </div>
              )}

              {bizMarketing.quick_wins?.length > 0 && (
                <div className="aa-card">
                  <h2>⚡ Quick Wins immédiats</h2>
                  <ul className="correlations-list">
                    {bizMarketing.quick_wins.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}

              {bizRecs.length > 0 && (
                <div className="aa-card">
                  <h2>🏪 Recommandations Produits ({bizRecs.length})</h2>
                  <div className="factors-grid">
                    {bizRecs.map((r, i) => (
                      <div key={i} className="factor-card" style={{ borderLeft: '3px solid #6366f1' }}>
                        <div className="factor-header">
                          <span className="factor-category">{r.category}</span>
                          <span style={{ fontSize: '0.75rem', color: r.priority === 'haute' ? '#ff4d4d' : r.priority === 'moyenne' ? '#f7c948' : '#26d476', fontWeight: 700 }}>{r.priority}</span>
                        </div>
                        <div className="factor-name">{r.product_name || 'Général'}</div>
                        <p className="factor-explanation">{r.action}</p>
                        {r.expected_impact && <div className="factor-action">💥 {r.expected_impact}</div>}
                        {r.timeframe && <span style={{ fontSize: '0.72rem', color: '#475569' }}>⏱ {r.timeframe}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {mktPlan.length > 0 && (
                <div className="aa-card">
                  <h2>📣 Plan Marketing ({mktPlan.length} actions)</h2>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {mktPlan.map((m, i) => (
                      <div key={i} className="reco-item" style={{ borderRadius: 10, padding: '12px 16px' }}>
                        <div className="reco-index" style={{ minWidth: 36, fontSize: '1rem' }}>
                          {['📘','🛍️','✉️','📱','🎵','📸','💬','🔍'][['Facebook Ads','Google Shopping','Email','SMS','TikTok','Instagram','WhatsApp','SEO'].indexOf(m.channel)] ?? '📡'}
                        </div>
                        <div className="reco-body">
                          <div className="reco-action">
                            <PriorityPill priority={m.priority} />
                            <strong>{m.channel}</strong>
                          </div>
                          <p className="reco-result">{m.action}</p>
                          {m.message_key && <p style={{ fontSize: '0.8rem', color: '#a5b4fc', margin: '4px 0 0' }}>💬 {m.message_key}</p>}
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 4 }}>
                            {m.target_segment && <span className="impact-tag" style={{ background: 'rgba(99,102,241,0.08)', color: '#818cf8' }}>🎯 {m.target_segment}</span>}
                            {m.timing && <span className="impact-tag" style={{ background: 'rgba(255,255,255,0.04)', color: '#64748b' }}>⏰ {m.timing}</span>}
                            {m.kpi_to_watch && <span className="impact-tag" style={{ background: 'rgba(38,212,118,0.07)', color: '#26d476' }}>📊 {m.kpi_to_watch}</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {bizMarketing.raw_output && (
                <div className="aa-card raw-output">
                  <h2>Sortie brute agent Advisor</h2>
                  <pre>{bizMarketing.raw_output}</pre>
                </div>
              )}
            </div>
          )}

          {/* Full JSON download */}
          <div className="aa-json-export">
            <details>
              <summary>📥 Voir / Exporter le JSON complet</summary>
              <div className="json-actions">
                <button
                  onClick={() => {
                    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `agent-analysis-${result.kpi_day ?? 'export'}.json`
                    a.click()
                  }}
                >
                  ⬇ Télécharger JSON
                </button>
              </div>
              <pre className="full-json">{JSON.stringify(result, null, 2)}</pre>
            </details>
          </div>
        </>
      )}
    </div>
  )
}
