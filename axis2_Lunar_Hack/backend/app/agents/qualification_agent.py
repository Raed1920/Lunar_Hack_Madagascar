from __future__ import annotations

from typing import Any, Dict

from app.agents.base import BaseJsonAgent
from app.models import QualificationResult, SchemaBlueprint
from app.prompts import QUALIFICATION_SYSTEM_PROMPT, build_qualification_prompt


class QualificationAgent(BaseJsonAgent):
    def __init__(self, settings, ollama):
        super().__init__(
            settings=settings,
            ollama=ollama,
            stage_name="qualification",
            system_prompt=QUALIFICATION_SYSTEM_PROMPT,
            use_reasoning_model=getattr(settings, "qualification_use_reasoning_model", False),
        )

    async def run(
        self,
        message: str,
        profile: Dict[str, Any],
        context: str,
        language: str,
        schema: SchemaBlueprint,
    ) -> QualificationResult:
        prompt = build_qualification_prompt(
            message=self._truncate(message, max_chars=950),
            required_fields=schema.required_fields,
            field_descriptions=schema.field_descriptions,
            profile=self._compact_profile(profile, schema.required_fields),
            context=self._truncate(context, max_chars=1600),
            language=language,
        )
        fallback = {
            "updated_profile": {},
            "missing_fields": [
                field for field in schema.required_fields if not self._has_value(profile.get(field))
            ],
            "next_question": "",
        }

        result = await self.run_contract(prompt, QualificationResult, fallback)

        updated_profile: Dict[str, Any] = {}
        if isinstance(result.updated_profile, dict):
            for field in schema.required_fields:
                value = result.updated_profile.get(field)
                if self._has_value(value):
                    updated_profile[field] = self._normalize_value(value)

        merged = dict(profile)
        merged.update(updated_profile)

        missing_fields = [
            field
            for field in schema.required_fields
            if not self._has_value(merged.get(field))
        ]

        next_question = (result.next_question or "").strip()
        if missing_fields and not next_question:
            next_question = self._default_question(
                missing_fields[0],
                schema.field_descriptions.get(missing_fields[0], ""),
                language,
            )

        if not missing_fields:
            next_question = None
        elif next_question and "?" not in next_question:
            next_question = f"{next_question.rstrip('.')}?"

        return QualificationResult(
            updated_profile=updated_profile,
            missing_fields=missing_fields,
            next_question=next_question,
        )

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
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, dict):
            return {str(k).strip(): str(v).strip() for k, v in value.items() if str(k).strip()}
        return value

    @staticmethod
    def _default_question(field: str, description: str, language: str) -> str:
        prompts = {
            "en": {
                "business_type": "What type of business context should this decision optimize for?",
                "goal": "What is the single business outcome you want to improve first?",
                "budget": "What budget or financial limit should this plan respect?",
                "timeline": "What timeline should we plan against?",
                "constraints": "What constraints can block execution right now?",
                "kpis": "Which KPI should we use to measure success?",
                "customer_segment": "Which customer segment is the main focus?",
            },
            "fr": {
                "business_type": "Quel contexte business doit guider cette decision ?",
                "goal": "Quel est le resultat business numero un a atteindre ?",
                "budget": "Quelle limite budgetaire doit-on respecter ?",
                "timeline": "Quel horizon de temps devons-nous viser ?",
                "constraints": "Quelles contraintes peuvent bloquer l'execution ?",
                "kpis": "Quel KPI doit mesurer le succes ?",
                "customer_segment": "Quel segment client est prioritaire ?",
            },
            "ar": {
                "business_type": "ما سياق العمل الذي يجب ان يوجه هذا القرار؟",
                "goal": "ما النتيجة التجارية الاهم التي تريد تحسينها اولا؟",
                "budget": "ما الحد المالي الذي يجب الالتزام به؟",
                "timeline": "ما الاطار الزمني الذي نعتمد عليه؟",
                "constraints": "ما القيود التي قد تعطل التنفيذ حاليا؟",
                "kpis": "ما مؤشر الاداء الذي سنقيس به النجاح؟",
                "customer_segment": "ما الشريحة العميلية الاكثر اولوية؟",
            },
        }

        language_map = prompts.get(language, prompts["en"])
        if field in language_map:
            return language_map[field]

        if language == "fr":
            return f"Pouvez-vous preciser {description or field.replace('_', ' ')} ?"
        if language == "ar":
            return f"هل يمكنك توضيح {description or field.replace('_', ' ')}؟"
        return f"Can you clarify {description or field.replace('_', ' ')}?"

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        value = (text or "").strip()
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars].rstrip()}..."

    def _compact_profile(self, profile: Dict[str, Any], required_fields: list[str]) -> Dict[str, Any]:
        compact: Dict[str, Any] = {}
        prioritized_keys = [
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
        ]
        keys = [*prioritized_keys, *required_fields]
        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            value = profile.get(key)
            if self._has_value(value):
                compact[key] = self._normalize_value(value)
            if len(compact) >= 12:
                break
        return compact
