from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_session_id: ContextVar[str] = ContextVar("session_id", default="-")
_user_id: ContextVar[str] = ContextVar("user_id", default="-")
_ollama_calls: ContextVar[int] = ContextVar("ollama_calls", default=0)
_ragflow_calls: ContextVar[int] = ContextVar("ragflow_calls", default=0)


@dataclass
class TraceTokens:
    trace_id: Token[str]
    session_id: Token[str]
    user_id: Token[str]
    ollama_calls: Token[int]
    ragflow_calls: Token[int]


def set_request_trace(trace_id: str, session_id: str, user_id: str) -> TraceTokens:
    return TraceTokens(
        trace_id=_trace_id.set(trace_id),
        session_id=_session_id.set(session_id),
        user_id=_user_id.set(user_id),
        ollama_calls=_ollama_calls.set(0),
        ragflow_calls=_ragflow_calls.set(0),
    )


def reset_request_trace(tokens: TraceTokens) -> None:
    _trace_id.reset(tokens.trace_id)
    _session_id.reset(tokens.session_id)
    _user_id.reset(tokens.user_id)
    _ollama_calls.reset(tokens.ollama_calls)
    _ragflow_calls.reset(tokens.ragflow_calls)


def get_trace_id() -> str:
    return _trace_id.get()


def get_session_id() -> str:
    return _session_id.get()


def get_user_id() -> str:
    return _user_id.get()


def increment_ollama_calls() -> int:
    current = _ollama_calls.get() + 1
    _ollama_calls.set(current)
    return current


def increment_ragflow_calls() -> int:
    current = _ragflow_calls.get() + 1
    _ragflow_calls.set(current)
    return current


def get_call_counts() -> dict[str, int]:
    return {
        "ollama": _ollama_calls.get(),
        "ragflow": _ragflow_calls.get(),
    }
