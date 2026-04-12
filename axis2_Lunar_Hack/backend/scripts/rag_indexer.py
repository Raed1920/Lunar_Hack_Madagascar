from __future__ import annotations

import argparse
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List

import httpx

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


SUCCESS_CODES = {0, 200}
UNAUTHORIZED_CODES = {401, 403}
DEFAULT_EXTENSIONS = ".md,.txt,.pdf,.doc,.docx,.csv,.json,.html,.htm"


@dataclass
class KBRef:
    kb_id: str
    name: str


class RAGFlowError(RuntimeError):
    pass


class RAGFlowIndexer:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        email: str = "",
        password: str = "",
        timeout_s: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.email = email.strip()
        self.password = password
        self.client = httpx.Client(timeout=httpx.Timeout(timeout_s, connect=8.0))
        self._logged_in = False
        self._login_failed = False
        self._login_error = ""

    def close(self) -> None:
        self.client.close()

    def auth_variants(self) -> list[dict[str, str]]:
        variants: list[dict[str, str]] = []
        if self.api_key:
            variants.extend(
                [
                    {"Authorization": f"Bearer {self.api_key}"},
                    {"Authorization": f"Token {self.api_key}"},
                    {"X-API-Key": self.api_key},
                    {"Api-Key": self.api_key},
                    {"X-Auth-Token": self.api_key},
                    {"Authorization": self.api_key},
                ]
            )

        # Keep an empty-header variant to support cookie/session auth after login.
        variants.append({})
        return variants

    def login(self) -> bool:
        if not self.email or not self.password:
            self._login_error = "Missing email/password for login fallback."
            return False
        if self._logged_in:
            return True
        if self._login_failed:
            return False

        try:
            response = self.client.post(
                f"{self.base_url}/v1/user/login",
                json={"email": self.email, "password": self.password},
            )
        except httpx.HTTPError:
            self._login_error = "HTTP error while calling /v1/user/login."
            self._login_failed = True
            return False

        payload = self._to_json(response)
        if not self._is_success(response, payload):
            self._login_error = self._extract_message(payload) or "Unknown login error"
            self._login_failed = True
            return False

        data = self._extract_data(payload)
        if isinstance(data, dict):
            token = (
                data.get("token")
                or data.get("access_token")
                or data.get("api_key")
                or data.get("authorization")
            )
            if token:
                self.api_key = str(token).strip()

        self._logged_in = True
        return True

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        strict: bool = True,
    ) -> dict[str, Any] | None:
        if not path.startswith("/"):
            path = f"/{path}"

        last_error = "request failed"
        attempted_login = False

        while True:
            for headers in self.auth_variants():
                try:
                    response = self.client.request(
                        method=method,
                        url=f"{self.base_url}{path}",
                        headers=headers,
                        json=json_body,
                        data=form_data,
                        files=files,
                    )
                except httpx.HTTPError as exc:
                    last_error = f"HTTP error on {path}: {exc}"
                    continue

                payload = self._to_json(response)

                if self._is_unauthorized(response, payload):
                    last_error = (
                        "Unauthorized. Provide a valid API key with --api-key "
                        "or set RAGFLOW_API_KEY. You can also use --email and --password "
                        "(or RAGFLOW_EMAIL / RAGFLOW_PASSWORD) for login fallback."
                    )
                    if self._login_error:
                        last_error += f" Login error: {self._login_error}."
                    continue

                if self._is_success(response, payload):
                    return payload

                message = self._extract_message(payload) or response.text[:240]
                last_error = f"{path} failed: {message}"
                if strict:
                    raise RAGFlowError(last_error)
                return None

            if attempted_login:
                break
            attempted_login = True

            if not self.login():
                break

        if strict:
            raise RAGFlowError(last_error)
        return None

    @staticmethod
    def _to_json(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {"status_code": response.status_code, "raw": response.text}

        if isinstance(data, dict):
            data.setdefault("status_code", response.status_code)
            return data

        return {"status_code": response.status_code, "data": data}

    @staticmethod
    def _is_success(response: httpx.Response, payload: dict[str, Any]) -> bool:
        if response.status_code >= 400:
            return False

        message = str(payload.get("message", "")).lower()
        if "authorization format" in message or "unauthorized" in message:
            return False

        code = payload.get("code")
        if code is None:
            return True

        return int(code) in SUCCESS_CODES

    @staticmethod
    def _is_unauthorized(response: httpx.Response, payload: dict[str, Any]) -> bool:
        if response.status_code in UNAUTHORIZED_CODES:
            return True

        code = payload.get("code")
        if code is not None and int(code) in UNAUTHORIZED_CODES:
            return True

        message = str(payload.get("message", ""))
        lowered = message.lower()
        return "unauthorized" in lowered or "authorization format" in lowered

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        return str(payload.get("message") or payload.get("raw") or "").strip()

    @staticmethod
    def _extract_data(payload: dict[str, Any]) -> Any:
        if "data" in payload:
            return payload["data"]
        return payload

    @classmethod
    def _extract_items(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = cls._extract_data(payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            for key in ["kbs", "datasets", "items", "list", "records", "rows"]:
                maybe = data.get(key)
                if isinstance(maybe, list):
                    return [item for item in maybe if isinstance(item, dict)]

            for value in data.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return value

        return []

    @staticmethod
    def _pick_kb_id(item: dict[str, Any]) -> str:
        for key in ["id", "kb_id", "dataset_id", "uuid"]:
            value = item.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _pick_kb_name(item: dict[str, Any]) -> str:
        for key in ["name", "kb_name", "dataset_name", "title"]:
            value = item.get(key)
            if value:
                return str(value)
        return ""

    def list_kbs(self) -> list[KBRef]:
        candidates = [
            ("POST", "/v1/kb/list", {"keywords": "", "page_size": 200, "page": 1}),
            ("GET", "/api/v1/datasets", None),
        ]

        last_error = "No list endpoint succeeded"
        for method, path, body in candidates:
            try:
                payload = self.request(method, path, json_body=body)
                assert payload is not None
            except (RAGFlowError, AssertionError) as exc:
                last_error = str(exc)
                continue

            items = self._extract_items(payload)
            refs: list[KBRef] = []
            for item in items:
                kb_id = self._pick_kb_id(item)
                kb_name = self._pick_kb_name(item)
                if kb_id and kb_name:
                    refs.append(KBRef(kb_id=kb_id, name=kb_name))
            return refs

        raise RAGFlowError(last_error)

    def create_kb(self, dataset_name: str, embedding_model: str) -> KBRef:
        api_payloads: list[dict[str, Any]] = [{"name": dataset_name}]
        # /api/v1/datasets accepts model identifiers like <model>@<provider>.
        if embedding_model and "@" in embedding_model:
            api_payloads.append({"name": dataset_name, "embedding_model": embedding_model})

        candidates = [
            ("POST", "/v1/kb/create", {"name": dataset_name, "embedding_model": embedding_model}),
            (
                "POST",
                "/v1/kb/create",
                {
                    "kb_name": dataset_name,
                    "embedding_model": embedding_model,
                    "description": "Indexed by rag_indexer.py",
                },
            ),
        ]

        for payload in api_payloads:
            candidates.append(("POST", "/api/v1/datasets", payload))

        last_error = "KB creation failed"
        for method, path, body in candidates:
            try:
                payload = self.request(method, path, json_body=body)
                assert payload is not None
            except (RAGFlowError, AssertionError) as exc:
                last_error = str(exc)
                continue

            data = self._extract_data(payload)
            if isinstance(data, dict):
                kb_id = self._pick_kb_id(data)
                kb_name = self._pick_kb_name(data) or dataset_name
                if kb_id:
                    return KBRef(kb_id=kb_id, name=kb_name)

            # Fallback: fetch from list after create if create response has no ID.
            kbs = self.list_kbs()
            maybe = self.find_kb(kbs, dataset_name)
            if maybe:
                return maybe

        raise RAGFlowError(last_error)

    @staticmethod
    def find_kb(kbs: list[KBRef], dataset_id_or_name: str) -> KBRef | None:
        target = dataset_id_or_name.strip().lower()
        for kb in kbs:
            if kb.kb_id.lower() == target or kb.name.lower() == target:
                return kb
        return None

    def upload_file(self, kb: KBRef, file_path: Path, verbose: bool = False) -> bool:
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

        candidates = [
            (
                "POST",
                "/v1/document/upload",
                {"kb_id": kb.kb_id},
                "file",
            ),
            (
                "POST",
                "/v1/document/upload",
                {"kb_name": kb.name},
                "file",
            ),
            (
                "POST",
                "/v1/document/upload",
                {"dataset_id": kb.kb_id},
                "file",
            ),
            (
                "POST",
                f"/api/v1/datasets/{kb.kb_id}/documents",
                {},
                "file",
            ),
            (
                "POST",
                f"/api/v1/datasets/{kb.kb_id}/documents/upload",
                {},
                "file",
            ),
            (
                "POST",
                "/v1/document/upload",
                {"kb_id": kb.kb_id},
                "files",
            ),
        ]

        for method, path, form_data, field in candidates:
            try:
                with file_path.open("rb") as stream:
                    files = {field: (file_path.name, stream, mime)}
                    payload = self.request(
                        method=method,
                        path=path,
                        form_data=form_data,
                        files=files,
                        strict=False,
                    )

                if payload is not None:
                    if verbose:
                        print(f"Uploaded: {file_path.name} via {path} [{field}]")
                    return True
            except OSError:
                return False

        if verbose:
            print(f"Failed upload: {file_path.name}")
        return False

    def start_parsing(self, kb_id: str, verbose: bool = False) -> bool:
        list_payload = self.request(
            "GET",
            f"/api/v1/datasets/{kb_id}/documents",
            strict=False,
        )
        if not list_payload:
            if verbose:
                print("Parse skipped: failed to list documents")
            return False

        data = self._extract_data(list_payload)
        docs: list[dict[str, Any]] = []
        if isinstance(data, dict):
            maybe_docs = data.get("docs")
            if isinstance(maybe_docs, list):
                docs = [item for item in maybe_docs if isinstance(item, dict)]

        if not docs:
            if verbose:
                print("Parse skipped: no documents found")
            return False

        parse_candidates: list[str] = []
        for item in docs:
            doc_id = item.get("id")
            if not doc_id:
                continue
            run_state = str(item.get("run", "")).upper()
            progress = item.get("progress", 0)
            try:
                progress_value = float(progress)
            except (TypeError, ValueError):
                progress_value = 0.0

            if run_state in {"DONE", "SUCCESS", "FINISH", "COMPLETED"} or progress_value >= 1.0:
                continue

            parse_candidates.append(str(doc_id))

        if not parse_candidates:
            if verbose:
                print("Parse skipped: no pending documents")
            return True

        parse_payload = self.request(
            "POST",
            f"/api/v1/datasets/{kb_id}/chunks",
            json_body={"document_ids": parse_candidates},
            strict=False,
        )
        if not parse_payload:
            if verbose:
                print("Parse request failed")
            return False

        if verbose:
            print(f"Parse started for {len(parse_candidates)} documents")
        return True

    def list_documents(self, kb_id: str) -> list[dict[str, Any]]:
        list_payload = self.request(
            "GET",
            f"/api/v1/datasets/{kb_id}/documents",
            strict=False,
        )
        if not list_payload:
            return []

        data = self._extract_data(list_payload)
        if isinstance(data, dict):
            docs = data.get("docs")
            if isinstance(docs, list):
                return [item for item in docs if isinstance(item, dict)]

        return []

    def wait_for_parse_completion(
        self,
        kb_id: str,
        timeout_s: int,
        poll_interval_s: int,
        verbose: bool = False,
    ) -> tuple[bool, list[dict[str, Any]]]:
        deadline = time.time() + max(timeout_s, 1)
        last_docs: list[dict[str, Any]] = []

        while time.time() < deadline:
            docs = self.list_documents(kb_id)
            if docs:
                last_docs = docs
                done = 0
                failed = 0
                for doc in docs:
                    run = str(doc.get("run", "")).upper()
                    progress = doc.get("progress", 0)
                    try:
                        progress_value = float(progress)
                    except (TypeError, ValueError):
                        progress_value = 0.0

                    if run in {"DONE", "SUCCESS", "COMPLETED"} or progress_value >= 1.0:
                        done += 1
                    elif run in {"FAIL", "FAILED", "ERROR"}:
                        failed += 1

                if verbose:
                    print(f"Parse progress: done={done} failed={failed} total={len(docs)}")

                if done + failed >= len(docs):
                    return failed == 0, docs

            time.sleep(max(poll_interval_s, 1))

        return False, last_docs


def iter_files(folder: Path, allowed_exts: set[str]) -> Iterable[Path]:
    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in allowed_exts:
            continue
        yield file_path


def parse_extensions(raw: str) -> set[str]:
    items = [item.strip().lower() for item in raw.split(",") if item.strip()]
    normalized = {item if item.startswith(".") else f".{item}" for item in items}
    return normalized


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()
        backend_env = Path(__file__).resolve().parents[1] / ".env"
        if backend_env.exists():
            load_dotenv(backend_env, override=False)

    parser = argparse.ArgumentParser(
        description="Upload local documents to a local RAGFlow knowledge base"
    )
    parser.add_argument(
        "--docs-dir",
        default="../data/sample_docs",
        help="Folder with local documents to upload",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380"),
        help="RAGFlow base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("RAGFLOW_API_KEY", ""),
        help="RAGFlow API key",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("RAGFLOW_EMAIL", ""),
        help="RAGFlow login email (optional fallback when API key auth fails)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("RAGFLOW_PASSWORD", ""),
        help="RAGFlow login password (optional fallback when API key auth fails)",
    )
    parser.add_argument(
        "--dataset-id",
        default=os.getenv("RAGFLOW_DATASET_IDS", "sales-kb").split(",")[0].strip() or "sales-kb",
        help="Target KB/dataset ID or name",
    )
    parser.add_argument(
        "--create-dataset",
        action="store_true",
        help="Create the KB if it does not exist",
    )
    parser.add_argument(
        "--embedding-model",
        default="bge-m3",
        help="Embedding model name used when creating a KB",
    )
    parser.add_argument(
        "--extensions",
        default=DEFAULT_EXTENSIONS,
        help="Comma-separated file extensions to include",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed upload logs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list what would be uploaded",
    )
    parser.add_argument(
        "--skip-parse",
        action="store_true",
        help="Upload only and skip parse trigger",
    )
    parser.add_argument(
        "--wait-parse",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Wait for parse completion and print final status",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=180,
        help="Seconds to wait for parsing completion",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=3,
        help="Polling interval in seconds while waiting for parse",
    )

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs folder not found: {docs_dir}")

    allowed_exts = parse_extensions(args.extensions)
    files = list(iter_files(docs_dir, allowed_exts))

    if not files:
        print(f"No matching files found in {docs_dir}")
        return

    print(f"Docs dir: {docs_dir}")
    print(f"Files found: {len(files)}")

    if args.dry_run:
        for path in files:
            print(f"[DRY RUN] {path.name}")
        return

    indexer = RAGFlowIndexer(
        base_url=args.base_url,
        api_key=args.api_key,
        email=args.email,
        password=args.password,
    )
    try:
        kbs = indexer.list_kbs()
        kb = indexer.find_kb(kbs, args.dataset_id)

        if kb is None:
            if not args.create_dataset:
                raise RAGFlowError(
                    f"KB '{args.dataset_id}' not found. Use --create-dataset to create it."
                )
            kb = indexer.create_kb(args.dataset_id, args.embedding_model)
            print(f"Created KB: {kb.name} ({kb.kb_id})")
        else:
            print(f"Using KB: {kb.name} ({kb.kb_id})")

        success = 0
        failed: list[str] = []

        for file_path in files:
            ok = indexer.upload_file(kb, file_path, verbose=args.verbose)
            if ok:
                success += 1
            else:
                failed.append(file_path.name)

        print(f"Uploaded files: {success}/{len(files)}")
        if failed:
            print("Failed files:")
            for name in failed:
                print(f"- {name}")
            raise SystemExit(1)

        if not args.skip_parse:
            parse_ok = indexer.start_parsing(kb.kb_id, verbose=args.verbose)
            if not parse_ok:
                print("Warning: upload succeeded but parse was not triggered.")
            elif args.wait_parse:
                done_ok, docs = indexer.wait_for_parse_completion(
                    kb_id=kb.kb_id,
                    timeout_s=args.wait_timeout,
                    poll_interval_s=args.poll_interval,
                    verbose=args.verbose,
                )
                if docs:
                    print("Final document status:")
                    for doc in docs:
                        name = str(doc.get("name", "unknown"))
                        run = str(doc.get("run", "UNKNOWN"))
                        progress = doc.get("progress", 0)
                        chunks = doc.get("chunk_count", 0)
                        print(f"- {name}: run={run} progress={progress} chunks={chunks}")

                if not done_ok:
                    print("Warning: parse did not fully complete within timeout.")

    finally:
        indexer.close()


if __name__ == "__main__":
    main()
