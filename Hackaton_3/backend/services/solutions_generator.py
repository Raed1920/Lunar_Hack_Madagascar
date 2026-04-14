import json
from typing import Any

from ..models.marketing import StrategyPlan
from ..models.schemas import (
    GenerateMarketingRequest,
    SolutionBudget,
    SolutionExecution,
    SolutionItem,
    SolutionOutcomes,
)
from .budget_estimator import BudgetEstimator
from .llm_router import LLMResult, LLMRouter
from .prompt_hub import PromptHub


class SolutionsGenerator:
    def __init__(
        self,
        budget_estimator: BudgetEstimator,
        llm_router: LLMRouter,
        prompt_hub: PromptHub | None = None,
    ):
        self.budget_estimator = budget_estimator
        self.llm_router = llm_router
        self.prompt_hub = prompt_hub or PromptHub()
        self.last_llm_result: LLMResult | None = None

    @staticmethod
    def _normalize_channel(channel: str) -> str:
        normalized = channel.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "social": "social_media",
            "instagram": "social_media",
            "facebook": "social_media",
            "tiktok": "social_media",
            "mail": "email",
            "ads": "paid_ads",
            "paid": "paid_ads",
            "search": "seo",
            "events_marketing": "events",
            "community_events": "events",
            "partnership": "partnerships",
            "creator_partnerships": "partnerships",
            "organic_content": "content",
        }
        return aliases.get(normalized, normalized or "social_media")

    @staticmethod
    def _extract_list_payload(payload: dict[str, Any] | list[Any] | None) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("solutions", "items", "portfolio", "allocations"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    def _parse_solution_blueprints(
        self,
        raw_items: list[Any],
        signal_keys: list[str],
    ) -> list[dict[str, Any]]:
        blueprints: list[dict[str, Any]] = []
        for item in raw_items[:9]:
            if not isinstance(item, dict):
                continue

            channel = self._normalize_channel(str(item.get("channel") or ""))
            solution_name = str(item.get("solution_name") or item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            reasoning = str(item.get("reasoning") or "").strip()

            if not channel or not solution_name or not description or not reasoning:
                continue

            raw_signals = item.get("signals_used")
            signals_used = [
                str(signal).strip()
                for signal in raw_signals
                if str(signal).strip()
            ] if isinstance(raw_signals, list) else signal_keys

            try:
                confidence_score = self._parse_confidence(item.get("confidence_score"))
            except Exception:
                continue

            blueprints.append(
                {
                    "channel": channel,
                    "solution_name": solution_name,
                    "description": description,
                    "reasoning": reasoning,
                    "confidence_score": confidence_score,
                    "signals_used": signals_used or signal_keys,
                }
            )

        deduped: list[dict[str, Any]] = []
        seen_channels: set[str] = set()
        for item in blueprints:
            channel = item["channel"]
            if channel in seen_channels:
                continue
            seen_channels.add(channel)
            deduped.append(item)

        return deduped

    @staticmethod
    def _parse_confidence(value: Any) -> float:
        parsed = float(value)
        return round(max(0.55, min(parsed, 0.95)), 2)

    @staticmethod
    def _risk_from_budget_and_confidence(high_budget: float, confidence: float) -> str:
        if confidence < 0.62:
            return "high"
        if high_budget >= 800:
            return "high"
        if high_budget >= 350:
            return "medium"
        return "low"

    async def _build_solution_blueprints(
        self,
        request: GenerateMarketingRequest,
        strategy: StrategyPlan,
        signal_keys: list[str],
        selected_channels: list[str],
        workspace_memory: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], LLMResult | None]:
        context_json = json.dumps(
            {
                "product_name": request.product_name,
                "objective": request.objective,
                "location": request.audience.location,
                "language_preference": request.language_preference,
                "tone_preference": request.tone_preference or strategy.tone_recommendation,
                "constraints": request.constraints,
                "channel_priorities": selected_channels,
                "signal_keys": signal_keys,
                "brand_memory": workspace_memory or {},
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("solutions_v1.txt", context_json=context_json)
        llm_result = await self.llm_router.try_generate_json(
            "solutions_architect_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        raw_items = self._extract_list_payload(llm_result.data if llm_result else None)
        deduped = self._parse_solution_blueprints(raw_items, signal_keys)
        if len(deduped) >= 5:
            return deduped[:7], llm_result

        local_result = await self.llm_router.try_generate_json(
            "solutions_architect_agent",
            prompt,
            provider_order=["local"],
            allow_local_fallback=True,
            respect_test_local=False,
        )
        local_items = self._extract_list_payload(local_result.data if local_result else None)
        local_blueprints = self._parse_solution_blueprints(local_items, signal_keys)
        if len(local_blueprints) < 5:
            raise RuntimeError("Solutions architect did not generate enough valid channel plans")

        return local_blueprints[:7], local_result

    async def _allocate_budgets(
        self,
        request: GenerateMarketingRequest,
        blueprints: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        context_json = json.dumps(
            {
                "objective": request.objective,
                "campaign_timeline": request.campaign_timeline,
                "budget_constraint": request.budget_constraint.model_dump(),
                "channels": [
                    {"channel": item["channel"], "solution_name": item.get("solution_name")}
                    for item in blueprints
                ],
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("budget_allocator_v1.txt", context_json=context_json)
        llm_result = await self.llm_router.try_generate_json(
            "budget_allocator_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )

        allocations_map: dict[str, dict[str, Any]] = {}
        raw_allocations = self._extract_list_payload(llm_result.data if llm_result else None)
        for item in raw_allocations:
            if not isinstance(item, dict):
                continue

            channel = self._normalize_channel(str(item.get("channel") or ""))
            if not channel:
                continue

            try:
                total_low = float(item.get("total_low"))
                total_high = float(item.get("total_high"))
            except (TypeError, ValueError):
                continue

            if total_high < total_low:
                total_high = total_low

            breakdown_raw = item.get("breakdown") if isinstance(item.get("breakdown"), dict) else {}
            required_keys = {"content_creation", "ad_spend", "management", "tools"}
            if not required_keys.issubset(set(breakdown_raw.keys())):
                continue

            breakdown = {
                "content_creation": round(float(breakdown_raw.get("content_creation") or 0.0), 2),
                "ad_spend": round(float(breakdown_raw.get("ad_spend") or 0.0), 2),
                "management": round(float(breakdown_raw.get("management") or 0.0), 2),
                "tools": round(float(breakdown_raw.get("tools") or 0.0), 2),
            }
            currency = str(item.get("currency") or request.budget_constraint.currency or "TND")

            allocations_map[channel] = {
                "total_low": round(total_low, 2),
                "total_high": round(total_high, 2),
                "currency": currency,
                "breakdown": breakdown,
            }

        if any(blueprint["channel"] not in allocations_map for blueprint in blueprints):
            local_result = await self.llm_router.try_generate_json(
                "budget_allocator_agent",
                prompt,
                provider_order=["local"],
                allow_local_fallback=True,
                respect_test_local=False,
            )
            allocations_map = {}
            local_allocations = self._extract_list_payload(local_result.data if local_result else None)
            for item in local_allocations:
                if not isinstance(item, dict):
                    continue
                channel = self._normalize_channel(str(item.get("channel") or ""))
                if not channel:
                    continue
                try:
                    total_low = float(item.get("total_low"))
                    total_high = float(item.get("total_high"))
                except (TypeError, ValueError):
                    continue
                if total_high < total_low:
                    total_high = total_low

                breakdown_raw = item.get("breakdown") if isinstance(item.get("breakdown"), dict) else {}
                required_keys = {"content_creation", "ad_spend", "management", "tools"}
                if not required_keys.issubset(set(breakdown_raw.keys())):
                    continue

                allocations_map[channel] = {
                    "total_low": round(total_low, 2),
                    "total_high": round(total_high, 2),
                    "currency": str(item.get("currency") or request.budget_constraint.currency or "TND"),
                    "breakdown": {
                        "content_creation": round(float(breakdown_raw.get("content_creation") or 0.0), 2),
                        "ad_spend": round(float(breakdown_raw.get("ad_spend") or 0.0), 2),
                        "management": round(float(breakdown_raw.get("management") or 0.0), 2),
                        "tools": round(float(breakdown_raw.get("tools") or 0.0), 2),
                    },
                }

            for blueprint in blueprints:
                if blueprint["channel"] not in allocations_map:
                    raise RuntimeError("Budget allocator did not return a valid allocation for every solution")

        high_budgets = [float(alloc["total_high"]) for alloc in allocations_map.values()]
        if allocations_map and not any(value <= 180.0 for value in high_budgets):
            quick_channel = min(
                allocations_map.keys(),
                key=lambda channel_key: float(allocations_map[channel_key]["total_high"]),
            )
            quick_alloc = allocations_map[quick_channel]
            quick_alloc["total_high"] = round(min(180.0, float(quick_alloc["total_high"])), 2)
            quick_alloc["total_low"] = round(min(float(quick_alloc["total_low"]), quick_alloc["total_high"]), 2)

        budget_ceiling = float(request.budget_constraint.high or 0.0)
        high_budgets = [float(alloc["total_high"]) for alloc in allocations_map.values()]
        if budget_ceiling >= 500.0 and allocations_map and not any(value >= 500.0 for value in high_budgets):
            scale_channel = max(
                allocations_map.keys(),
                key=lambda channel_key: float(allocations_map[channel_key]["total_high"]),
            )
            scale_alloc = allocations_map[scale_channel]
            scale_alloc["total_high"] = round(max(500.0, float(scale_alloc["total_high"])), 2)
            scale_alloc["total_low"] = round(
                min(float(scale_alloc["total_low"]), scale_alloc["total_high"] * 0.7),
                2,
            )

        return allocations_map

    async def _build_execution_bundle(
        self,
        request: GenerateMarketingRequest,
        strategy: StrategyPlan,
        blueprint: dict[str, Any],
        budget_data: dict[str, Any],
    ) -> tuple[SolutionExecution, SolutionOutcomes]:
        context_json = json.dumps(
            {
                "product_name": request.product_name,
                "product_category": request.product_category,
                "objective": request.objective,
                "location": request.audience.location,
                "language_preference": request.language_preference,
                "tone_preference": request.tone_preference or strategy.tone_recommendation,
                "campaign_timeline": request.campaign_timeline,
                "constraints": request.constraints,
                "channel": blueprint.get("channel"),
                "solution_name": blueprint.get("solution_name"),
                "description": blueprint.get("description"),
                "reasoning": blueprint.get("reasoning"),
                "budget": budget_data,
            },
            ensure_ascii=True,
        )
        prompt = self.prompt_hub.render("execution_agent_v1.txt", context_json=context_json)
        llm_result = await self.llm_router.try_generate_json(
            "execution_agent",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )

        if llm_result and isinstance(llm_result.data, dict):
            try:
                execution_raw, outcomes_raw = self._normalize_execution_payload(llm_result.data)
                execution = SolutionExecution.model_validate(execution_raw)
                outcomes = SolutionOutcomes.model_validate(outcomes_raw)
                return execution, outcomes
            except Exception:
                pass

        local_result = await self.llm_router.try_generate_json(
            "execution_agent",
            prompt,
            provider_order=["local"],
            allow_local_fallback=True,
            respect_test_local=False,
        )
        if local_result and isinstance(local_result.data, dict):
            try:
                execution_raw, outcomes_raw = self._normalize_execution_payload(local_result.data)
                execution = SolutionExecution.model_validate(execution_raw)
                outcomes = SolutionOutcomes.model_validate(outcomes_raw)
                return execution, outcomes
            except Exception as exc:
                raise RuntimeError("Execution agent produced invalid schema") from exc

        raise RuntimeError("Execution agent failed to generate JSON output")

    @staticmethod
    def _normalize_execution_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        execution_candidate = payload.get("execution") if isinstance(payload.get("execution"), dict) else payload
        outcomes_candidate = (
            payload.get("expected_outcomes")
            if isinstance(payload.get("expected_outcomes"), dict)
            else {
                "reach": payload.get("reach"),
                "engagement_rate": payload.get("engagement_rate"),
                "conversion_assumption": payload.get("conversion_assumption"),
                "roi_estimate": payload.get("roi_estimate"),
            }
        )

        execution = dict(execution_candidate)
        outcomes = dict(outcomes_candidate)

        for key in (
            "content_format",
            "message",
            "timeline",
            "frequency",
            "image_prompt",
            "exact_copy",
            "text_overlay",
            "cta_text",
        ):
            if key in execution and execution.get(key) is not None:
                execution[key] = str(execution.get(key)).strip()

        for key in ("assets_needed", "hashtags", "production_steps"):
            value = execution.get(key)
            if isinstance(value, str):
                execution[key] = [
                    part.strip(" -")
                    for part in value.replace("\n", ",").split(",")
                    if part.strip(" -")
                ]

        posting_windows = execution.get("posting_windows")
        if isinstance(posting_windows, dict):
            execution["posting_windows"] = [posting_windows]

        for key in ("reach", "engagement_rate", "conversion_assumption", "roi_estimate"):
            if outcomes.get(key) is not None:
                outcomes[key] = str(outcomes.get(key)).strip()

        return execution, outcomes

    async def generate(
        self,
        request: GenerateMarketingRequest,
        strategy: StrategyPlan,
        signals: list[dict],
        workspace_memory: dict[str, Any] | None = None,
    ) -> list[SolutionItem]:
        signal_keys = [str(signal.get("signal_key") or "signal").strip() for signal in signals[:5]]
        signal_keys = [key for key in signal_keys if key] or ["market_signal"]

        selected_channels = [
            self._normalize_channel(str(channel))
            for channel in strategy.channel_priorities
            if str(channel).strip()
        ]
        selected_channels = list(dict.fromkeys(selected_channels))[:8]
        if len(selected_channels) < 3:
            raise RuntimeError("Strategy plan did not provide enough channel priorities")

        blueprints, architect_result = await self._build_solution_blueprints(
            request,
            strategy,
            signal_keys,
            selected_channels,
            workspace_memory,
        )
        self.last_llm_result = architect_result

        allocations_map = await self._allocate_budgets(request, blueprints)

        solutions: list[SolutionItem] = []
        for idx, blueprint in enumerate(blueprints):
            channel = self._normalize_channel(str(blueprint.get("channel") or ""))
            if not channel:
                raise RuntimeError("Solutions architect returned an invalid channel")

            budget_data = allocations_map.get(channel)
            if not budget_data:
                raise RuntimeError("Missing budget allocation for generated solution")

            execution, outcomes = await self._build_execution_bundle(request, strategy, blueprint, budget_data)
            budget = SolutionBudget(**budget_data)

            confidence = self._parse_confidence(blueprint.get("confidence_score"))
            risk_level = self._risk_from_budget_and_confidence(float(budget.total_high), confidence)

            raw_signals = blueprint.get("signals_used")
            signals_used = [
                str(item).strip()
                for item in raw_signals
                if str(item).strip()
            ] if isinstance(raw_signals, list) else signal_keys

            if not signals_used:
                signals_used = signal_keys

            solutions.append(
                SolutionItem(
                    id=f"sol_{idx + 1:03d}",
                    index=idx,
                    channel=channel,
                    solution_name=str(blueprint.get("solution_name") or "").strip(),
                    description=str(blueprint.get("description") or "").strip(),
                    execution=execution,
                    budget=budget,
                    expected_outcomes=outcomes,
                    confidence_score=confidence,
                    reasoning=str(blueprint.get("reasoning") or "").strip(),
                    signals_used=signals_used[:5],
                    risk_level=risk_level,
                )
            )

        if len(solutions) < 5:
            raise RuntimeError("Generated portfolio did not meet minimum solution count")

        return solutions
