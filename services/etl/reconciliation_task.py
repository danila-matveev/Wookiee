"""
Reconciliation task — compares managed DB vs read-only source DB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from services.marketplace_etl.etl.reconciliation import DataReconciliation

logger = logging.getLogger(__name__)


class ReconciliationTask:
    """Compare managed and source databases."""

    def __init__(self, threshold_pct: float = 1.0):
        self.threshold_pct = threshold_pct

    def run(self, days: int = 1) -> dict:
        """Run reconciliation for recent days.

        Args:
            days: Number of days back to check.

        Returns:
            dict with 'passed', 'wb', 'ozon', 'report' keys.
        """
        date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.run_range(date_from, date_to)

    def run_range(self, date_from: str, date_to: str) -> dict:
        """Run reconciliation for a specific date range.

        Returns:
            dict with results.
        """
        logger.info("Reconciliation: %s -> %s", date_from, date_to)

        recon = DataReconciliation()
        result = {
            "date_from": date_from,
            "date_to": date_to,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        try:
            passed = recon.run(date_from, date_to)
            result["passed"] = passed
            result["status"] = "PASS" if passed else "FAIL"
        except Exception as e:
            logger.error("Reconciliation failed: %s", e, exc_info=True)
            result["passed"] = False
            result["status"] = "ERROR"
            result["error"] = str(e)

        if not result["passed"]:
            logger.warning(
                "Reconciliation %s for %s -> %s",
                result["status"], date_from, date_to,
            )

        return result

    def run_full(self, months: int = 3) -> dict:
        """Run full reconciliation for the last N months.

        Returns:
            dict with results.
        """
        date_to = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        return self.run_range(date_from, date_to)
