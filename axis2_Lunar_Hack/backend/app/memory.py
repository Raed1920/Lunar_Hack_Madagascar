from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class MemoryStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    business_type TEXT,
                    budget TEXT,
                    goals TEXT,
                    timeline TEXT,
                    intent TEXT,
                    domain TEXT,
                    preferred_language TEXT,
                    preferences_json TEXT,
                    lead_score INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_message(self, session_id: str, user_id: str, role: str, message: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO interactions (session_id, user_id, role, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, role, message, self._utc_now()),
            )
            conn.commit()

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT role, message, created_at
                FROM interactions
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()

        ordered = list(reversed(rows))
        return [
            {
                "role": row["role"],
                "message": row["message"],
                "created_at": row["created_at"],
            }
            for row in ordered
        ]

    def list_sessions(self, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    latest.session_id AS session_id,
                    latest.role AS last_role,
                    latest.message AS last_message,
                    latest.created_at AS last_created_at,
                    agg.message_count AS message_count
                FROM interactions AS latest
                JOIN (
                    SELECT session_id, MAX(id) AS max_id, COUNT(*) AS message_count
                    FROM interactions
                    WHERE user_id = ?
                    GROUP BY session_id
                ) AS agg
                ON latest.id = agg.max_id
                ORDER BY latest.id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [
            {
                "session_id": row["session_id"],
                "last_role": row["last_role"],
                "last_message": row["last_message"],
                "last_created_at": row["last_created_at"],
                "message_count": int(row["message_count"] or 0),
            }
            for row in rows
        ]

    def get_session_messages(self, user_id: str, session_id: str, limit: int = 200) -> List[Dict[str, str]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT role, message, created_at
                FROM interactions
                WHERE user_id = ? AND session_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (user_id, session_id, limit),
            ).fetchall()

        return [
            {
                "role": row["role"],
                "message": row["message"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()

        if not row:
            return {}

        preferences = {}
        if row["preferences_json"]:
            try:
                preferences = json.loads(row["preferences_json"])
            except json.JSONDecodeError:
                preferences = {}

        return {
            "user_id": row["user_id"],
            "business_type": row["business_type"],
            "budget": row["budget"],
            "goals": row["goals"],
            "timeline": row["timeline"],
            "intent": row["intent"],
            "domain": row["domain"],
            "preferred_language": row["preferred_language"],
            "preferences": preferences,
            "lead_score": row["lead_score"] or 0,
        }

    def upsert_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        current = self.get_profile(user_id)
        merged = {**current, **{k: v for k, v in profile.items() if v is not None}}

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO profiles (
                    user_id,
                    business_type,
                    budget,
                    goals,
                    timeline,
                    intent,
                    domain,
                    preferred_language,
                    preferences_json,
                    lead_score,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    business_type = excluded.business_type,
                    budget = excluded.budget,
                    goals = excluded.goals,
                    timeline = excluded.timeline,
                    intent = excluded.intent,
                    domain = excluded.domain,
                    preferred_language = excluded.preferred_language,
                    preferences_json = excluded.preferences_json,
                    lead_score = excluded.lead_score,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    merged.get("business_type"),
                    merged.get("budget"),
                    merged.get("goals"),
                    merged.get("timeline"),
                    merged.get("intent"),
                    merged.get("domain"),
                    merged.get("preferred_language"),
                    json.dumps(merged.get("preferences", {}), ensure_ascii=False),
                    int(merged.get("lead_score", 0)),
                    self._utc_now(),
                ),
            )
            conn.commit()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
