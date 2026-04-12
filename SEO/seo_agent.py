from __future__ import annotations

import json
import os
from typing import Any
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
from crewai_tools import SerperDevTool

DEFAULT_HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _safe_serper_tool() -> list[BaseTool]:
    """Enable Serper only when explicitly requested."""
    if os.getenv("SEO_ENABLE_SERPER", "").strip().lower() not in {"1", "true", "yes"}:
        return []
    try:
        return [SerperDevTool()]
    except Exception:
        return []


def _resolve_llm() -> LLM:
    model = (os.getenv("CREWAI_MODEL") or "").strip()
    max_tokens = _int_env("SEO_MAX_TOKENS", 900)
    if model and "rerank" in model.lower():
        raise RuntimeError(
            "CREWAI_MODEL points to a rerank model. Use a chat model, e.g. "
            "Qwen/Qwen2.5-7B-Instruct (Hugging Face)."
        )

    api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
    if not api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY (or HF_TOKEN) is required.")
    if not model:
        model = DEFAULT_HF_MODEL
    if not model.startswith("huggingface/"):
        model = f"huggingface/{model}"
    return LLM(
        model=model,
        api_key=api_key,
        base_url="https://router.huggingface.co/v1",
        max_tokens=max_tokens,
        temperature=0.3,
    )


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_model_json(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    candidate = _extract_json_object(text)
    if not candidate:
        return None

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _fallback_prompt(inputs: dict[str, Any]) -> str:
    return dedent(
        f"""
        Return ONLY valid JSON and no extra text.
        Build concise SEO recommendations for:
        - Business: {inputs.get("business_name", "")}
        - Website: {inputs.get("website_url", "")}
        - Core offer: {inputs.get("core_offer", "")}
        - Industry: {inputs.get("industry", "")}
        - Audience: {inputs.get("audience", "")}
        - Target market: {inputs.get("target_market", "")}
        - Conversion goal: {inputs.get("conversion_goal", "")}
        - Brand voice: {inputs.get("brand_voice", "")}
        - Competitors: {inputs.get("competitors", "")}

        Use exactly this JSON shape:
        {{
          "business_summary": "...",
          "recommended_keywords": [
            {{
              "keyword": "...",
              "intent": "informational|commercial|transactional|navigational",
              "priority_score": 0,
              "reasoning": "...",
              "difficulty_estimate": "low|medium|high",
              "bucket": "quick_win|strategic_bet"
            }}
          ],
          "topic_clusters": [
            {{
              "cluster_name": "...",
              "pillar_topic": "...",
              "supporting_keywords": ["..."]
            }}
          ],
          "article_titles": ["..."],
          "landing_page_targets": ["..."],
          "next_30_day_actions": ["..."]
        }}
        """
    ).strip()


def _deterministic_fallback(inputs: dict[str, Any]) -> dict[str, Any]:
    core_offer = str(inputs.get("core_offer", "marketing ai assistant")).strip()
    industry = str(inputs.get("industry", "B2B SaaS")).strip()
    audience = str(inputs.get("audience", "growth marketers")).strip()
    target_market = str(inputs.get("target_market", "English / Global")).strip()
    base_keywords = [
        f"{core_offer} for {audience}",
        f"best {industry} marketing ai tools",
        "ai campaign planning software",
        "automate marketing campaigns with ai",
        "marketing ai assistant for small teams",
        "ai content and messaging assistant",
    ]
    recs = [
        {
            "keyword": kw,
            "intent": "commercial" if i < 2 else "transactional",
            "priority_score": 88 - (i * 6),
            "reasoning": "High relevance to offer and conversion intent.",
            "difficulty_estimate": "medium" if i < 3 else "low",
            "bucket": "strategic_bet" if i < 2 else "quick_win",
        }
        for i, kw in enumerate(base_keywords[: int(inputs.get("keyword_count", 6))])
    ]
    return {
        "business_summary": (
            f"SEO fallback strategy for {inputs.get('business_name', 'the business')} in "
            f"{industry}, targeting {audience} in {target_market}."
        ),
        "recommended_keywords": recs,
        "topic_clusters": [
            {
                "cluster_name": "AI Campaign Automation",
                "pillar_topic": "How AI improves campaign planning and execution",
                "supporting_keywords": [k["keyword"] for k in recs[:3]],
            },
            {
                "cluster_name": "Marketing Team Productivity",
                "pillar_topic": "Using AI assistants for lean marketing teams",
                "supporting_keywords": [k["keyword"] for k in recs[3:6]],
            },
        ],
        "article_titles": [
            "How to Choose a Marketing AI Assistant for a Lean Team",
            "AI Campaign Planning: A Practical Playbook for Startups",
            "Quick-Win SEO Strategy for Marketing AI Products",
        ][: int(inputs.get("article_title_count", 3))],
        "landing_page_targets": [
            "marketing ai assistant",
            "ai campaign planning software",
            "automate marketing campaigns with ai",
        ][: int(inputs.get("landing_page_target_count", 3))],
        "next_30_day_actions": [
            "Publish one pillar page and two supporting articles.",
            "Optimize product and feature pages for transactional keywords.",
            "Refresh title/meta tags for top-priority target terms.",
            "Track ranking and conversions weekly for quick-win keywords.",
        ][: int(inputs.get("next_actions_count", 4))],
    }


def build_seo_crew() -> Crew:
    llm = _resolve_llm()

    seo_strategist = Agent(
        role="Senior SEO Growth Strategist",
        goal=(
            "Design high-impact keyword opportunities that increase qualified "
            "organic traffic and conversions."
        ),
        backstory=dedent(
            """
            You are the SEO lead in a fast-moving growth squad for AI-powered marketing products.
            You balance creativity and data, using SERP signals, intent mapping, and realistic
            go-to-market constraints. You specialize in finding low-competition opportunities
            and converting them into executable content clusters.
            """
        ).strip(),
        tools=_safe_serper_tool(),
        allow_delegation=False,
        llm=llm,
        max_rpm=_int_env("SEO_MAX_RPM", 20),
        verbose=False,
    )

    seo_task = Task(
        description=dedent(
            """
            Build an SEO keyword strategy for this business context:

            Business: {business_name}
            Website URL: {website_url}
            Core offer: {core_offer}
            Industry: {industry}
            ICP / audience: {audience}
            Target market (language + geography): {target_market}
            Main conversion goal: {conversion_goal}
            Brand voice: {brand_voice}
            Competitors: {competitors}

            Scenario:
            The company is launching a "Marketing AI Assistant" that helps small teams automate
            campaign ideation, messaging, and execution. Budget is limited, so we need practical
            opportunities that can rank in 3-6 months with high commercial relevance.

            Produce:
            1) Top {keyword_count} recommended keywords (mix of short-tail + long-tail).
            2) Search intent per keyword (informational, commercial, transactional, navigational).
            3) Priority score (1-100) based on business relevance, ranking difficulty estimate,
               and conversion potential.
            4) Group keywords into {cluster_count} topical clusters suitable for pillar + supporting content.
            5) Suggest {article_title_count} SEO article titles and {landing_page_target_count} landing-page keyword targets.
            6) Include "quick wins" (lower competition) and "strategic bets" (higher volume).
            7) Keep output concise: max {next_actions_count} next actions, max 1 short sentence for each reasoning,
               and keep total output under 1100 words.
            8) Return ONLY raw JSON (no code fences, no prefixed text, no explanations).

            Return valid JSON with this shape exactly:
            {{
              "business_summary": "...",
              "recommended_keywords": [
                {{
                  "keyword": "...",
                  "intent": "...",
                  "priority_score": 0,
                  "reasoning": "...",
                  "difficulty_estimate": "low|medium|high",
                  "bucket": "quick_win|strategic_bet"
                }}
              ],
              "topic_clusters": [
                {{
                  "cluster_name": "...",
                  "pillar_topic": "...",
                  "supporting_keywords": ["..."]
                }}
              ],
              "article_titles": ["..."],
              "landing_page_targets": ["..."],
              "next_30_day_actions": ["..."]
            }}
            """
        ).strip(),
        expected_output="A strict JSON strategy document with prioritized SEO keywords and clusters.",
        agent=seo_strategist,
    )

    return Crew(
        agents=[seo_strategist],
        tasks=[seo_task],
        process=Process.sequential,
        verbose=False,
    )


def run_seo_recommendation(inputs: dict) -> dict:
    try:
        crew = build_seo_crew()
        result = crew.kickoff(inputs=inputs)
    except Exception as exc:
        # Some HF models are not compatible with chat-completions in this flow.
        # Retry once with the known-safe default model.
        if "None or empty" not in str(exc):
            raise
        os.environ["CREWAI_MODEL"] = DEFAULT_HF_MODEL
        crew = build_seo_crew()
        result = crew.kickoff(inputs=inputs)

    raw_text = str(getattr(result, "raw", result)).strip()
    parsed = _parse_model_json(raw_text)
    if parsed is not None:
        return parsed

    retry_inputs = dict(inputs)
    retry_inputs["keyword_count"] = min(int(retry_inputs.get("keyword_count", 12)), 10)
    retry_inputs["cluster_count"] = min(int(retry_inputs.get("cluster_count", 4)), 4)
    retry_inputs["article_title_count"] = min(
        int(retry_inputs.get("article_title_count", 6)), 6
    )
    retry_inputs["landing_page_target_count"] = min(
        int(retry_inputs.get("landing_page_target_count", 3)), 3
    )
    retry_inputs["next_actions_count"] = min(
        int(retry_inputs.get("next_actions_count", 5)), 5
    )

    result_retry = crew.kickoff(inputs=retry_inputs)
    raw_retry = str(getattr(result_retry, "raw", result_retry)).strip()
    parsed_retry = _parse_model_json(raw_retry)
    if parsed_retry is not None:
        return parsed_retry

    llm = _resolve_llm()
    llm_text = str(llm.call([{"role": "user", "content": _fallback_prompt(retry_inputs)}]))
    parsed_llm = _parse_model_json(llm_text)
    if parsed_llm is not None:
        return parsed_llm

    return _deterministic_fallback(retry_inputs)
