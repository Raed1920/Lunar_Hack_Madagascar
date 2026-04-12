from __future__ import annotations

import logging
import re
from time import perf_counter
from typing import Any, Dict

from app.agents import SingleGenerationAgent
from app.config import Settings
from app.lead_scoring import compute_decision_priority, compute_lead_score
from app.memory import MemoryStore
from app.models import ChatRequest, ChatResponse, StructuredOutput
from app.ollama_client import OllamaClient
from app.ragflow_client import RAGFlowClient
from app.router import LightweightRouter
from app.trace_context import get_trace_id
from app.utils import compact_context, detect_language


logger = logging.getLogger("uvicorn.error")


class SalesIntelligenceOrchestrator:
    REQUIRED_PROFILE_FIELDS = ["business_type", "goal", "constraints"]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.memory_store = MemoryStore(settings.sqlite_path)
        self.ollama = OllamaClient(settings)
        self.ragflow = RAGFlowClient(settings)

        self.router = LightweightRouter()
        self.single_generation_agent = SingleGenerationAgent(settings, self.ollama)

        self.crewai_enabled = False

    async def close(self) -> None:
        await self.ollama.close()
        await self.ragflow.close()

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        trace_id = get_trace_id()
        stage_times: dict[str, float] = {}

        def mark_stage(name: str, start: float) -> None:
            elapsed_ms = (perf_counter() - start) * 1000
            stage_times[name] = elapsed_ms
            logger.info("[TRACE %s] stage=%s ms=%.1f", trace_id, name, elapsed_ms)
            print(f"[TRACE {trace_id}] stage={name} ms={elapsed_ms:.1f}")

        stage_start = perf_counter()
        existing_profile = self.memory_store.get_profile(request.user_id)
        language = detect_language(
            request.message,
            request.language or existing_profile.get("preferred_language") or self.settings.default_language,
        )
        mark_stage("profile_load_and_language_detect", stage_start)

        stage_start = perf_counter()
        history = self.memory_store.get_recent_messages(
            request.session_id,
            limit=self.settings.max_context_turns,
        )
        context_window = compact_context(history, self.settings.max_context_turns)
        mark_stage("context_load", stage_start)

        stage_start = perf_counter()
        self.memory_store.save_message(
            session_id=request.session_id,
            user_id=request.user_id,
            role="user",
            message=request.message,
        )
        mark_stage("persist_user_message", stage_start)

        stage_start = perf_counter()
        route = self.router.route(request.message)
        profile = self._merge_profile(
            existing=existing_profile,
            route_intent=route.intent,
            route_risk=route.risk_level,
            language=language,
        )
        mark_stage("router", stage_start)

        rag_sources: list[str] = []
        rag_context = ""
        rag_grounded = False
        if route.requires_rag:
            stage_start = perf_counter()
            chunks = await self.ragflow.retrieve(
                request.message,
                language=language,
                top_k=min(max(self.settings.ragflow_top_k, 1), 8),
            )
            mark_stage("ragflow_retrieve", stage_start)

            rag_sources = self._collect_rag_sources(chunks)
            rag_sources = list(dict.fromkeys([self._display_source_label(source) for source in rag_sources]))
            rag_context = self.ragflow.build_context(chunks, max_chars=1800)
            rag_grounded = bool(chunks)
            logger.info(
                "[TRACE %s] rag=enabled chunks=%d citations=%d",
                trace_id,
                len(chunks),
                len(rag_sources),
            )
            print(f"[TRACE {trace_id}] rag=enabled chunks={len(chunks)} citations={len(rag_sources)}")
        else:
            logger.info("[TRACE %s] rag=skipped", trace_id)
            print(f"[TRACE {trace_id}] rag=skipped")

        stage_start = perf_counter()
        lead_score = compute_lead_score(
            profile,
            intent=route.intent,
            confidence=float(route.confidence),
            turns=max(len(history) + 1, 1),
            urgency=self._risk_to_urgency(route.risk_level),
            required_fields=self.REQUIRED_PROFILE_FIELDS,
        )
        mark_stage("lead_scoring", stage_start)

        stage_start = perf_counter()
        generated = await self.single_generation_agent.run(
            language=language,
            user_message=request.message,
            route=route,
            profile=profile,
            context=context_window,
            rag_context=rag_context,
            rag_sources=rag_sources,
        )
        mark_stage("single_generation_agent", stage_start)

        stage_start = perf_counter()
        missing_fields = self._missing_fields(profile, self.REQUIRED_PROFILE_FIELDS)
        priority_hint, priority_score = compute_decision_priority(
            urgency=self._risk_to_urgency(generated.risk_level),
            confidence=float(route.confidence),
            missing_fields=missing_fields,
            action_count=len(generated.recommendation.actions),
            risk_count=1 if generated.risk_level in {"high", "critical"} else 0,
        )
        mark_stage("priority_scoring", stage_start)

        final_message = self._ensure_source_mention(
            response=generated.response,
            rag_sources=rag_sources,
            language=language,
            rag_used=route.requires_rag,
        )
        actions = generated.recommendation.actions[:5]
        cta = actions[0] if actions else (generated.recommendation.strategy or "Start implementation")

        profile["lead_score"] = lead_score
        profile["required_fields"] = self.REQUIRED_PROFILE_FIELDS
        profile["intent"] = route.intent
        profile["urgency"] = self._risk_to_urgency(generated.risk_level)

        stage_start = perf_counter()
        self.memory_store.upsert_profile(request.user_id, profile)
        self.memory_store.save_message(
            session_id=request.session_id,
            user_id=request.user_id,
            role="assistant",
            message=final_message,
        )
        mark_stage("persist_assistant_state", stage_start)

        structured = StructuredOutput(
            business_type=self._first_non_empty(profile.get("business_type"), profile.get("company_type"), "unknown"),
            need=self._first_non_empty(profile.get("goal"), profile.get("goals"), route.intent),
            recommended_strategy=generated.recommendation.strategy,
            estimated_impact=self._estimated_impact_from_risk(generated.risk_level),
            cta=cta,
            lead_score=lead_score,
            concern_area=profile.get("concern_area", "general_management"),
            urgency=self._risk_to_urgency(generated.risk_level),
            priority_actions=actions,
            missing_fields=missing_fields,
        )

        follow_up_email = self._format_follow_up_email(
            action=cta,
            priority=priority_hint,
            priority_score=priority_score,
            steps=actions[:3],
        )

        dynamic_profile = {
            field: profile.get(field)
            for field in self.REQUIRED_PROFILE_FIELDS
            if self._has_value(profile.get(field))
        }

        stage_snapshot = ", ".join(
            f"{name}={elapsed:.1f}ms" for name, elapsed in stage_times.items()
        )
        logger.info("[TRACE %s] stage_timeline %s", trace_id, stage_snapshot)
        print(f"[TRACE {trace_id}] stage_timeline {stage_snapshot}")

        return ChatResponse(
            response=final_message,
            language=language,
            structured=structured,
            user_profile={
                "business_type": profile.get("business_type"),
                "budget": profile.get("budget"),
                "goals": self._first_non_empty(profile.get("goal"), profile.get("goals")),
                "timeline": profile.get("timeline"),
                "intent": route.intent,
                "domain": profile.get("domain", self._domain_from_intent(route.intent)),
                "concern_area": profile.get("concern_area", "general_management"),
                "urgency": self._risk_to_urgency(generated.risk_level),
                "constraints": profile.get("constraints"),
                "kpis": profile.get("kpis"),
                "decision_options": [],
                "priority_actions": actions,
                "risks": [f"Risk level: {generated.risk_level}"],
                "immediate_actions": actions[:3],
                "lead_score": lead_score,
                "priority": priority_hint,
                "priority_score": priority_score,
                "required_fields": self.REQUIRED_PROFILE_FIELDS,
                "field_descriptions": {
                    "business_type": "Business model or company type",
                    "goal": "Primary outcome expected from this decision",
                    "constraints": "Main execution constraints",
                },
                "dynamic_profile": dynamic_profile,
                "rag_grounded": rag_grounded,
            },
            rag_sources=rag_sources,
            follow_up_email=follow_up_email,
            next_question=generated.next_question if generated.requires_follow_up and generated.next_question else None,
        )

    def _collect_rag_sources(self, chunks: list[Any]) -> list[str]:
        sources: list[str] = []
        placeholders = {
            "",
            "unknown",
            "none",
            "null",
            "n/a",
            "na",
            "knowledge_base",
        }

        for chunk in chunks:
            raw = str(getattr(chunk, "source", "")).strip()
            normalized = raw.lower()
            candidate = raw
            if normalized in placeholders or normalized.startswith("chunk:") or normalized.startswith("retrieved_chunk_"):
                inferred = ""
                try:
                    infer_fn = getattr(self.ragflow, "_infer_source_from_text", None)
                    if callable(infer_fn):
                        inferred = str(infer_fn(str(getattr(chunk, "text", ""))))
                except Exception:
                    inferred = ""
                candidate = inferred.strip()
                if not candidate:
                    continue

            if candidate not in sources:
                sources.append(self._display_source_label(candidate))
            if len(sources) >= 8:
                break

        if sources:
            return sources

        # Fallback to dataset labels if chunks had no usable file-level source metadata.
        dataset_sources = [f"dataset:{dataset_id}" for dataset_id in self.settings.rag_dataset_list if dataset_id]
        if dataset_sources:
            return [self._display_source_label(source) for source in dataset_sources[:5]]
        return ["knowledge_base"]

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

    def _merge_profile(
        self,
        existing: Dict[str, Any],
        route_intent: str,
        route_risk: str,
        language: str,
    ) -> Dict[str, Any]:
        profile = dict(existing)
        profile["intent"] = route_intent
        profile["domain"] = self._domain_from_intent(route_intent)
        profile["urgency"] = self._risk_to_urgency(route_risk)
        profile["preferred_language"] = language

        if self._has_value(profile.get("goal")) and not self._has_value(profile.get("goals")):
            profile["goals"] = profile.get("goal")

        return profile

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, str):
                return str(value)
        return ""

    @staticmethod
    def _format_follow_up_email(action: str, priority: str, priority_score: int, steps: list[str]) -> str:
        subject = f"Decision Plan - Priority {str(priority).upper()}"
        step_lines = [f"- {step}" for step in steps[:5]]
        body_lines = [
            "Thanks for the update.",
            f"Recommended decision: {action}",
            f"Priority: {priority} ({priority_score}/100)",
            "Execution steps:",
            *step_lines,
            "",
            "Reply with blockers and owners to finalize execution.",
        ]
        return f"Subject: {subject}\n\n" + "\n".join(body_lines).strip()

    @staticmethod
    def _missing_fields(profile: Dict[str, Any], fields: list[str]) -> list[str]:
        return [field for field in fields if not SalesIntelligenceOrchestrator._has_value(profile.get(field))]

    @staticmethod
    def _risk_to_urgency(risk_level: str) -> str:
        normalized = (risk_level or "").strip().lower()
        if normalized == "critical":
            return "critical"
        if normalized == "high":
            return "high"
        if normalized == "low":
            return "low"
        return "medium"

    @staticmethod
    def _estimated_impact_from_risk(risk_level: str) -> str:
        normalized = (risk_level or "").strip().lower()
        if normalized in {"high", "critical"}:
            return "High downside risk if delayed; prioritize immediate mitigation this cycle."
        if normalized == "low":
            return "Low risk profile with steady incremental upside expected."
        return "Moderate risk-adjusted upside with measurable gains in 30 to 60 days."

    @staticmethod
    def _domain_from_intent(intent: str) -> str:
        if intent == "risk_check":
            return "legal"
        if intent == "faq":
            return "general"
        return "analytics"

    @staticmethod
    def _ensure_source_mention(
        response: str,
        rag_sources: list[str],
        language: str,
        rag_used: bool,
    ) -> str:
        text = (response or "").strip()
        if not rag_used:
            return text

        sources = [
            SalesIntelligenceOrchestrator._display_source_label(str(item).strip())
            for item in rag_sources
            if str(item).strip()
        ][:2]
        if not sources:
            sources = ["dataset:sales-kb"]

        non_chunk_sources = [
            src
            for src in sources
            if not src.lower().startswith("chunk:") and not src.lower().startswith("retrieved_chunk_")
        ]
        if not non_chunk_sources:
            non_chunk_sources = ["dataset:sales-kb"]

        lowered = text.lower()
        source_markers = ["source", "sources", "citation", "المصدر", "المصادر", "source officielle"]
        if any(src.lower() in lowered for src in non_chunk_sources):
            return SalesIntelligenceOrchestrator._normalize_source_tokens_in_text(text)

        # Remove noisy chunk-style source suffix if model already added one.
        text = re.sub(
            r"(?i)(source|sources|citation|source officielle|المصدر|المصادر)\s*:\s*(chunk:[^\s.,;]+|retrieved_chunk_[^\s.,;]+)\.?",
            "",
            text,
        ).strip()

        source_text = ", ".join(non_chunk_sources)
        if language == "fr":
            suffix = f" Source: {source_text}."
        elif language == "ar":
            suffix = f" المصدر: {source_text}."
        else:
            suffix = f" Source: {source_text}."

        if not text:
            return suffix.strip()

        if re.search(r"[.!?؟]\s*$", text):
            final_text = f"{text}{suffix}"
        else:
            final_text = f"{text}. {suffix.strip()}"
        return SalesIntelligenceOrchestrator._normalize_source_tokens_in_text(final_text)

    @staticmethod
    def _display_source_label(source: str) -> str:
        text = str(source or "").strip()
        if not text:
            return "knowledge_base"

        # Keep dataset labels explicit and readable.
        if text.lower().startswith("dataset:"):
            dataset = text.split(":", 1)[1].strip() if ":" in text else text
            dataset = dataset.replace("_", " ").replace("-", " ").strip()
            return f"dataset:{dataset}" if dataset else "dataset:knowledge base"

        # Remove common file extensions for cleaner UI/response text.
        for extension in (".txt", ".md", ".pdf", ".docx", ".csv", ".json"):
            if text.lower().endswith(extension):
                return text[: -len(extension)]

        return text

    @staticmethod
    def _normalize_source_tokens_in_text(text: str) -> str:
        normalized = text
        for extension in ("txt", "md", "pdf", "docx", "csv", "json"):
            normalized = re.sub(
                rf"\b([A-Za-z0-9_\-]+)\.{extension}\b",
                r"\1",
                normalized,
                flags=re.IGNORECASE,
            )
        return normalized
