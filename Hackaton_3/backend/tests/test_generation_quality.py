from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_generate_response_quality_gate() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "product_name": "Pain au levain artisanal",
        "product_description": "Launch a local campaign in Tunis with strong weekly repeat sales",
        "product_category": "food_artisan",
        "objective": "sales",
        "campaign_timeline": "2 weeks",
        "audience": {
            "location": "Tunis",
            "interests": ["food", "healthy_living", "artisan_products"],
            "segment": "premium"
        },
        "budget_constraint": {
            "low": 100,
            "high": 900,
            "currency": "TND"
        },
        "language_preference": "bilingual",
        "tone_preference": "storytelling",
        "constraints": "No exaggerated claims"
    }

    response = client.post("/v1/marketing/generate", json=payload)
    assert response.status_code == 200

    data = response.json()
    solutions = data.get("solutions", [])
    strategic_options = data.get("strategic_options", [])

    assert len(solutions) >= 5, f"Expected >=5 solutions, got {len(solutions)}"

    channels = {item.get("channel") for item in solutions}
    assert len(channels) >= 3, f"Expected >=3 channels, got {len(channels)}"

    assert len(data.get("market_signals_used", [])) >= 2, "Expected at least 2 market signals"
    assert float(data.get("confidence_overall", 0.0)) >= 0.60, "Low overall confidence"
    explanation_len = len(str(data.get("assistant_explanation", "")).strip())
    assert explanation_len >= 100, "Assistant explanation is too short"
    assert explanation_len <= 900, "Assistant explanation is too long"
    explanation = str(data.get("assistant_explanation", ""))
    assert "Strategy:" in explanation, "Assistant output missing Strategy section"
    assert "Insight:" in explanation, "Assistant output missing Insight section"
    assert "Marketing Post:" in explanation, "Assistant output missing Marketing Post section"
    assert "Hashtags:" in explanation, "Assistant output missing Hashtags section"
    assert "Image Prompt:" in explanation, "Assistant output missing Image Prompt section"
    assert len(str(data.get("recommended_path", "")).strip()) >= 40, "Recommended path is too short"
    assert len(str(data.get("recommended_path", "")).strip()) <= 450, "Recommended path is too long"
    assert len(data.get("insights", [])) >= 1, "Expected at least 1 insight"
    assert len(data.get("next_7_days_plan", [])) == 7, "Expected exactly 7-day action plan entries"

    assert len(strategic_options) >= 5, f"Expected >=5 strategic options, got {len(strategic_options)}"
    option_keys = [str(option.get("option_key", "")).strip() for option in strategic_options]
    assert all(option_keys), "Every strategic option must have a non-empty option_key"
    assert len(set(option_keys)) == len(option_keys), "Strategic option keys must be unique"
    recommended_count = sum(1 for option in strategic_options if bool(option.get("recommended")))
    assert recommended_count >= 2, "Expected at least two recommended strategic options"

    has_quick_win = False
    has_scale_play = False

    for idx, solution in enumerate(solutions):
        reasoning = str(solution.get("reasoning", "")).strip()
        assert len(reasoning) >= 30, f"Solution {idx} has weak reasoning text"

        execution = solution.get("execution", {})
        assert str(execution.get("image_prompt", "")).strip(), f"Solution {idx} missing image_prompt"
        assert str(execution.get("exact_copy", "")).strip(), f"Solution {idx} missing exact_copy"
        assert str(execution.get("cta_text", "")).strip(), f"Solution {idx} missing cta_text"

        budget = solution.get("budget", {})
        total_low = float(budget.get("total_low", 0))
        total_high = float(budget.get("total_high", 0))

        assert total_low <= total_high, f"Solution {idx} has invalid budget range"

        if total_high <= 150:
            has_quick_win = True
        if total_high >= 500:
            has_scale_play = True

        assert solution.get("execution"), f"Solution {idx} missing execution block"
        assert solution.get("expected_outcomes"), f"Solution {idx} missing expected outcomes"

    for idx, option in enumerate(strategic_options):
        assert str(option.get("title", "")).strip(), f"Strategic option {idx} missing title"
        why_text = str(option.get("why_it_fits", "")).strip()
        assert why_text, f"Strategic option {idx} missing explanation"
        assert len(why_text) >= 30, f"Strategic option {idx} explanation is too short"
        budget = option.get("budget_range_tnd", {})
        low = float(budget.get("low", 0))
        high = float(budget.get("high", 0))
        assert low <= high, f"Strategic option {idx} has invalid budget range"
        assert len(option.get("first_actions", [])) >= 2, f"Strategic option {idx} has too few first actions"

    assert has_quick_win, "Missing quick-win low-budget solution"
    assert has_scale_play, "Missing scale-play high-budget solution"
