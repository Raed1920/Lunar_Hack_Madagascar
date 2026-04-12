from __future__ import annotations

import logging
from time import perf_counter
from typing import Optional

import httpx

from app.config import Settings
from app.trace_context import get_trace_id, increment_ollama_calls


logger = logging.getLogger("uvicorn.error")


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        timeout = httpx.Timeout(60.0, connect=5.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=30)
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits)

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        format_json: bool = False,
    ) -> str:
        payload = {
            "model": model or self.settings.ollama_model_fast,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }

        if format_json:
            payload["format"] = "json"

        trace_id = get_trace_id()
        call_index = increment_ollama_calls()
        request_started = perf_counter()
        logger.info(
            "[TRACE %s] ollama:call=%d model=%s prompt_len=%d",
            trace_id,
            call_index,
            payload["model"],
            len(user_prompt),
        )
        print(f"[TRACE {trace_id}] ollama:call={call_index} model={payload['model']} prompt_len={len(user_prompt)}")

        response = await self._client.post(f"{self.settings.ollama_base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        elapsed_ms = (perf_counter() - request_started) * 1000
        logger.info(
            "[TRACE %s] ollama:done call=%d status=%d ms=%.1f",
            trace_id,
            call_index,
            response.status_code,
            elapsed_ms,
        )
        # print output snippet for easier console debugging
        content_preview = data.get("message", {}).get("content", "")[:300]
        print(f"[TRACE {trace_id}] ollama:done call={call_index} status={response.status_code} ms={elapsed_ms:.1f} preview={content_preview!r}")

        message = data.get("message", {})
        return message.get("content", "").strip()
