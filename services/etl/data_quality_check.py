"""Data quality check — daily cron job.

Wraps existing DataQuality from agents/ibrahim/tasks/data_quality.py.
Not an agent — deterministic script safe to run from cron or CLI.

Checks: freshness (yesterday loaded), completeness (no gaps in last 30 days),
consistency (control sums), advertising data cross-validation.
"""

import asyncio
import logging

from agents.ibrahim.tasks.data_quality import DataQuality

logger = logging.getLogger(__name__)


async def run_data_quality_check(date: str = None) -> dict:
    """Run all data quality checks.

    Args:
        date: Date to check consistency for (YYYY-MM-DD). Defaults to yesterday.

    Returns:
        dict with freshness, completeness, consistency, adv_freshness,
        adv_consistency results. Each sub-dict has an 'ok' flag.
    """
    checker = DataQuality()
    logger.info("Running data quality checks (date=%s)", date or "yesterday")

    result = {
        "freshness": checker.check_freshness(),
        "completeness": checker.check_completeness(),
        "consistency": checker.check_consistency(date),
        "adv_freshness": checker.check_adv_freshness(),
        "adv_consistency": checker.check_adv_consistency(date),
    }

    # Compute overall pass/fail for easy cron alerting
    all_ok = all(
        sub.get("ok", True) if isinstance(sub, dict) else True
        for key, sub in result.items()
        if key not in ("completeness",)  # completeness returns per-table
    )
    # completeness: ok if no missing dates in any table
    completeness_ok = all(
        t.get("complete", True)
        for t in result["completeness"].get("tables", {}).values()
    )
    result["overall_ok"] = all_ok and completeness_ok

    return result


if __name__ == "__main__":
    import sys

    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = asyncio.run(run_data_quality_check(date_arg))
    import json
    print(json.dumps(result, indent=2, default=str))
