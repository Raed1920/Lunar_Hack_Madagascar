"""
Multi-Agent KPI Analysis System
================================
Agents:
  1. KPI Analyst              — Deep KPI analysis + risk scoring
  2. Customer Profiler        — High-value buyers & churn emails
  3. Market Researcher        — External business/macro/political causes
  4. Business & Mktg Advisor  — Product business recs + marketing action plan

Entrypoints:
  run_kpi_analysis(snapshot)         -> full 4-agent pipeline
  run_smart_recommendations(snapshot) -> Agent 4 only (fast, for dashboard)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from crewai import LLM, Agent, Crew, Task
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ─────────────────────────────────────────────
# LLM Setup (OpenRouter)
# ─────────────────────────────────────────────
_llm = LLM(
    model="openai/gpt-3.5-turbo",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


# ─────────────────────────────────────────────
# Helper – build a compact KPI summary string
# ─────────────────────────────────────────────
def _format_kpi_summary(snapshot: Dict[str, Any]) -> str:
    kpis = snapshot.get("kpis", {})
    breakdowns = snapshot.get("breakdowns", {})
    top_products = breakdowns.get("top_products", [])
    top_customers = breakdowns.get("top_customers", [])
    insights = snapshot.get("insights", [])
    day = snapshot.get("day", "unknown")
    currency = snapshot.get("currency", "TND")

    top_prod_str = "\n".join(
        f"  - {p.get('product_name', p.get('product_id', 'N/A'))} | qty={p.get('quantity', 0)} | revenue={p.get('revenue', 0)} {currency}"
        for p in top_products[:5]
    ) or "  (aucun produit)"

    top_cust_str = "\n".join(
        f"  - {c.get('customer_name', c.get('customer_id', 'N/A'))} | orders={c.get('orders', 0)} | revenue={c.get('revenue', 0)} {currency}"
        for c in top_customers[:5]
    ) or "  (aucun client)"

    cart = breakdowns.get("cart_distribution", {})

    return f"""
=== KPI SNAPSHOT — {day} | Devise: {currency} ===
Chiffre d'affaires: {kpis.get('revenue_today', 0)} {currency}
Commandes aujourd'hui: {kpis.get('orders_today', 0)} | Complétées: {kpis.get('orders_completed', 0)}
Taux de conversion: {kpis.get('conversion_rate', 0):.2f}%
Panier moyen: {kpis.get('average_basket', 0):.2f} {currency}
Taux d'abandon panier: {kpis.get('cart_abandonment_rate', 0):.2f}%
Conversations aujourd'hui: {kpis.get('conversations_today', 0)}
Campagnes aujourd'hui: {kpis.get('campaigns_today', 0)}

Distribution paniers: petit={cart.get('petit_panier', 0)} | moyen={cart.get('panier_moyen', 0)} | gros={cart.get('gros_panier', 0)}

Top Produits:
{top_prod_str}

Top Clients:
{top_cust_str}

Insights système:
{chr(10).join('  ' + i for i in insights) or '  (aucun)'}
""".strip()


# ─────────────────────────────────────────────
# Helper – build customer context for profiler
# ─────────────────────────────────────────────
def _format_customer_data(snapshot: Dict[str, Any]) -> str:
    breakdowns = snapshot.get("breakdowns", {})
    top_customers = breakdowns.get("top_customers", [])
    catalog = snapshot.get("catalog", {})
    all_customers = catalog.get("customers", [])
    currency = snapshot.get("currency", "TND")
    kpis = snapshot.get("kpis", {})
    avg_basket = float(kpis.get("average_basket", 0))

    # Build map for quick lookup
    cust_map: Dict[str, Dict] = {str(c["id"]): c for c in all_customers}

    high_value: List[Dict] = []
    for c in top_customers:
        cid = str(c.get("customer_id", ""))
        info = cust_map.get(cid, {})
        revenue = float(c.get("revenue", 0))
        if revenue > avg_basket * 2 or c.get("orders", 0) >= 3:
            high_value.append({
                "customer_id": cid,
                "name": c.get("customer_name", cid),
                "email": info.get("email", ""),
                "segment": info.get("segment", "standard"),
                "orders": c.get("orders", 0),
                "revenue": revenue,
            })

    # Churn candidates: customers in catalog with segment="at_risk" or "churned"
    churn_candidates: List[Dict] = []
    for c in all_customers:
        seg = str(c.get("segment", "")).lower()
        if seg in ("at_risk", "churned", "vip_at_risk", "churn"):
            churn_candidates.append({
                "customer_id": str(c.get("id", "")),
                "name": c.get("name", ""),
                "email": c.get("email", ""),
                "segment": c.get("segment", ""),
                "last_order": c.get("last_order_date", "N/A"),
            })

    return json.dumps({
        "currency": currency,
        "average_basket": avg_basket,
        "high_value_buyers": high_value,
        "churn_candidates": churn_candidates,
    }, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# AGENT 1 – KPI Analyst
# ─────────────────────────────────────────────
def _build_analyst_agent() -> Agent:
    return Agent(
        role="Senior KPI Business Analyst",
        goal=(
            "Analyser en profondeur les KPIs e-commerce en temps réel et fournir "
            "des recommandations actionnables précises pour le marché tunisien."
        ),
        backstory=(
            "Tu es un expert en analytics e-commerce avec 10 ans d'expérience sur le marché "
            "MENA. Tu maîtrises parfaitement les KPIs (CA, conversion, abandon panier, LTV) "
            "et tu sais identifier les signaux faibles dans les données temps réel."
        ),
        llm=_llm,
        verbose=False,
        allow_delegation=False,
    )


def _build_analyst_task(agent: Agent, kpi_summary: str) -> Task:
    return Task(
        description=f"""
