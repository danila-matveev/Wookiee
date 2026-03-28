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
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        validation_result: Optional[str] = None,
        notion_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conductor_log
                    (date, report_type, status, attempts, data_ready_at,
                     started_at, finished_at, validation_result, notion_url, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (date, report_type) DO UPDATE SET
                    status = excluded.status,
                    attempts = MAX(conductor_log.attempts, excluded.attempts),
                    data_ready_at = COALESCE(excluded.data_ready_at, conductor_log.data_ready_at),
                    started_at = COALESCE(excluded.started_at, conductor_log.started_at),
                    finished_at = COALESCE(excluded.finished_at, conductor_log.finished_at),
                    validation_result = COALESCE(excluded.validation_result, conductor_log.validation_result),
                    notion_url = COALESCE(excluded.notion_url, conductor_log.notion_url),
                    error = excluded.error,
                    updated_at = datetime('now')
                """,
                (date, report_type, status, attempt, data_ready_at,
                 started_at, finished_at, validation_result, notion_url, error),
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

    def get_all_successful_types(self, lookback_days: int = 7) -> set:
        """Return all report_types that succeeded in the last N days."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT report_type FROM conductor_log "
                "WHERE status = 'success' AND date >= date('now', ?)",
                (f"-{lookback_days} days",),
            ).fetchall()
        return {r[0] for r in rows}

    def get_failed_types(self, lookback_days: int = 7) -> set:
        """Return report_types that failed (or never succeeded) in the last N days.

        A type is 'failed' if its last status is 'failed' or it was scheduled
        but has no conductor_log entry at all.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT report_type FROM conductor_log "
                "WHERE status = 'failed' AND date >= date('now', ?) "
                "AND report_type NOT IN ("
                "  SELECT report_type FROM conductor_log "
                "  WHERE status = 'success' AND date >= date('now', ?)"
                ")",
                (f"-{lookback_days} days", f"-{lookback_days} days"),
            ).fetchall()
        return {r[0] for r in rows}

    def get_exhausted_types(self, date: str, max_attempts: int) -> set:
        """Return report_types that have already exhausted max_attempts for the given date.

        Used to prevent infinite re-queueing of persistently failing reports via
        get_missed_reports recovery. A report that has already been attempted
        max_attempts times for a given date should not be retried again that day.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT report_type FROM conductor_log "
                "WHERE date = ? AND attempts >= ? AND status = 'failed'",
                (date, max_attempts),
            ).fetchall()
        return {r[0] for r in rows}

    def already_notified(self, report_date: str) -> bool:
        """Check if data_ready notification was already sent for this date.

        Uses only SQLite — no in-memory state. Safe across async contexts
        and container restarts.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM conductor_log WHERE date = ? AND status = 'notified' LIMIT 1",
                (report_date,),
            ).fetchone()
        return row is not None

    def mark_notified(self, report_date: str) -> None:
        """Mark that data_ready notification was sent for this date.

        Atomic INSERT OR IGNORE — safe for concurrent async calls.
        """
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conductor_log (date, report_type, status, attempts) "
                "VALUES (?, '_notification', 'notified', 0)",
                (report_date,),
            )

    def mark_telegram_sent(self, report_date: str, report_type: str) -> None:
        """Mark that Telegram message was sent for this report."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conductor_log (date, report_type, status, attempts) "
                "VALUES (?, ?, 'telegram_sent', 0)",
                (f"{report_date}:tg", report_type),
            )

    def is_telegram_sent(self, report_date: str, report_type: str) -> bool:
        """Check if Telegram message was already sent for this report."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM conductor_log WHERE date = ? AND report_type = ? AND status = 'telegram_sent' LIMIT 1",
                (f"{report_date}:tg", report_type),
            ).fetchone()
        return row is not None
