from __future__ import annotations

import json
from typing import Any, Dict, TypeVar

from pydantic import BaseModel

from app.config import Settings
from app.ollama_client import OllamaClient
from app.utils import parse_and_validate_json
from app.trace_context import get_trace_id


TModel = TypeVar("TModel", bound=BaseModel)


class BaseJsonAgent:
    def __init__(
        self,
        settings: Settings,
        ollama: OllamaClient,
        stage_name: str,
        system_prompt: str,
        use_reasoning_model: bool,
    ):
        self.settings = settings
        self.ollama = ollama
        self.stage_name = stage_name
        self.system_prompt = system_prompt
        self.use_reasoning_model = use_reasoning_model

    async def run_contract(
        self,
        user_prompt: str,
        model_cls: type[TModel],
        fallback: Dict[str, Any],
    ) -> TModel:
        raw = await self._ask_model(user_prompt)
        model, validation = parse_and_validate_json(raw, model_cls, fallback)
        if not validation.used_fallback or not self.settings.agent_json_repair_retry:
            return model

        repair_prompt = (
            "The previous output was invalid. Return strict JSON only.\n"
            f"Required keys example: {json.dumps(fallback, ensure_ascii=True)}\n\n"
            f"Original input:\n{user_prompt}"
        )
        repaired_raw = await self._ask_model(repair_prompt)
        repaired_model, repaired_validation = parse_and_validate_json(
            repaired_raw,
            model_cls,
            fallback,
        )
        if repaired_validation.used_fallback:
            return model

        return repaired_model

    async def _ask_model(self, user_prompt: str) -> str:
        model_name = (
            self.settings.ollama_model_reasoning
            if self.use_reasoning_model
            else self.settings.ollama_model_fast
        )
        trace_id = get_trace_id()
        # print prompt for debugging
        try:
            print(f"[TRACE {trace_id}] agent={self.stage_name} prompt_len={len(user_prompt)} system_prompt_len={len(self.system_prompt)}")
        except Exception:
            print(f"[TRACE {trace_id}] agent={self.stage_name} prompt (could not measure length)")

        raw = await self.ollama.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            model=model_name,
            format_json=True,
        )
        # print model raw output for traceability (trim large outputs)
        try:
            print(f"[TRACE {trace_id}] agent={self.stage_name} raw_out={raw[:600]!r}")
        except Exception:
            print(f"[TRACE {trace_id}] agent={self.stage_name} raw_out (unprintable)")

        return raw
