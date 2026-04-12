from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings
from app.models import RAGChunk
from app.trace_context import get_trace_id, increment_ragflow_calls


logger = logging.getLogger("uvicorn.error")


class RAGFlowClient:
    SOURCE_KEYS = [
        "source",
        "document",
        "docnm_kwd",
        "doc_name",
        "document_name",
        "filename",
        "file_name",
        "name",
        "title",
        "path",
        "file_path",
        "uri",
        "url",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        timeout = httpx.Timeout(45.0, connect=5.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        self._local_source_index = self._load_local_source_index()

    async def close(self) -> None:
        await self._client.aclose()

    async def retrieve(
        self,
        query: str,
        language: str = "en",
        top_k: Optional[int] = None,
        dataset_ids: Optional[list[str]] = None,
    ) -> List[RAGChunk]:
        trace_id = get_trace_id()
        headers: Dict[str, str] = {}
        if self.settings.ragflow_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ragflow_api_key}"

        candidates = [
            "/api/v1/retrieval",
            "/api/v1/search",
        ]

        resolved_datasets = await self._resolve_dataset_ids(
            client=self._client,
            headers=headers,
            requested_ids=dataset_ids or self.settings.rag_dataset_list,
        )
        logger.info(
            "[TRACE %s] ragflow:resolved_datasets=%s",
            trace_id,
            resolved_datasets,
        )
        print(f"[TRACE {trace_id}] ragflow:resolved_datasets={resolved_datasets}")

        payload = {
            "question": query,
            "query": query,
            "dataset_ids": resolved_datasets,
            "top_k": top_k or self.settings.ragflow_top_k,
            "language": language,
        }

        for path in candidates:
            try:
                call_index = increment_ragflow_calls()
                started = perf_counter()
                response = await self._client.post(
                    f"{self.settings.ragflow_base_url}{path}",
                    json=payload,
                    headers=headers,
                )
                elapsed_ms = (perf_counter() - started) * 1000
                if response.status_code >= 400:
                    logger.warning(
                        "[TRACE %s] ragflow:done call=%d path=%s status=%d ms=%.1f chunks=0",
                        trace_id,
                        call_index,
                        path,
                        response.status_code,
                        elapsed_ms,
                    )
                    continue
                data = response.json()
                chunks = self._parse_chunks(data)
                logger.info(
                    "[TRACE %s] ragflow:done call=%d path=%s status=%d ms=%.1f chunks=%d",
                    trace_id,
                    call_index,
                    path,
                    response.status_code,
                    elapsed_ms,
                    len(chunks),
                )
                # print chunk snippets for console visibility
                preview = []
                for ch in chunks[:3]:
                    preview.append((ch.source, ch.text.strip()[:180].replace('\n',' ')))
                print(f"[TRACE {trace_id}] ragflow:done call={call_index} path={path} status={response.status_code} ms={elapsed_ms:.1f} chunks={len(chunks)} previews={preview}")
                if chunks:
                    return chunks
            except httpx.HTTPError:
                logger.exception("[TRACE %s] ragflow:http_error path=%s", trace_id, path)
                continue

        return []

    async def _resolve_dataset_ids(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        requested_ids: List[str],
    ) -> List[str]:
        trace_id = get_trace_id()
        cleaned = [value.strip() for value in requested_ids if isinstance(value, str) and value.strip()]
        if not cleaned:
            return []

        lookup: Dict[str, str] = {}
        try:
            call_index = increment_ragflow_calls()
            started = perf_counter()
            response = await client.get(f"{self.settings.ragflow_base_url}/api/v1/datasets", headers=headers)
            elapsed_ms = (perf_counter() - started) * 1000
            logger.info(
                "[TRACE %s] ragflow:done call=%d path=/api/v1/datasets status=%d ms=%.1f",
                trace_id,
                call_index,
                response.status_code,
                elapsed_ms,
            )
            if response.status_code < 400:
                payload = response.json().get("data", [])
                rows = payload if isinstance(payload, list) else []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    row_id = str(row.get("id", "")).strip()
                    row_name = str(row.get("name", "")).strip().lower()
                    if row_id:
                        lookup[row_id.lower()] = row_id
                    if row_name and row_id:
                        lookup[row_name] = row_id
        except (httpx.HTTPError, ValueError, TypeError):
            logger.exception("[TRACE %s] ragflow:dataset_resolution_error", trace_id)
            print(f"[TRACE {trace_id}] ragflow:dataset_resolution_error")
            pass

        resolved: List[str] = []
        for value in cleaned:
            key = value.lower()
            resolved.append(lookup.get(key, value))

        deduped = list(dict.fromkeys(resolved))
        return deduped

    @staticmethod
    def build_context(chunks: List[RAGChunk], max_chars: int = 2400) -> str:
        if not chunks:
            return ""

        blocks: List[str] = []
        total = 0
        for idx, chunk in enumerate(chunks, start=1):
            snippet = f"[{idx}] source={chunk.source}\n{chunk.text.strip()}"
            total += len(snippet)
            if total > max_chars:
                break
            blocks.append(snippet)

        return "\n\n".join(blocks)

    def _parse_chunks(self, payload: Dict[str, Any]) -> List[RAGChunk]:
        possible = payload.get("data", payload)

        if isinstance(possible, dict):
            for key in ["chunks", "records", "items", "docs", "results", "list"]:
                if key in possible and isinstance(possible[key], list):
                    possible = possible[key]
                    break

        if not isinstance(possible, list):
            return []

        chunks: List[RAGChunk] = []
        for item in possible:
            if not isinstance(item, dict):
                continue

            text = (
                item.get("text")
                or item.get("content")
                or item.get("content_with_weight")
                or item.get("chunk")
                or item.get("answer")
                or ""
            )
            if not text:
                continue

            score_raw = item.get("score", item.get("vector_similarity", item.get("similarity", 0.0)))
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0

            source = self._extract_source(item, text)

            chunks.append(
                RAGChunk(
                    text=text,
                    score=score,
                    source=source,
                )
            )

        return chunks

    def _extract_source(self, item: Dict[str, Any], chunk_text: str) -> str:
        # First, inspect common top-level source keys.
        direct = self._first_non_empty_value(item, self.SOURCE_KEYS)
        normalized_direct = self._normalize_source(direct)
        if normalized_direct:
            return normalized_direct

        # Then inspect nested objects commonly used by retrievers.
        nested_candidates = [
            item.get("metadata"),
            item.get("meta"),
            item.get("document"),
            item.get("doc"),
            item.get("payload"),
            item.get("extra"),
        ]
        for nested in nested_candidates:
            if isinstance(nested, dict):
                nested_value = self._first_non_empty_value(nested, self.SOURCE_KEYS)
                normalized_nested = self._normalize_source(nested_value)
                if normalized_nested:
                    return normalized_nested

        # Attempt to infer the true file source by matching chunk text to local KB docs.
        inferred_source = self._infer_source_from_text(chunk_text)
        if inferred_source:
            return inferred_source

        # Last-resort semantic source label (never expose chunk IDs as sources).
        return "knowledge_base"

    def _load_local_source_index(self) -> list[dict[str, Any]]:
        candidates = [
            Path(__file__).resolve().parents[2] / "data" / "sample_docs",
            Path(__file__).resolve().parents[1] / "data" / "sample_docs",
        ]

        index: list[dict[str, Any]] = []
        for directory in candidates:
            if not directory.exists() or not directory.is_dir():
                continue

            for file_path in sorted(directory.glob("*.txt")):
                try:
                    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                normalized_text = self._normalize_text(raw_text)
                token_set = set(re.findall(r"\w+", normalized_text, flags=re.UNICODE))
                index.append(
                    {
                        "name": file_path.name,
                        "text": normalized_text,
                        "tokens": token_set,
                    }
                )

        return index

    def _infer_source_from_text(self, chunk_text: str) -> str:
        if not self._local_source_index:
            return ""

        normalized_chunk = self._normalize_text(chunk_text)
        if len(normalized_chunk) < 24:
            return ""

        chunk_tokens = set(re.findall(r"\w+", normalized_chunk, flags=re.UNICODE))
        if not chunk_tokens:
            return ""

        best_name = ""
        best_score = 0.0

        for doc in self._local_source_index:
            doc_text = doc["text"]
            score = 0.0

            # Strong signal if a sizable normalized snippet appears directly in the file.
            probe = normalized_chunk[:180]
            if len(probe) >= 40 and probe in doc_text:
                score += 1.0

            intersection = len(chunk_tokens & doc["tokens"])
            coverage = intersection / max(min(len(chunk_tokens), 60), 1)
            score += coverage

            if score > best_score:
                best_score = score
                best_name = str(doc["name"])

        if best_score >= 0.22:
            return best_name
        return ""

    @staticmethod
    def _first_non_empty_value(data: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                continue
            text = str(value).strip() if value is not None else ""
            if text:
                return text
        return ""

    @staticmethod
    def _normalize_source(value: str) -> str:
        text = str(value or "").strip()
        lowered = text.lower()
        if not text or lowered in {"unknown", "none", "null", "n/a", "na"}:
            return ""

        if lowered.startswith("chunk:") or lowered.startswith("retrieved_chunk_"):
            return ""

        # If a path-like value is provided, prefer the basename for readability.
        if any(sep in text for sep in ["/", "\\"]):
            basename = os.path.basename(text)
            if basename.strip():
                return basename.strip()

        return text

    @staticmethod
    def _normalize_text(text: str) -> str:
        lowered = (text or "").lower()
        return re.sub(r"\s+", " ", lowered).strip()