Tu reçois un snapshot KPI en temps réel d'une plateforme e-commerce tunisienne.

{kpi_summary}

Ta mission:
1. Analyse détaillée de chaque KPI (forces, faiblesses, tendances).
2. Identifie les 3 problèmes critiques prioritaires avec impact business estimé.
3. Formule 5 recommandations actionnables concrètes classées par priorité (haute/moyenne/faible).
4. Évalue le niveau de risque global: CRITIQUE / ÉLEVÉ / MODÉRÉ / FAIBLE.

Réponds en JSON structuré avec les clés:
- "analysis": string (analyse narrative)
- "critical_issues": list of objects {{title, description, estimated_impact}}
- "recommendations": list of objects {{priority, action, expected_result}}
- "risk_level": string
- "executive_summary": string (2-3 lignes)
        """,
        expected_output="JSON avec analysis, critical_issues, recommendations, risk_level, executive_summary",
        agent=agent,
    )


# ─────────────────────────────────────────────
# AGENT 2 – Customer Profiler
# ─────────────────────────────────────────────
def _build_profiler_agent() -> Agent:
    return Agent(
        role="Customer Segmentation & Email Marketing Specialist",
        goal=(
            "Identifier les clients à forte valeur et les clients à risque de churn, "
            "puis générer des emails JSON personnalisés pour chaque segment."
        ),
        backstory=(
            "Tu es spécialiste CRM et marketing automation. Tu crées des campagnes email "
            "hyper-personnalisées qui augmentent la rétention et le LTV. Tu connais très bien "
            "les habitudes d'achat des consommateurs tunisiens et les meilleures pratiques "
            "d'email marketing dans la région MENA."
        ),
        llm=_llm,
        verbose=False,
        allow_delegation=False,
    )


def _build_profiler_task(agent: Agent, customer_data: str) -> Task:
    return Task(
        description=f"""
Tu reçois les données clients d'une plateforme e-commerce tunisienne.

DONNÉES CLIENTS:
{customer_data}

Ta mission:
1. Pour les HIGH VALUE BUYERS (gros acheteurs): génère des emails JSON de fidélisation/récompense.
2. Pour les CHURN CANDIDATES: génère des emails JSON de réactivation urgente.
3. Si aucun client dans une catégorie, génère des exemples basés sur le contexte.

Format de chaque email JSON:
{{
  "to": "email@example.com",
  "customer_name": "...",
  "subject": "...",
  "body_html": "...",
  "segment": "high_value" | "churn_risk",
  "campaign_type": "...",
  "personalization_tokens": {{...}}
}}

Réponds en JSON avec:
- "high_value_emails": liste d'emails pour les gros acheteurs
- "churn_emails": liste d'emails pour les clients à risque
- "segmentation_summary": string (résumé de la stratégie)
        """,
        expected_output="JSON avec high_value_emails, churn_emails, segmentation_summary",
        agent=agent,
    )


# ─────────────────────────────────────────────
# AGENT 3 – Market Researcher
# ─────────────────────────────────────────────
def _build_researcher_agent() -> Agent:
    return Agent(
        role="Market Intelligence & Macro Research Analyst",
        goal=(
            "Identifier les causes externes (business, économiques, politiques, saisonnières) "
            "qui peuvent expliquer les anomalies dans les KPIs e-commerce."
        ),
        backstory=(
            "Tu es analyste en veille stratégique et intelligence économique, spécialisé "
            "dans le marché tunisien et nord-africain. Tu connais les facteurs macro-économiques, "
            "politiques, saisonniers et concurrentiels qui influencent le commerce en ligne. "
            "Tu utilises ta base de connaissances pour relier les données business aux contextes externes."
        ),
        llm=_llm,
        verbose=False,
        allow_delegation=False,
    )


def _build_researcher_task(agent: Agent, kpi_summary: str) -> Task:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Task(
        description=f"""
