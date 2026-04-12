from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterator, List

import httpx


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        if end >= length:
            break
        start = max(end - overlap, 0)

    return chunks


def iter_documents(folder: Path) -> Iterator[Path]:
    for extension in ["*.md", "*.txt", "*.pdf"]:
        yield from folder.rglob(extension)


def push_chunk(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    dataset_id: str,
    document_name: str,
    chunk_id: str,
    content: str,
) -> bool:
    payload = {
        "dataset_id": dataset_id,
        "document_name": document_name,
        "chunk_id": chunk_id,
        "content": content,
        "metadata": {"source": document_name},
    }

    candidate_paths = [
        f"/api/v1/datasets/{dataset_id}/chunks",
        "/api/v1/chunks",
    ]

    for path in candidate_paths:
        try:
            response = client.post(f"{base_url}{path}", json=payload, headers=headers)
            if response.status_code < 400:
                return True
        except httpx.HTTPError:
            continue

    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Index local docs into RAGFlow")
    parser.add_argument("--docs-dir", required=True, help="Path to docs folder")
    parser.add_argument("--base-url", default="http://localhost:9380", help="RAGFlow base URL")
    parser.add_argument("--api-key", default="", help="RAGFlow API key")
    parser.add_argument("--dataset-id", default="sales-kb", help="RAGFlow dataset identifier")
    parser.add_argument("--chunk-size", type=int, default=900, help="Characters per chunk")
    parser.add_argument("--overlap", type=int, default=120, help="Chunk overlap")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs folder not found: {docs_dir}")

    headers: dict[str, str] = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    success = 0
    failed = 0

    with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        for path in iter_documents(docs_dir):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                failed += 1
                continue

            chunks = chunk_text(content, chunk_size=args.chunk_size, overlap=args.overlap)
            for index, chunk in enumerate(chunks, start=1):
                chunk_id = f"{path.stem}-{index}"
                ok = push_chunk(
                    client=client,
                    base_url=args.base_url,
                    headers=headers,
                    dataset_id=args.dataset_id,
                    document_name=str(path.name),
                    chunk_id=chunk_id,
                    content=chunk,
                )
                if ok:
                    success += 1
                else:
                    failed += 1

    print(f"Indexed chunks: {success}")
    print(f"Failed chunks: {failed}")


if __name__ == "__main__":
    main()
