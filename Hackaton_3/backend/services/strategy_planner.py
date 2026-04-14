import json
from typing import Any

from ..models.marketing import StrategyPlan
from ..models.schemas import GenerateMarketingRequest
from .llm_router import LLMResult, LLMRouter
from .prompt_hub import PromptHub


class StrategyPlanner:
    def __init__(self, llm_router: LLMRouter, prompt_hub: PromptHub | None = None):
        self.llm_router = llm_router
        self.prompt_hub = prompt_hub or PromptHub()
        self.last_llm_result: LLMResult | None = None

    async def plan(
        self,
        request: GenerateMarketingRequest,
        signals: list[dict],
        workspace_memory: dict[str, Any] | None = None,
    ) -> StrategyPlan:
        signal_keys = [s.get("signal_key", "market_signal") for s in signals[:3]]

        context_json = json.dumps(
            {
                "product_name": request.product_name,
                "product_category": request.product_category,
                "objective": request.objective,
                "campaign_timeline": request.campaign_timeline,
                "audience": request.audience.model_dump(),
                "budget_constraint": request.budget_constraint.model_dump(),
                "language_preference": request.language_preference,
                "tone_preference": request.tone_preference,
                "constraints": request.constraints,
                "signals": signal_keys,
                "brand_memory": workspace_memory or {},
            },
            ensure_ascii=True,
        )

        prompt = self.prompt_hub.render("strategy_v1.txt", context_json=context_json)

        llm_result = await self.llm_router.try_generate_json(
            "strategy_planner",
            prompt,
            provider_order=["groq", "gemini"],
            allow_local_fallback=True,
        )
        self.last_llm_result = llm_result
        if llm_result and isinstance(llm_result.data, dict):
            try:
                normalized = self._normalize_strategy_payload(llm_result.data)
                return StrategyPlan.model_validate(normalized)
            except Exception:
                pass

        local_result = await self.llm_router.try_generate_json(
            "strategy_planner",
            prompt,
            provider_order=["local"],
            allow_local_fallback=True,
            respect_test_local=False,
        )
        if local_result and isinstance(local_result.data, dict):
            try:
                normalized = self._normalize_strategy_payload(local_result.data)
                self.last_llm_result = local_result
                return StrategyPlan.model_validate(normalized)
            except Exception:
                pass

        raise RuntimeError("Strategy planner failed to generate JSON output")

    @staticmethod
    def _normalize_strategy_payload(payload: dict) -> dict:
        normalized = dict(payload)

        for key in (
            "positioning",
            "target_psychology",
            "market_opportunity",
            "tone_recommendation",
            "timeline_summary",
        ):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = value.strip()
                continue
            if isinstance(value, dict):
                normalized[key] = "; ".join(
                    f"{str(inner_key).strip()}: {str(inner_value).strip()}"
                    for inner_key, inner_value in value.items()
                    if str(inner_key).strip() and str(inner_value).strip()
                )
                continue
            if isinstance(value, list):
                normalized[key] = " | ".join(str(item).strip() for item in value if str(item).strip())
                continue
            normalized[key] = str(value or "").strip()

        for key in ("messaging_pillars", "channel_priorities", "risk_notes"):
            value = normalized.get(key)
            if isinstance(value, str):
                split_values = [
                    item.strip(" -")
                    for item in value.replace("\n", ",").split(",")
                    if item.strip(" -")
                ]
                normalized[key] = split_values
            elif isinstance(value, dict):
                normalized[key] = [
                    f"{str(inner_key).strip()}: {str(inner_value).strip()}"
                    for inner_key, inner_value in value.items()
                    if str(inner_key).strip() and str(inner_value).strip()
                ]

        tone_value = str(normalized.get("tone_recommendation") or "").strip().lower()
        if "story" in tone_value or "narrative" in tone_value:
            normalized["tone_recommendation"] = "storytelling"
        elif "fun" in tone_value or "play" in tone_value or "friendly" in tone_value:
            normalized["tone_recommendation"] = "fun"
        elif (
            "professional" in tone_value
            or "formal" in tone_value
            or "consult" in tone_value
            or "direct" in tone_value
        ):
            normalized["tone_recommendation"] = "professional"
        else:
            normalized["tone_recommendation"] = (tone_value or "professional")[:50]

        return normalized
