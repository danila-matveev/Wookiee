"""Reconciliation check — weekly cron job.

Wraps existing ReconciliationTask from agents/ibrahim/tasks/reconciliation.py.
Not an agent — deterministic script safe to run from cron or CLI.

Compares managed DB totals against the read-only source DB (89.23.119.253:6433)
to detect ETL drift. Raises non-zero exit code on FAIL so cron can alert.
"""

import asyncio
import logging
import sys

from agents.ibrahim.tasks.reconciliation import ReconciliationTask

logger = logging.getLogger(__name__)


async def run_reconciliation_check(
    date_from: str = None,
    date_to: str = None,
    days: int = 1,
    threshold_pct: float = 1.0,
) -> dict:
    """Run reconciliation between managed DB and source DB.

    Args:
        date_from: Start date YYYY-MM-DD. If provided together with date_to,
            runs for the explicit range.
        date_to: End date YYYY-MM-DD.
        days: Number of days back from yesterday to check (used when
            date_from/date_to are not provided).
        threshold_pct: Acceptable divergence percentage (default 1.0%).

    Returns:
        dict with 'passed', 'status' ("PASS"|"FAIL"|"ERROR"), 'date_from',
        'date_to', and optional 'error' keys.
    """
    task = ReconciliationTask(threshold_pct=threshold_pct)

    if date_from and date_to:
        logger.info("Running reconciliation: %s → %s", date_from, date_to)
        return task.run_range(date_from, date_to)

    logger.info("Running reconciliation for last %d day(s)", days)
    return task.run(days=days)


if __name__ == "__main__":
    date_from_arg = sys.argv[1] if len(sys.argv) > 1 else None
    date_to_arg = sys.argv[2] if len(sys.argv) > 2 else None

    result = asyncio.run(run_reconciliation_check(date_from_arg, date_to_arg))
    import json
    print(json.dumps(result, indent=2, default=str))

    # Non-zero exit so cron/CI can detect failures
    if not result.get("passed", False):
        sys.exit(1)
