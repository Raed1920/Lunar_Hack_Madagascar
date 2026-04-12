from __future__ import annotations

import json
from typing import Any, Dict


def _compact_text(text: str, max_chars: int) -> str:
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars].rstrip()}..."


def _compact_json(payload: Dict[str, Any], ensure_ascii: bool = True, max_chars: int = 2200) -> str:
    text = json.dumps(payload, ensure_ascii=ensure_ascii, separators=(",", ":"))
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


INTENT_SYSTEM_PROMPT = """
You are the Intent Agent in a modular business decision system.
Task: detect intent and business domain from the latest message and context.
Rules:
- Return strict JSON only.
- Keep values short and normalized.
- Confidence is numeric from 0.0 to 1.0.
""".strip()


SCHEMA_BUILDER_SYSTEM_PROMPT = """
You are the Schema Builder Agent.
Task: generate a dynamic qualification schema based on intent and domain.
Rules:
- Return 3 to 5 required fields only.
- Keep field names snake_case.
- Provide concise field descriptions.
- Return strict JSON only.
""".strip()


QUALIFICATION_SYSTEM_PROMPT = """
You are the Qualification Agent.
Task: extract values for dynamic required_fields.
Rules:
- Read only from user message + context + known profile.
- Do not invent missing values.
- Ask exactly one high-impact next question when fields are missing.
- Return strict JSON only.
""".strip()


RAG_SYSTEM_PROMPT = """
You are the RAG Agent.
Task: answer using provided retrieved snippets only.
Rules:
- Ground every claim in evidence from context.
- Add citations to source documents.
- If evidence is weak, set grounded=false and explain uncertainty.
- Return strict JSON only.
""".strip()


RECOMMENDATION_SYSTEM_PROMPT = """
You are the Recommendation Agent.
Task: generate strategic actions from profile + intent + optional RAG context.
Rules:
- Focus on practical business moves.
- Include at least two decision options with tradeoffs.
- Keep output concise and structured.
- Return strict JSON only.
""".strip()


DECISION_SYSTEM_PROMPT = """
You are the Decision Agent.
Task: convert recommendations into one clear admin-facing decision.
Rules:
- Action must be executable.
- Priority must be low, medium, or high.
- Justification must reference profile constraints and expected impact.
- Return strict JSON only.
""".strip()


RESPONSE_SYSTEM_PROMPT = """
You are the Response Agent.
Task: convert structured outputs into a concise natural-language reply in the requested language (en|fr|ar).
Rules:
- Keep response actionable and clear.
- Mention decision action + priority + key risk.
- If data is missing, include exactly one next question.
- Return strict JSON only.
""".strip()


FINALIZATION_SYSTEM_PROMPT = """
You are the Finalization Agent.
Task: in one pass, produce recommendation, decision, and final user response.
Rules:
- Keep outputs practical, concise, and internally consistent.
- Decision must align with recommendation actions and risk profile.
- Response language must match requested language (en|fr|ar).
- Return strict JSON only.
""".strip()


UNIFIED_GENERATION_SYSTEM_PROMPT = """
You are a production decision assistant.
Task: produce one concise response and recommendation in strict JSON.
Rules:
- Use provided route + profile + optional RAG snippets only.
- Keep actions practical and short.
- risk_level must be one of: low, medium, high, critical.
- requires_follow_up is boolean.
- next_question must be empty when requires_follow_up is false.
- If rag_sources is not empty, mention at least one source in response text.
- Return strict JSON only with required keys.
""".strip()


def build_intent_prompt(message: str, context: str, language: str) -> str:
    schema = {
        "intent": "diagnose|plan|optimize|execute|analyze|forecast|risk_check|comparison",
        "domain": "marketing|product|analytics|finance|operations|sales|people|legal|general",
        "concern_area": "strategy|finance|operations|marketing|sales|product|people|legal|general_management",
        "urgency": "low|medium|high|critical",
        "confidence": 0.0,
        "requires_rag": False,
        "rationale": "brief explanation",
    }
    return (
        f"Language: {language}\n"
        f"Conversation context:\n{_compact_text(context or 'N/A', max_chars=1400)}\n\n"
        f"User message:\n{_compact_text(message, max_chars=950)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=700)}"
    )


