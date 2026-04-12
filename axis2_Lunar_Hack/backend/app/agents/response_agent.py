from __future__ import annotations

from app.agents.base import BaseJsonAgent
from app.models import (
    DecisionResult,
    IntentAnalysis,
    QualificationResult,
    RAGResult,
    RecommendationResult,
    ResponseDraft,
    SchemaBlueprint,
)
from app.prompts import RESPONSE_SYSTEM_PROMPT, build_response_prompt


class ResponseAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="response",
            system_prompt=RESPONSE_SYSTEM_PROMPT,
            use_reasoning_model=True,
        )

    async def run(
        self,
        language: str,
        user_message: str,
        intent: IntentAnalysis,
        schema: SchemaBlueprint,
        qualification: QualificationResult,
        rag: RAGResult,
        recommendation: RecommendationResult,
        decision: DecisionResult,
    ) -> ResponseDraft:
        prompt = build_response_prompt(
            language=language,
            user_message=user_message,
            intent_data=intent.model_dump(),
            schema_data=schema.model_dump(),
            qualification_data=qualification.model_dump(),
            rag_data=rag.model_dump(),
            recommendation_data=recommendation.model_dump(),
            decision_data=decision.model_dump(),
        )

        fallback = {
            "response": self._fallback_response(language, recommendation, decision, qualification),
            "next_question": qualification.next_question,
        }

        result = await self.run_contract(prompt, ResponseDraft, fallback)

        response = result.response.strip() or fallback["response"]
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
