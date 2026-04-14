import re
from typing import Any

from ..models.schemas import BudgetConstraint


class BudgetEstimator:
    def __init__(self):
        self.objective_multiplier: dict[str, float] = {
            "awareness": 0.95,
            "engagement": 1.0,
            "leads": 1.08,
            "sales": 1.15,
        }

        self.channel_profiles: dict[str, dict[str, Any]] = {
            "social_media": {
                "baseline": (120.0, 500.0),
                "share": (0.16, 0.42),
                "mix": {
                    "content_creation": 0.45,
                    "ad_spend": 0.25,
                    "management": 0.2,
                    "tools": 0.1,
                },
                "min_viable": 90.0,
            },
            "whatsapp": {
                "baseline": (30.0, 140.0),
                "share": (0.04, 0.16),
                "mix": {
                    "content_creation": 0.35,
                    "ad_spend": 0.05,
                    "management": 0.45,
                    "tools": 0.15,
                },
                "min_viable": 25.0,
            },
            "email": {
                "baseline": (40.0, 190.0),
                "share": (0.05, 0.2),
                "mix": {
                    "content_creation": 0.3,
                    "ad_spend": 0.05,
                    "management": 0.5,
                    "tools": 0.15,
                },
                "min_viable": 30.0,
            },
            "paid_ads": {
                "baseline": (180.0, 950.0),
                "share": (0.22, 0.65),
                "mix": {
                    "content_creation": 0.2,
                    "ad_spend": 0.6,
                    "management": 0.15,
                    "tools": 0.05,
                },
                "min_viable": 120.0,
            },
            "events": {
                "baseline": (320.0, 1600.0),
                "share": (0.25, 0.75),
                "mix": {
                    "content_creation": 0.4,
                    "ad_spend": 0.25,
                    "management": 0.25,
                    "tools": 0.1,
                },
                "min_viable": 220.0,
            },
            "partnerships": {
                "baseline": (160.0, 900.0),
                "share": (0.12, 0.5),
                "mix": {
                    "content_creation": 0.35,
                    "ad_spend": 0.25,
                    "management": 0.25,
                    "tools": 0.15,
                },
                "min_viable": 90.0,
            },
            "content": {
                "baseline": (110.0, 520.0),
                "share": (0.12, 0.35),
                "mix": {
                    "content_creation": 0.55,
                    "ad_spend": 0.1,
                    "management": 0.25,
                    "tools": 0.1,
                },
                "min_viable": 80.0,
            },
            "seo": {
                "baseline": (90.0, 580.0),
                "share": (0.1, 0.4),
                "mix": {
                    "content_creation": 0.5,
                    "ad_spend": 0.1,
                    "management": 0.25,
                    "tools": 0.15,
                },
                "min_viable": 70.0,
            },
        }

    def estimate(
        self,
        channel: str,
        constraint: BudgetConstraint,
        *,
        objective: str = "sales",
        timeline: str | None = None,
        priority_rank: int = 0,
        total_channels: int = 6,
    ) -> dict[str, float | str | dict[str, float]]:
        profile = self.channel_profiles.get(channel, self.channel_profiles["social_media"])
        base_low, base_high = profile["baseline"]
        share_low, share_high = profile["share"]
        mix = profile["mix"]
        min_viable = float(profile["min_viable"])

        objective_mult = self.objective_multiplier.get(objective, 1.0)
        timeline_mult = self._timeline_multiplier(timeline)
        priority_mult = self._priority_multiplier(priority_rank, total_channels)

        modeled_low = base_low * objective_mult * timeline_mult * priority_mult
        modeled_high = base_high * objective_mult * timeline_mult * priority_mult

        campaign_low = float(constraint.low or 0.0)
        campaign_high = float(constraint.high) if constraint.high is not None else None

        envelope_low = max(min_viable, campaign_low * share_low if campaign_low > 0 else 0.0)
        envelope_high = campaign_high * share_high if campaign_high is not None else modeled_high

        final_low = max(modeled_low, envelope_low)
        final_high = min(modeled_high, envelope_high) if campaign_high is not None else modeled_high

        if campaign_high is not None and final_low > campaign_high:
            final_low = campaign_high

        if final_high < final_low:
            final_high = final_low

        midpoint = (final_low + final_high) / 2
        breakdown = {
            key: round(midpoint * float(ratio), 2)
            for key, ratio in mix.items()
        }

        return {
            "total_low": round(final_low, 2),
            "total_high": round(final_high, 2),
            "currency": constraint.currency,
            "breakdown": breakdown,
        }

    @staticmethod
    def _timeline_multiplier(timeline: str | None) -> float:
        if not timeline:
            return 1.0

        normalized = timeline.lower().strip()
        match = re.search(r"(\d+(?:\.\d+)?)", normalized)
        if not match:
            return 1.0

        value = float(match.group(1))
        if "month" in normalized:
            weeks = value * 4
        elif "day" in normalized:
            weeks = max(1.0, value / 7.0)
        else:
            weeks = value

        # 2 weeks is baseline multiplier 1.0
        return max(0.75, min(2.4, weeks / 2.0))

    @staticmethod
    def _priority_multiplier(priority_rank: int, total_channels: int) -> float:
        if total_channels <= 1:
            return 1.1

        clamped_rank = max(0, min(priority_rank, total_channels - 1))
        spread = total_channels - 1
        return 1.12 - (0.27 * (clamped_rank / spread))
