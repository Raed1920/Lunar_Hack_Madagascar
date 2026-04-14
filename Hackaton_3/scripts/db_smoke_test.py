import os
from pathlib import Path

import psycopg


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def build_dsn() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "55432")
    db = os.getenv("POSTGRES_DB", "marketing_ai_dev")
    user = os.getenv("POSTGRES_USER", "marketing_user")
    pwd = os.getenv("POSTGRES_PASSWORD", "marketing_pwd_local")
    return f"host={host} port={port} dbname={db} user={user} password={pwd}"


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    load_env(root / ".env")
    load_env(root / ".env.example")

    dsn = build_dsn()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM workspaces;")
            workspaces = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM marketing_solutions_library;")
            templates = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM market_signals;")
            signals = cur.fetchone()[0]

    print("Database connection OK")
    print(f"workspaces={workspaces}")
    print(f"templates={templates}")
    print(f"signals={signals}")


if __name__ == "__main__":
    main()
