from __future__ import annotations

import re
from typing import Any, Dict

from app.agents.base import BaseJsonAgent
from app.models import RouteDecision, UnifiedGenerationOutput
from app.prompts import UNIFIED_GENERATION_SYSTEM_PROMPT, build_unified_generation_prompt


class SingleGenerationAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="single_generation",
            system_prompt=UNIFIED_GENERATION_SYSTEM_PROMPT,
            use_reasoning_model=getattr(settings, "single_generation_use_reasoning_model", False),
        )

    async def run(
        self,
        language: str,
        user_message: str,
        route: RouteDecision,
        profile: Dict[str, Any],
        context: str,
        rag_context: str,
        rag_sources: list[str],
    ) -> UnifiedGenerationOutput:
        prompt = build_unified_generation_prompt(
            language=language,
            user_message=self._truncate(user_message, max_chars=950),
            route_data=route.model_dump(),
            profile=self._compact_profile(profile),
            context=self._truncate(context, max_chars=1400),
            rag_context=self._truncate(rag_context, max_chars=2200),
            rag_sources=rag_sources[:8],
        )

        fallback = {
            "response": "I recommend a focused plan for the highest-impact bottleneck this cycle.",
            "recommendation": {
                "strategy": "Run a focused 30-day execution plan on the top bottleneck.",
                "actions": [
                    "Assign a single owner with weekly KPI check-ins",
                    "Run a 2-week execution sprint on the top initiative",
                    "Review KPI movement and adjust scope",
                ],
            },
            "risk_level": route.risk_level,
            "requires_follow_up": False,
            "next_question": "",
        }

        result = await self.run_contract(prompt, UnifiedGenerationOutput, fallback)
        return self._sanitize(result, fallback)

    def _sanitize(self, result: UnifiedGenerationOutput, fallback: Dict[str, Any]) -> UnifiedGenerationOutput:
        strategy = (result.recommendation.strategy or "").strip() or fallback["recommendation"]["strategy"]
        actions = self._normalize_actions(result.recommendation.actions)
        if not actions:
            actions = fallback["recommendation"]["actions"]

        risk = (result.risk_level or "").strip().lower()
        if risk not in {"low", "medium", "high", "critical"}:
            risk = str(fallback["risk_level"])

        response = (result.response or "").strip() or fallback["response"]
        requires_follow_up = bool(result.requires_follow_up)
        next_question = (result.next_question or "").strip()
        if not requires_follow_up:
            next_question = ""
        elif requires_follow_up and next_question and "?" not in next_question:
            next_question = f"{next_question.rstrip('.')}?"

        return UnifiedGenerationOutput(
            response=response,
            recommendation={
                "strategy": strategy,
                "actions": actions[:5],
            },
            risk_level=risk,
            requires_follow_up=requires_follow_up,
            next_question=next_question,
        )

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        value = (text or "").strip()
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars].rstrip()}..."

    @staticmethod
    def _compact_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
        keys = [
            "business_type",
            "company_type",
            "goal",
            "goals",
            "budget",
            "timeline",
            "constraints",
            "kpis",
            "urgency",
            "concern_area",
            "lead_score",
            "intent",
            "domain",
            "preferred_language",
        ]
        compact: Dict[str, Any] = {}
        for key in keys:
            value = profile.get(key)
            if value in (None, "", [], {}):
                continue
            if isinstance(value, str):
                compact[key] = value.strip()[:220]
            else:
                compact[key] = value
        return compact

    @staticmethod
    def _normalize_actions(items: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text:
                continue

            if len(items) == 1 and (", 2." in text or ";" in text):
                chunks = re.split(r"\s*;\s*|\s*,\s*(?=\d+\.)", text)
            else:
                chunks = [text]

            for chunk in chunks:
                cleaned = re.sub(r"^\d+\.\s*", "", chunk.strip())
                if cleaned and cleaned not in normalized:
                    normalized.append(cleaned)
        return normalized