Tu analyses les KPIs d'une plateforme e-commerce tunisienne (date: {today}).

{kpi_summary}

Ta mission: Identifie et explique les CAUSES EXTERNES potentielles des anomalies KPI.

Recherche dans ces catégories:
1. **Facteurs Business**: concurrence, promotions marché, tendances sectorielles e-commerce MENA
2. **Facteurs Économiques**: inflation TND, pouvoir d'achat, taux de change, coût logistique
3. **Facteurs Politiques/Réglementaires**: nouvelles lois commerce digital, fiscalité, douanes
4. **Facteurs Saisonniers/Culturels**: Ramadan, Aïd, rentrée, vacances, événements locaux
5. **Facteurs Technologiques**: pannes internet, adoption mobile payment, fintech tunisienne
6. **Corrélations identifiées**: liens entre les KPIs et ces facteurs externes

Réponds en JSON avec:
- "external_factors": liste d'objets {{category, factor, relevance_score (0-10), explanation, action_recommendation}}
- "top_correlations": liste des 3 liens les plus forts entre KPIs et facteurs externes
- "research_summary": string
- "confidence_level": "high" | "medium" | "low"
        """,
        expected_output="JSON avec external_factors, top_correlations, research_summary, confidence_level",
        agent=agent,
    )


# ─────────────────────────────────────────────
# AGENT 4 – Business & Marketing Advisor
# ─────────────────────────────────────────────
def _build_advisor_agent() -> Agent:
    return Agent(
        role="E-commerce Business & Marketing Strategy Advisor",
        goal=(
            "Générer des recommandations concrètes sur les produits (business) et le marketing "
            "pour maximiser les revenus et la visibilité de la plateforme e-commerce."
        ),
        backstory=(
            "Tu es conseiller stratégique e-commerce avec une double expertise: "
            "business produit (pricing, bundle, assortiment, stock) et marketing digital "
            "(SEA, SEO, réseaux sociaux, email, SMS, influence). "
            "Tu as accompagné des dizaines de boutiques en ligne en Tunisie et au Maghreb "
            "vers leur croissance. Tu maîtrises les canaux digitaux locaux (Facebook Ads, "
            "TikTok, Instagram, Google Shopping, WhatsApp Business)."
        ),
        llm=_llm,
        verbose=False,
        allow_delegation=False,
    )


def _build_advisor_task(agent: Agent, kpi_summary: str) -> Task:
    return Task(
        description=f"""
Tu es conseiller stratégique d'une plateforme e-commerce tunisienne.
Analyse les données suivantes et génère un plan d'action business + marketing:

{kpi_summary}

## PARTIE 1 — RECOMMANDATIONS BUSINESS PRODUITS
Pour chaque produit identifié dans le top:
1. Stratégie de pricing (augmenter, maintenir, promotionner).
2. Opportunités de bundling / cross-sell / upsell.
3. Alertes de réassort ou risque de rupture de stock.
4. Produits à mettre en avant ou à retirer du catalogue.
5. Segmentation produit par profil client (VIP, nouveau, standard).

## PARTIE 2 — PLAN MARKETING
1. Canaux prioritaires à activer aujourd'hui (Facebook Ads, Google, Email, SMS, TikTok...).
2. Messages clés par segment client (VIP, abandonneurs, nouveaux).
3. Timing optimal des campagnes (heures et jours basés sur les données horaires).
4. Offres promotionnelles à mettre en place (codes promo, frais de port offerts, flash sales).
5. KPIs marketing à surveiller en priorité.

