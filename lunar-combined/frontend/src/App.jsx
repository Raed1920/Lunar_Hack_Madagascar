import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const WS_BASE = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/kpis'

const numberFmt = new Intl.NumberFormat('fr-FR')
const moneyFmt = new Intl.NumberFormat('fr-TN', { style: 'currency', currency: 'TND' })

const KPI_META = {
  revenue_today: {
    title: "Chiffre d'affaires du jour",
    explain: "Mesure la performance commerciale immédiate et la capacité à générer du revenu.",
    format: (value) => moneyFmt.format(value ?? 0),
  },
  conversion_rate: {
    title: 'Taux de conversion',
    explain: "Indique l'efficacité du tunnel d'achat (visite -> commande).",
    format: (value) => `${(value ?? 0).toFixed(2)}%`,
  },
  average_basket: {
    title: 'Panier moyen',
    explain: "Aide à piloter les stratégies d'upsell, de bundles et de cross-sell.",
    format: (value) => moneyFmt.format(value ?? 0),
  },
  cart_abandonment_rate: {
    title: 'Taux d’abandon panier',
    explain: "Révèle les frictions de checkout et les pertes de revenus évitables.",
    format: (value) => `${(value ?? 0).toFixed(2)}%`,
  },
  orders_completed: {
    title: 'Commandes complétées',
    explain: "Suit le volume de ventes finalisées et la demande réelle.",
    format: (value) => numberFmt.format(value ?? 0),
  },
  conversations_today: {
    title: "Conversations client aujourd'hui",
    explain: "Signal d'intention et de besoins clients pour améliorer l'assistance et le produit.",
    format: (value) => numberFmt.format(value ?? 0),
  },
}

function buildQuery(filters) {
  const params = new URLSearchParams()
  if (filters.product_id) params.set('product_id', filters.product_id)
  if (filters.customer_id) params.set('customer_id', filters.customer_id)
  if (filters.cart_filter) params.set('cart_filter', filters.cart_filter)
  return params.toString()
}

function LineChart({ points, dataKey, color, title }) {
  if (!points.length) return <p className="empty">Pas assez de données pour cette tendance.</p>
  const values = points.map((p) => Number(p[dataKey] ?? 0))
  const max = Math.max(1, ...values)
  const min = Math.min(...values)
  const range = Math.max(1, max - min)
  const width = 560
  const height = 180
  const step = values.length > 1 ? width / (values.length - 1) : width
  const polyline = values
    .map((value, idx) => {
      const x = idx * step
      const y = height - ((value - min) / range) * (height - 10) - 5
      return `${x},${y}`
    })
    .join(' ')

  return (
    <div className="chart-block">
      <h3>{title}</h3>
      <svg className="line-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <polyline fill="none" stroke={color} strokeWidth="3" points={polyline} />
      </svg>
    </div>
  )
}

