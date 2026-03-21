"""
SQLite store for categorization suggestions, feedback, and learned rules.

Extended from Oleg's store with Notion page mapping for feedback loop.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import DB_PATH

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS finolog_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id INTEGER NOT NULL,
    txn_date TEXT,
    txn_description TEXT,
    txn_value REAL,
    txn_contractor_id INTEGER,
    suggested_category_id INTEGER,
    suggested_report_date TEXT,
    confidence REAL,
    rule_name TEXT,
    status TEXT DEFAULT 'pending',
    user_correction_category_id INTEGER,
    notion_page_id TEXT,
    page_index INTEGER,
    created_at TEXT,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS finolog_learned_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    pattern_type TEXT DEFAULT 'description',
    category_id INTEGER NOT NULL,
    times_confirmed INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON finolog_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestions_txn ON finolog_suggestions(txn_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_page ON finolog_suggestions(notion_page_id);
CREATE INDEX IF NOT EXISTS idx_learned_active ON finolog_learned_rules(active, pattern_type);
"""


class CategorizerStore:
    """SQLite-backed store for categorization suggestions and learned rules."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()

    # ── Suggestions ───────────────────────────────────────────────

    def save_suggestion(
        self,
        txn_id: int,
        txn_date: str,
        txn_description: str,
        txn_value: float,
        txn_contractor_id: int | None,
        suggested_category_id: int,
        suggested_report_date: str,
        confidence: float,
        rule_name: str,
    ) -> int:
        """Save a categorization suggestion. Returns suggestion ID."""
        conn = self._get_conn()
        cur = conn.execute(
            """INSERT INTO finolog_suggestions
            (txn_id, txn_date, txn_description, txn_value, txn_contractor_id,
             suggested_category_id, suggested_report_date, confidence, rule_name,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (txn_id, txn_date, txn_description, txn_value, txn_contractor_id,
             suggested_category_id, suggested_report_date, confidence, rule_name,
             datetime.now().isoformat()),
        )
        sid = cur.lastrowid
        conn.commit()
        conn.close()
        return sid

    def already_suggested(self, txn_id: int) -> bool:
        """Check if a suggestion already exists for this transaction."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM finolog_suggestions WHERE txn_id = ? AND status IN ('pending', 'approved', 'applied')",
            (txn_id,),
        ).fetchone()
        conn.close()
        return row is not None

    def get_pending(self) -> list[dict]:
        """Get all pending suggestions."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM finolog_suggestions WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_suggestion(self, suggestion_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM finolog_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── Notion page mapping ───────────────────────────────────────

    def update_page_mapping(self, suggestion_id: int, notion_page_id: str, page_index: int):
        """Link a suggestion to its Notion page and display index (#N)."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE finolog_suggestions SET notion_page_id = ?, page_index = ? WHERE id = ?",
            (notion_page_id, page_index, suggestion_id),
        )
        conn.commit()
        conn.close()

    def get_by_page_index(self, notion_page_id: str, page_index: int) -> Optional[dict]:
        """Get suggestion by its Notion page index (#N)."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM finolog_suggestions WHERE notion_page_id = ? AND page_index = ?",
            (notion_page_id, page_index),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_suggestions_for_page(self, notion_page_id: str) -> list[dict]:
        """Get all suggestions linked to a Notion page."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM finolog_suggestions WHERE notion_page_id = ? ORDER BY page_index",
            (notion_page_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Approve / reject ──────────────────────────────────────────

    def approve(self, suggestion_id: int) -> Optional[dict]:
        """Mark suggestion as approved. Tracks for learning."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE finolog_suggestions SET status = 'approved', resolved_at = ? WHERE id = ?",
            (datetime.now().isoformat(), suggestion_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM finolog_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        conn.close()
        if row:
            suggestion = dict(row)
            self._track_confirmation(suggestion["txn_description"], suggestion["suggested_category_id"])
            return suggestion
        return None

    def reject(self, suggestion_id: int, correct_category_id: int | None = None):
        """Mark suggestion as rejected, optionally with user's correct category."""
        conn = self._get_conn()
        conn.execute(
            """UPDATE finolog_suggestions
            SET status = 'rejected', user_correction_category_id = ?, resolved_at = ?
            WHERE id = ?""",
            (correct_category_id, datetime.now().isoformat(), suggestion_id),
        )
        conn.commit()
        conn.close()
        if correct_category_id:
            row = self.get_suggestion(suggestion_id)
            if row:
                self._track_confirmation(row["txn_description"], correct_category_id)

    # ── Learned rules ─────────────────────────────────────────────

    def get_learned_rules(self) -> list[dict]:
        """Get all active learned rules."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM finolog_learned_rules WHERE active = 1 ORDER BY times_confirmed DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _track_confirmation(self, description: str, category_id: int):
        """Track a confirmation and promote to learned rule after 3 confirmations."""
        if not description:
            return
        pattern = description.strip()[:50].lower()
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT id, times_confirmed FROM finolog_learned_rules WHERE pattern = ? AND category_id = ?",
            (pattern, category_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE finolog_learned_rules SET times_confirmed = times_confirmed + 1 WHERE id = ?",
                (existing["id"],),
            )
        else:
            conn.execute(
                """INSERT INTO finolog_learned_rules (pattern, pattern_type, category_id, times_confirmed, active, created_at)
                VALUES (?, 'description', ?, 1, 0, ?)""",
                (pattern, category_id, datetime.now().isoformat()),
            )
        # Promote: activate after 3 confirmations
        conn.execute(
            """UPDATE finolog_learned_rules SET active = 1
            WHERE pattern = ? AND category_id = ? AND times_confirmed >= 3 AND active = 0""",
            (pattern, category_id),
        )
        conn.commit()
        conn.close()
