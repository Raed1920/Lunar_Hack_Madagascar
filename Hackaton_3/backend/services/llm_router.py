import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings, get_settings


@dataclass
class LLMResult:
    provider: str
    model: str
    data: dict[str, Any] | list[Any] | None
    raw_text: str
    latency_ms: int
    retries: int
    input_tokens_estimate: int
    output_tokens_estimate: int
    cost_estimate: float


class LLMRouter:
    _MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
        # Approximate public pricing anchors in USD per 1K tokens.
        "llama-3.1-8b-instant": (0.00005, 0.00008),
        "llama3-8b-8192": (0.00005, 0.00008),
        "llama-3.3-70b-versatile": (0.00059, 0.00079),
        "gemini-1.5-flash": (0.000075, 0.0003),
        "gemini-1.5-flash-latest": (0.000075, 0.0003),
        "gemini-2.0-flash": (0.0001, 0.0004),
    }

    _PROVIDER_DEFAULT_PRICING_PER_1K: dict[str, tuple[float, float]] = {
        "groq": (0.0002, 0.0005),
        "gemini": (0.0001, 0.00035),
    }

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _provider_order(self) -> list[str]:
        # Keep tests deterministic and network-free.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return ["local"]

        providers: list[str] = []
        for provider in (
            self.settings.llm_primary_provider,
            self.settings.llm_fallback_provider,
        ):
            normalized = (provider or "").strip().lower()
            if normalized and normalized not in providers:
                providers.append(normalized)

        if not providers:
            providers = ["groq", "gemini"]
        return providers

    @staticmethod
    def _normalize_provider_order(
        providers: list[str] | None,
        *,
        include_local: bool,
    ) -> list[str]:
        normalized_list: list[str] = []
        for provider in providers or []:
            normalized = (provider or "").strip().lower()
            if not normalized:
                continue
            if normalized == "local" and not include_local:
                continue
            if normalized not in normalized_list:
                normalized_list.append(normalized)

        if include_local and "local" not in normalized_list:
            normalized_list.append("local")
        return normalized_list

    def _vision_provider_order(self) -> list[str]:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return ["local"]

        providers: list[str] = []
        for provider in (
            "gemini",
            self.settings.llm_primary_provider,
            self.settings.llm_fallback_provider,
            "groq",
        ):
            normalized = (provider or "").strip().lower()
            if normalized and normalized not in providers:
                providers.append(normalized)

        if not providers:
            providers = ["gemini", "groq"]
        return providers

    def _provider_ready(self, provider: str) -> bool:
        if provider == "local":
            return True
        if provider == "groq":
            return bool(self.settings.groq_api_key)
        if provider == "gemini":
            return bool(self.settings.gemini_api_key)
        return False

    def _groq_model_candidates(self) -> list[str]:
        candidates: list[str] = []
        for model in (
            self.settings.groq_model,
            "llama-3.1-8b-instant",
            "llama3-8b-8192",
        ):
            normalized = (model or "").strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _gemini_model_candidates(self) -> list[str]:
        candidates: list[str] = []
        for model in (
            self.settings.gemini_model,
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ):
            normalized = (model or "").strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _estimate_cost_usd(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        provider_key = str(provider or "").strip().lower()
        model_key = str(model or "").strip().lower()
        if provider_key == "local":
            return 0.0

        rates = self._MODEL_PRICING_PER_1K.get(model_key)
        if rates is None:
            rates = next(
                (
                    price
                    for candidate, price in self._MODEL_PRICING_PER_1K.items()
                    if candidate in model_key
                ),
                None,
            )

        if rates is None:
            rates = self._PROVIDER_DEFAULT_PRICING_PER_1K.get(provider_key, (0.0001, 0.0003))

        input_rate, output_rate = rates
        estimated = ((max(input_tokens, 0) / 1000.0) * input_rate) + (
            (max(output_tokens, 0) / 1000.0) * output_rate
        )
        return round(max(estimated, 0.0), 6)

    @staticmethod
    def safe_parse_json(raw_text: str) -> dict[str, Any] | list[Any] | None:
        text = raw_text.strip()
        if not text:
            return None

        # Prefer fenced JSON when providers wrap responses in markdown.
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1).strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass

        object_match = re.search(r"\{[\s\S]*\}", text)
        if object_match:
            try:
                parsed = json.loads(object_match.group(0))
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass

        array_match = re.search(r"\[[\s\S]*\]", text)
        if array_match:
            try:
                parsed = json.loads(array_match.group(0))
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _extract_context_json(prompt: str) -> dict[str, Any]:
        lower = prompt.lower()
        markers = (
            "campaign context json:",
            "campaign + channel context json:",
            "solution context json:",
            "conversation context json:",
            "context json:",
        )

        for marker in markers:
            index = lower.rfind(marker)
            if index == -1:
                continue
            snippet = prompt[index + len(marker):].strip()
            parsed = LLMRouter.safe_parse_json(snippet)
            if isinstance(parsed, dict):
                return parsed

        return {}

    @staticmethod
    def _extract_user_message(prompt: str) -> str:
        marker = "user message:"
        lower = prompt.lower()
        index = lower.rfind(marker)
        if index == -1:
            return ""
        return prompt[index + len(marker):].strip()

    @staticmethod
    def _channels_for_objective(objective: str) -> list[str]:
        mapping = {
            "awareness": ["social_media", "content", "events", "paid_ads", "seo"],
            "engagement": ["social_media", "whatsapp", "email", "content", "events"],
            "leads": ["paid_ads", "seo", "email", "whatsapp", "partnerships"],
            "sales": ["whatsapp", "social_media", "paid_ads", "email", "events"],
        }
        return mapping.get(objective, ["social_media", "email", "whatsapp", "seo", "events"])

    @staticmethod
    def _effort_from_budget(high_budget: float) -> str:
        if high_budget >= 700:
            return "high"
        if high_budget >= 250:
            return "medium"
        return "low"

    def _generate_local_strategy(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        product_name = str(context.get("product_name") or "SME Offer").strip()
        objective = str(context.get("objective") or "sales").strip()
        timeline = str(context.get("campaign_timeline") or "2 weeks").strip()
        audience = context.get("audience") if isinstance(context.get("audience"), dict) else {}
        location = str(audience.get("location") or "target market").strip()
        tone = str(context.get("tone_preference") or "storytelling").strip()
        signal_keys = [str(item).strip() for item in context.get("signals", []) if str(item).strip()]
        top_signal = signal_keys[0] if signal_keys else "current demand shifts"

        return {
            "positioning": (
                f"Position {product_name} as the practical, trusted choice for {location} buyers "
                f"who want fast and tangible results."
            ),
            "target_psychology": (
                "Prioritize trust proof, urgency with credibility, and frictionless next-step decisions."
            ),
            "market_opportunity": (
                f"Current opportunity is strongest around {top_signal}, where intent and discoverability can be captured quickly."
            ),
            "messaging_pillars": [
                "Proof-driven value proposition",
                "Local relevance and timing",
                "Clear single-call-to-action per touchpoint",
            ],
            "tone_recommendation": tone,
            "channel_priorities": self._channels_for_objective(objective)[:6],
            "timeline_summary": f"{timeline} rollout with daily measurement and weekly budget reallocation.",
            "risk_notes": [
                "Avoid inflated claims that reduce trust",
                "Cut underperforming placements quickly",
            ],
        }

    def _generate_local_solutions(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        product_name = str(context.get("product_name") or "SME Offer").strip()
        objective = str(context.get("objective") or "sales").strip()
        location = str(context.get("location") or "target market").strip()
        signal_keys = [str(item).strip() for item in context.get("signal_keys", []) if str(item).strip()]
        priorities = [
            str(item).strip().lower().replace(" ", "_")
            for item in context.get("channel_priorities", [])
            if str(item).strip()
        ]
        channels = list(dict.fromkeys(priorities + self._channels_for_objective(objective)))[:7]

        solutions: list[dict[str, Any]] = []
        for index, channel in enumerate(channels[:6]):
            channel_label = channel.replace("_", " ").title()
            solutions.append(
                {
                    "channel": channel,
                    "solution_name": f"{channel_label} Conversion Sprint",
                    "description": (
                        f"Deploy a context-specific {channel_label.lower()} play for {product_name} in {location} "
                        f"to accelerate {objective}."
                    ),
                    "reasoning": (
                        f"{channel_label} aligns with audience behavior for this objective and improves speed-to-feedback "
                        f"within the active campaign window."
                    ),
                    "confidence_score": round(max(0.58, 0.9 - (index * 0.05)), 2),
                    "signals_used": signal_keys[:4] if signal_keys else ["market_signal"],
                }
            )

        return {"solutions": solutions}

    def _generate_local_budget_allocations(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        budget_constraint = (
            context.get("budget_constraint")
            if isinstance(context.get("budget_constraint"), dict)
            else {}
        )
        channels_payload = context.get("channels") if isinstance(context.get("channels"), list) else []
        channels = [
            str(item.get("channel") or "").strip().lower().replace(" ", "_")
            for item in channels_payload
            if isinstance(item, dict) and str(item.get("channel") or "").strip()
        ]
        channels = list(dict.fromkeys(channels))

        low_total = float(budget_constraint.get("low") or 100.0)
        high_total = float(budget_constraint.get("high") or 800.0)
        if high_total < low_total:
            high_total = low_total

        weight_map = {
            "whatsapp": 0.7,
            "email": 0.75,
            "content": 0.85,
            "social_media": 1.0,
            "seo": 1.1,
            "partnerships": 1.2,
            "events": 1.5,
            "paid_ads": 1.55,
        }
        total_weight = sum(weight_map.get(channel, 1.0) for channel in channels) or 1.0

        allocations: list[dict[str, Any]] = []
        for channel in channels:
            share = weight_map.get(channel, 1.0) / total_weight
            total_low = round(max(20.0, low_total * share * 0.75), 2)
            total_high = round(max(total_low, high_total * share * 1.15), 2)

            midpoint = (total_low + total_high) / 2
            breakdown = {
                "content_creation": round(midpoint * 0.33, 2),
                "ad_spend": round(midpoint * 0.37, 2),
                "management": round(midpoint * 0.2, 2),
                "tools": round(midpoint * 0.1, 2),
            }
            allocations.append(
                {
                    "channel": channel,
                    "total_low": total_low,
                    "total_high": total_high,
                    "currency": str(budget_constraint.get("currency") or "TND"),
                    "breakdown": breakdown,
                }
            )

        if allocations:
            quick_index = next(
                (idx for idx, item in enumerate(allocations) if item["channel"] in {"whatsapp", "email", "content", "social_media"}),
                0,
            )
            allocations[quick_index]["total_high"] = min(150.0, allocations[quick_index]["total_high"])
            allocations[quick_index]["total_low"] = min(
                allocations[quick_index]["total_low"],
                allocations[quick_index]["total_high"],
            )

            scale_index = next(
                (idx for idx, item in enumerate(allocations) if item["channel"] in {"paid_ads", "events", "partnerships"}),
                len(allocations) - 1,
            )
            allocations[scale_index]["total_high"] = max(500.0, allocations[scale_index]["total_high"])
            allocations[scale_index]["total_low"] = min(
                allocations[scale_index]["total_low"],
                round(allocations[scale_index]["total_high"] * 0.65, 2),
            )

        return {"allocations": allocations}

    def _generate_local_execution(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        channel = str(context.get("channel") or "social_media").strip().lower().replace(" ", "_")
        product_name = str(context.get("product_name") or "SME Offer").strip()
        location = str(context.get("location") or "target market").strip()
        objective = str(context.get("objective") or "sales").strip()
        budget = context.get("budget") if isinstance(context.get("budget"), dict) else {}
        high_budget = float(budget.get("total_high") or 250.0)

        cta_text = (
            "Send LEAD on WhatsApp for full details"
            if objective == "leads"
            else "Order now on WhatsApp"
        )
        overlay_text = f"{product_name} | {location}"

        reach_low = int(max(500, high_budget * 8))
        reach_high = int(max(1600, high_budget * 20))

        return {
            "execution": {
                "content_format": "campaign_asset",
                "message": f"Execution-ready {channel.replace('_', ' ')} activation for {product_name}.",
                "assets_needed": ["brand_kit", "product_visual", "cta_variant"],
                "timeline": "Deploy in 48 hours",
                "frequency": "3x/week",
                "posting_windows": [{"day": "Mon-Fri", "time": "18:30", "reason": "high attention window"}],
                "image_prompt": (
                    f"Create a {channel.replace('_', ' ')} visual for {product_name} in {location}. "
                    f"Overlay text exactly: '{overlay_text}'. Keep CTA block visible in lower-right zone."
                ),
                "exact_copy": (
                    f"HOOK: {product_name} is available in {location}.\n"
                    "BODY: Clear value, concrete proof, and one focused next step.\n"
                    f"CTA: {cta_text}"
                ),
                "text_overlay": overlay_text,
                "cta_text": cta_text,
                "hashtags": ["#SME", "#Growth", "#PerformanceMarketing"],
                "production_steps": [
                    "Generate creative from image_prompt",
                    "Publish exact_copy with one CTA",
                    "Track CTR and conversion daily",
                ],
            },
            "expected_outcomes": {
                "reach": f"{reach_low}-{reach_high}",
                "engagement_rate": "3-7%",
                "conversion_assumption": "1.5-4.5%",
                "roi_estimate": "2x-6x",
            },
        }

    def _generate_local_response_composer(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        product_name = str(context.get("product_name") or "SME Offer").strip()
        objective = str(context.get("objective") or "sales").strip()
        location = str(context.get("location") or "target market").strip()
        budget_constraint = (
            context.get("budget_constraint")
            if isinstance(context.get("budget_constraint"), dict)
            else {}
        )
        budget_low = float(budget_constraint.get("low") or 100.0)
        budget_high = float(budget_constraint.get("high") or 800.0)
        solutions = context.get("solutions") if isinstance(context.get("solutions"), list) else []
        signals = context.get("market_signals_used") if isinstance(context.get("market_signals_used"), list) else []

        channels = [
            str(item.get("channel") or "").strip().lower().replace(" ", "_")
            for item in solutions
            if isinstance(item, dict)
        ]
        channels = [channel for channel in channels if channel]

        signal_labels = [
            str(item.get("signal") or "").strip()
            for item in signals
            if isinstance(item, dict)
        ]
        signal_labels = [label for label in signal_labels if label]

        timing_hint = "7:00-9:00 AM" if objective in {"sales", "leads"} else "6:00-9:00 PM"
        audience_hint = "commuters and office workers" if objective in {"sales", "leads"} else "students and families"

        strategic_options: list[dict[str, Any]] = []
        for index, solution in enumerate(solutions[:7]):
            if not isinstance(solution, dict):
                continue
            channel = str(solution.get("channel") or "channel").strip().lower().replace(" ", "_")
            name = str(solution.get("solution_name") or f"{channel.title()} Activation").strip()
            reasoning = str(solution.get("reasoning") or "").strip() or "Channel fit is strong for this campaign objective."
            outcomes = solution.get("expected_outcomes") if isinstance(solution.get("expected_outcomes"), dict) else {}
            budget = solution.get("budget") if isinstance(solution.get("budget"), dict) else {}
            high_budget = float(budget.get("total_high") or 250.0)
            low_budget = float(budget.get("total_low") or 80.0)

            strategic_options.append(
                {
                    "option_key": f"{channel}_{index + 1}",
                    "title": name,
                    "category": channel,
                    "why_it_fits": reasoning,
                    "expected_impact": str(outcomes.get("roi_estimate") or "2x-5x"),
                    "effort_level": self._effort_from_budget(high_budget),
                    "budget_range_tnd": {"low": round(low_budget, 2), "high": round(high_budget, 2)},
                    "recommended": index < 2,
                    "first_actions": [
                        f"Launch {name}",
                        "Publish the first execution asset in 48h",
                        "Track one primary KPI daily",
                    ],
                }
            )

        if len(strategic_options) < 5:
            for index in range(len(strategic_options), 5):
                channel = channels[index % len(channels)] if channels else "social_media"
                strategic_options.append(
                    {
                        "option_key": f"{channel}_extra_{index + 1}",
                        "title": f"{channel.replace('_', ' ').title()} Expansion Track",
                        "category": channel,
                        "why_it_fits": "Expands validated channel performance without breaking budget discipline.",
                        "expected_impact": "2x-5x",
                        "effort_level": "medium",
                        "budget_range_tnd": {"low": 100.0, "high": 320.0},
                        "recommended": index < 2,
                        "first_actions": [
                            "Prepare one channel-specific creative variant",
                            "Launch with daily measurement",
                        ],
                    }
                )

        strategy_lines = [
            f"1. Run {channels[0].replace('_', ' ')} daily at {timing_hint} for {audience_hint} with same-day CTA and a hard cap of {int(max(40.0, budget_high * 0.25))} TND.",
            f"2. Use WhatsApp follow-up within 2 hours for every inbound lead and allocate around {int(max(25.0, budget_high * 0.18))} TND to retarget warm prospects.",
            "3. Launch a weekend-only limited offer (Fri-Sun) to trigger urgency and shift spend to the best-performing post after 72 hours.",
        ]
        insight_sentence = (
            f"In {location}, conversion intent spikes when the first message is posted in narrow peak windows and followed by immediate direct-channel follow-up."
        )

        post_caption = (
            f"{product_name} in {location} today. Fresh stock, fast response, and a limited weekend bonus for early orders. "
            "Send us a message now and we confirm your order in minutes."
        )
        hashtag_line = f"#{location.replace(' ', '')} #SmallBusiness #LocalDeals #{objective.title()}"
        first_channel = channels[0].replace("_", " ") if channels else "social media"
        image_prompt_line = (
            f"Realistic {first_channel} photo in {location}, natural light, clear product focus, short CTA text area in lower-right, no clutter."
        )

        explanation = (
            "Strategy:\n"
            f"{strategy_lines[0]}\n"
            f"{strategy_lines[1]}\n"
            f"{strategy_lines[2]}\n"
            f"Insight: {insight_sentence}\n"
            f"Marketing Post: {post_caption}\n"
            f"Hashtags: {hashtag_line}\n"
            f"Image Prompt: {image_prompt_line}"
        )

        insights = [insight_sentence]

        recommended_titles = [
            option["title"]
            for option in strategic_options
            if bool(option.get("recommended"))
        ]
        recommended_path = (
            f"Step 1: Start with {recommended_titles[0]}. Step 2: Add {recommended_titles[1]} once baseline metrics are stable. "
            "Step 3: Scale only channels that hit KPI thresholds and pause low-return activities."
            if len(recommended_titles) >= 2
            else "Step 1: Launch the highest-confidence option. Step 2: Measure KPI movement in 72h. Step 3: Scale winning channels only."
        )

        action_plan: list[dict[str, Any]] = []
        for day in range(1, 8):
            solution = solutions[(day - 1) % len(solutions)] if solutions else {}
            focus_channel = str(solution.get("channel") or "campaign").replace("_", " ")
            focus_name = str(solution.get("solution_name") or "Core activation")
            action_plan.append(
                {
                    "day": day,
                    "focus": focus_channel.title(),
                    "action": f"Execute and review {focus_name} with one primary KPI checkpoint.",
                    "expected_output": f"Measured {focus_channel} performance update and optimization decision.",
                }
            )

        next_actions = [
            f"Launch {option['title']} with final creative assets"
            for option in strategic_options[:4]
        ]

        return {
            "assistant_explanation": explanation,
            "strategic_options": strategic_options[:7],
            "insights": insights,
            "recommended_path": recommended_path,
            "next_7_days_plan": action_plan,
            "next_actions": next_actions,
        }

    def _generate_local_creative_brief(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        product_name = str(context.get("product_name") or "SME Offer").strip()
        channel = str(context.get("channel") or "social_media").strip().lower()
        objective = str(context.get("objective") or "sales").strip()

        audience = context.get("audience") if isinstance(context.get("audience"), dict) else {}
        location = str(audience.get("location") or "target market").strip()
        tone = str(context.get("tone_preference") or "storytelling").strip()

        return {
            "objective": objective,
            "channel": channel,
            "image_prompt": (
                f"Create a high-clarity {channel} visual for {product_name} in {location}, "
                f"with {tone} tone, product-focused composition, and one CTA area."
            ),
            "canva_template_suggestion": "Product Story - Performance CTA",
            "color_palette": ["#1F6F5C", "#F3E9D2", "#2C2C2C"],
            "text_overlay": f"{product_name} | {location}",
            "do_not_include": [
                "blurry product details",
                "overcrowded text blocks",
                "misleading claims",
            ],
            "recommended_aspect_ratio": "4:5",
            "rationale": "Designed for channel fit, legibility, and direct conversion intent.",
        }

    def _generate_local_refine_solution(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        instruction = str(context.get("refinement_instruction") or "Refine current solution").strip()
        channel = "social_media"
        lowered = instruction.lower()
        if "email" in lowered:
            channel = "email"
        elif "whatsapp" in lowered:
            channel = "whatsapp"
        elif "seo" in lowered:
            channel = "seo"

        return {
            "channel": channel,
            "solution_name": f"{channel.replace('_', ' ').title()} Refined Plan",
            "description": f"Refined solution generated from instruction: {instruction}",
            "execution": {
                "content_format": "campaign_asset",
                "message": "Refined execution focused on the updated instruction.",
                "assets_needed": ["brand_kit", "product_visual"],
                "timeline": "Deploy within 48h",
                "frequency": "3x/week",
                "posting_windows": [{"day": "Mon-Fri", "time": "18:30", "reason": "attention peak"}],
                "image_prompt": "Create a refined visual with clear CTA and strong product focus.",
                "exact_copy": "HOOK: Updated offer. BODY: Strong proof and clear value. CTA: Reply now.",
                "text_overlay": "Updated Offer",
                "cta_text": "Reply now",
                "hashtags": ["#Growth", "#Optimization"],
                "production_steps": [
                    "Generate revised visual",
                    "Publish updated copy",
                    "Track conversion impact",
                ],
            },
            "budget": {
                "total_low": 120.0,
                "total_high": 360.0,
                "currency": "TND",
                "breakdown": {
                    "content_creation": 120.0,
                    "ad_spend": 140.0,
                    "management": 70.0,
                    "tools": 30.0,
                },
            },
            "expected_outcomes": {
                "reach": "1200-4200",
                "engagement_rate": "3-7%",
                "conversion_assumption": "1.5-4.0%",
                "roi_estimate": "2x-5x",
            },
            "confidence_score": 0.78,
            "reasoning": "Refinement emphasizes clearer messaging and tighter channel fit.",
            "signals_used": ["user_refinement_instruction"],
            "risk_level": "medium",
        }

    def _generate_local_clarification(self, prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(prompt)
        missing_fields = context.get("missing_fields") if isinstance(context.get("missing_fields"), list) else []
        questions = [
            f"Can you clarify your {str(field).strip().replace('_', ' ')}?"
            for field in missing_fields
            if str(field).strip()
        ]
        if not questions:
            questions = ["Can you share the missing context so I can generate the final plan?"]
        return {"questions": questions[:3]}

    def _generate_local_brief_extractor(self, prompt: str) -> dict[str, Any]:
        message = self._extract_user_message(prompt)
        normalized = message.lower()

        objective = None
        if "lead" in normalized:
            objective = "leads"
        elif "engage" in normalized or "interaction" in normalized:
            objective = "engagement"
        elif "aware" in normalized or "reach" in normalized or "visibility" in normalized:
            objective = "awareness"
        elif "sale" in normalized or "sell" in normalized:
            objective = "sales"

        city = None
        for candidate in ("tunis", "sfax", "sousse", "nabeul", "ariana", "bizerte", "gabes", "monastir", "kairouan"):
            if candidate in normalized:
                city = candidate.title()
                break

        budget_low = None
        budget_high = None
        currency = None
        range_match = re.search(r"(\d{2,6})\s*(?:-|to|–)\s*(\d{2,6})\s*(tnd|dt|usd|eur)?", normalized)
        if range_match:
            budget_low = float(range_match.group(1))
            budget_high = float(range_match.group(2))
            currency = (range_match.group(3) or "TND").upper()
            if currency == "DT":
                currency = "TND"

        timeline = None
        timeline_match = re.search(r"(\d+\s*(?:day|days|week|weeks|month|months))", normalized)
        if timeline_match:
            timeline = timeline_match.group(1)

        words = [word for word in re.split(r"\s+", message.strip()) if word]
        product_name = " ".join(words[:4]).strip(" ,.-") if len(words) >= 2 else None

        return {
            "product_name": product_name or None,
            "product_category": None,
            "objective": objective,
            "audience_location": city,
            "audience_segment": None,
            "interests": [],
            "budget_low": budget_low,
            "budget_high": budget_high,
            "currency": currency,
            "campaign_timeline": timeline,
            "language_preference": None,
            "tone_preference": None,
            "constraints": None,
        }

    def _generate_local_json(self, task_name: str, prompt: str) -> dict[str, Any] | None:
        if task_name == "strategy_planner":
            return self._generate_local_strategy(prompt)
        if task_name == "solutions_architect_agent":
            return self._generate_local_solutions(prompt)
        if task_name == "budget_allocator_agent":
            return self._generate_local_budget_allocations(prompt)
        if task_name == "execution_agent":
            return self._generate_local_execution(prompt)
        if task_name == "response_composer_agent":
            return self._generate_local_response_composer(prompt)
        if task_name == "creative_brief_agent":
            return self._generate_local_creative_brief(prompt)
        if task_name == "refine_solution_agent":
            return self._generate_local_refine_solution(prompt)
        if task_name == "clarification_agent":
            return self._generate_local_clarification(prompt)
        if task_name == "brief_extractor":
            return self._generate_local_brief_extractor(prompt)
        return None

    def _generate_local_vision_json(self, images: list[dict[str, str]]) -> dict[str, Any]:
        result = {"images": []}
        for image in images:
            filename = str(image.get("filename") or "image.jpg")
            result["images"].append(
                {
                    "filename": filename,
                    "quality_score": 0.72,
                    "priority": "medium",
                    "findings": ["Visual is usable but CTA hierarchy can be improved"],
                    "recommendations": ["Increase CTA contrast and keep product dominant"],
                }
            )
        return result

    async def _call_groq(
        self,
        prompt: str,
        timeout: int,
    ) -> tuple[str, str, dict[str, Any] | list[Any], int, int]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None

        for model_candidate in self._groq_model_candidates():
            payload = {
                "model": model_candidate,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON API. Return valid JSON only, no markdown, no explanations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": self.settings.llm_temperature,
                "max_completion_tokens": self.settings.llm_max_output_tokens,
                "top_p": self.settings.llm_top_p,
                "stream": False,
            }

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {404, 429, 503}:
                    continue
                raise

            body = response.json()
            choices = body.get("choices") or []
            message = (choices[0] or {}).get("message", {}) if choices else {}
            raw_text = str(message.get("content") or "").strip()
            parsed_data = self.safe_parse_json(raw_text)
            if parsed_data is None:
                last_error = ValueError("Groq returned non-JSON output")
                continue

            usage = body.get("usage") or {}
            input_tokens = int(usage.get("prompt_tokens") or self._estimate_tokens(prompt))
            output_tokens = int(usage.get("completion_tokens") or self._estimate_tokens(raw_text))
            model = str(body.get("model") or model_candidate)
            return model, raw_text, parsed_data, input_tokens, output_tokens

        if last_error:
            raise last_error
        raise RuntimeError("Groq call failed without a specific error")

    async def _call_gemini(
        self,
        prompt: str,
        timeout: int,
    ) -> tuple[str, str, dict[str, Any] | list[Any], int, int]:
        last_error: Exception | None = None

        for model_candidate in self._gemini_model_candidates():
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": self.settings.llm_temperature,
                    "topP": self.settings.llm_top_p,
                    "maxOutputTokens": self.settings.llm_max_output_tokens,
                },
                "systemInstruction": {
                    "parts": [
                        {
                            "text": "Return valid JSON only. No markdown and no additional commentary."
                        }
                    ]
                },
            }

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        params={"key": self.settings.gemini_api_key},
                        json=payload,
                    )
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {404, 429, 503}:
                    continue
                raise

            body = response.json()
            candidates = body.get("candidates") or []
            first_candidate = candidates[0] if candidates else {}
            content = first_candidate.get("content") or {}
            parts = content.get("parts") or []
            raw_text = "".join(str(part.get("text") or "") for part in parts).strip()
            parsed_data = self.safe_parse_json(raw_text)
            if parsed_data is None:
                last_error = ValueError("Gemini returned non-JSON output")
                continue

            usage = body.get("usageMetadata") or {}
            input_tokens = int(usage.get("promptTokenCount") or self._estimate_tokens(prompt))
            output_tokens = int(usage.get("candidatesTokenCount") or self._estimate_tokens(raw_text))
            return model_candidate, raw_text, parsed_data, input_tokens, output_tokens

        if last_error:
            raise last_error
        raise RuntimeError("Gemini call failed without a specific error")

    async def _call_provider(
        self,
        provider: str,
        prompt: str,
        timeout: int,
    ) -> tuple[str, str, dict[str, Any] | list[Any], int, int]:
        if provider == "groq":
            return await self._call_groq(prompt, timeout)
        if provider == "gemini":
            return await self._call_gemini(prompt, timeout)
        raise ValueError(f"Unsupported provider: {provider}")

    async def _call_groq_vision(
        self,
        prompt: str,
        images: list[dict[str, str]],
        timeout: int,
    ) -> tuple[str, str, dict[str, Any] | list[Any], int, int]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image in images:
            mime_type = str(image.get("mime_type") or "image/jpeg")
            data_base64 = str(image.get("data_base64") or "")
            if not data_base64:
                continue
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{data_base64}",
                    },
                }
            )

        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a JSON API. Return valid JSON only, no markdown, no explanations."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": self.settings.llm_temperature,
            "max_completion_tokens": self.settings.llm_max_output_tokens,
            "top_p": self.settings.llm_top_p,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        body = response.json()
        choices = body.get("choices") or []
        message = (choices[0] or {}).get("message", {}) if choices else {}
        raw_text = str(message.get("content") or "").strip()
        parsed_data = self.safe_parse_json(raw_text)
        if parsed_data is None:
            raise ValueError("Groq vision returned non-JSON output")

        usage = body.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or self._estimate_tokens(prompt))
        output_tokens = int(usage.get("completion_tokens") or self._estimate_tokens(raw_text))
        model = str(body.get("model") or self.settings.groq_model)
        return model, raw_text, parsed_data, input_tokens, output_tokens

    async def _call_gemini_vision(
        self,
        prompt: str,
        images: list[dict[str, str]],
        timeout: int,
    ) -> tuple[str, str, dict[str, Any] | list[Any], int, int]:
        last_error: Exception | None = None

        parts: list[dict[str, Any]] = [{"text": prompt}]
        for image in images:
            mime_type = str(image.get("mime_type") or "image/jpeg")
            data_base64 = str(image.get("data_base64") or "")
            if not data_base64:
                continue
            parts.append(
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": data_base64,
                    }
                }
            )

        for model_candidate in self._gemini_model_candidates():
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": parts,
                    }
                ],
                "generationConfig": {
                    "temperature": self.settings.llm_temperature,
                    "topP": self.settings.llm_top_p,
                    "maxOutputTokens": self.settings.llm_max_output_tokens,
                },
                "systemInstruction": {
                    "parts": [
                        {
                            "text": "Return valid JSON only. No markdown and no additional commentary."
                        }
                    ]
                },
            }

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        params={"key": self.settings.gemini_api_key},
                        json=payload,
                    )
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {404, 429, 503}:
                    continue
                raise

            body = response.json()
            candidates = body.get("candidates") or []
            first_candidate = candidates[0] if candidates else {}
            content = first_candidate.get("content") or {}
            parts_out = content.get("parts") or []
            raw_text = "".join(str(part.get("text") or "") for part in parts_out).strip()
            parsed_data = self.safe_parse_json(raw_text)
            if parsed_data is None:
                last_error = ValueError("Gemini vision returned non-JSON output")
                continue

            usage = body.get("usageMetadata") or {}
            input_tokens = int(usage.get("promptTokenCount") or self._estimate_tokens(prompt))
            output_tokens = int(usage.get("candidatesTokenCount") or self._estimate_tokens(raw_text))
            return model_candidate, raw_text, parsed_data, input_tokens, output_tokens

        if last_error:
            raise last_error
        raise RuntimeError("Gemini vision call failed without a specific error")

    async def _call_provider_vision(
        self,
        provider: str,
        prompt: str,
        images: list[dict[str, str]],
        timeout: int,
    ) -> tuple[str, str, dict[str, Any] | list[Any], int, int]:
        if provider == "groq":
            return await self._call_groq_vision(prompt, images, timeout)
        if provider == "gemini":
            return await self._call_gemini_vision(prompt, images, timeout)
        raise ValueError(f"Unsupported vision provider: {provider}")

    async def try_generate_json(
        self,
        task_name: str,
        prompt: str,
        *,
        provider_order: list[str] | None = None,
        allow_local_fallback: bool = True,
        respect_test_local: bool = True,
    ) -> LLMResult | None:
        timeout = self.settings.llm_timeout_seconds
        retries = self.settings.llm_max_retries

        if respect_test_local and os.getenv("PYTEST_CURRENT_TEST"):
            selected_order = ["local"]
        else:
            selected_order = self._normalize_provider_order(
                provider_order or self._provider_order(),
                include_local=allow_local_fallback,
            )

        for provider in selected_order:
            if not self._provider_ready(provider):
                continue

            if provider == "local":
                local_data = self._generate_local_json(task_name, prompt)
                raw_text = json.dumps(local_data, ensure_ascii=True) if local_data is not None else ""
                return LLMResult(
                    provider=provider,
                    model="local_rules",
                    data=local_data,
                    raw_text=raw_text,
                    latency_ms=0,
                    retries=0,
                    input_tokens_estimate=self._estimate_tokens(prompt),
                    output_tokens_estimate=self._estimate_tokens(raw_text) if raw_text else 0,
                    cost_estimate=0.0,
                )

            for attempt in range(retries + 1):
                started = time.perf_counter()
                call_prompt = (
                    prompt
                    if attempt == 0
                    else (
                        f"{prompt}\n\nIMPORTANT: Return strict JSON only. "
                        "No markdown, no explanations, no trailing text."
                    )
                )
                try:
                    model, raw_text, parsed_data, input_tokens, output_tokens = await asyncio.wait_for(
                        self._call_provider(provider, call_prompt, timeout),
                        timeout=timeout,
                    )
                    elapsed_ms = int((time.perf_counter() - started) * 1000)

                    return LLMResult(
                        provider=provider,
                        model=model,
                        data=parsed_data,
                        raw_text=raw_text,
                        latency_ms=elapsed_ms,
                        retries=attempt,
                        input_tokens_estimate=input_tokens,
                        output_tokens_estimate=output_tokens,
                        cost_estimate=self._estimate_cost_usd(provider, model, input_tokens, output_tokens),
                    )
                except Exception:
                    continue

        return None

    async def try_generate_vision_json(
        self,
        task_name: str,
        prompt: str,
        images: list[dict[str, str]],
        *,
        provider_order: list[str] | None = None,
        allow_local_fallback: bool = True,
        respect_test_local: bool = True,
    ) -> LLMResult | None:
        if not images:
            return None

        timeout = self.settings.llm_timeout_seconds
        retries = self.settings.llm_max_retries

        if respect_test_local and os.getenv("PYTEST_CURRENT_TEST"):
            selected_order = ["local"]
        else:
            selected_order = self._normalize_provider_order(
                provider_order or self._vision_provider_order(),
                include_local=allow_local_fallback,
            )

        for provider in selected_order:
            if not self._provider_ready(provider):
                continue

            if provider == "local":
                local_data = self._generate_local_vision_json(images)
                raw_text = json.dumps(local_data, ensure_ascii=True)
                return LLMResult(
                    provider=provider,
                    model="local_rules_vision",
                    data=local_data,
                    raw_text=raw_text,
                    latency_ms=0,
                    retries=0,
                    input_tokens_estimate=self._estimate_tokens(prompt),
                    output_tokens_estimate=self._estimate_tokens(raw_text),
                    cost_estimate=0.0,
                )

            for attempt in range(retries + 1):
                started = time.perf_counter()
                call_prompt = (
                    prompt
                    if attempt == 0
                    else (
                        f"{prompt}\n\nIMPORTANT: Return strict JSON only. "
                        "No markdown, no explanations, no trailing text."
                    )
                )
                try:
                    model, raw_text, parsed_data, input_tokens, output_tokens = await asyncio.wait_for(
                        self._call_provider_vision(provider, call_prompt, images, timeout),
                        timeout=timeout,
                    )
                    elapsed_ms = int((time.perf_counter() - started) * 1000)

                    return LLMResult(
                        provider=provider,
                        model=model,
                        data=parsed_data,
                        raw_text=raw_text,
                        latency_ms=elapsed_ms,
                        retries=attempt,
                        input_tokens_estimate=input_tokens,
                        output_tokens_estimate=output_tokens,
                        cost_estimate=self._estimate_cost_usd(provider, model, input_tokens, output_tokens),
                    )
                except Exception:
                    continue

        return None