function BarChart({ rows, valueKey = 'quantity', labelKey = 'product_name', secondaryKey = 'revenue' }) {
  if (!rows.length) return <p className="empty">Pas de données disponibles.</p>
  const maxVal = Math.max(1, ...rows.map((r) => Number(r[valueKey] ?? 0)))
  return (
    <div className="bars">
      {rows.map((row, idx) => (
        <div className="bar-row" key={`${row[labelKey]}-${idx}`}>
          <div className="bar-label">
            <strong>{row[labelKey]}</strong>
            <span>{secondaryKey ? moneyFmt.format(row[secondaryKey] ?? 0) : ''}</span>
          </div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(Number(row[valueKey] ?? 0) / maxVal) * 100}%` }} />
          </div>
          <span className="bar-val">{numberFmt.format(row[valueKey] ?? 0)}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Channel icon map ────────────────────────────────────────
const CHANNEL_ICONS = {
  'Facebook Ads': '📘', 'Google Shopping': '🛍️', 'Email': '✉️',
  'SMS': '📱', 'TikTok': '🎵', 'Instagram': '📸',
  'WhatsApp': '💬', 'SEO': '🔍',
}

// ─── Priority color map ──────────────────────────────────────
const PRIORITY_STYLES = {
  haute:   { bg: 'rgba(255,77,77,0.12)',   color: '#ff6b6b',  border: 'rgba(255,77,77,0.25)' },
  moyenne: { bg: 'rgba(247,201,72,0.12)',  color: '#f7c948',  border: 'rgba(247,201,72,0.25)' },
  faible:  { bg: 'rgba(38,212,118,0.10)', color: '#26d476',  border: 'rgba(38,212,118,0.2)' },
}

const CATEGORY_LABELS = {
  pricing: '💰 Pricing', bundle: '📦 Bundle / Cross-sell',
  stock: '🏭 Stock / Réassort', visibility: '👁️ Visibilité',
  segmentation: '👥 Segmentation',
}

function SmartRecoPanel({ data, generatedAt }) {
  const businessRecs = data?.business_recommendations ?? []
  const marketingPlan = data?.marketing_plan ?? []
  const quickWins = data?.quick_wins ?? []
  const summary = data?.strategy_summary ?? ''
  const [tab, setTab] = useState('business')

  return (
    <div className="srp">
      {summary && (
        <div className="srp-summary">
          <span className="srp-summary-icon">📋</span>
          <p>{summary}</p>
          {generatedAt && <span className="srp-ts">{generatedAt.slice(0, 19).replace('T', ' ')} UTC</span>}
        </div>
      )}

      {quickWins.length > 0 && (
        <div className="srp-quickwins">
          <span className="srp-qw-label">⚡ Quick Wins</span>
          <div className="srp-qw-list">
            {quickWins.map((w, i) => <span key={i} className="srp-qw">{w}</span>)}
          </div>
        </div>
      )}

      <div className="srp-tabs">
        <button className={`srp-tab${tab === 'business' ? ' active' : ''}`} onClick={() => setTab('business')}>
          🏪 Produits Business
          {businessRecs.length > 0 && <span className="srp-badge">{businessRecs.length}</span>}
        </button>
        <button className={`srp-tab${tab === 'marketing' ? ' active' : ''}`} onClick={() => setTab('marketing')}>
          📣 Plan Marketing
          {marketingPlan.length > 0 && <span className="srp-badge">{marketingPlan.length}</span>}
        </button>
      </div>

      {tab === 'business' && (
        <div className="srp-content">
          {businessRecs.length === 0 ? (
            <p className="srp-empty">Aucune recommandation produit disponible.</p>
          ) : (
            <div className="srp-biz-grid">
              {businessRecs.map((r, i) => {
                const pStyle = PRIORITY_STYLES[r.priority?.toLowerCase()] ?? PRIORITY_STYLES.moyenne
                return (
                  <div key={i} className="srp-biz-card" style={{ borderLeft: `3px solid ${pStyle.color}` }}>
                    <div className="srp-biz-top">
                      <span className="srp-product-name">{r.product_name || 'Général'}</span>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span className="srp-cat">{CATEGORY_LABELS[r.category] ?? r.category}</span>
                        <span className="srp-pri" style={{ background: pStyle.bg, color: pStyle.color, border: `1px solid ${pStyle.border}` }}>
                          {r.priority}
                        </span>
                      </div>
                    </div>
                    <p className="srp-action">{r.action}</p>
                    {r.expected_impact && (
                      <div className="srp-impact">💥 {r.expected_impact}</div>
                    )}
                    {r.timeframe && (
                      <span className="srp-timeframe">⏱ {r.timeframe}</span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {tab === 'marketing' && (
        <div className="srp-content">
          {marketingPlan.length === 0 ? (
            <p className="srp-empty">Aucun plan marketing disponible.</p>
          ) : (
            <div className="srp-mkt-list">
              {marketingPlan.map((m, i) => {
                const pStyle = PRIORITY_STYLES[m.priority?.toLowerCase()] ?? PRIORITY_STYLES.moyenne
                const icon = CHANNEL_ICONS[m.channel] ?? '📡'
                return (
                  <div key={i} className="srp-mkt-row">
                    <div className="srp-mkt-channel">
                      <span className="srp-ch-icon">{icon}</span>
                      <span className="srp-ch-name">{m.channel}</span>
                      <span className="srp-pri" style={{ background: pStyle.bg, color: pStyle.color, border: `1px solid ${pStyle.border}` }}>
                        {m.priority}
                      </span>
                    </div>
                    <div className="srp-mkt-body">
                      <p className="srp-action">{m.action}</p>
                      {m.message_key && <div className="srp-msg-key">💬 {m.message_key}</div>}
                      <div className="srp-mkt-meta">
                        {m.target_segment && <span className="srp-seg">🎯 {m.target_segment}</span>}
                        {m.timing && <span className="srp-timing">⏰ {m.timing}</span>}
                        {m.kpi_to_watch && <span className="srp-kpi">📊 {m.kpi_to_watch}</span>}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {data?.raw_output && (
        <details className="srp-raw">
          <summary>Sortie brute agent</summary>
          <pre>{data.raw_output}</pre>
        </details>
      )}
    </div>
  )
}

function App() {
  const [snapshot, setSnapshot] = useState(null)
  const [connection, setConnection] = useState('connecting')
  const [filters, setFilters] = useState({ product_id: '', customer_id: '', cart_filter: '' })
  const query = useMemo(() => buildQuery(filters), [filters])
  const wsUrl = useMemo(() => (query ? `${WS_BASE}?${query}` : WS_BASE), [query])

  // ── Smart Recommendations state ──────────────────────────
  const [smartReco, setSmartReco] = useState(null)
  const [recoStatus, setRecoStatus] = useState('idle') // idle | running | done | error
  const [recoElapsed, setRecoElapsed] = useState(0)

  // Load last cached reco on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/smart-recommendations/last`)
      .then((r) => r.json())
      .then((d) => { if (d?.business_marketing) setSmartReco(d) })
      .catch(() => {})
  }, [])

  const triggerSmartReco = useCallback(async () => {
    setRecoStatus('running')
    setRecoElapsed(0)
    const iv = setInterval(() => setRecoElapsed((e) => e + 1), 1000)
    try {
      const qs = query ? `?${query}` : ''
      const res = await fetch(`${API_BASE}/api/smart-recommendations${qs}`, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setSmartReco(data)
      setRecoStatus('done')
    } catch {
      setRecoStatus('error')
    } finally {
      clearInterval(iv)
    }
  }, [query])

  useEffect(() => {
    let ws
    let reconnectTimer
    let mounted = true

    const connect = () => {
      setConnection('connecting')
      ws = new WebSocket(wsUrl)
      ws.onopen = () => mounted && setConnection('live')
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (mounted) setSnapshot(payload)
        } catch {
          if (mounted) setConnection('error')
        }
      }
      ws.onerror = () => mounted && setConnection('error')
      ws.onclose = () => {
        if (!mounted) return
        setConnection('reconnecting')
        reconnectTimer = setTimeout(connect, 1500)
      }
    }

    connect()
    return () => {
      mounted = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (ws && ws.readyState < 2) ws.close()
    }
  }, [wsUrl])

  useEffect(() => {
    fetch(query ? `${API_BASE}/api/kpis?${query}` : `${API_BASE}/api/kpis`)
      .then((res) => res.json())
      .then((payload) => setSnapshot(payload))
      .catch(() => setConnection('error'))
  }, [query])

  const kpis = snapshot?.kpis ?? {}
  const breakdowns = snapshot?.breakdowns ?? {}
  const topProducts = breakdowns.top_products ?? []
  const topCustomers = breakdowns.top_customers ?? []
  const cartDistribution = breakdowns.cart_distribution ?? {}
  const hourly = breakdowns.hourly ?? []
  const insights = snapshot?.insights ?? []
  const streamHistory = snapshot?.stream?.history ?? []
  const products = snapshot?.catalog?.products ?? []
  const customers = snapshot?.catalog?.customers ?? []
  const cartFilters = snapshot?.catalog?.cart_filters ?? []

  const revenueTrend = useMemo(
    () => streamHistory.slice(-40).map((p) => ({ value: p.revenue_today ?? 0 })),
    [streamHistory],
  )
  const conversionTrend = useMemo(
    () => streamHistory.slice(-40).map((p) => ({ value: p.conversion_rate ?? 0 })),
    [streamHistory],
  )

  return (
    <main className="dashboard">
      <header className="header">
        <div>
          <h1>Cockpit Business Tunisie (TND)</h1>
          <p>KPIs temps réel filtrables par produit, client et type de panier.</p>
        </div>
        <span className={`status status-${connection}`}>{connection}</span>
      </header>

      <section className="card filters">
        <h2>Filtres statistiques</h2>
        <div className="filters-grid">
          <label>
            Produit
            <select
              value={filters.product_id}
              onChange={(e) => setFilters((f) => ({ ...f, product_id: e.target.value }))}
            >
              <option value="">Tous les produits</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label>
            Client
            <select
              value={filters.customer_id}
              onChange={(e) => setFilters((f) => ({ ...f, customer_id: e.target.value }))}
            >
              <option value="">Tous les clients</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.id})</option>
              ))}
            </select>
          </label>
          <label>
            Type de panier
            <select
              value={filters.cart_filter}
              onChange={(e) => setFilters((f) => ({ ...f, cart_filter: e.target.value }))}
            >
              <option value="">Tous les paniers</option>
              {cartFilters.filter((c) => c.id !== 'tous_les_paniers').map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </label>
          <button onClick={() => setFilters({ product_id: '', customer_id: '', cart_filter: '' })}>
            Reinitialiser
          </button>
        </div>
      </section>

      <section className="kpi-grid">
        {Object.entries(KPI_META).map(([key, meta]) => (
          <article className="card kpi" key={key}>
            <h3>{meta.title}</h3>
            <strong>{meta.format(kpis[key])}</strong>
            <p>{meta.explain}</p>
          </article>
        ))}
      </section>

      <section className="split">
        <article className="card">
          <h2>Tendance CA (global stream)</h2>
          <LineChart points={revenueTrend} dataKey="value" color="#4ade80" title="Evolution CA en TND" />
        </article>
        <article className="card">
          <h2>Tendance conversion (global stream)</h2>
          <LineChart points={conversionTrend} dataKey="value" color="#60a5fa" title="Evolution conversion %" />
        </article>
      </section>

      <section className="split">
        <article className="card">
          <h2>Top produits (nom + CA)</h2>
          <BarChart rows={topProducts} valueKey="quantity" labelKey="product_name" secondaryKey="revenue" />
        </article>
        <article className="card">
          <h2>Top clients (commandes + CA)</h2>
          <BarChart rows={topCustomers} valueKey="orders" labelKey="customer_name" secondaryKey="revenue" />
        </article>
      </section>

      <section className="split">
        <article className="card">
          <h2>Distribution des paniers</h2>
          <table>
            <thead>
              <tr>
                <th>Segment</th>
                <th>Nombre</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(cartDistribution).map(([segment, count]) => (
                <tr key={segment}>
                  <td>{segment}</td>
                  <td>{numberFmt.format(count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="card">
          <h2>Repartition horaire</h2>
          <table>
            <thead>
              <tr>
                <th>Heure</th>
                <th>CA</th>
                <th>Commandes</th>
              </tr>
            </thead>
            <tbody>
              {hourly
                .filter((h) => h.revenue > 0 || h.orders > 0)
                .map((h) => (
                  <tr key={h.hour}>
                    <td>{h.hour}:00</td>
                    <td>{moneyFmt.format(h.revenue ?? 0)}</td>
                    <td>{numberFmt.format(h.orders ?? 0)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </article>
      </section>

      <section className="card insights">
        <h2>Insights automatiques</h2>
        <ul>
          {insights.map((text, idx) => (
            <li key={`${idx}-${text}`}>{text}</li>
          ))}
        </ul>
        <small>Derniere mise a jour: {snapshot?.last_updated ?? '-'}</small>
      </section>

      {/* ── AI Business & Marketing Recommendations ── */}
      <section className="card smart-reco">
        <div className="reco-header">
          <div>
            <h2>🤖 Recommandations IA — Business & Marketing</h2>
            <p className="reco-subtitle">
              Agent IA spécialisé: stratégie produit · pricing · bundles · plan marketing multicanal
            </p>
          </div>
          <button
            className={`reco-trigger-btn${recoStatus === 'running' ? ' running' : ''}`}
            onClick={triggerSmartReco}
            disabled={recoStatus === 'running'}
          >
            {recoStatus === 'running'
              ? `⏳ Analyse… ${recoElapsed}s`
              : smartReco ? '🔄 Relancer' : '⚡ Générer'}
          </button>
        </div>

        {recoStatus === 'running' && (
          <div className="reco-loading">
            <span className="reco-dot" /><span className="reco-dot" /><span className="reco-dot" />
            <span>Agent Business &amp; Marketing en cours… {recoElapsed}s</span>
          </div>
        )}

        {recoStatus === 'error' && (
          <p className="reco-error">❌ Erreur lors de l'analyse. Vérifiez le backend.</p>
        )}

        {smartReco?.business_marketing && (
          <SmartRecoPanel data={smartReco.business_marketing} generatedAt={smartReco.generated_at} />
        )}

        {!smartReco && recoStatus === 'idle' && (
          <p className="reco-placeholder">
            Cliquez sur <strong>«&nbsp;Générer&nbsp;»</strong> pour lancer l'agent et obtenir
            un plan business &amp; marketing basé sur les KPIs actuels.
          </p>
        )}
      </section>
    </main>
  )
}

export default App
