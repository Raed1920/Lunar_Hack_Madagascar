from __future__ import annotations

from app.agents.base import BaseJsonAgent
from app.models import IntentAnalysis
from app.prompts import INTENT_SYSTEM_PROMPT, build_intent_prompt


class IntentAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="intent",
            system_prompt=INTENT_SYSTEM_PROMPT,
            use_reasoning_model=getattr(settings, "intent_use_reasoning_model", False),
        )

    async def run(self, message: str, context: str, language: str) -> IntentAnalysis:
        prompt = build_intent_prompt(
            self._truncate(message, max_chars=900),
            self._truncate(context, max_chars=1400),
            language,
        )
        fallback = self._heuristic_intent(message)
        result = await self.run_contract(prompt, IntentAnalysis, fallback)

        return IntentAnalysis(
            intent=self._normalize_intent(result.intent),
            domain=self._normalize_domain(result.domain),
            confidence=max(0.0, min(float(result.confidence), 1.0)),
            concern_area=self._normalize_concern_area(result.concern_area),
            urgency=self._normalize_urgency(result.urgency),
            requires_rag=bool(result.requires_rag),
            rationale=result.rationale,
        )

    def _heuristic_intent(self, message: str) -> dict:
        lowered = message.lower()

        domain = "general"
        intent = "diagnose"
        concern_area = "general_management"
        requires_rag = False

        if any(token in lowered for token in ["campaign", "ads", "seo", "funnel", "growth marketing"]):
            domain = "marketing"
            intent = "optimize"
            concern_area = "marketing"
        elif any(token in lowered for token in ["feature", "roadmap", "retention", "activation"]):
            domain = "product"
            intent = "plan"
            concern_area = "product"
        elif any(token in lowered for token in ["cohort", "dashboard", "metric", "analytics", "forecast"]):
            domain = "analytics"
            intent = "analyze"
            concern_area = "strategy"
        elif any(token in lowered for token in ["cash", "burn", "margin", "budget", "pricing"]):
            domain = "finance"
            intent = "forecast"
            concern_area = "finance"
        elif any(token in lowered for token in ["operations", "inventory", "supply", "delivery", "process"]):
            domain = "operations"
            intent = "optimize"
            concern_area = "operations"
        elif any(token in lowered for token in ["hire", "team", "recruit", "workforce"]):
            domain = "people"
            intent = "plan"
            concern_area = "people"
        elif any(token in lowered for token in ["legal", "contract", "compliance", "policy", "regulation", "gdpr"]):
            domain = "legal"
            intent = "risk_check"
            concern_area = "legal"
            requires_rag = True
        elif any(token in lowered for token in ["sales", "pipeline", "lead", "conversion"]):
            domain = "sales"
            intent = "optimize"
            concern_area = "sales"

        urgency = "medium"
        if any(token in lowered for token in ["critical", "urgent", "asap", "immediately", "today"]):
            urgency = "high"
        elif any(token in lowered for token in ["later", "eventually", "next quarter"]):
            urgency = "low"

        return {
            "intent": intent,
            "domain": domain,
            "confidence": 0.62,
            "concern_area": concern_area,
            "urgency": urgency,
            "requires_rag": requires_rag,
            "rationale": "heuristic fallback",
        }

    @staticmethod
    def _normalize_intent(value: str) -> str:
        normalized = (value or "").strip().lower()
        allowed = {
            "diagnose",
            "plan",
            "optimize",
            "execute",
            "analyze",
            "forecast",
            "risk_check",
            "comparison",
        }
        return normalized if normalized in allowed else "diagnose"

    @staticmethod
    def _normalize_domain(value: str) -> str:
        normalized = (value or "").strip().lower()
        allowed = {
            "marketing",
            "product",
            "analytics",
            "finance",
            "operations",
            "sales",
            "people",
            "legal",
            "general",
        }
        return normalized if normalized in allowed else "general"

    @staticmethod
    def _normalize_concern_area(value: str) -> str:
        normalized = (value or "").strip().lower()
        aliases = {
            "management": "general_management",
            "general": "general_management",
            "compliance": "legal",
        }
        normalized = aliases.get(normalized, normalized)
        allowed = {
            "strategy",
            "finance",
            "operations",
            "marketing",
            "sales",
            "product",
            "people",
            "legal",
            "general_management",
        }
        return normalized if normalized in allowed else "general_management"

    @staticmethod
    def _normalize_urgency(value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized in {"critical", "high", "medium", "low"}:
            return normalized
        if normalized in {"urgent", "very_high"}:
            return "high"
        return "medium"

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        value = (text or "").strip()
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars].rstrip()}..."
