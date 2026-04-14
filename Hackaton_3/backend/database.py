from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings


_db_pool: ConnectionPool | None = None


def _normalize_conninfo(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


def init_db_pool() -> None:
    global _db_pool

    if _db_pool is not None:
        return

    settings = get_settings()
    conninfo = _normalize_conninfo(settings.database_url)

    _db_pool = ConnectionPool(
        conninfo=conninfo,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )
    _db_pool.open(wait=True)


def close_db_pool() -> None:
    global _db_pool

    if _db_pool is None:
        return

    _db_pool.close()
    _db_pool = None


@contextmanager
def get_db_connection() -> Iterator[psycopg.Connection]:
    if _db_pool is None:
        init_db_pool()

    if _db_pool is None:
        raise RuntimeError("Database pool is not initialized")

    with _db_pool.connection() as connection:
        yield connection


def fetch_all(query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return list(rows)


def fetch_one(query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return row


def execute(query: str, params: Sequence[Any] | None = None) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
