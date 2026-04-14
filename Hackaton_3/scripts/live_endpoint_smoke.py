import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from backend.database import fetch_all, fetch_one
from backend.main import app


PAYLOAD = {
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
        "segment": "premium",
    },
    "budget_constraint": {"low": 100, "high": 800, "currency": "TND"},
    "language_preference": "bilingual",
    "tone_preference": "storytelling",
    "constraints": "No exaggerated claims",
}

CHAT_PAYLOAD = {
    "workspace_id": "11111111-1111-1111-1111-111111111111",
    "message": "I run a small natural cosmetics brand in Sousse and need a practical 2-week plan to increase sales quickly with a 150-700 TND budget.",
    "images": [
        {
            "filename": "product-shot.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 120340,
            "width": 1080,
            "height": 1350,
            "notes": "Primary product visual",
        }
    ],
}


def main() -> int:
    client = TestClient(app)

    generate_resp = client.post("/v1/marketing/generate", json=PAYLOAD)
    print(f"generate_status={generate_resp.status_code}")
    if generate_resp.status_code != 200:
        print(generate_resp.text)
        return 1

    campaign_id = generate_resp.json().get("campaign_id")
    print(f"campaign_id={campaign_id}")

    stream_resp = client.post("/v1/marketing/generate/stream", json=PAYLOAD)
    print(f"stream_status={stream_resp.status_code}")
    if stream_resp.status_code == 200:
        lines = [line for line in stream_resp.text.splitlines() if line.strip()]
        if lines:
            first_event = json.loads(lines[0])
            last_event = json.loads(lines[-1])
            print(f"stream_first_status={first_event.get('status')}")
            print(f"stream_last_status={last_event.get('status')}")

    chat_resp = client.post("/v1/marketing/chat", json=CHAT_PAYLOAD)
    print(f"chat_status={chat_resp.status_code}")
    if chat_resp.status_code == 200:
        chat_body = chat_resp.json()
        print("chat_assumptions_used=" + str(len(chat_body.get("assumptions_used", []))))
        print("chat_clarifying_questions=" + str(len(chat_body.get("clarifying_questions", []))))
        print("chat_visual_insights=" + str(len(chat_body.get("visual_insights", []))))

    creative_resp = client.post(
        "/v1/marketing/media/generate-creative-brief",
        json={
            "workspace_id": "11111111-1111-1111-1111-111111111111",
            "campaign_id": campaign_id,
            "product_name": "Pain au levain artisanal",
            "objective": "sales",
            "channel": "social_media",
            "audience": {"location": "Tunis"},
            "language_preference": "bilingual",
            "tone_preference": "storytelling",
            "style_constraints": ["warm tones", "close-up product shot"],
        },
    )
    print(f"creative_brief_status={creative_resp.status_code}")

    strategy_row = fetch_one(
        """
        SELECT model_used, latency_ms, tokens_used, created_at
        FROM campaign_strategies
        WHERE campaign_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (campaign_id,),
    )

    solution_rows = fetch_all(
        """
        SELECT model_used, latency_ms
        FROM campaign_solutions
        WHERE campaign_id = %s
        ORDER BY solution_index ASC
        """,
        (campaign_id,),
    )

    log_row = fetch_one(
        """
        SELECT prompt_version, total_latency_ms, tokens_input, tokens_output, cost_estimate, passed_critic
        FROM campaign_generation_logs
        WHERE campaign_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (campaign_id,),
    )

    print("strategy_model_used=" + str((strategy_row or {}).get("model_used")))
    print("strategy_latency_ms=" + str((strategy_row or {}).get("latency_ms")))
    print("strategy_tokens_used=" + str((strategy_row or {}).get("tokens_used")))

    solution_models = sorted({str(row.get("model_used")) for row in solution_rows})
    print("solutions_model_used=" + ",".join(solution_models))

    print("generation_prompt_version=" + str((log_row or {}).get("prompt_version")))
    print("generation_total_latency_ms=" + str((log_row or {}).get("total_latency_ms")))
    print("generation_tokens_input=" + str((log_row or {}).get("tokens_input")))
    print("generation_tokens_output=" + str((log_row or {}).get("tokens_output")))
    print("generation_cost_estimate=" + str((log_row or {}).get("cost_estimate")))
    print("generation_passed_critic=" + str((log_row or {}).get("passed_critic")))

    return 0


if __name__ == "__main__":
    sys.exit(main())
