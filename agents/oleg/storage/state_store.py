"""
StateStore — SQLite persistence for operational state, gate history, report log.
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class StateStore:
    """SQLite store for operational state."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS op_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS gate_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    marketplace TEXT,
                    gate_name TEXT,
                    passed BOOLEAN,
                    is_hard BOOLEAN,
                    value REAL,
                    detail TEXT
                );

                CREATE TABLE IF NOT EXISTS report_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_type TEXT,
                    agent TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_ms INTEGER,
                    cost_usd REAL,
                    chain_steps INTEGER DEFAULT 1,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS feedback_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    feedback_text TEXT,
                    report_context TEXT,
                    decision TEXT,
                    reasoning TEXT,
                    playbook_update TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS prompt_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT NOT NULL,
                    category TEXT NOT NULL,
                    suggestion TEXT NOT NULL,
                    reasoning TEXT,
                    feedback_ids TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'sent',
                    content_hash TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP
                );
            """)
        logger.info(f"StateStore initialized at {self.db_path}")

    # ── Op State ──────────────────────────────────────────────

    def get_state(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM op_state WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO op_state (key, value, updated_at) "
                "VALUES (?, ?, ?)",
                (key, value, datetime.utcnow().isoformat()),
            )

    # ── Gate History ──────────────────────────────────────────

    def log_gate_check(
        self, marketplace: str, gate_name: str,
        passed: bool, is_hard: bool,
        value: float = None, detail: str = "",
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO gate_history "
                "(marketplace, gate_name, passed, is_hard, value, detail) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (marketplace, gate_name, passed, is_hard, value, detail),
            )

    def get_consecutive_failures(self, marketplace: str = "wb") -> int:
        """Count consecutive days with hard gate failures."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT check_time, passed FROM gate_history "
                "WHERE marketplace = ? AND is_hard = 1 "
                "ORDER BY check_time DESC LIMIT 30",
                (marketplace,),
            ).fetchall()

        count = 0
        for _, passed in rows:
            if not passed:
                count += 1
            else:
                break
        return count

    # ── Report Log ────────────────────────────────────────────

    def log_report(
        self, report_type: str, agent: str, status: str,
        duration_ms: int = 0, cost_usd: float = 0.0,
        chain_steps: int = 1, error: str = None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO report_log "
                "(report_type, agent, status, duration_ms, cost_usd, chain_steps, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report_type, agent, status, duration_ms, cost_usd, chain_steps, error),
            )
            return cur.lastrowid

    def get_recent_errors(self, hours: int = 24) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM report_log "
                "WHERE status = 'error' "
                "AND created_at >= datetime('now', ?)",
                (f"-{hours} hours",),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Feedback Log ──────────────────────────────────────────

    def log_feedback(
        self, user_id: int, feedback_text: str,
        report_context: str = "", decision: str = "",
        reasoning: str = "", playbook_update: str = "",
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO feedback_log "
                "(user_id, feedback_text, report_context, decision, reasoning, playbook_update) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, feedback_text, report_context, decision, reasoning, playbook_update),
            )
            return cur.lastrowid

    def get_feedback_history(self, last_n: int = 20) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback_log ORDER BY created_at DESC LIMIT ?",
                (last_n,),
            ).fetchall()
            return [dict(r) for r in rows]
