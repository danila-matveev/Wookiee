"""
SQLite key-value store for Wookiee v3 state persistence.

Handles report delivery dedup, retry tracking, and generic KV storage.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone


class StateStore:
    """Simple SQLite-backed key-value store with optional TTL."""

    def __init__(self, db_path: str = "data/v3_state.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at TEXT
            )"""
        )
        self._conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_expired(self, expires_at: str | None) -> bool:
        if expires_at is None:
            return False
        return datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc)

    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value, expires_at FROM kv_store WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if self._is_expired(expires_at):
            self.delete(key)
            return None
        return value

    def set(self, key: str, value: str, ttl_hours: int | None = None) -> None:
        expires_at = None
        if ttl_hours is not None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
            ).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value, expires_at) VALUES (?, ?, ?)",
            (key, value, expires_at),
        )
        self._conn.commit()

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
        self._conn.commit()

    # ---- delivery dedup ---------------------------------------------------

    def mark_delivered(self, report_type: str, date: str) -> None:
        self.set(f"delivered:{report_type}:{date}", "1", ttl_hours=48)

    def is_delivered(self, report_type: str, date: str) -> bool:
        return self.exists(f"delivered:{report_type}:{date}")

    # ---- retry tracking ---------------------------------------------------

    def increment_retries(self, report_type: str, date: str) -> int:
        key = f"retries:{report_type}:{date}"
        current = int(self.get(key) or "0")
        new_val = current + 1
        self.set(key, str(new_val), ttl_hours=24)
        return new_val

    def get_retries(self, report_type: str, date: str) -> int:
        return int(self.get(f"retries:{report_type}:{date}") or "0")
