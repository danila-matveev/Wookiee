"""
Report Storage Service
SQLite database for report history with FTS5 search
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportStorage:
    """Service for storing and retrieving reports"""

    def __init__(self, db_path: str = "bot/data/reports.db"):
        """
        Initialize report storage

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    report_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    start_date DATE,
                    end_date DATE
                )
            """)

            # Create FTS5 virtual table for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5(
                    title,
                    content,
                    content='reports',
                    content_rowid='id'
                )
            """)

            # Create triggers to keep FTS5 in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS reports_ai AFTER INSERT ON reports BEGIN
                    INSERT INTO reports_fts(rowid, title, content)
                    VALUES (new.id, new.title, new.content);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS reports_ad AFTER DELETE ON reports BEGIN
                    INSERT INTO reports_fts(reports_fts, rowid, title, content)
                    VALUES('delete', old.id, old.title, old.content);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS reports_au AFTER UPDATE ON reports BEGIN
                    INSERT INTO reports_fts(reports_fts, rowid, title, content)
                    VALUES('delete', old.id, old.title, old.content);
                    INSERT INTO reports_fts(rowid, title, content)
                    VALUES (new.id, new.title, new.content);
                END
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_user_id
                ON reports(user_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_type
                ON reports(report_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_created_at
                ON reports(created_at DESC)
            """)

            conn.commit()
            logger.info("Report storage initialized")

    def save_report(
        self,
        user_id: int,
        report_type: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """
        Save report to database

        Args:
            user_id: Telegram user ID
            report_type: Type of report (daily, period, abc, custom)
            title: Report title
            content: Report content (markdown)
            metadata: Additional metadata (dict)
            start_date: Report start date
            end_date: Report end date

        Returns:
            Report ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO reports (
                    user_id, report_type, title, content, metadata,
                    start_date, end_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                report_type,
                title,
                content,
                json.dumps(metadata) if metadata else None,
                start_date.strftime("%Y-%m-%d") if start_date else None,
                end_date.strftime("%Y-%m-%d") if end_date else None
            ))

            report_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Report saved: ID={report_id}, type={report_type}")
            return report_id

    def get_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        """
        Get report by ID

        Args:
            report_id: Report ID

        Returns:
            Report dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM reports WHERE id = ?
            """, (report_id,))

            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_dict(row)

    def get_user_reports(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        report_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get reports for a user

        Args:
            user_id: Telegram user ID
            limit: Maximum number of reports
            offset: Offset for pagination
            report_type: Filter by report type (optional)

        Returns:
            List of report dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if report_type:
                cursor.execute("""
                    SELECT * FROM reports
                    WHERE user_id = ? AND report_type = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (user_id, report_type, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM reports
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))

            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def search_reports(
        self,
        user_id: int,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Full-text search in reports

        Args:
            user_id: Telegram user ID
            query: Search query
            limit: Maximum results

        Returns:
            List of matching report dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT r.*, rank
                FROM reports r
                JOIN reports_fts ON reports_fts.rowid = r.id
                WHERE r.user_id = ? AND reports_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (user_id, query, limit))

            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def delete_report(self, report_id: int) -> bool:
        """
        Delete report

        Args:
            report_id: Report ID

        Returns:
            True if deleted, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM reports WHERE id = ?
            """, (report_id,))

            deleted = cursor.rowcount > 0
            conn.commit()

            if deleted:
                logger.info(f"Report deleted: ID={report_id}")

            return deleted

    def cleanup_old_reports(self, days: int = 90) -> int:
        """
        Delete reports older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted reports
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM reports
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))

            deleted = cursor.rowcount
            conn.commit()

            logger.info(f"Cleaned up {deleted} old reports (>{days} days)")
            return deleted

    def get_report_count(self, user_id: int) -> int:
        """
        Get total report count for user

        Args:
            user_id: Telegram user ID

        Returns:
            Number of reports
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM reports WHERE user_id = ?
            """, (user_id,))

            return cursor.fetchone()[0]

    def has_report_for_period(self, report_type: str, period_key: str) -> bool:
        """
        Check if a report of given type with period_key in title already exists.

        Args:
            report_type: Report type (e.g. 'monthly_auto')
            period_key: Period identifier to search in title (e.g. '2026-01')

        Returns:
            True if report exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM reports
                WHERE report_type = ? AND title LIKE ?
            """, (report_type, f"%{period_key}%"))
            return cursor.fetchone()[0] > 0

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert SQLite row to dict

        Args:
            row: SQLite row

        Returns:
            Dict representation
        """
        data = dict(row)

        # Parse metadata JSON
        if data.get("metadata"):
            data["metadata"] = json.loads(data["metadata"])

        return data
