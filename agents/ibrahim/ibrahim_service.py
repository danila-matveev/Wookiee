"""
IbrahimService — main orchestrator for the Ibrahim agent.

Coordinates ETL, reconciliation, data quality, API analysis, schema management.
Logs all task results to a local SQLite database.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from agents.ibrahim.config import (
    SQLITE_DB,
    LLM_API_KEY,
    LLM_MODEL,
    DATA_DIR,
)
from agents.ibrahim.tasks.etl_operator import ETLOperator
from agents.ibrahim.tasks.reconciliation import ReconciliationTask
from agents.ibrahim.tasks.data_quality import DataQuality
from agents.ibrahim.tasks.api_docs_analyzer import APIDocsAnalyzer
from agents.ibrahim.tasks.schema_manager import SchemaManager

logger = logging.getLogger(__name__)


class IbrahimService:
    """Main orchestrator for Ibrahim agent."""

    DEFAULT_TIMEOUT = 5.0  # seconds

    def __init__(self, timeout: float = None):
        self.etl = ETLOperator()
        self.reconciler = ReconciliationTask()
        self.quality = DataQuality()
        self.api_analyzer = APIDocsAnalyzer()
        self.schema_mgr = SchemaManager()
        self._llm = None
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(SQLITE_DB), timeout=self._timeout)
        conn.execute(f"PRAGMA busy_timeout={int(self._timeout * 1000)}")
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite database for task history."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS task_log ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  timestamp TEXT NOT NULL,"
            "  task_type TEXT NOT NULL,"
            "  status TEXT NOT NULL,"
            "  result_json TEXT"
            ")"
        )
        conn.commit()
        conn.close()

    def _log_task(self, task_type: str, status: str, result: dict) -> None:
        """Log task result to SQLite."""
        try:
            conn = self._connect()
            conn.execute(
                "INSERT INTO task_log (timestamp, task_type, status, result_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    task_type,
                    status,
                    json.dumps(result, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to log task: %s", e)

    def _get_llm(self):
        """Lazy-init LLM client."""
        if self._llm is None and LLM_API_KEY:
            from shared.clients.openrouter_client import OpenRouterClient
            self._llm = OpenRouterClient(
                api_key=LLM_API_KEY,
                model=LLM_MODEL,
            )
        return self._llm

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync_yesterday(self) -> dict:
        """Daily ETL sync for yesterday."""
        logger.info("=== Daily sync: yesterday ===")
        result = self.etl.sync_yesterday()
        has_errors = any(
            r.get("status") != "ok"
            for r in result.get("wb", []) + result.get("ozon", [])
        )
        self._log_task("sync", "error" if has_errors else "ok", result)
        return result

    def sync_range(self, date_from: str, date_to: str) -> dict:
        """ETL sync for a date range."""
        logger.info("=== Sync: %s -> %s ===", date_from, date_to)
        result = self.etl.sync_range(date_from, date_to)
        has_errors = any(
            r.get("status") != "ok"
            for r in result.get("wb", []) + result.get("ozon", [])
        )
        self._log_task("sync", "error" if has_errors else "ok", result)
        return result

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile(self, days: int = 1) -> dict:
        """Run reconciliation."""
        logger.info("=== Reconciliation: last %d days ===", days)
        result = self.reconciler.run(days)
        self._log_task("reconciliation", result.get("status", "unknown"), result)
        return result

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get DB status and recent task history."""
        db_status = self.etl.get_status()

        # Recent tasks from SQLite
        recent = []
        try:
            conn = self._connect()
            cursor = conn.execute(
                "SELECT timestamp, task_type, status FROM task_log "
                "ORDER BY id DESC LIMIT 10"
            )
            recent = [
                {"timestamp": r[0], "task": r[1], "status": r[2]}
                for r in cursor.fetchall()
            ]
            conn.close()
        except Exception:
            pass

        return {"db": db_status, "recent_tasks": recent}

    def health(self) -> dict:
        """Full health check."""
        result = {
            "db_status": self.etl.get_status(),
            "data_quality": self.quality.run_all(),
        }
        return result

    # ------------------------------------------------------------------
    # Daily / Weekly routines
    # ------------------------------------------------------------------

    async def daily_routine(self) -> dict:
        """Daily routine: sync + reconcile + quality check.

        Called at 05:00 MSK by scheduler.
        """
        logger.info("=" * 60)
        logger.info("DAILY ROUTINE START")
        logger.info("=" * 60)

        results = {}

        # 1. ETL sync
        results["sync"] = self.sync_yesterday()

        # 2. Reconciliation
        results["reconciliation"] = self.reconcile(days=1)

        # 3. Data quality
        results["quality"] = self.quality.run_all()
        self._log_task("daily_routine", "ok", {"summary": "completed"})

        logger.info("DAILY ROUTINE COMPLETED")
        return results

    async def weekly_routine(self) -> dict:
        """Weekly routine: API analysis + schema analysis + full reconciliation.

        Called Sunday 03:00 MSK by scheduler.
        """
        logger.info("=" * 60)
        logger.info("WEEKLY ROUTINE START")
        logger.info("=" * 60)

        results = {}
        llm = self._get_llm()

        # 1. API docs analysis
        results["api_analysis"] = await self.api_analyzer.analyze(llm_client=llm)

        # 2. Schema analysis
        results["schema_analysis"] = await self.schema_mgr.analyze(llm_client=llm)

        # 3. Full reconciliation (3 months)
        results["reconciliation"] = self.reconciler.run_full(months=3)

        self._log_task("weekly_routine", "ok", {"summary": "completed"})

        logger.info("WEEKLY ROUTINE COMPLETED")
        return results

    # ------------------------------------------------------------------
    # Manual LLM tasks
    # ------------------------------------------------------------------

    async def analyze_api(self) -> dict:
        """Manual trigger: analyze API documentation."""
        llm = self._get_llm()
        result = await self.api_analyzer.analyze(llm_client=llm)
        self._log_task("api_analysis", "ok", result)
        return result

    async def analyze_schema(self) -> dict:
        """Manual trigger: analyze schema."""
        llm = self._get_llm()
        result = await self.schema_mgr.analyze(llm_client=llm)
        self._log_task("schema_analysis", "ok", result)
        return result