Réponds UNIQUEMENT en JSON valide avec cette structure:
{{
  "business_recommendations": [
    {{
      "product_name": "...",
      "category": "pricing" | "bundle" | "stock" | "visibility" | "segmentation",
      "priority": "haute" | "moyenne" | "faible",
      "action": "description de l'action concrète",
      "expected_impact": "impact attendu en chiffres ou qualitativement",
      "timeframe": "immédiat" | "cette semaine" | "ce mois"
    }}
  ],
  "marketing_plan": [
    {{
      "channel": "Facebook Ads" | "Google Shopping" | "Email" | "SMS" | "TikTok" | "Instagram" | "WhatsApp" | "SEO",
      "priority": "haute" | "moyenne" | "faible",
      "action": "description de la campagne ou action",
      "target_segment": "VIP" | "churn_risk" | "new_customer" | "all",
      "message_key": "message principal de la campagne",
      "timing": "heure ou moment optimal",
      "kpi_to_watch": "KPI à mesurer"
    }}
  ],
  "quick_wins": ["action rapide 1", "action rapide 2", "action rapide 3"],
  "strategy_summary": "résumé de la stratégie globale en 3-4 lignes"
}}
        """,
        expected_output="JSON avec business_recommendations, marketing_plan, quick_wins, strategy_summary",
        agent=agent,
    )


# ─────────────────────────────────────────────
# Shared safe JSON parser
# ─────────────────────────────────────────────
def _safe_parse(raw: str) -> Any:
    """Extract JSON from agent output (may have markdown code fences)."""
    if not raw:
        return {}
    text = str(raw).strip()
    # Strip ```json ... ``` wrappers
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_output": text}


# ─────────────────────────────────────────────
# Entrypoint 1 — Full 4-agent pipeline
# ─────────────────────────────────────────────
def run_kpi_analysis(kpi_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full 4-agent CrewAI pipeline on a live KPI snapshot.
    Returns analyst, profiler, researcher, and advisor outputs.
    """
    kpi_summary = _format_kpi_summary(kpi_snapshot)
    customer_data = _format_customer_data(kpi_snapshot)

    analyst = _build_analyst_agent()
    profiler = _build_profiler_agent()
    researcher = _build_researcher_agent()
    advisor = _build_advisor_agent()

    analyst_task = _build_analyst_task(analyst, kpi_summary)
    profiler_task = _build_profiler_task(profiler, customer_data)
    researcher_task = _build_researcher_task(researcher, kpi_summary)
    advisor_task = _build_advisor_task(advisor, kpi_summary)

    crew = Crew(
        agents=[analyst, profiler, researcher, advisor],
        tasks=[analyst_task, profiler_task, researcher_task, advisor_task],
        verbose=False,
    )

    crew_result = crew.kickoff()
    task_outputs = crew_result.tasks_output if hasattr(crew_result, "tasks_output") else []

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpi_day": kpi_snapshot.get("day", "N/A"),
        "analyst": _safe_parse(str(task_outputs[0].raw) if len(task_outputs) > 0 else ""),
        "customer_profiler": _safe_parse(str(task_outputs[1].raw) if len(task_outputs) > 1 else ""),
        "market_researcher": _safe_parse(str(task_outputs[2].raw) if len(task_outputs) > 2 else ""),
        "business_marketing": _safe_parse(str(task_outputs[3].raw) if len(task_outputs) > 3 else ""),
    }


# ─────────────────────────────────────────────
# Entrypoint 2 — Lightweight dashboard recs
# ─────────────────────────────────────────────
def run_smart_recommendations(kpi_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run ONLY the Business & Marketing Advisor agent.
    Fast call suitable for inline dashboard usage.
    """
    kpi_summary = _format_kpi_summary(kpi_snapshot)
    advisor = _build_advisor_agent()
    advisor_task = _build_advisor_task(advisor, kpi_summary)

    crew = Crew(
        agents=[advisor],
        tasks=[advisor_task],
        verbose=False,
    )

    crew_result = crew.kickoff()
    task_outputs = crew_result.tasks_output if hasattr(crew_result, "tasks_output") else []
    raw = str(task_outputs[0].raw) if task_outputs else ""

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpi_day": kpi_snapshot.get("day", "N/A"),
        "business_marketing": _safe_parse(raw),
    }


# ─────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    sample_snapshot = {
        "day": "2026-04-11",
        "currency": "TND",
        "kpis": {
            "revenue_today": 8450.0,
            "orders_today": 42,
            "orders_completed": 35,
            "conversion_rate": 3.5,
            "average_basket": 201.2,
            "cart_abandonment_rate": 38.0,
            "conversations_today": 18,
            "campaigns_today": 3,
        },
        "breakdowns": {
            "top_products": [
                {"product_id": "P1", "product_name": "Sneakers Pro X", "quantity": 12, "revenue": 2880.0},
                {"product_id": "P2", "product_name": "Sac Cuir Premium", "quantity": 8, "revenue": 1920.0},
            ],
            "top_customers": [
                {"customer_id": "C1", "customer_name": "Ahmed Ben Ali", "orders": 5, "revenue": 1050.0},
                {"customer_id": "C2", "customer_name": "Fatima Khalil", "orders": 4, "revenue": 840.0},
            ],
            "cart_distribution": {"petit_panier": 8, "panier_moyen": 20, "gros_panier": 14},
        },
        "insights": ["Abandon panier élevé: >38%", "Conversion correcte mais stable"],
        "catalog": {
            "customers": [
                {"id": "C1", "name": "Ahmed Ben Ali", "email": "ahmed@example.com", "segment": "VIP"},
                {"id": "C2", "name": "Fatima Khalil", "email": "fatima@example.com", "segment": "at_risk"},
                {"id": "C3", "name": "Karim Trabelsi", "email": "karim@example.com", "segment": "churned"},
            ]
        },
    }

    result = run_kpi_analysis(sample_snapshot)
    print(json.dumps(result, ensure_ascii=False, indent=2))