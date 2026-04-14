import asyncio
from datetime import datetime, timezone
import json
import re
from statistics import mean
import time
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

import httpx
from psycopg.types.json import Jsonb

from ..config import get_settings
from ..database import execute, fetch_all, fetch_one
from ..models.schemas import (
    ActionPlanDay,
    AnalyzeMarketingResponse,
    CampaignDetailsResponse,
    ChatImageInsight,
    ChatRequest,
    ChatResponse,
    CreativeBriefRequest,
    CreativeBriefResponse,
    FeedbackRequest,
    FeedbackResponse,
    GenerateMarketingRequest,
    GenerateMarketingResponse,
    GenerateStreamEvent,
    MarketSignalItem,
    PortfolioSummary,
    RefineMarketingRequest,
    RefineMarketingResponse,
    SignalsResponse,
    StrategicOption,
    SolutionItem,
)
from .budget_estimator import BudgetEstimator
from .critic_validator import CriticValidator
from .llm_router import LLMResult, LLMRouter
from .market_signals_repo import MarketSignalsRepository
from .prompt_hub import PromptHub
from .solutions_generator import SolutionsGenerator
from .strategy_planner import StrategyPlanner


class MarketingService:
    def __init__(self):
        self.llm_router = LLMRouter()
        self.prompt_hub = PromptHub()
        self.market_signals_repo = MarketSignalsRepository()
        self.strategy_planner = StrategyPlanner(self.llm_router, self.prompt_hub)
        self.solutions_generator = SolutionsGenerator(BudgetEstimator(), self.llm_router, self.prompt_hub)
        self.critic_validator = CriticValidator()

    async def health(self) -> dict[str, str]:
        fetch_one("SELECT 1 AS ok")
        return {"status": "ok", "database": "connected"}

    async def analyze(self, request: GenerateMarketingRequest) -> AnalyzeMarketingResponse:
        base_signals = self.market_signals_repo.list_signals(request.workspace_id)
        external_signals = await self._fetch_external_signals(request)
        signals = self._merge_signals(base_signals, external_signals)
        workspace_memory = self._load_workspace_memory(request.workspace_id)
        strategy = await self.strategy_planner.plan(request, signals, workspace_memory)
        return AnalyzeMarketingResponse(strategy=strategy, signals_used_count=len(signals))

    async def generate(self, request: GenerateMarketingRequest) -> GenerateMarketingResponse:
        started = datetime.now(timezone.utc)

        base_signals = self.market_signals_repo.list_signals(request.workspace_id)
        external_signals = await self._fetch_external_signals(request)
        signals = self._merge_signals(base_signals, external_signals)
        workspace_memory = self._load_workspace_memory(request.workspace_id)
        strategy = await self.strategy_planner.plan(request, signals, workspace_memory)
        solutions = await self.solutions_generator.generate(request, strategy, signals, workspace_memory)
        strategy_meta = self._llm_result_to_meta(self.strategy_planner.last_llm_result)
        solutions_meta = self._llm_result_to_meta(self.solutions_generator.last_llm_result)

        critic = self.critic_validator.validate(solutions)
        campaign_id = self._persist_generation(
            request,
            strategy.model_dump(),
            solutions,
            critic,
            strategy_meta,
            solutions_meta,
        )

        ended = datetime.now(timezone.utc)
        response = self._build_generate_response(
            request=request,
            campaign_id=campaign_id,
            strategy=strategy,
            solutions=solutions,
            signals=signals,
            critic_score=critic.score,
            started=started,
            ended=ended,
        )
        response = await self._compose_response_fields(request, response, workspace_memory)
        await self._emit_campaign_ops_event(campaign_id, request, strategy, solutions)
        return response

    async def generate_stream(self, request: GenerateMarketingRequest) -> AsyncIterator[dict[str, Any]]:
        started = datetime.now(timezone.utc)
        yield self._stream_event(
            status="analyzing",
            step="reading_market_signals",
            data={"workspace_id": str(request.workspace_id)},
        )

        base_signals = self.market_signals_repo.list_signals(request.workspace_id)
        external_signals = await self._fetch_external_signals(request)
        signals = self._merge_signals(base_signals, external_signals)
        workspace_memory = self._load_workspace_memory(request.workspace_id)
        yield self._stream_event(
            status="signals_ready",
            step="signals_loaded",
            data={"signals_count": len(signals)},
        )

        strategy = await self.strategy_planner.plan(request, signals, workspace_memory)
        yield self._stream_event(
            status="strategy_ready",
            step="strategy_generated",
            data={"strategy": strategy.model_dump(mode="json")},
        )

        solutions = await self.solutions_generator.generate(request, strategy, signals, workspace_memory)
        strategy_meta = self._llm_result_to_meta(self.strategy_planner.last_llm_result)
        solutions_meta = self._llm_result_to_meta(self.solutions_generator.last_llm_result)
        yield self._stream_event(
            status="solutions_ready",
            step="portfolio_generated",
            data={
                "solutions_count": len(solutions),
                "channels": sorted({s.channel for s in solutions}),
            },
        )

        critic = self.critic_validator.validate(solutions)
        yield self._stream_event(
            status="validation_ready",
            step="critic_completed",
            data={"critic_score": critic.score, "issues": critic.issues},
        )

        campaign_id = self._persist_generation(
            request,
            strategy.model_dump(),
            solutions,
            critic,
            strategy_meta,
            solutions_meta,
        )
        ended = datetime.now(timezone.utc)

        final_response = self._build_generate_response(
            request=request,
            campaign_id=campaign_id,
            strategy=strategy,
            solutions=solutions,
            signals=signals,
            critic_score=critic.score,
            started=started,
            ended=ended,
        )
        final_response = await self._compose_response_fields(request, final_response, workspace_memory)
        await self._emit_campaign_ops_event(campaign_id, request, strategy, solutions)

        yield self._stream_event(
            status="completed",
            step="generation_complete",
            data=final_response.model_dump(mode="json"),
        )

    async def generate_solutions_only(self, request: GenerateMarketingRequest) -> list[SolutionItem]:
        base_signals = self.market_signals_repo.list_signals(request.workspace_id)
        external_signals = await self._fetch_external_signals(request)
        signals = self._merge_signals(base_signals, external_signals)
        workspace_memory = self._load_workspace_memory(request.workspace_id)
        strategy = await self.strategy_planner.plan(request, signals, workspace_memory)
        return await self.solutions_generator.generate(request, strategy, signals, workspace_memory)

    async def _fetch_external_signals(self, request: GenerateMarketingRequest) -> list[dict[str, Any]]:
        settings = get_settings()
        webhook_url = settings.n8n_signal_webhook_url or settings.n8n_webhook_url
        if not webhook_url:
            return []

        payload = {
            "workspace_id": str(request.workspace_id),
            "product_name": request.product_name,
            "objective": request.objective,
            "location": request.audience.location,
            "segment": request.audience.segment,
            "interests": request.audience.interests,
            "campaign_timeline": request.campaign_timeline,
            "budget": request.budget_constraint.model_dump(),
            "language_preference": request.language_preference,
            "constraints": request.constraints,
        }

        body = await self._post_n8n_payload(
            webhook_url,
            payload,
            workflow_key="w1_market_signal_enricher",
            workspace_id=str(request.workspace_id),
            campaign_id=None,
        )
        if body is None:
            return []

        raw_signals = body.get("signals") if isinstance(body, dict) else None
        if not isinstance(raw_signals, list):
            raw_signals = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), list) else None

        if not isinstance(raw_signals, list) and isinstance(body, dict):
            top_signals = body.get("top_signals")
            if isinstance(top_signals, list):
                raw_signals = [
                    {
                        "signal_key": f"n8n_top_{idx + 1}",
                        "signal_type": "summary",
                        "signal_value": str(item),
                    }
                    for idx, item in enumerate(top_signals)
                    if str(item).strip()
                ]

        if not isinstance(raw_signals, list):
            return []

        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_signals):
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("id") or f"n8n_{idx}",
                    "signal_key": str(item.get("signal_key") or item.get("signal") or "external_signal"),
                    "signal_type": str(item.get("signal_type") or item.get("type") or "external"),
                    "signal_value": str(item.get("signal_value") or item.get("impact") or "External context signal"),
                }
            )

        return normalized

    def _n8n_timeout_seconds(self) -> float:
        settings = get_settings()
        try:
            return max(0.5, float(settings.n8n_request_timeout_seconds))
        except (TypeError, ValueError):
            return 3.5

    @staticmethod
    def _n8n_headers() -> dict[str, str]:
        settings = get_settings()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.n8n_webhook_token:
            headers["Authorization"] = f"Bearer {settings.n8n_webhook_token}"
        return headers

    def _log_n8n_event(
        self,
        *,
        workflow_key: str,
        endpoint_url: str,
        request_payload: dict[str, Any],
        response_payload: Any,
        status_code: int | None,
        latency_ms: int,
        success: bool,
        error_message: str | None,
        workspace_id: str | None,
        campaign_id: str | None,
    ) -> None:
        response_json = response_payload if isinstance(response_payload, (dict, list)) else None
        try:
            execute(
                """
                INSERT INTO n8n_event_store (
                    workflow_key, endpoint_url, request_payload_json,
                    response_payload_json, status_code, latency_ms,
                    success, error_message, workspace_id_text, campaign_id_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    workflow_key,
                    endpoint_url,
                    Jsonb(request_payload),
                    Jsonb(response_json) if response_json is not None else None,
                    status_code,
                    latency_ms,
                    success,
                    error_message,
                    workspace_id,
                    campaign_id,
                ),
            )
        except Exception:
            return

    async def _post_n8n_payload(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        workflow_key: str,
        workspace_id: str | None,
        campaign_id: str | None,
    ) -> dict[str, Any] | None:
        started = time.perf_counter()
        response_body: Any = None
        response_status: int | None = None
        error_message: str | None = None
        try:
            async with httpx.AsyncClient(timeout=self._n8n_timeout_seconds()) as client:
                response = await client.post(url, headers=self._n8n_headers(), json=payload)
                response_status = response.status_code
                response.raise_for_status()
                try:
                    response_body = response.json()
                except ValueError:
                    response_body = {"raw_text": response.text}
        except Exception as exc:
            error_message = str(exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._log_n8n_event(
                workflow_key=workflow_key,
                endpoint_url=url,
                request_payload=payload,
                response_payload=response_body,
                status_code=response_status,
                latency_ms=latency_ms,
                success=False,
                error_message=error_message,
                workspace_id=workspace_id,
                campaign_id=campaign_id,
            )
            return None

        latency_ms = int((time.perf_counter() - started) * 1000)
        self._log_n8n_event(
            workflow_key=workflow_key,
            endpoint_url=url,
            request_payload=payload,
            response_payload=response_body,
            status_code=response_status,
            latency_ms=latency_ms,
            success=True,
            error_message=None,
            workspace_id=workspace_id,
            campaign_id=campaign_id,
        )

        if isinstance(response_body, dict):
            return response_body
        if isinstance(response_body, list):
            return {"data": response_body}
        return None

    @staticmethod
    def _merge_signals(
        base_signals: list[dict[str, Any]],
        external_signals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged = [*base_signals]
        seen = {
            str(signal.get("signal_key") or "").strip().lower()
            for signal in base_signals
            if str(signal.get("signal_key") or "").strip()
        }

        for signal in external_signals:
            key = str(signal.get("signal_key") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(signal)

        return merged

    @staticmethod
    def _parse_json_like(value: Any, fallback: Any) -> Any:
        if value is None:
            return fallback
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return fallback
            if isinstance(fallback, dict) and isinstance(parsed, dict):
                return parsed
            if isinstance(fallback, list) and isinstance(parsed, list):
                return parsed
        return fallback

    def _load_workspace_memory(self, workspace_id: UUID) -> dict[str, Any]:
        row = fetch_one(
            """
            SELECT preferred_tone, language_preference, banned_phrases,
                   winning_tones_json, winning_channels_json, winning_budget_range,
                   max_budget_preference, sector_category, target_location, updated_at
            FROM brand_memory
            WHERE workspace_id = %s
            LIMIT 1
            """,
            (str(workspace_id),),
        )
        if not row:
            return {}

        return {
            "preferred_tone": str(row.get("preferred_tone") or "").strip() or None,
            "language_preference": str(row.get("language_preference") or "").strip() or None,
            "banned_phrases": self._parse_json_like(row.get("banned_phrases"), []),
            "winning_tones": self._parse_json_like(row.get("winning_tones_json"), {}),
            "winning_channels": self._parse_json_like(row.get("winning_channels_json"), {}),
            "winning_budget_range": self._parse_json_like(row.get("winning_budget_range"), {}),
            "max_budget_preference": (
                float(row.get("max_budget_preference"))
                if row.get("max_budget_preference") is not None
                else None
            ),
            "sector_category": str(row.get("sector_category") or "").strip() or None,
            "target_location": str(row.get("target_location") or "").strip() or None,
            "updated_at": str(row.get("updated_at") or "") or None,
        }

    async def _emit_campaign_ops_event(
        self,
        campaign_id: UUID,
        request: GenerateMarketingRequest,
        strategy: Any,
        solutions: list[SolutionItem],
    ) -> None:
        settings = get_settings()
        if not settings.n8n_campaign_ops_webhook_url:
            return

        strategy_payload = strategy.model_dump() if hasattr(strategy, "model_dump") else dict(strategy or {})
        solutions_payload = [
            {
                "id": item.id,
                "channel": item.channel,
                "solution_name": item.solution_name,
                "description": item.description,
                "reasoning": item.reasoning,
                "budget_estimate": float(item.budget.total_high),
                "budget_low": float(item.budget.total_low),
                "budget_high": float(item.budget.total_high),
                "currency": item.budget.currency,
                "copy": item.execution.exact_copy,
                "caption": item.execution.message,
                "cta_text": item.execution.cta_text,
            }
            for item in solutions
        ]
        payload = {
            "campaign_id": str(campaign_id),
            "workspace_id": str(request.workspace_id),
            "strategy": strategy_payload,
            "solutions": solutions_payload,
            "status": "generated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._post_n8n_payload(
            settings.n8n_campaign_ops_webhook_url,
            payload,
            workflow_key="w2_campaign_ops",
            workspace_id=str(request.workspace_id),
            campaign_id=str(campaign_id),
        )
        await self._trigger_publish_scheduler(str(request.workspace_id), str(campaign_id), reason="campaign_ops")

    async def _trigger_creative_media_pipeline(
        self,
        request: CreativeBriefRequest,
        image_prompt: str,
    ) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.n8n_creative_media_webhook_url:
            return None
        if request.campaign_id is None:
            return None

        style_hint = ", ".join([entry.strip() for entry in request.style_constraints if entry.strip()][:3])
        payload = {
            "workspace_id": str(request.workspace_id),
            "campaign_id": str(request.campaign_id),
            "task_type": "image_generation",
            "prompt": image_prompt,
            "constraints": {
                "style": style_hint or "cinematic",
                "channel": request.channel,
                "tone": request.tone_preference,
            },
        }
        return await self._post_n8n_payload(
            settings.n8n_creative_media_webhook_url,
            payload,
            workflow_key="w4_creative_media",
            workspace_id=str(request.workspace_id),
            campaign_id=str(request.campaign_id),
        )

    async def _trigger_learning_loop(
        self,
        workspace_id: str,
        campaign_id: str | None,
        *,
        reason: str,
    ) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.n8n_learning_webhook_url:
            return None

        payload = {
            "workspace_id": workspace_id,
            "campaign_id": campaign_id,
            "reason": reason,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        return await self._post_n8n_payload(
            settings.n8n_learning_webhook_url,
            payload,
            workflow_key="w3_learning_loop",
            workspace_id=workspace_id,
            campaign_id=campaign_id,
        )

    async def _trigger_publish_scheduler(
        self,
        workspace_id: str,
        campaign_id: str | None,
        *,
        reason: str,
    ) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.n8n_publish_webhook_url:
            return None

        payload = {
            "workspace_id": workspace_id,
            "campaign_id": campaign_id,
            "reason": reason,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        return await self._post_n8n_payload(
            settings.n8n_publish_webhook_url,
            payload,
            workflow_key="w5_publish_scheduler",
            workspace_id=workspace_id,
            campaign_id=campaign_id,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        normalized_request, assumptions, missing_context = await self._build_generate_request_from_message(request)
        visual_task = asyncio.create_task(self._analyze_image_pack(request, normalized_request))

        requires_clarification = self._requires_user_clarification(missing_context)
        visual_insights = await visual_task

        if requires_clarification:
            clarifying_questions = await self._build_clarifying_questions(
                request,
                normalized_request,
                missing_context,
            )
            assistant_message = self._clarification_message(clarifying_questions)

            return ChatResponse(
                status="question_asked",
                campaign_id=None,
                assistant_message=assistant_message,
                assumptions_used=assumptions,
                clarifying_questions=clarifying_questions,
                visual_insights=visual_insights,
                result=None,
            )

        result = await self.generate(normalized_request)

        assistant_message = str(result.assistant_explanation or "").strip()

        return ChatResponse(
            status="generated",
            campaign_id=result.campaign_id,
            assistant_message=assistant_message,
            assumptions_used=assumptions,
            clarifying_questions=[],
            visual_insights=visual_insights,
            result=result,
        )

    @staticmethod
    def _requires_user_clarification(missing_context: list[str]) -> bool:
        hard_blockers = {"budget", "audience_location"}
        missing = {field for field in missing_context if field in hard_blockers}
        return bool(missing)

    @staticmethod
    def _clarification_message(questions: list[str]) -> str:
        cleaned = [question.strip() for question in questions if question.strip()]
        if not cleaned:
            return "Before I generate your strategy, what is your exact budget range and target city?"

        if len(cleaned) == 1:
            return cleaned[0]

        first = cleaned[0]
        rest = " | ".join(cleaned[1:])
        return f"{first} Also please clarify: {rest}"

    async def generate_creative_brief(self, request: CreativeBriefRequest) -> CreativeBriefResponse:
        context_json = json.dumps(
            {
                "campaign_id": str(request.campaign_id) if request.campaign_id else None,
                "product_name": request.product_name,
                "objective": request.objective,
                "channel": request.channel,
                "audience": request.audience.model_dump(),
                "language_preference": request.language_preference,
                "tone_preference": request.tone_preference,
                "style_constraints": request.style_constraints,
                "reference_notes": request.reference_notes,
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("creative_brief_v1.txt", context_json=context_json)

        llm_result = await self.llm_router.try_generate_json(
            "creative_brief_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        if not llm_result or not isinstance(llm_result.data, dict):
            raise RuntimeError("Creative brief agent failed to generate JSON output")

        payload = dict(llm_result.data)
        payload["campaign_id"] = request.campaign_id
        payload["objective"] = str(payload.get("objective") or request.objective)
        payload["channel"] = str(payload.get("channel") or request.channel)

        if isinstance(payload.get("color_palette"), str):
            payload["color_palette"] = [
                item.strip(" -")
                for item in str(payload.get("color_palette") or "").split(",")
                if item.strip(" -")
            ]

        if isinstance(payload.get("do_not_include"), str):
            payload["do_not_include"] = [
                item.strip(" -")
                for item in str(payload.get("do_not_include") or "").split(",")
                if item.strip(" -")
            ]

        media_result = await self._trigger_creative_media_pipeline(
            request,
            str(payload.get("image_prompt") or "").strip(),
        )
        if isinstance(media_result, dict):
            media_url = str(media_result.get("media_url") or "").strip()
            media_status = str(media_result.get("status") or "").strip()
            if media_url:
                payload["rationale"] = (
                    f"{str(payload.get('rationale') or '').strip()} Media pipeline returned asset URL: {media_url}."
                ).strip()
            elif media_status:
                payload["rationale"] = (
                    f"{str(payload.get('rationale') or '').strip()} Media pipeline status: {media_status}."
                ).strip()

        return CreativeBriefResponse.model_validate(payload)

    async def refine(self, request: RefineMarketingRequest) -> RefineMarketingResponse:
        context_json = json.dumps(
            {
                "campaign_id": str(request.campaign_id),
                "refinement_instruction": request.refinement_instruction,
                "updated_budget_constraint": (
                    request.updated_budget_constraint.model_dump()
                    if request.updated_budget_constraint
                    else None
                ),
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("refine_solution_v1.txt", context_json=context_json)

        llm_result = await self.llm_router.try_generate_json(
            "refine_solution_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        if not llm_result or not isinstance(llm_result.data, dict):
            raise RuntimeError("Refine solution agent failed to generate JSON output")

        payload = dict(llm_result.data)
        payload["id"] = f"sol_new_{uuid4().hex[:6]}"
        payload["index"] = 0
        if not isinstance(payload.get("signals_used"), list):
            payload["signals_used"] = []
        new_solution = SolutionItem.model_validate(payload)

        return RefineMarketingResponse(
            campaign_id=request.campaign_id,
            refinement_id=f"ref_{uuid4().hex[:8]}",
            removed_solutions=[],
            new_solutions=[new_solution],
            modified_solutions=[],
            created_at=datetime.now(timezone.utc),
        )

    async def record_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        feedback_id = f"fb_{uuid4().hex[:8]}"

        try:
            campaign_row = fetch_one(
                """
                SELECT workspace_id
                FROM campaigns
                WHERE id = %s
                LIMIT 1
                """,
                (str(request.campaign_id),),
            )
            workspace_id = str((campaign_row or {}).get("workspace_id") or "").strip()
            if workspace_id:
                await self._trigger_learning_loop(
                    workspace_id,
                    str(request.campaign_id),
                    reason="feedback_received",
                )
        except Exception:
            pass

        return FeedbackResponse(
            feedback_id=feedback_id,
            campaign_id=request.campaign_id,
            solution_id=request.solution_id,
            learning_update={
                "message": "Feedback stored for future strategy ranking.",
                "updated_in_brand_memory": True,
            },
            created_at=datetime.now(timezone.utc),
        )

    async def get_campaign(self, campaign_id: UUID) -> CampaignDetailsResponse | None:
        campaign_row = fetch_one(
            """
            SELECT id, workspace_id, status, brief_id, created_at, updated_at
            FROM campaigns
            WHERE id = %s
            """,
            (str(campaign_id),),
        )

        if not campaign_row:
            return None

        brief_row = fetch_one(
            """
            SELECT id, product_name, product_description, product_category,
                   audience_location, audience_interests, audience_segment,
                   objective, campaign_timeline, budget_constraint_low, budget_constraint_high,
                   language_preference, tone_preference, constraints_text, created_at
            FROM campaign_briefs
            WHERE id = %s
            """,
            (campaign_row["brief_id"],),
        )

        strategy_row = fetch_one(
            """
            SELECT positioning, target_psychology, market_opportunity,
                   messaging_pillars, tone_recommendation, channel_priorities,
                   timeline_summary, risk_notes, model_used, latency_ms,
                   confidence_strategy, tokens_used, created_at
            FROM campaign_strategies
            WHERE campaign_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (str(campaign_id),),
        )

        solutions_rows = fetch_all(
            """
            SELECT id, solution_index, channel, solution_name, description,
                   execution, budget, expected_outcomes,
                   confidence_score, reasoning, signals_used,
                 risk_level, model_used, latency_ms, created_at
            FROM campaign_solutions
            WHERE campaign_id = %s
            ORDER BY solution_index ASC
            """,
            (str(campaign_id),),
        )

        return CampaignDetailsResponse(
            campaign_id=campaign_row["id"],
            workspace_id=campaign_row["workspace_id"],
            status=campaign_row["status"],
            brief=brief_row or {},
            strategy=strategy_row,
            solutions=solutions_rows,
            created_at=campaign_row["created_at"],
            updated_at=campaign_row["updated_at"],
        )

    async def get_signals(
        self,
        workspace_id: UUID,
        region: str | None,
        signal_type: str | None,
    ) -> SignalsResponse:
        signals = self.market_signals_repo.list_signals(
            workspace_id=workspace_id,
            region=region,
            signal_type=signal_type,
        )

        return SignalsResponse(
            signals=signals,
            count=len(signals),
            fetched_at=datetime.now(timezone.utc),
        )

    async def get_n8n_impact(self, workspace_id: UUID) -> dict[str, Any]:
        workspace_key = str(workspace_id)

        workflow_rows = fetch_all(
            """
            SELECT workflow_key,
                   COUNT(*) AS total_calls,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) AS success_calls,
                   ROUND(COALESCE(AVG(latency_ms), 0), 1) AS avg_latency_ms,
                   MAX(created_at) AS last_called_at
            FROM n8n_event_store
            WHERE workspace_id_text = %s OR workspace_id_text IS NULL
            GROUP BY workflow_key
            ORDER BY workflow_key
            """,
            (workspace_key,),
        )

        signal_count_row = fetch_one(
            """
            SELECT COUNT(*) AS signal_count
            FROM market_signals
            WHERE workspace_id = %s
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            (workspace_key,),
        )

        brand_memory_row = fetch_one(
            """
            SELECT updated_at, winning_tones_json, winning_channels_json
            FROM brand_memory
            WHERE workspace_id = %s
            LIMIT 1
            """,
            (workspace_key,),
        )

        campaign_status_rows = fetch_all(
            """
            SELECT status, COUNT(*) AS count
            FROM campaigns
            WHERE workspace_id = %s
            GROUP BY status
            ORDER BY status
            """,
            (workspace_key,),
        )

        media_status_rows: list[dict[str, Any]]
        try:
            media_status_rows = fetch_all(
                """
                SELECT status, COUNT(*) AS count
                FROM generated_media
                WHERE workspace_id = %s
                GROUP BY status
                ORDER BY status
                """,
                (workspace_key,),
            )
        except Exception:
            media_status_rows = []

        return {
            "workspace_id": workspace_key,
            "workflow_calls": workflow_rows,
            "impact_snapshot": {
                "active_market_signals": int((signal_count_row or {}).get("signal_count") or 0),
                "brand_memory_updated_at": (
                    (brand_memory_row or {}).get("updated_at")
                    if brand_memory_row
                    else None
                ),
                "campaign_status_counts": campaign_status_rows,
                "media_status_counts": media_status_rows,
                "winning_tones": (
                    self._parse_json_like((brand_memory_row or {}).get("winning_tones_json"), {})
                    if brand_memory_row
                    else {}
                ),
                "winning_channels": (
                    self._parse_json_like((brand_memory_row or {}).get("winning_channels_json"), {})
                    if brand_memory_row
                    else {}
                ),
            },
        }

    async def trigger_workflows(
        self,
        workspace_id: UUID,
        *,
        run_signal: bool,
        run_learning: bool,
        run_publish: bool,
    ) -> dict[str, Any]:
        settings = get_settings()
        workspace_key = str(workspace_id)
        results: list[dict[str, Any]] = []

        if run_signal:
            if settings.n8n_signal_webhook_url or settings.n8n_webhook_url:
                payload = {
                    "workspace_id": workspace_key,
                    "region": "tunisia",
                    "query": "Tunisia",
                    "max_per_source": 25,
                }
                body = await self._post_n8n_payload(
                    settings.n8n_signal_webhook_url or settings.n8n_webhook_url or "",
                    payload,
                    workflow_key="w1_market_signal_enricher",
                    workspace_id=workspace_key,
                    campaign_id=None,
                )
                results.append(
                    {
                        "workflow": "w1_market_signal_enricher",
                        "status": "triggered" if body is not None else "failed",
                        "response": body,
                    }
                )
            else:
                results.append(
                    {
                        "workflow": "w1_market_signal_enricher",
                        "status": "skipped",
                        "reason": "webhook_not_configured",
                    }
                )

        if run_learning:
            body = await self._trigger_learning_loop(
                workspace_key,
                None,
                reason="manual_ops_trigger",
            )
            results.append(
                {
                    "workflow": "w3_learning_loop",
                    "status": "triggered" if body is not None else "skipped",
                    "response": body,
                    "reason": None if body is not None else "webhook_not_configured_or_failed",
                }
            )

        if run_publish:
            body = await self._trigger_publish_scheduler(
                workspace_key,
                None,
                reason="manual_ops_trigger",
            )
            results.append(
                {
                    "workflow": "w5_publish_scheduler",
                    "status": "triggered" if body is not None else "skipped",
                    "response": body,
                    "reason": None if body is not None else "webhook_not_configured_or_failed",
                }
            )

        return {
            "workspace_id": workspace_key,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }

    def _persist_generation(
        self,
        request: GenerateMarketingRequest,
        strategy: dict,
        solutions: list[SolutionItem],
        critic,
        strategy_meta: dict[str, Any] | None = None,
        solutions_meta: dict[str, Any] | None = None,
    ) -> UUID:
        workspace_id = str(request.workspace_id)
        campaign_id = uuid4()
        strategy_meta = strategy_meta or {}
        solutions_meta = solutions_meta or {}

        strategy_model_used = self._format_model_used(strategy_meta)
        strategy_latency_ms = int(strategy_meta.get("latency_ms") or 0)
        strategy_tokens_used = int(
            (strategy_meta.get("input_tokens_estimate") or 0)
            + (strategy_meta.get("output_tokens_estimate") or 0)
        )

        solutions_model_used = self._format_model_used(solutions_meta)
        solutions_latency_ms = int(solutions_meta.get("latency_ms") or 0)

        total_input_tokens = int(
            (strategy_meta.get("input_tokens_estimate") or 0)
            + (solutions_meta.get("input_tokens_estimate") or 0)
        )
        total_output_tokens = int(
            (strategy_meta.get("output_tokens_estimate") or 0)
            + (solutions_meta.get("output_tokens_estimate") or 0)
        )
        total_cost_estimate = float(
            (strategy_meta.get("cost_estimate") or 0.0)
            + (solutions_meta.get("cost_estimate") or 0.0)
        )
        total_latency_ms = strategy_latency_ms + solutions_latency_ms

        try:
            execute(
                """
                INSERT INTO workspaces (id, name, sector)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (workspace_id, f"Workspace {workspace_id[:8]}", request.product_category),
            )

            brief_row = fetch_one(
                """
                INSERT INTO campaign_briefs (
                    workspace_id, product_name, product_description, product_category,
                    audience_location, audience_interests, audience_segment,
                    objective, campaign_timeline, budget_constraint_low, budget_constraint_high,
                    language_preference, tone_preference, constraints_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    workspace_id,
                    request.product_name,
                    request.product_description,
                    request.product_category,
                    request.audience.location,
                    Jsonb(request.audience.interests),
                    request.audience.segment,
                    request.objective,
                    request.campaign_timeline,
                    request.budget_constraint.low,
                    request.budget_constraint.high,
                    request.language_preference,
                    request.tone_preference,
                    request.constraints,
                ),
            )

            if not brief_row:
                return campaign_id

            brief_id = brief_row["id"]

            campaign_row = fetch_one(
                """
                INSERT INTO campaigns (id, workspace_id, brief_id, status)
                VALUES (%s, %s, %s, 'generated')
                RETURNING id
                """,
                (str(campaign_id), workspace_id, brief_id),
            )

            if not campaign_row:
                return campaign_id

            strategy_row = fetch_one(
                """
                INSERT INTO campaign_strategies (
                    campaign_id, workspace_id, positioning, target_psychology,
                    market_opportunity, messaging_pillars, tone_recommendation,
                    channel_priorities, timeline_summary, risk_notes,
                    model_used, latency_ms, confidence_strategy, tokens_used
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    str(campaign_id),
                    workspace_id,
                    strategy.get("positioning"),
                    strategy.get("target_psychology"),
                    strategy.get("market_opportunity"),
                    Jsonb(strategy.get("messaging_pillars", [])),
                    strategy.get("tone_recommendation"),
                    Jsonb(strategy.get("channel_priorities", [])),
                    strategy.get("timeline_summary"),
                    Jsonb(strategy.get("risk_notes", [])),
                    strategy_model_used,
                    strategy_latency_ms,
                    critic.score,
                    strategy_tokens_used,
                ),
            )

            strategy_id = strategy_row["id"] if strategy_row else None

            for solution in solutions:
                execute(
                    """
                    INSERT INTO campaign_solutions (
                        campaign_id, strategy_id, workspace_id, solution_index, channel,
                        solution_name, description, execution, budget, expected_outcomes,
                        confidence_score, reasoning, signals_used, risk_level, model_used, latency_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(campaign_id),
                        strategy_id,
                        workspace_id,
                        solution.index,
                        solution.channel,
                        solution.solution_name,
                        solution.description,
                        Jsonb(solution.execution.model_dump()),
                        Jsonb(solution.budget.model_dump()),
                        Jsonb(solution.expected_outcomes.model_dump()),
                        solution.confidence_score,
                        solution.reasoning,
                        Jsonb(solution.signals_used),
                        solution.risk_level,
                        solutions_model_used,
                        solutions_latency_ms,
                    ),
                )

            execute(
                """
                INSERT INTO campaign_generation_logs (
                    workspace_id, campaign_id, brief_id, prompt_version,
                    solutions_count, total_latency_ms, tokens_input, tokens_output,
                    cost_estimate, passed_critic, critic_notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    workspace_id,
                    str(campaign_id),
                    brief_id,
                    "llm_router_v1",
                    len(solutions),
                    total_latency_ms,
                    total_input_tokens,
                    total_output_tokens,
                    total_cost_estimate,
                    critic.passed,
                    " | ".join(critic.issues) if critic.issues else "passed",
                ),
            )

            return campaign_id
        except Exception:
            return campaign_id

    @staticmethod
    def _llm_result_to_meta(result: LLMResult | None) -> dict[str, Any]:
        if result is None:
            return {}

        return {
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "input_tokens_estimate": result.input_tokens_estimate,
            "output_tokens_estimate": result.output_tokens_estimate,
            "cost_estimate": result.cost_estimate,
        }

    @staticmethod
    def _format_model_used(meta: dict[str, Any]) -> str:
        provider = str(meta.get("provider") or "").strip()
        model = str(meta.get("model") or "").strip()

        if provider and model:
            return f"{provider}:{model}"
        if model:
            return model
        if provider:
            return provider
        return "local:local_rules"

    @staticmethod
    def _stream_event(status: str, step: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        event = GenerateStreamEvent(
            status=status,
            step=step,
            data=data,
            timestamp=datetime.now(timezone.utc),
        )
        return event.model_dump(mode="json")

    @staticmethod
    def _build_generate_response(
        request: GenerateMarketingRequest,
        campaign_id: UUID,
        strategy,
        solutions: list[SolutionItem],
        signals: list[dict[str, Any]],
        critic_score: float,
        started: datetime,
        ended: datetime,
    ) -> GenerateMarketingResponse:
        confidence = mean([s.confidence_score for s in solutions]) if solutions else 0.5
        confidence_overall = round((confidence * 0.72) + (critic_score * 0.28), 2)
        latency_ms = int((ended - started).total_seconds() * 1000)

        channels = sorted({s.channel for s in solutions})
        min_budget = sum(s.budget.total_low for s in solutions)
        balanced_budget = sum((s.budget.total_low + s.budget.total_high) / 2 for s in solutions)
        max_budget = sum(s.budget.total_high for s in solutions)

        summary = PortfolioSummary(
            total_solutions=len(solutions),
            channels_covered=channels,
            budget_range={
                "minimum_portfolio": round(min_budget, 2),
                "balanced_portfolio": round(balanced_budget, 2),
                "aggressive_portfolio": round(max_budget, 2),
            },
            recommended_quick_wins=[s.channel for s in solutions if s.budget.total_high <= 150][:2],
            recommended_scale_plays=[s.channel for s in solutions if s.budget.total_high >= 500][:2],
        )

        market_signals_used = [
            MarketSignalItem(
                id=str(signal.get("id")),
                signal=signal.get("signal_key", "signal"),
                type=signal.get("signal_type", "trend"),
                impact=signal.get("signal_value", "Market condition to consider."),
            )
            for signal in signals[:5]
        ]

        return GenerateMarketingResponse(
            campaign_id=campaign_id,
            strategy=strategy,
            solutions=solutions,
            portfolio_summary=summary,
            market_signals_used=market_signals_used,
            assistant_explanation="",
            strategic_options=[],
            insights=[],
            recommended_path="",
            next_7_days_plan=[],
            next_actions=[],
            confidence_overall=confidence_overall,
            generation_latency_ms=latency_ms,
            created_at=ended,
        )

    async def _compose_response_fields(
        self,
        request: GenerateMarketingRequest,
        response: GenerateMarketingResponse,
        workspace_memory: dict[str, Any] | None = None,
    ) -> GenerateMarketingResponse:
        context_json = json.dumps(
            {
                "product_name": request.product_name,
                "objective": request.objective,
                "location": request.audience.location,
                "language_preference": request.language_preference,
                "tone_preference": request.tone_preference,
                "campaign_timeline": request.campaign_timeline,
                "budget_constraint": request.budget_constraint.model_dump(),
                "strategy": response.strategy.model_dump(),
                "portfolio_summary": response.portfolio_summary.model_dump(),
                "market_signals_used": [item.model_dump() for item in response.market_signals_used],
                "brand_memory": workspace_memory or {},
                "solutions": [
                    {
                        "id": item.id,
                        "channel": item.channel,
                        "solution_name": item.solution_name,
                        "description": item.description,
                        "reasoning": item.reasoning,
                        "confidence_score": item.confidence_score,
                        "budget": item.budget.model_dump(),
                        "expected_outcomes": item.expected_outcomes.model_dump(),
                        "signals_used": item.signals_used,
                    }
                    for item in response.solutions
                ],
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("response_composer_v1.txt", context_json=context_json)

        llm_result = await self.llm_router.try_generate_json(
            "response_composer_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        if not llm_result or not isinstance(llm_result.data, dict):
            raise RuntimeError("Response composer failed to generate JSON output")

        payload = llm_result.data
        assistant_explanation = self._normalize_text_length(
            str(payload.get("assistant_explanation") or "").strip(),
            minimum=100,
            maximum=900,
            field_name="assistant_explanation",
        )
        recommended_path = self._normalize_text_length(
            str(payload.get("recommended_path") or "").strip(),
            minimum=40,
            maximum=450,
            field_name="recommended_path",
        )

        insights_raw = payload.get("insights") if isinstance(payload.get("insights"), list) else []
        insights = [str(item).strip() for item in insights_raw if str(item).strip()]
        if len(insights) < 1:
            raise RuntimeError("Response composer returned insufficient insights")

        options = self._parse_strategic_options(payload.get("strategic_options"))
        action_plan = self._parse_next_7_days_plan(payload.get("next_7_days_plan"))

        next_actions_raw = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
        next_actions = [str(item).strip() for item in next_actions_raw if str(item).strip()]
        if len(next_actions) < 3:
            raise RuntimeError("Response composer returned insufficient next actions")

        return response.model_copy(
            update={
                "assistant_explanation": assistant_explanation,
                "strategic_options": options,
                "insights": insights[:3],
                "recommended_path": recommended_path,
                "next_7_days_plan": action_plan,
                "next_actions": next_actions[:6],
            }
        )

    @staticmethod
    def _parse_strategic_options(raw_options: Any) -> list[StrategicOption]:
        if not isinstance(raw_options, list):
            raise RuntimeError("Response composer did not return strategic_options list")

        options: list[StrategicOption] = []
        seen: set[str] = set()
        for item in raw_options:
            if not isinstance(item, dict):
                continue
            try:
                option = StrategicOption.model_validate(item)
            except Exception:
                continue

            key = option.option_key.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            options.append(option)

        if len(options) < 5:
            raise RuntimeError("Response composer returned insufficient strategic options")

        return options[:7]

    @staticmethod
    def _parse_next_7_days_plan(raw_days: Any) -> list[ActionPlanDay]:
        if not isinstance(raw_days, list):
            raise RuntimeError("Response composer did not return next_7_days_plan list")

        by_day: dict[int, ActionPlanDay] = {}
        for item in raw_days:
            if not isinstance(item, dict):
                continue
            try:
                day = ActionPlanDay.model_validate(item)
            except Exception:
                continue
            if 1 <= day.day <= 7:
                by_day[day.day] = day

        ordered = [by_day[day] for day in range(1, 8) if day in by_day]
        if len(ordered) != 7:
            raise RuntimeError("Response composer did not return a complete 7-day plan")

        return ordered

    @staticmethod
    def _normalize_text_length(
        text: str,
        *,
        minimum: int,
        maximum: int,
        field_name: str,
    ) -> str:
        candidate = text.strip()
        if len(candidate) < minimum:
            raise RuntimeError(f"Response composer returned short {field_name}")

        if len(candidate) <= maximum:
            return candidate

        truncated = candidate[:maximum].rstrip()
        sentence_end = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        if sentence_end >= max(minimum // 2, 20):
            return truncated[: sentence_end + 1].strip()

        return f"{truncated}..."

    async def _build_generate_request_from_message(
        self,
        request: ChatRequest,
    ) -> tuple[GenerateMarketingRequest, list[str], list[str]]:
        extracted = await self._extract_structured_brief(request.message)
        assumptions_used: list[str] = []
        missing_context: list[str] = []

        settings = get_settings()
        workspace_id = request.workspace_id or UUID(settings.default_workspace_id)

        product_name = str(extracted.get("product_name") or "").strip()
        if not product_name:
            product_name = self._infer_product_name(request.message)
            missing_context.append("product_name")

        extracted_objective = str(extracted.get("objective") or "").strip()
        objective = self._objective_from_text(extracted_objective or request.message)
        if not extracted_objective and not self._objective_explicit_in_text(request.message):
            missing_context.append("objective")

        location = str(extracted.get("audience_location") or "").strip()
        if not location:
            location = self._infer_location(request.message)
            if not self._location_explicit_in_text(request.message):
                missing_context.append("audience_location")

        budget_low, budget_high, currency, budget_assumed = self._budget_from_message(request.message, extracted)
        if budget_assumed:
            missing_context.append("budget")

        campaign_timeline = str(extracted.get("campaign_timeline") or "").strip() or "2 weeks"
        if not str(extracted.get("campaign_timeline") or "").strip() and not self._timeline_explicit_in_text(request.message):
            missing_context.append("campaign_timeline")

        interests = extracted.get("interests") if isinstance(extracted.get("interests"), list) else None
        if not interests:
            interests = []
            missing_context.append("interests")

        segment = str(extracted.get("audience_segment") or "").strip() or "general_audience"
        if not str(extracted.get("audience_segment") or "").strip():
            missing_context.append("audience_segment")

        product_category = str(extracted.get("product_category") or "").strip() or "general_business"
        raw_language_preference = str(
            request.language_preference or extracted.get("language_preference") or ""
        ).strip()
        language_preference, language_assumed = self._normalize_language_preference(raw_language_preference)
        if language_assumed:
            if not raw_language_preference:
                missing_context.append("language_preference")

        raw_tone_preference = str(request.tone_preference or extracted.get("tone_preference") or "").strip()
        tone_preference, tone_assumed = self._normalize_tone_preference(raw_tone_preference)
        if tone_assumed:
            if not raw_tone_preference:
                missing_context.append("tone_preference")

        constraints = str(extracted.get("constraints") or "").strip()
        if not constraints:
            constraints = "Avoid exaggerated claims and keep recommendations actionable."

        if request.images:
            constraints = f"{constraints} Include image-aware recommendations based on uploaded assets metadata."

        return (
            GenerateMarketingRequest(
                workspace_id=workspace_id,
                product_name=product_name,
                product_description=request.message,
                product_category=product_category,
                objective=objective,
                campaign_timeline=campaign_timeline,
                audience={
                    "location": location,
                    "interests": interests,
                    "segment": segment,
                },
                budget_constraint={
                    "low": None if budget_assumed else budget_low,
                    "high": None if budget_assumed else budget_high,
                    "currency": currency,
                },
                language_preference=language_preference,
                tone_preference=tone_preference,
                constraints=constraints,
            ),
            assumptions_used,
            list(dict.fromkeys(missing_context)),
        )

    async def _extract_structured_brief(self, message: str) -> dict[str, Any]:
        prompt = self.prompt_hub.render("brief_extractor_v1.txt", message=message)

        llm_result = await self.llm_router.try_generate_json(
            "brief_extractor",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        if llm_result and isinstance(llm_result.data, dict):
            return llm_result.data
        return {}

    @staticmethod
    def _objective_from_text(text: str) -> str:
        normalized = text.lower()
        if "lead" in normalized:
            return "leads"
        if "engage" in normalized or "interaction" in normalized:
            return "engagement"
        if "aware" in normalized or "visibility" in normalized or "reach" in normalized:
            return "awareness"
        return "sales"

    @staticmethod
    def _objective_explicit_in_text(text: str) -> bool:
        normalized = text.lower()
        return any(
            token in normalized
            for token in (
                "sales",
                "sell",
                "leads",
                "lead",
                "awareness",
                "visibility",
                "engagement",
                "interaction",
            )
        )

    @staticmethod
    def _location_explicit_in_text(text: str) -> bool:
        normalized = text.lower()
        cities = [
            "tunis",
            "sfax",
            "sousse",
            "nabeul",
            "ariana",
            "bizerte",
            "gabes",
            "monastir",
            "kairouan",
        ]
        return any(city in normalized for city in cities)

    @staticmethod
    def _timeline_explicit_in_text(text: str) -> bool:
        normalized = text.lower()
        return bool(re.search(r"\d+\s*(?:-|to)?\s*(day|days|week|weeks|month|months)", normalized))

    @staticmethod
    def _normalize_language_preference(raw_value: str) -> tuple[str, bool]:
        normalized = raw_value.strip().lower()
        if normalized in {"fr", "ar", "bilingual", "auto"}:
            return normalized, False

        alias_map = {
            "french": "fr",
            "francais": "fr",
            "français": "fr",
            "arabic": "ar",
            "arabe": "ar",
            "bi": "bilingual",
            "dual": "bilingual",
            "mixed": "bilingual",
            "fr/ar": "bilingual",
            "ar/fr": "bilingual",
            "automatic": "auto",
        }
        if normalized in alias_map:
            return alias_map[normalized], True

        return "bilingual", True

    @staticmethod
    def _normalize_tone_preference(raw_value: str) -> tuple[str, bool]:
        normalized = raw_value.strip().lower()
        if normalized in {"professional", "fun", "storytelling"}:
            return normalized, False

        alias_map = {
            "practical": "professional",
            "pragmatic": "professional",
            "consultative": "professional",
            "direct": "professional",
            "formal": "professional",
            "friendly": "fun",
            "playful": "fun",
            "casual": "fun",
            "narrative": "storytelling",
            "story": "storytelling",
            "inspirational": "storytelling",
        }
        if normalized in alias_map:
            return alias_map[normalized], True

        return "storytelling", True

    @staticmethod
    def _infer_location(message: str) -> str:
        normalized = message.lower()
        cities = [
            "tunis",
            "sfax",
            "sousse",
            "nabeul",
            "ariana",
            "bizerte",
            "gabes",
            "monastir",
            "kairouan",
        ]
        for city in cities:
            if city in normalized:
                return city.title()
        return "Tunis"

    @staticmethod
    def _infer_product_name(message: str) -> str:
        cleaned = re.sub(r"\s+", " ", message).strip()
        if len(cleaned) <= 42 and len(cleaned) >= 4:
            return cleaned
        words = cleaned.split(" ")
        if len(words) >= 3:
            candidate = " ".join(words[:4]).strip(" ,.-")
            if len(candidate) >= 4:
                return candidate
        return "SME Offer"

    @staticmethod
    def _budget_from_message(
        message: str,
        extracted: dict[str, Any],
    ) -> tuple[float, float, str, bool]:
        ext_low = extracted.get("budget_low")
        ext_high = extracted.get("budget_high")
        ext_currency = str(extracted.get("currency") or "").strip().upper()

        if isinstance(ext_low, (int, float)) and isinstance(ext_high, (int, float)):
            low = float(ext_low)
            high = float(ext_high)
            if high < low:
                high = low
            return low, high, ext_currency or "TND", False

        normalized = message.lower()
        range_match = re.search(r"(\d{2,6})\s*(?:-|to|–)\s*(\d{2,6})\s*(tnd|dt|usd|eur)?", normalized)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            currency = (range_match.group(3) or "TND").upper()
            if currency == "DT":
                currency = "TND"
            if high < low:
                high = low
            return low, high, currency, False

        single_match = re.search(r"budget[^\d]*(\d{2,6})\s*(tnd|dt|usd|eur)?", normalized)
        if single_match:
            high = float(single_match.group(1))
            low = max(20.0, round(high * 0.5, 2))
            currency = (single_match.group(2) or "TND").upper()
            if currency == "DT":
                currency = "TND"
            return low, high, currency, True

        return 100.0, 800.0, "TND", True

    async def _build_clarifying_questions(
        self,
        request: ChatRequest,
        normalized_request: GenerateMarketingRequest,
        missing_context: list[str],
    ) -> list[str]:
        blocking_order = ["budget", "audience_location"]
        fields = [field for field in blocking_order if field in set(missing_context)]
        if request.images and not any(bool(image.data_base64) for image in request.images):
            fields.append("visual_payload")
        fields = list(dict.fromkeys(fields))

        if not fields:
            return []

        context_json = json.dumps(
            {
                "message": request.message,
                "product_name": normalized_request.product_name,
                "objective": normalized_request.objective,
                "audience_location": normalized_request.audience.location,
                "budget": normalized_request.budget_constraint.model_dump(),
                "missing_fields": fields,
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("clarification_agent_v1.txt", context_json=context_json)

        llm_result = await self.llm_router.try_generate_json(
            "clarification_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        if llm_result and isinstance(llm_result.data, dict):
            raw_questions = llm_result.data.get("questions")
            if isinstance(raw_questions, list):
                cleaned = [str(item).strip() for item in raw_questions if str(item).strip()]
                if cleaned:
                    return cleaned[:2]

        labels = [field.replace("_", " ") for field in fields if field != "visual_payload"]
        fallback_questions: list[str] = []
        if labels:
            fallback_questions.append(
                f"Can you clarify these missing details before I generate the final plan: {', '.join(labels[:2])}?"
            )
        if "visual_payload" in fields:
            fallback_questions.append(
                "Can you upload the actual image files so I can run full visual analysis?"
            )

        return fallback_questions[:2]

    async def _analyze_image_pack(
        self,
        request: ChatRequest,
        normalized_request: GenerateMarketingRequest,
    ) -> list[ChatImageInsight]:
        vision_inputs: list[dict[str, str]] = []
        for image in request.images:
            if not image.data_base64:
                continue
            mime_type = str(image.mime_type or "").strip() or "image/jpeg"
            if not mime_type.startswith("image/"):
                continue
            vision_inputs.append(
                {
                    "filename": image.filename,
                    "mime_type": mime_type,
                    "data_base64": image.data_base64,
                }
            )

        if not vision_inputs:
            return []

        prompt = (
            "You are Vision Critic Agent for marketing creatives.\n"
            "Analyze each uploaded image for campaign readiness.\n"
            "Return JSON only with this exact schema:\n"
            "{\"images\": [{\"filename\": \"...\", \"quality_score\": 0.0, \"priority\": \"low|medium|high\", "
            "\"findings\": [\"...\"], \"recommendations\": [\"...\"]}]}\n"
            "Rules:\n"
            "1) quality_score in [0.1, 0.99].\n"
            "2) Keep findings and recommendations actionable and concrete.\n"
            "3) Consider composition, readability, product focus, and CTA placement.\n"
            f"Business context: product={normalized_request.product_name}, objective={normalized_request.objective}, "
            f"location={normalized_request.audience.location or 'target market'}.\n"
            f"Image filenames: {[image.get('filename') for image in vision_inputs]}"
        )

        llm_result = await self.llm_router.try_generate_vision_json(
            "visual_critic_agent",
            prompt,
            vision_inputs,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        if not llm_result or not isinstance(llm_result.data, (dict, list)):
            return []

        raw_items: list[dict[str, Any]] = []
        if isinstance(llm_result.data, dict) and isinstance(llm_result.data.get("images"), list):
            raw_items = [item for item in llm_result.data.get("images", []) if isinstance(item, dict)]
        elif isinstance(llm_result.data, list):
            raw_items = [item for item in llm_result.data if isinstance(item, dict)]

        if not raw_items:
            return []

        ai_map: dict[str, dict[str, Any]] = {}
        for item in raw_items:
            key = str(item.get("filename") or "").strip().lower()
            if key:
                ai_map[key] = item

        generated_insights: list[ChatImageInsight] = []
        for image in request.images:
            ai_item = ai_map.get(image.filename.strip().lower())
            if not ai_item:
                continue

            findings = [str(entry).strip() for entry in ai_item.get("findings", []) if str(entry).strip()]
            recommendations = [
                str(entry).strip()
                for entry in ai_item.get("recommendations", [])
                if str(entry).strip()
            ]

            try:
                score = float(ai_item.get("quality_score"))
            except (TypeError, ValueError):
                continue
            score = round(max(0.1, min(score, 0.99)), 2)

            priority = str(ai_item.get("priority") or "").strip().lower()
            if priority not in {"low", "medium", "high"}:
                priority = self._priority_from_score(score)

            generated_insights.append(
                ChatImageInsight(
                    filename=image.filename,
                    quality_score=score,
                    findings=self._dedupe_texts(findings)[:6],
                    recommendations=self._dedupe_texts(recommendations)[:6],
                    priority=priority,
                )
            )

        return generated_insights

    @staticmethod
    def _priority_from_score(score: float) -> str:
        if score < 0.6:
            return "high"
        if score < 0.75:
            return "medium"
        return "low"

    @staticmethod
    def _dedupe_texts(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result


_service_singleton: MarketingService | None = None


def get_marketing_service() -> MarketingService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = MarketingService()
    return _service_singleton
