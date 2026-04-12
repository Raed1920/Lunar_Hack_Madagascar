from __future__ import annotations

import os
import warnings
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from seo_agent import run_seo_recommendation

load_dotenv()

# CrewAI/Pydantic can emit this non-fatal serialization warning; keep API logs clean.
warnings.filterwarnings(
    "ignore",
    message=r".*method callbacks cannot be serialized and will prevent checkpointing.*",
    category=UserWarning,
)

app = FastAPI(title="SEO Agent API", version="1.0.0")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5176")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SEORequest(BaseModel):
    business_name: str = "Acme Growth Labs"
    website_url: str = "https://example.com"
    core_offer: str = "Marketing AI assistant for campaign planning and execution"
    industry: str = "B2B SaaS"
    audience: str = "startup founders, growth marketers, and lean marketing teams"
    target_market: str = "English / US + Europe"
    conversion_goal: str = "book product demo or start free trial"
    brand_voice: str = "practical, expert, friendly"
    competitors: str = "HubSpot AI, Jasper, Copy.ai, Notion AI"
    keyword_count: int = Field(default=12, ge=3, le=30)
    cluster_count: int = Field(default=4, ge=2, le=8)
    article_title_count: int = Field(default=6, ge=2, le=20)
    landing_page_target_count: int = Field(default=3, ge=1, le=10)
    next_actions_count: int = Field(default=5, ge=1, le=10)
    max_output_tokens: int = Field(default=900, ge=200, le=2000)


class KeywordItem(BaseModel):
    keyword: str
    intent: str
    priority_score: int
    reasoning: str
    difficulty_estimate: Literal["low", "medium", "high"] | str
    bucket: Literal["quick_win", "strategic_bet"] | str


class ClusterItem(BaseModel):
    cluster_name: str
    pillar_topic: str
    supporting_keywords: list[str]


class SEORecommendations(BaseModel):
    primary_keywords: list[str]
    long_tail_keywords: list[str]
    quick_win_keywords: list[str]
    strategic_bet_keywords: list[str]
    on_page_recommendations: list[str]


class SEOResponse(BaseModel):
    business_summary: str
    recommended_keywords: list[KeywordItem]
    topic_clusters: list[ClusterItem]
    article_titles: list[str]
    landing_page_targets: list[str]
    next_30_day_actions: list[str]
    seo_recommendations: SEORecommendations


def _build_seo_recommendations(result: dict) -> dict:
    keywords = result.get("recommended_keywords", [])
    ordered = sorted(
        keywords,
        key=lambda item: int(item.get("priority_score", 0)),
        reverse=True,
    )

    all_terms = [str(item.get("keyword", "")).strip() for item in ordered if item.get("keyword")]
    primary = all_terms[:5]
    long_tail = [k for k in all_terms if len(k.split()) >= 4][:6]
    quick_wins = [
        str(item.get("keyword", "")).strip()
        for item in ordered
        if str(item.get("bucket", "")).strip().lower() == "quick_win" and item.get("keyword")
    ][:6]
    strategic = [
        str(item.get("keyword", "")).strip()
        for item in ordered
        if str(item.get("bucket", "")).strip().lower() == "strategic_bet" and item.get("keyword")
    ][:6]

    landing_targets = result.get("landing_page_targets", [])[:3]
    page_titles = result.get("article_titles", [])[:2]
    on_page_recs = [
        f"Use primary keyword in title and H1 for: {landing_targets[0]}"
        if landing_targets
        else "Use top keyword in the page title and H1.",
        "Add one long-tail keyword variation in H2/H3 sections.",
        "Write meta descriptions with clear conversion intent.",
        f"Create internal links from blog posts to: {page_titles[0]}"
        if page_titles
        else "Create internal links from blogs to product pages.",
    ]

    return {
        "primary_keywords": primary,
        "long_tail_keywords": long_tail,
        "quick_win_keywords": quick_wins,
        "strategic_bet_keywords": strategic,
        "on_page_recommendations": on_page_recs,
    }


def _normalize_result_shape(result: dict) -> dict:
    normalized = dict(result)
    normalized.setdefault("business_summary", "")
    normalized.setdefault("recommended_keywords", [])
    normalized.setdefault("topic_clusters", [])
    normalized.setdefault("article_titles", [])
    normalized.setdefault("landing_page_targets", [])
    normalized.setdefault("next_30_day_actions", [])
    if not isinstance(normalized.get("seo_recommendations"), dict):
        normalized["seo_recommendations"] = _build_seo_recommendations(normalized)
    return normalized


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/seo/recommend", response_model=SEOResponse)
async def recommend(payload: SEORequest) -> SEOResponse:
    os.environ["SEO_MAX_TOKENS"] = str(payload.max_output_tokens)
    try:
        result = await run_in_threadpool(run_seo_recommendation, payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if "raw_output" in result:
        raise HTTPException(
            status_code=502,
            detail="Model returned non-JSON output. Try again or use a different HF chat model.",
        )

    try:
        return SEOResponse.model_validate(_normalize_result_shape(result))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid response shape: {exc}") from exc