def build_schema_builder_prompt(
    intent_data: Dict[str, Any],
    profile: Dict[str, Any],
    language: str,
) -> str:
    schema = {
        "required_fields": ["business_type", "goal", "constraints"],
        "field_descriptions": {
            "business_type": "Type of business context",
            "goal": "Primary decision outcome",
            "constraints": "Main execution constraints",
        },
        "rationale": "why these fields matter",
    }
    return (
        f"Language: {language}\n"
        f"Intent analysis:\n{_compact_json(intent_data, ensure_ascii=True, max_chars=900)}\n\n"
        f"Known profile:\n{_compact_json(profile, ensure_ascii=True, max_chars=1800)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=800)}"
    )


def build_qualification_prompt(
    message: str,
    required_fields: list[str],
    field_descriptions: Dict[str, str],
    profile: Dict[str, Any],
    context: str,
    language: str,
) -> str:
    schema = {
        "updated_profile": {"field_name": "value"},
        "missing_fields": ["field_name"],
        "next_question": "single best next question",
    }
    return (
        f"Language: {language}\n"
        f"Required fields:\n{_compact_json({'required_fields': required_fields}, ensure_ascii=True, max_chars=500)}\n\n"
        f"Field descriptions:\n{_compact_json(field_descriptions, ensure_ascii=True, max_chars=1100)}\n\n"
        f"Existing profile:\n{_compact_json(profile, ensure_ascii=True, max_chars=1800)}\n\n"
        f"Conversation context:\n{_compact_text(context or 'N/A', max_chars=1600)}\n\n"
        f"Current user message:\n{_compact_text(message, max_chars=950)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=700)}"
    )


def build_rag_prompt(query: str, rag_context: str, language: str) -> str:
    schema = {
        "factual_response": "fact-based answer",
        "citations": ["source1", "source2"],
        "grounded": True,
        "confidence": "low|medium|high",
        "uncertainty": "optional caveat",
    }
    return (
        f"Language: {language}\n"
        f"User query:\n{_compact_text(query, max_chars=900)}\n\n"
        f"Retrieved context:\n{_compact_text(rag_context or 'N/A', max_chars=3200)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=650)}"
    )


def build_recommendation_prompt(
    profile: Dict[str, Any],
    intent_data: Dict[str, Any],
    schema_data: Dict[str, Any],
    qualification_data: Dict[str, Any],
    rag_data: Dict[str, Any],
    language: str,
) -> str:
    schema = {
        "recommended_strategy": "personalized strategy",
        "actions": ["action 1", "action 2", "action 3"],
        "expected_impact": "quantified business impact",
        "decision_options": [
            {
                "title": "Option A",
                "summary": "what to do",
                "tradeoff": "cost, risk, or effort tradeoff",
            },
            {
                "title": "Option B",
                "summary": "alternative path",
                "tradeoff": "cost, risk, or effort tradeoff",
            },
        ],
        "risks": ["key risk 1", "key risk 2"],
    }
    return (
        f"Language: {language}\n"
        f"User profile:\n{_compact_json(profile, ensure_ascii=True, max_chars=1800)}\n\n"
        f"Intent analysis:\n{_compact_json(intent_data, ensure_ascii=True, max_chars=900)}\n\n"
        f"Dynamic schema:\n{_compact_json(schema_data, ensure_ascii=True, max_chars=900)}\n\n"
        f"Qualification output:\n{_compact_json(qualification_data, ensure_ascii=True, max_chars=1100)}\n\n"
        f"RAG output:\n{_compact_json(rag_data, ensure_ascii=True, max_chars=1400)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=900)}"
    )


