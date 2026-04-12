from __future__ import annotations

import re
from typing import Dict, List

from app.agents.base import BaseJsonAgent
from app.models import IntentAnalysis, SchemaBlueprint
from app.prompts import SCHEMA_BUILDER_SYSTEM_PROMPT, build_schema_builder_prompt


class SchemaBuilderAgent(BaseJsonAgent):
    FIELD_LIBRARY: Dict[str, str] = {
        "business_type": "Business model or company type",
        "goal": "Primary outcome expected from this decision",
        "budget": "Available budget or financial boundary",
        "timeline": "Target delivery or decision horizon",
        "constraints": "Main execution constraints",
        "kpis": "Metrics that define success",
        "customer_segment": "Target customer profile",
        "channel": "Primary acquisition or delivery channel",
        "product_stage": "Current product maturity stage",
        "team_capacity": "Current team bandwidth",
        "data_availability": "Quality and availability of required data",
        "risk_tolerance": "Accepted level of business risk",
        "cash_runway": "Cash horizon before funding pressure",
        "north_star_metric": "Single metric to optimize",
        "compliance_requirements": "Regulatory constraints to satisfy",
        "price_point": "Current or target pricing level",
        "region": "Primary market geography",
    }

    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="schema_builder",
            system_prompt=SCHEMA_BUILDER_SYSTEM_PROMPT,
            use_reasoning_model=getattr(settings, "schema_builder_use_reasoning_model", False),
        )

    async def run(self, intent: IntentAnalysis, profile: dict, language: str) -> SchemaBlueprint:
        prompt = build_schema_builder_prompt(
            intent.model_dump(),
            self._compact_profile(profile),
            language,
        )
        fallback_fields = self._fallback_fields(intent.intent, intent.domain)
        fallback = {
            "required_fields": fallback_fields,
            "field_descriptions": {field: self.FIELD_LIBRARY.get(field, field.replace("_", " ")) for field in fallback_fields},
            "rationale": "fallback dynamic schema",
        }

        result = await self.run_contract(prompt, SchemaBlueprint, fallback)
        fields = self._sanitize_fields(result.required_fields)

        if len(fields) < 3:
            for field in fallback_fields:
                if field not in fields:
                    fields.append(field)
                if len(fields) >= 3:
                    break

        if len(fields) > 5:
            fields = fields[:5]

        descriptions: Dict[str, str] = {}
        for field in fields:
            description = (result.field_descriptions or {}).get(field)
            if isinstance(description, str) and description.strip():
                descriptions[field] = description.strip()
            else:
                descriptions[field] = self.FIELD_LIBRARY.get(field, f"Provide {field.replace('_', ' ')} details")

        return SchemaBlueprint(required_fields=fields, field_descriptions=descriptions, rationale=result.rationale)

    def _sanitize_fields(self, fields: List[str]) -> List[str]:
        cleaned: List[str] = []
        for item in fields:
            normalized = re.sub(r"[^a-z0-9_]+", "_", str(item).strip().lower())
            normalized = re.sub(r"_+", "_", normalized).strip("_")
            if not normalized:
                continue
            if normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned

    @staticmethod
    def _compact_profile(profile: dict) -> dict:
        important_keys = [
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
        ]
        compact: dict = {}
        for key in important_keys:
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                compact[key] = value.strip()[:240]
            elif value not in (None, "", [], {}):
                compact[key] = value
        return compact

    @staticmethod
    def _fallback_fields(intent: str, domain: str) -> List[str]:
        by_domain = {
            "marketing": ["goal", "customer_segment", "channel", "budget"],
            "product": ["goal", "product_stage", "timeline", "kpis"],
            "analytics": ["goal", "north_star_metric", "data_availability", "timeline"],
            "finance": ["goal", "cash_runway", "budget", "risk_tolerance"],
            "operations": ["goal", "constraints", "team_capacity", "timeline"],
            "sales": ["goal", "customer_segment", "channel", "kpis"],
            "people": ["goal", "team_capacity", "timeline", "budget"],
            "legal": ["goal", "compliance_requirements", "region", "timeline"],
            "general": ["business_type", "goal", "constraints", "timeline"],
        }
        domain_fields = by_domain.get(domain, by_domain["general"])

        if intent in {"execute", "optimize"}:
            return [domain_fields[0], domain_fields[1], "kpis", "timeline"]
        if intent in {"forecast", "analyze"}:
            return [domain_fields[0], "north_star_metric", "data_availability", "timeline"]
        return domain_fields
