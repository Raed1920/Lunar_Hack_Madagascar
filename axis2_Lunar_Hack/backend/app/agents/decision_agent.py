from __future__ import annotations

from app.agents.base import BaseJsonAgent
from app.models import DecisionResult, IntentAnalysis, RecommendationResult
from app.prompts import DECISION_SYSTEM_PROMPT, build_decision_prompt


class DecisionAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="decision",
            system_prompt=DECISION_SYSTEM_PROMPT,
            use_reasoning_model=True,
        )

    async def run(
        self,
        profile: dict,
        intent: IntentAnalysis,
        recommendation: RecommendationResult,
        priority_hint: str,
        priority_score: int,
        language: str,
    ) -> DecisionResult:
        prompt = build_decision_prompt(
            profile=profile,
            intent_data=intent.model_dump(),
            recommendation_data=recommendation.model_dump(),
            priority_hint=priority_hint,
            language=language,
        )

        fallback = {
            "action": recommendation.actions[0] if recommendation.actions else "Execute the highest-impact action this week",
            "priority": priority_hint,
            "justification": "Priority is based on urgency, confidence, and expected impact.",
            "steps": recommendation.actions[:3] if recommendation.actions else [
                "Assign owner",
                "Set KPI target",
                "Launch execution sprint",
            ],
            "priority_score": priority_score,
        }

        result = await self.run_contract(prompt, DecisionResult, fallback)
        priority = self._normalize_priority(result.priority)
        steps = [str(item).strip() for item in result.steps if str(item).strip()]
        if not steps:
            steps = fallback["steps"]

        return DecisionResult(
            action=result.action.strip() or fallback["action"],
            priority=priority,
            justification=result.justification.strip() or fallback["justification"],
            steps=steps[:5],
            priority_score=max(0, min(priority_score, 100)),
        )

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        normalized = (priority or "").strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return "medium"
