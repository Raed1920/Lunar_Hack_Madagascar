from __future__ import annotations

from typing import Any, Dict

from app.agents.base import BaseJsonAgent
from app.models import (
    DecisionResult,
    FinalizationResult,
    IntentAnalysis,
    QualificationResult,
    RAGResult,
    RecommendationResult,
    ResponseDraft,
    SchemaBlueprint,
)
from app.prompts import FINALIZATION_SYSTEM_PROMPT, build_finalization_prompt


class FinalizationAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="finalization",
            system_prompt=FINALIZATION_SYSTEM_PROMPT,
            use_reasoning_model=getattr(settings, "finalization_use_reasoning_model", False),
        )

    async def run(
        self,
        language: str,
        user_message: str,
        profile: Dict[str, Any],
        intent: IntentAnalysis,
        schema: SchemaBlueprint,
        qualification: QualificationResult,
        rag: RAGResult,
        priority_hint: str,
        priority_score: int,
    ) -> FinalizationResult:
        prompt = build_finalization_prompt(
            language=language,
            user_message=user_message,
            profile=self._compact_profile(profile, schema.required_fields),
            intent_data=self._compact_intent(intent),
            schema_data=self._compact_schema(schema),
            qualification_data=self._compact_qualification(qualification, schema.required_fields),
            rag_data=self._compact_rag(rag),
            priority_hint=priority_hint,
            priority_score=priority_score,
        )

        recommendation_fallback = {
            "recommended_strategy": "Run a focused 30-day execution cycle on the highest-impact bottleneck.",
            "actions": [
                "Assign one owner for the decision and weekly KPI review",
                "Execute the top-priority initiative in a 2-week sprint",
                "Review results and adjust based on KPI movement",
            ],
            "expected_impact": "Improved KPI stability and measurable 10% to 25% performance gain in 60 to 90 days.",
            "decision_options": [
                {
                    "title": "Conservative Path",
                    "summary": "Prioritize low-risk process improvements first",
                    "tradeoff": "Lower downside with slower upside",
                },
                {
                    "title": "Acceleration Path",
                    "summary": "Invest aggressively in the highest-leverage growth move",
                    "tradeoff": "Higher upside with higher execution risk",
                },
            ],
            "risks": ["Execution capacity", "Weak KPI instrumentation"],
        }

        decision_fallback = {
            "action": recommendation_fallback["actions"][0],
            "priority": priority_hint,
            "justification": "Priority is based on urgency, confidence, and expected impact.",
            "steps": recommendation_fallback["actions"][:3],
            "priority_score": priority_score,
        }

        recommendation_model = RecommendationResult.model_validate(recommendation_fallback)
        decision_model = DecisionResult.model_validate(decision_fallback)

        fallback = {
            "recommendation": recommendation_fallback,
            "decision": decision_fallback,
            "response": {
                "response": self._fallback_response(language, recommendation_model, decision_model, qualification),
                "next_question": qualification.next_question,
            },
        }

        result = await self.run_contract(prompt, FinalizationResult, fallback)

        recommendation = self._sanitize_recommendation(result.recommendation, recommendation_fallback)
        decision = self._sanitize_decision(result.decision, recommendation, priority_hint, priority_score)
        response = self._sanitize_response(result.response, language, recommendation, decision, qualification)

        return FinalizationResult(
            recommendation=recommendation,
            decision=decision,
            response=response,
        )

    def _sanitize_recommendation(
        self,
        result: RecommendationResult,
        fallback: Dict[str, Any],
    ) -> RecommendationResult:
        actions = [str(item).strip() for item in result.actions if str(item).strip()]
        if not actions:
            actions = fallback["actions"]

        risks = [str(item).strip() for item in result.risks if str(item).strip()]
        if not risks:
            risks = fallback["risks"]

        options = [option for option in result.decision_options if option.title.strip() and option.summary.strip()]
        if len(options) < 2:
            options = RecommendationResult.model_validate(fallback).decision_options

        return RecommendationResult(
            recommended_strategy=result.recommended_strategy.strip() or fallback["recommended_strategy"],
            actions=actions[:5],
            expected_impact=result.expected_impact.strip() or fallback["expected_impact"],
            decision_options=options[:3],
            risks=risks[:5],
        )

    def _sanitize_decision(
        self,
        result: DecisionResult,
        recommendation: RecommendationResult,
        priority_hint: str,
        priority_score: int,
    ) -> DecisionResult:
        fallback_action = recommendation.actions[0] if recommendation.actions else "Execute the highest-impact action this week"
        fallback_steps = recommendation.actions[:3] if recommendation.actions else [
            "Assign owner",
            "Set KPI target",
            "Launch execution sprint",
        ]

        steps = [str(item).strip() for item in result.steps if str(item).strip()]
        if not steps:
            steps = fallback_steps

        raw_score = self._safe_int(result.priority_score, default=priority_score)
        return DecisionResult(
            action=result.action.strip() or fallback_action,
            priority=self._normalize_priority(result.priority, default=priority_hint),
            justification=result.justification.strip() or "Priority is based on urgency, confidence, and expected impact.",
            steps=steps[:5],
            priority_score=max(0, min(raw_score, 100)),
        )

    def _sanitize_response(
        self,
        result: ResponseDraft,
        language: str,
        recommendation: RecommendationResult,
        decision: DecisionResult,
        qualification: QualificationResult,
    ) -> ResponseDraft:
        fallback = self._fallback_response(language, recommendation, decision, qualification)
        response = result.response.strip() or fallback
        next_question = (result.next_question or "").strip() or qualification.next_question
        if qualification.missing_fields and next_question and "?" not in next_question:
            next_question = f"{next_question.rstrip('.')}?"

        return ResponseDraft(response=response, next_question=next_question)

    @staticmethod
    def _fallback_response(
        language: str,
        recommendation: RecommendationResult,
        decision: DecisionResult,
        qualification: QualificationResult,
    ) -> str:
        key_risk = recommendation.risks[0] if recommendation.risks else "execution risk"

        if language == "fr":
            response = (
                f"Orientation recommandee: {recommendation.recommended_strategy}. "
                f"Decision: {decision.action} (priorite {decision.priority}). "
                f"Risque principal: {key_risk}."
            )
            if qualification.missing_fields and qualification.next_question:
                return f"{response} {qualification.next_question}"
            return response

        if language == "ar":
            response = (
                f"التوجه الموصى به: {recommendation.recommended_strategy}. "
                f"القرار: {decision.action} (اولوية {decision.priority}). "
                f"المخاطرة الرئيسية: {key_risk}."
            )
            if qualification.missing_fields and qualification.next_question:
                return f"{response} {qualification.next_question}"
            return response

        response = (
            f"Recommended direction: {recommendation.recommended_strategy}. "
            f"Decision: {decision.action} (priority {decision.priority}). "
            f"Key risk: {key_risk}."
        )
        if qualification.missing_fields and qualification.next_question:
            return f"{response} {qualification.next_question}"
        return response

    @staticmethod
    def _normalize_priority(priority: str, default: str = "medium") -> str:
        normalized = (priority or "").strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized

        fallback = (default or "").strip().lower()
        if fallback in {"low", "medium", "high"}:
            return fallback
        return "medium"

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list):
            return bool([item for item in value if str(item).strip()])
        if isinstance(value, dict):
            return bool(value)
        return True

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        value = (text or "").strip()
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars].rstrip()}..."

    def _compact_profile(self, profile: Dict[str, Any], required_fields: list[str]) -> Dict[str, Any]:
        compact: Dict[str, Any] = {}
        base_fields = [
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
            "intent",
            "domain",
            "lead_score",
            "preferred_language",
        ]

        for field in base_fields:
            value = profile.get(field)
            if self._has_value(value):
                compact[field] = value

        required_values: Dict[str, Any] = {}
        for field in required_fields[:5]:
            value = profile.get(field)
            if self._has_value(value):
                required_values[field] = value
        if required_values:
            compact["required_field_values"] = required_values

        return compact

    @staticmethod
    def _compact_intent(intent: IntentAnalysis) -> Dict[str, Any]:
        return {
            "intent": intent.intent,
            "domain": intent.domain,
            "concern_area": intent.concern_area,
            "urgency": intent.urgency,
            "confidence": float(intent.confidence),
            "requires_rag": bool(intent.requires_rag),
        }

    def _compact_schema(self, schema: SchemaBlueprint) -> Dict[str, Any]:
        required_fields = schema.required_fields[:5]
        descriptions = {
            field: desc
            for field, desc in schema.field_descriptions.items()
            if field in required_fields and self._has_value(desc)
        }
        return {
            "required_fields": required_fields,
            "field_descriptions": descriptions,
        }

    def _compact_qualification(self, qualification: QualificationResult, required_fields: list[str]) -> Dict[str, Any]:
        selected_updates: Dict[str, Any] = {}
        updates = qualification.updated_profile
        for field in required_fields[:5]:
            value = updates.get(field)
            if self._has_value(value):
                selected_updates[field] = value

        if not selected_updates:
            for key, value in updates.items():
                if self._has_value(value):
                    selected_updates[key] = value
                if len(selected_updates) >= 5:
                    break

        return {
            "updated_profile": selected_updates,
            "missing_fields": qualification.missing_fields[:5],
            "next_question": (qualification.next_question or "").strip(),
        }

    def _compact_rag(self, rag: RAGResult) -> Dict[str, Any]:
        return {
            "grounded": bool(rag.grounded),
            "confidence": rag.confidence,
            "citations": rag.citations[:5],
            "uncertainty": self._truncate(rag.uncertainty, max_chars=220),
            "factual_response": self._truncate(rag.factual_response, max_chars=900),
        }
