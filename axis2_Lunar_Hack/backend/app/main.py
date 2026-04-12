from __future__ import annotations

import logging
from time import perf_counter
from typing import List
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.crew_orchestrator import SalesIntelligenceOrchestrator
from app.models import ChatRequest, ChatResponse, SessionMessage, SessionSummary
from app.trace_context import get_call_counts, reset_request_trace, set_request_trace

settings = get_settings()
orchestrator = SalesIntelligenceOrchestrator(settings)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Dynamic multi-agent decision engine using Ollama + RAGFlow + FastAPI",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await orchestrator.close()


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "crewai_enabled": orchestrator.crewai_enabled,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    trace_id = uuid4().hex[:8]
    tokens = set_request_trace(trace_id, request.session_id, request.user_id)
    started_at = perf_counter()
    logger.info(
        "[TRACE %s] chat:start session=%s user=%s message_len=%d",
        trace_id,
        request.session_id,
        request.user_id,
        len(request.message),
    )
    print(f"[TRACE {trace_id}] chat:start session={request.session_id} user={request.user_id} message_len={len(request.message)}")
    try:
        response = await orchestrator.handle_chat(request)
        # print a concise response preview to console for UI debugging
        print(f"[TRACE {trace_id}] chat:response preview={response.response[:200]!r} rag_sources={response.rag_sources}")
        elapsed_ms = (perf_counter() - started_at) * 1000
        counts = get_call_counts()
        logger.info(
            "[TRACE %s] chat:done total_ms=%.1f ollama_calls=%d ragflow_calls=%d rag_sources=%d",
            trace_id,
            elapsed_ms,
            counts["ollama"],
            counts["ragflow"],
            len(response.rag_sources),
        )
        print(f"[TRACE {trace_id}] chat:done total_ms={elapsed_ms:.1f}ms ollama_calls={counts['ollama']} ragflow_calls={counts['ragflow']} rag_sources={len(response.rag_sources)}")
        return response
    except httpx.HTTPError as exc:
        elapsed_ms = (perf_counter() - started_at) * 1000
        counts = get_call_counts()
        logger.error(
            "[TRACE %s] chat:upstream_error total_ms=%.1f ollama_calls=%d ragflow_calls=%d error=%s",
            trace_id,
            elapsed_ms,
            counts["ollama"],
            counts["ragflow"],
            exc,
        )
        print(f"[TRACE {trace_id}] chat:upstream_error total_ms={elapsed_ms:.1f}ms ollama_calls={counts['ollama']} ragflow_calls={counts['ragflow']} error={exc}")
        raise HTTPException(status_code=502, detail=f"Upstream service error: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        elapsed_ms = (perf_counter() - started_at) * 1000
        counts = get_call_counts()
        logger.exception(
            "[TRACE %s] chat:unhandled_error total_ms=%.1f ollama_calls=%d ragflow_calls=%d",
            trace_id,
            elapsed_ms,
            counts["ollama"],
            counts["ragflow"],
        )
        print(f"[TRACE {trace_id}] chat:unhandled_error total_ms={elapsed_ms:.1f}ms ollama_calls={counts['ollama']} ragflow_calls={counts['ragflow']} error={exc}")
        if settings.debug:
            raise HTTPException(status_code=500, detail=f"Unhandled error: {exc}") from exc
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    finally:
        reset_request_trace(tokens)


@app.get("/sessions/{user_id}", response_model=List[SessionSummary])
async def list_sessions(user_id: str, limit: int = 30) -> List[SessionSummary]:
    safe_limit = max(1, min(limit, 100))
    rows = orchestrator.memory_store.list_sessions(user_id=user_id, limit=safe_limit)
    return [SessionSummary.model_validate(row) for row in rows]


@app.get("/sessions/{user_id}/{session_id}/messages", response_model=List[SessionMessage])
async def get_session_messages(user_id: str, session_id: str, limit: int = 300) -> List[SessionMessage]:
    safe_limit = max(1, min(limit, 500))
    rows = orchestrator.memory_store.get_session_messages(
        user_id=user_id,
        session_id=session_id,
        limit=safe_limit,
    )
    return [SessionMessage.model_validate(row) for row in rows]
