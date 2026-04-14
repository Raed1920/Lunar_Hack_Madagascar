import json

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/v1/marketing/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] in {"connected", "disconnected"}


def test_generate_endpoint_returns_portfolio() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "product_name": "Pain au levain artisanal",
        "product_description": "Fresh daily bread made with natural fermentation",
        "product_category": "food_artisan",
        "objective": "sales",
        "campaign_timeline": "2 weeks",
        "audience": {
            "age_range": "25-45",
            "location": "Tunis",
            "interests": ["food", "healthy_living"],
            "segment": "premium"
        },
        "budget_constraint": {
            "low": 100,
            "high": 800,
            "currency": "TND"
        },
        "language_preference": "bilingual",
        "tone_preference": "storytelling",
        "constraints": "No exaggerated claims"
    }

    response = client.post("/v1/marketing/generate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "campaign_id" in data
    assert len(data["solutions"]) >= 3
    assert data["portfolio_summary"]["total_solutions"] >= 3


def test_campaign_details_endpoint() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "product_name": "Product for retrieval",
        "objective": "awareness",
        "audience": {
            "location": "Tunis",
            "interests": ["marketing"],
            "segment": "small_business"
        },
        "budget_constraint": {
            "low": 80,
            "high": 300,
            "currency": "TND"
        },
        "language_preference": "auto",
        "constraints": "Stay realistic"
    }

    generated = client.post("/v1/marketing/generate", json=payload)
    assert generated.status_code == 200
    campaign_id = generated.json()["campaign_id"]

    details = client.get(f"/v1/marketing/campaign/{campaign_id}")
    assert details.status_code == 200
    body = details.json()
    assert body["campaign_id"] == campaign_id
    assert body["status"] == "generated"
    assert isinstance(body["solutions"], list)


def test_generate_stream_endpoint_emits_progress() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "product_name": "Pain complet",
        "objective": "awareness",
        "audience": {
            "location": "Tunis",
            "interests": ["food", "wellness"],
            "segment": "families"
        },
        "budget_constraint": {
            "low": 50,
            "high": 400,
            "currency": "TND"
        },
        "language_preference": "auto"
    }

    response = client.post("/v1/marketing/generate/stream", json=payload)
    assert response.status_code == 200

    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) >= 3

    first_event = json.loads(lines[0])
    last_event = json.loads(lines[-1])

    assert first_event["status"] == "analyzing"
    assert last_event["status"] == "completed"
    assert "campaign_id" in last_event["data"]


def test_generate_creative_brief_endpoint() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "product_name": "Pain au levain artisanal",
        "objective": "sales",
        "channel": "social_media",
        "audience": {
            "location": "Tunis"
        },
        "language_preference": "bilingual",
        "tone_preference": "storytelling",
        "style_constraints": ["warm tones", "close-up product shot"]
    }

    response = client.post("/v1/marketing/media/generate-creative-brief", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["channel"] == "social_media"
    assert body["recommended_aspect_ratio"] == "4:5"
    assert "image_prompt" in body
    assert "canva_template_suggestion" in body


def test_chat_endpoint_accepts_message_and_image_pack() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "message": "I run a small natural cosmetics brand in Sousse and need a practical 2-week plan to increase sales quickly with a 150-700 TND budget.",
        "images": [
            {
                "filename": "product-shot.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 120340,
                "width": 1080,
                "height": 1350,
                "notes": "Primary product visual"
            }
        ]
    }

    response = client.post("/v1/marketing/chat", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "generated"
    assert body["campaign_id"]
    assert isinstance(body.get("assistant_message"), str)
    assert body["result"]["campaign_id"] == body["campaign_id"]
    assert isinstance(body.get("clarifying_questions", []), list)
    assert isinstance(body.get("visual_insights", []), list)
    assert isinstance(body.get("assumptions_used", []), list)


def test_chat_endpoint_requests_clarification_for_vague_prompt() -> None:
    payload = {
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "message": "Help me market my business",
    }

    response = client.post("/v1/marketing/chat", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "question_asked"
    assert body.get("result") is None
    assert body.get("campaign_id") is None
    assert len(body.get("clarifying_questions", [])) >= 1
    assert isinstance(body.get("assistant_message"), str)
    assert "?" in body.get("assistant_message", "")


def test_quality_test_ui_endpoint_serves_html() -> None:
    response = client.get("/v1/marketing/ui/quality-test")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Pillar 3 Quality Chat Test" in response.text


def test_n8n_impact_endpoint_returns_summary() -> None:
    response = client.get(
        "/v1/marketing/ops/n8n-impact",
        params={"workspace_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == "11111111-1111-1111-1111-111111111111"
    assert isinstance(body.get("workflow_calls", []), list)
    assert isinstance(body.get("impact_snapshot", {}), dict)


def test_trigger_workflows_endpoint_returns_result_list() -> None:
    response = client.post(
        "/v1/marketing/ops/workflows/trigger",
        params={
            "workspace_id": "11111111-1111-1111-1111-111111111111",
            "run_signal": True,
            "run_learning": True,
            "run_publish": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == "11111111-1111-1111-1111-111111111111"
    assert isinstance(body.get("results", []), list)
