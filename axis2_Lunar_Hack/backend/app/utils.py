from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, TypeVar

from pydantic import BaseModel, ValidationError


TModel = TypeVar("TModel", bound=BaseModel)


@dataclass
class JsonValidationResult:
    used_fallback: bool
    error: str = ""


def detect_language(text: str, preferred: Optional[str] = None) -> str:
    if preferred in {"en", "fr", "ar"}:
        return preferred

    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"

    french_markers = ["bonjour", "besoin", "objectif", "prix", "merci", "commerce"]
    lowered = text.lower()
    if any(marker in lowered for marker in french_markers):
        return "fr"

    return "en"


def parse_json_from_text(raw_text: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip()
        text = text.rstrip("`").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        return fallback

    try:
        return json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return fallback


def parse_and_validate_json(
    raw_text: str,
    model_cls: type[TModel],
    fallback: Dict[str, Any],
) -> tuple[TModel, JsonValidationResult]:
    payload = parse_json_from_text(raw_text, fallback)

    try:
        return model_cls.model_validate(payload), JsonValidationResult(used_fallback=False)
    except ValidationError as exc:
        fallback_model = model_cls.model_validate(fallback)
        short_error = str(exc).splitlines()[0].strip()
        return fallback_model, JsonValidationResult(used_fallback=True, error=short_error)


def compact_context(history: list[dict[str, str]], max_turns: int) -> str:
    window = history[-max_turns:]
    lines = [f"{item['role']}: {item['message']}" for item in window]
    return "\n".join(lines)
