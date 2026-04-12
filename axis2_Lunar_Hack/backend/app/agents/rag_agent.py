from __future__ import annotations

from typing import List

from app.agents.base import BaseJsonAgent
from app.models import RAGResult
from app.prompts import RAG_SYSTEM_PROMPT, build_rag_prompt


class RAGAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="rag",
            system_prompt=RAG_SYSTEM_PROMPT,
            use_reasoning_model=getattr(settings, "rag_use_reasoning_model", False),
        )

    async def run(self, query: str, rag_context: str, base_sources: List[str], language: str) -> RAGResult:
        compact_context = self._truncate(rag_context, max_chars=3200)
        normalized_sources = self._normalize_sources(base_sources)
        fallback = {
            "factual_response": compact_context[:420] if compact_context else "",
            "citations": normalized_sources,
            "grounded": bool(compact_context),
            "confidence": "medium" if compact_context else "low",
            "uncertainty": "No retrieved evidence found." if not compact_context else "",
        }

        if not compact_context.strip():
            return RAGResult.model_validate(fallback)

        prompt = build_rag_prompt(query=query, rag_context=compact_context, language=language)
        result = await self.run_contract(prompt, RAGResult, fallback)

        merged_citations: List[str] = []
        for item in [*result.citations, *normalized_sources]:
            text = str(item).strip()
            if text and text not in merged_citations:
                merged_citations.append(text)
            if len(merged_citations) >= 8:
                break

        grounded = bool(result.grounded and result.factual_response.strip())
        confidence = (result.confidence or "medium").strip().lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"

        return RAGResult(
            factual_response=result.factual_response.strip(),
            citations=merged_citations,
            grounded=grounded,
            confidence=confidence,
            uncertainty=result.uncertainty.strip(),
        )

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        value = (text or "").strip()
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars].rstrip()}..."

    @staticmethod
    def _normalize_sources(base_sources: List[str]) -> List[str]:
        deduped: List[str] = []
        for item in base_sources:
            text = str(item).strip()
            if text and text not in deduped:
                deduped.append(text)
            if len(deduped) >= 8:
                break
        return deduped