def build_decision_prompt(
    profile: Dict[str, Any],
    intent_data: Dict[str, Any],
    recommendation_data: Dict[str, Any],
    priority_hint: str,
    language: str,
) -> str:
    schema = {
        "action": "single admin-facing decision action",
        "priority": "low|medium|high",
        "justification": "short explanation",
        "steps": ["step 1", "step 2", "step 3"],
    }
    return (
        f"Language: {language}\n"
        f"User profile:\n{_compact_json(profile, ensure_ascii=True, max_chars=1800)}\n\n"
        f"Intent analysis:\n{_compact_json(intent_data, ensure_ascii=True, max_chars=900)}\n\n"
        f"Recommendation:\n{_compact_json(recommendation_data, ensure_ascii=True, max_chars=1400)}\n\n"
        f"Priority hint: {priority_hint}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=700)}"
    )


def build_response_prompt(
    language: str,
    user_message: str,
    intent_data: Dict[str, Any],
    schema_data: Dict[str, Any],
    qualification_data: Dict[str, Any],
    rag_data: Dict[str, Any],
    recommendation_data: Dict[str, Any],
    decision_data: Dict[str, Any],
) -> str:
    schema = {
        "response": "concise actionable response",
        "next_question": "optional follow-up question",
    }
    payload = {
        "language": language,
        "user_message": user_message,
        "intent": intent_data,
        "schema": schema_data,
        "qualification": qualification_data,
        "rag": rag_data,
        "recommendation": recommendation_data,
        "decision": decision_data,
    }
    return (
        "Use the payload to craft one concise response and optional next question.\n\n"
        f"Payload:\n{_compact_json(payload, ensure_ascii=False, max_chars=3200)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=400)}"
    )


def build_finalization_prompt(
    language: str,
    user_message: str,
    profile: Dict[str, Any],
    intent_data: Dict[str, Any],
    schema_data: Dict[str, Any],
    qualification_data: Dict[str, Any],
    rag_data: Dict[str, Any],
    priority_hint: str,
    priority_score: int,
) -> str:
    schema = {
        "recommendation": {
            "recommended_strategy": "personalized strategy",
            "actions": ["action 1", "action 2", "action 3"],
            "expected_impact": "quantified business impact",
            "decision_options": [
                {
                    "title": "Option A",
                    "summary": "what to do",
                    "tradeoff": "cost, risk, or effort tradeoff",
                },
                {
                    "title": "Option B",
                    "summary": "alternative path",
                    "tradeoff": "cost, risk, or effort tradeoff",
                },
            ],
            "risks": ["key risk 1", "key risk 2"],
        },
        "decision": {
            "action": "single admin-facing decision action",
            "priority": "low|medium|high",
            "justification": "short explanation",
            "steps": ["step 1", "step 2", "step 3"],
            "priority_score": priority_score,
        },
        "response": {
            "response": "concise actionable response",
            "next_question": "optional follow-up question",
        },
    }

    payload = {
        "language": language,
        "user_message": user_message,
        "profile": profile,
        "intent": intent_data,
        "schema": schema_data,
        "qualification": qualification_data,
        "rag": rag_data,
        "priority_hint": priority_hint,
        "priority_score": priority_score,
    }
    return (
        "Use the payload to produce recommendation, decision, and user response in one pass.\n\n"
        f"Payload:\n{_compact_json(payload, ensure_ascii=False, max_chars=4200)}\n\n"
        f"Return JSON with this schema:\n{_compact_json(schema, ensure_ascii=True, max_chars=1300)}"
    )


def build_unified_generation_prompt(
    language: str,
    user_message: str,
    route_data: Dict[str, Any],
    profile: Dict[str, Any],
    context: str,
    rag_context: str,
    rag_sources: list[str],
) -> str:
    schema = {
        "response": "",
        "recommendation": {
            "strategy": "",
            "actions": [""],
        },
        "risk_level": "medium",
        "requires_follow_up": True,
        "next_question": "",
    }

    payload = {
        "language": language,
        "user_message": user_message,
        "route": route_data,
        "known_profile": profile,
        "conversation_context": context,
        "rag_context": rag_context,
        "rag_sources": rag_sources,
    }

    return (
        "Produce the final answer from this payload in one pass.\n\n"
        f"Payload:\n{_compact_json(payload, ensure_ascii=False, max_chars=4200)}\n\n"
        f"Return JSON with this schema exactly:\n{_compact_json(schema, ensure_ascii=True, max_chars=550)}"
    )
