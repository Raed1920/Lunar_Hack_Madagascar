import asyncio

from backend.config import Settings
from backend.services.llm_router import LLMRouter


def test_router_fallbacks_from_groq_to_gemini(monkeypatch) -> None:
    settings = Settings(
        llm_primary_provider="groq",
        llm_fallback_provider="gemini",
        groq_api_key="groq_test_key",
        gemini_api_key="gemini_test_key",
        llm_max_retries=0,
    )
    router = LLMRouter(settings)

    monkeypatch.setattr(router, "_provider_order", lambda: ["groq", "gemini", "local"])
    monkeypatch.setattr(router, "_provider_ready", lambda _: True)

    async def fake_call(provider: str, prompt: str, timeout: int):
        if provider == "groq":
            raise RuntimeError("rate limit")
        return (
            "gemini-1.5-flash",
            '{"status":"ok","source":"gemini"}',
            {"status": "ok", "source": "gemini"},
            42,
            18,
        )

    monkeypatch.setattr(router, "_call_provider", fake_call)

    result = asyncio.run(
        router.try_generate_json(
            "strategy_planner",
            "prompt",
            respect_test_local=False,
        )
    )
    assert result is not None
    assert result.provider == "gemini"
    assert result.model == "gemini-1.5-flash"
    assert result.data == {"status": "ok", "source": "gemini"}
    assert result.input_tokens_estimate == 42
    assert result.output_tokens_estimate == 18


def test_router_fallbacks_to_local_when_apis_fail(monkeypatch) -> None:
    settings = Settings(
        llm_primary_provider="groq",
        llm_fallback_provider="gemini",
        groq_api_key="groq_test_key",
        gemini_api_key="gemini_test_key",
        llm_max_retries=0,
    )
    router = LLMRouter(settings)

    monkeypatch.setattr(router, "_provider_order", lambda: ["groq", "gemini", "local"])
    monkeypatch.setattr(router, "_provider_ready", lambda _: True)

    async def fake_call(provider: str, prompt: str, timeout: int):
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr(router, "_call_provider", fake_call)

    result = asyncio.run(
        router.try_generate_json(
            "solutions_generator",
            "prompt",
            respect_test_local=False,
        )
    )
    assert result is not None
    assert result.provider == "local"
    assert result.model == "local_rules"
    assert result.data is None


def test_vision_router_fallbacks_from_groq_to_gemini(monkeypatch) -> None:
    settings = Settings(
        llm_primary_provider="groq",
        llm_fallback_provider="gemini",
        groq_api_key="groq_test_key",
        gemini_api_key="gemini_test_key",
        llm_max_retries=0,
    )
    router = LLMRouter(settings)

    monkeypatch.setattr(router, "_vision_provider_order", lambda: ["groq", "gemini", "local"])
    monkeypatch.setattr(router, "_provider_ready", lambda _: True)

    async def fake_call(provider: str, prompt: str, images: list[dict[str, str]], timeout: int):
        if provider == "groq":
            raise RuntimeError("groq vision not available")
        return (
            "gemini-1.5-flash",
            '{"images":[{"filename":"x.jpg","quality_score":0.8,"priority":"medium","findings":["ok"],"recommendations":["tighten CTA"]}]}',
            {
                "images": [
                    {
                        "filename": "x.jpg",
                        "quality_score": 0.8,
                        "priority": "medium",
                        "findings": ["ok"],
                        "recommendations": ["tighten CTA"],
                    }
                ]
            },
            64,
            28,
        )

    monkeypatch.setattr(router, "_call_provider_vision", fake_call)

    result = asyncio.run(
        router.try_generate_vision_json(
            "visual_critic_agent",
            "prompt",
            [{"filename": "x.jpg", "mime_type": "image/jpeg", "data_base64": "abcd"}],
            respect_test_local=False,
        )
    )
    assert result is not None
    assert result.provider == "gemini"
    assert result.model == "gemini-1.5-flash"
    assert isinstance(result.data, dict)
    assert result.input_tokens_estimate == 64
    assert result.output_tokens_estimate == 28
