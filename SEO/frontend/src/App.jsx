import { useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

const initialForm = {
  business_name: "Wamia",
  website_url: "https://wamia.tn",
  core_offer: "AI-powered marketing assistant for campaign planning, messaging, and execution",
  industry: "Marketing Technology / B2B SaaS",
  audience: "startup founders, growth marketers, SMEs, and lean marketing teams",
  target_market: "Tunisia and North Africa (French, Arabic, and English)",
  conversion_goal: "book product demo or start free trial",
  brand_voice: "practical, expert, friendly",
  competitors: "HubSpot AI, Jasper, Copy.ai, Notion AI, Mailchimp",
  keyword_count: 12,
  cluster_count: 4,
  article_title_count: 6,
  landing_page_target_count: 3,
  next_actions_count: 5,
  max_output_tokens: 900,
};

const numberFields = new Set([
  "keyword_count",
  "cluster_count",
  "article_title_count",
  "landing_page_target_count",
  "next_actions_count",
  "max_output_tokens",
]);

const FIELD_LABELS = {
  business_name: "Business Name",
  website_url: "Website URL",
  core_offer: "Core Offer",
  industry: "Industry",
  audience: "Audience",
  target_market: "Target Market",
  conversion_goal: "Conversion Goal",
  brand_voice: "Brand Voice",
  competitors: "Competitors",
  keyword_count: "Keyword Count",
  cluster_count: "Cluster Count",
  article_title_count: "Article Titles",
  landing_page_target_count: "Landing Targets",
  next_actions_count: "Next Actions",
  max_output_tokens: "Max Output Tokens",
};

const FIELD_GROUPS = [
  {
    title: "Business Context",
    keys: [
      "business_name",
      "website_url",
      "core_offer",
      "industry",
      "audience",
      "target_market",
      "conversion_goal",
      "brand_voice",
      "competitors",
    ],
  },
  {
    title: "Output Controls",
    keys: [
      "keyword_count",
      "cluster_count",
      "article_title_count",
      "landing_page_target_count",
      "next_actions_count",
      "max_output_tokens",
    ],
  },
];

const quickBriefs = [
  {
    name: "B2B SaaS Sprint",
    values: {
      industry: "B2B SaaS",
      conversion_goal: "book product demo or start free trial",
      keyword_count: 12,
      cluster_count: 4,
    },
  },
  {
    name: "Ecommerce Push",
    values: {
      industry: "Ecommerce",
      conversion_goal: "increase product page purchases",
      keyword_count: 16,
      cluster_count: 5,
    },
  },
  {
    name: "Local Lead Funnel",
    values: {
      industry: "Local Services",
      conversion_goal: "generate qualified local leads",
      target_market: "English / Local city + nearby regions",
      keyword_count: 10,
      cluster_count: 3,
    },
  },
];

function toList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function safeResultShape(result) {
  if (!result || typeof result !== "object") {
    return null;
  }

  const recommendations = result.seo_recommendations || {};
  return {
    business_summary: result.business_summary || "",
    recommended_keywords: toList(result.recommended_keywords),
    topic_clusters: toList(result.topic_clusters),
    article_titles: toList(result.article_titles),
    landing_page_targets: toList(result.landing_page_targets),
    next_30_day_actions: toList(result.next_30_day_actions),
    seo_recommendations: {
      primary_keywords: toList(recommendations.primary_keywords),
      long_tail_keywords: toList(recommendations.long_tail_keywords),
      quick_win_keywords: toList(recommendations.quick_win_keywords),
      strategic_bet_keywords: toList(recommendations.strategic_bet_keywords),
      on_page_recommendations: toList(recommendations.on_page_recommendations),
    },
  };
}

function toPriorityLevel(score) {
  const numeric = Number(score);
  if (numeric >= 80) {
    return "high";
  }
  if (numeric >= 60) {
    return "medium";
  }
  return "low";
}

function toBucketLabel(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

function parseNumberInput(rawValue, fallback) {
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const hydrated = useMemo(() => safeResultShape(result), [result]);
  const keywordRows = useMemo(() => hydrated?.recommended_keywords || [], [hydrated]);

  const topKeyword = useMemo(() => {
    if (keywordRows.length === 0) {
      return null;
    }
    return [...keywordRows].sort(
      (a, b) => Number(b?.priority_score || 0) - Number(a?.priority_score || 0)
    )[0];
  }, [keywordRows]);

  const onChange = (key, value) => {
    setForm((prev) => ({
      ...prev,
      [key]: numberFields.has(key) ? parseNumberInput(value, prev[key]) : value,
    }));
  };

  const applyBrief = (patchValues) => {
    setForm((prev) => ({
      ...prev,
      ...patchValues,
    }));
  };

  const resetAll = () => {
    setForm(initialForm);
    setResult(null);
    setError("");
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/seo/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Request failed");
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app seo-app" dir="ltr">
      <div className="ambient" />

      <header className="topbar">
        <div className="title-wrap">
          <span className="eyebrow">Lunar Hack SEO Console</span>
          <h1>SEO Strategy Agent</h1>
          <p>CrewAI + FastAPI orchestration with execution-ready keyword plans.</p>
        </div>
        <div className="top-controls">
          <button type="button" className="ghost-btn" onClick={resetAll} disabled={loading}>
            Reset Brief
          </button>
        </div>
      </header>

      <main className="layout">
        <aside className="control-shell">
          <div className="panel-head">
            <h2>Campaign Brief</h2>
            <span>Configure inputs</span>
          </div>

          <div className="chip-row">
            {quickBriefs.map((brief) => (
              <button
                key={brief.name}
                type="button"
                className="chip-btn"
                onClick={() => applyBrief(brief.values)}
                disabled={loading}
              >
                {brief.name}
              </button>
            ))}
          </div>

          <form onSubmit={onSubmit} className="planner-form">
            {FIELD_GROUPS.map((group) => (
              <section key={group.title} className="form-block">
                <h3>{group.title}</h3>
                <div className="input-grid">
                  {group.keys.map((key) => (
                    <label key={key} className="field">
                      <span>{FIELD_LABELS[key] || key}</span>
                      <input
                        type={numberFields.has(key) ? "number" : "text"}
                        value={form[key]}
                        min={numberFields.has(key) ? 1 : undefined}
                        onChange={(e) => onChange(key, e.target.value)}
                        required
                      />
                    </label>
                  ))}
                </div>
              </section>
            ))}

            <button disabled={loading} type="submit" className="submit-btn">
              {loading ? "Generating SEO Plan..." : "Generate SEO Strategy"}
            </button>
          </form>
        </aside>

        <section className="insights-shell">
          <div className="lunar-hud">
            <div className="hud-chip">
              <span className="hud-label">Status</span>
              <span className={`hud-value ${loading ? "medium" : hydrated ? "high" : "text"}`}>
                {loading ? "Running" : hydrated ? "Ready" : "Idle"}
              </span>
            </div>
            <div className="hud-chip">
              <span className="hud-label">Keywords</span>
              <span className="hud-value">{keywordRows.length}</span>
            </div>
            <div className="hud-chip">
              <span className="hud-label">Clusters</span>
              <span className="hud-value">{hydrated?.topic_clusters.length || 0}</span>
            </div>
            <div className="hud-chip">
              <span className="hud-label">Top Score</span>
              <span className="hud-value">{topKeyword ? topKeyword.priority_score : "-"}</span>
            </div>
          </div>

          {error ? <p className="error-banner">{error}</p> : null}

          {!hydrated && !loading ? (
            <div className="empty-result">
              <h2>Waiting For Strategy Run</h2>
              <p>
                Fill the brief on the left and launch generation to get keywords, cluster maps,
                titles, and next 30-day actions.
              </p>
            </div>
          ) : null}

          {loading ? (
            <div className="loading-state">
              <div className="typing-dots">
                <span />
                <span />
                <span />
              </div>
              <p>Analyzing market signals and generating SEO strategy...</p>
            </div>
          ) : null}

          {hydrated ? (
            <div className="result-grid">
              <article className="result-card span-2">
                <h2>Business Summary</h2>
                <p>{hydrated.business_summary || "No summary generated."}</p>
              </article>

              <article className="result-card span-2">
                <div className="card-head">
                  <h2>Recommended Keywords</h2>
                  <span>{keywordRows.length} items</span>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Keyword</th>
                        <th>Intent</th>
                        <th>Priority</th>
                        <th>Difficulty</th>
                        <th>Bucket</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keywordRows.map((k, idx) => (
                        <tr key={`${k.keyword}-${idx}`}>
                          <td>{k.keyword}</td>
                          <td>{k.intent}</td>
                          <td>
                            <div className="meter">
                              <div
                                className={`meter-fill ${toPriorityLevel(k.priority_score)}`}
                                style={{ width: `${Math.min(100, Number(k.priority_score) || 0)}%` }}
                              />
                              <span>{k.priority_score}</span>
                            </div>
                          </td>
                          <td>{k.difficulty_estimate}</td>
                          <td>{toBucketLabel(k.bucket)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>

              <article className="result-card">
                <h2>Topic Clusters</h2>
                <ul className="stack-list">
                  {hydrated.topic_clusters.map((cluster, idx) => (
                    <li key={`${cluster.cluster_name}-${idx}`}>
                      <strong>{cluster.cluster_name}</strong>
                      <p>{cluster.pillar_topic}</p>
                      <div className="chip-wrap">
                        {toList(cluster.supporting_keywords).map((word) => (
                          <span key={`${cluster.cluster_name}-${word}`} className="source-chip">
                            {word}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              </article>

              <article className="result-card">
                <h2>SEO Recommendations</h2>
                <div className="recommend-grid">
                  <div>
                    <label>Primary Keywords</label>
                    <p>{hydrated.seo_recommendations.primary_keywords.join(", ") || "-"}</p>
                  </div>
                  <div>
                    <label>Long-tail Keywords</label>
                    <p>{hydrated.seo_recommendations.long_tail_keywords.join(", ") || "-"}</p>
                  </div>
                  <div>
                    <label>Quick Wins</label>
                    <p>{hydrated.seo_recommendations.quick_win_keywords.join(", ") || "-"}</p>
                  </div>
                  <div>
                    <label>Strategic Bets</label>
                    <p>{hydrated.seo_recommendations.strategic_bet_keywords.join(", ") || "-"}</p>
                  </div>
                </div>
                <ul className="tiny-list">
                  {hydrated.seo_recommendations.on_page_recommendations.map((item, idx) => (
                    <li key={`${idx}-${item}`}>{item}</li>
                  ))}
                </ul>
              </article>

              <article className="result-card">
                <h2>Article Titles</h2>
                <ul className="tiny-list">
                  {hydrated.article_titles.map((title) => (
                    <li key={title}>{title}</li>
                  ))}
                </ul>
              </article>

              <article className="result-card">
                <h2>Landing Page Targets</h2>
                <ul className="tiny-list">
                  {hydrated.landing_page_targets.map((target) => (
                    <li key={target}>{target}</li>
                  ))}
                </ul>
              </article>

              <article className="result-card span-2">
                <h2>Next 30 Days</h2>
                <ul className="tiny-list">
                  {hydrated.next_30_day_actions.map((action, idx) => (
                    <li key={`${idx}-${action}`}>{action}</li>
                  ))}
                </ul>
              </article>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}
