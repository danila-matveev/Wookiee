"""ConductorState — SQLite tracking for report generation."""
import sqlite3
from typing import Optional


class ConductorState:
    """Tracks report generation attempts, results, and delivery status."""

    def __init__(self, db_path: str = "agents/v3/data/v3_state.db"):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def ensure_table(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conductor_log (
                    date TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    data_ready_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    validation_result TEXT,
                    notion_url TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (date, report_type)
                )
            """)

    def log(
        self,
        date: str,
        report_type: str,
        status: str,
        attempt: int = 0,
        data_ready_at: Optional[str] = None,
        notion_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conductor_log
                    (date, report_type, status, attempts, data_ready_at, notion_url, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (date, report_type) DO UPDATE SET
                    status = excluded.status,
                    attempts = MAX(conductor_log.attempts, excluded.attempts),
                    data_ready_at = COALESCE(excluded.data_ready_at, conductor_log.data_ready_at),
                    notion_url = COALESCE(excluded.notion_url, conductor_log.notion_url),
                    error = excluded.error,
                    updated_at = datetime('now')
                """,
                (date, report_type, status, attempt, data_ready_at, notion_url, error),
            )

    def get_successful(self, date: str) -> set:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT report_type FROM conductor_log WHERE date = ? AND status = 'success'",
                (date,),
            ).fetchall()
        return {r[0] for r in rows}

    def get_attempts(self, date: str, report_type: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT attempts FROM conductor_log WHERE date = ? AND report_type = ?",
                (date, report_type),
            ).fetchone()
        return row[0] if row else 0
