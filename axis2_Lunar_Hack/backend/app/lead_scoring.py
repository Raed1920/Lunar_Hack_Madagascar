from __future__ import annotations

from typing import Any, Dict


def _budget_points(budget: str | None) -> int:
    if not budget:
        return 0

    normalized = budget.lower()
    if any(token in normalized for token in ["10000", "high", "enterprise", "large"]):
        return 30
    if any(token in normalized for token in ["5000", "medium", "mid"]):
        return 18
    return 10


def _intent_points(intent: str) -> int:
    normalized = intent.lower()
    if normalized in {"execute", "buy", "purchase", "subscribe", "meeting"}:
        return 28
    if normalized in {"plan", "optimize", "diagnose", "risk_check", "compare", "evaluate", "consideration"}:
        return 18
    if normalized in {"information", "support"}:
        return 10
    return 12


def _urgency_points(urgency: str) -> int:
    normalized = (urgency or "").lower()
    if normalized == "critical":
        return 18
    if normalized == "high":
        return 13
    if normalized == "medium":
        return 8
    if normalized == "low":
        return 4
    return 6


def _completeness_points(profile: Dict[str, Any], required_fields: list[str] | None = None) -> int:
    keys = required_fields or ["business_type", "budget", "goals", "timeline"]
    normalized_keys = [key for key in keys if key]
    if not normalized_keys:
        return 0

    completed = 0
    for key in normalized_keys:
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            completed += 1
            continue
        if value is not None and value != "":
            completed += 1

    return int((completed / len(normalized_keys)) * 22)


def compute_lead_score(
    profile: Dict[str, Any],
    intent: str,
    confidence: float,
    turns: int,
    urgency: str = "medium",
    required_fields: list[str] | None = None,
) -> int:
    score = 0
    score += _budget_points(profile.get("budget"))
    score += _intent_points(intent)
    score += _urgency_points(urgency)
    score += _completeness_points(profile, required_fields=required_fields)

    score += min(int(confidence * 12), 12)
    score += min(turns, 8)

    return max(0, min(score, 100))


def compute_decision_priority(
    urgency: str,
    confidence: float,
    missing_fields: list[str],
    action_count: int,
    risk_count: int,
) -> tuple[str, int]:
    urgency_points = {
        "low": 20,
        "medium": 45,
        "high": 70,
        "critical": 85,
    }
    score = urgency_points.get((urgency or "medium").lower(), 45)
    score += min(max(int(confidence * 18), 0), 18)
    score += min(action_count * 3, 12)
    score += min(risk_count * 2, 10)
    score -= min(len(missing_fields) * 7, 21)
    score = max(0, min(score, 100))

    if score >= 70:
        return "high", score
    if score >= 40:
        return "medium", score
    return "low", score
