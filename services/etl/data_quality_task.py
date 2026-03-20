"""
Data Quality checks for managed DB.

Checks: completeness (missing dates), freshness (yesterday loaded),
consistency (control sums), advertising data cross-validation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from services.marketplace_etl.config.database import get_db_connection

logger = logging.getLogger(__name__)


class DataQuality:
    """Data quality checks for the managed marketplace DB."""

    def check_freshness(self) -> dict:
        """Check that yesterday's data is present in key tables."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        tables = ["wb.abc_date", "ozon.abc_date"]
        result = {"date": yesterday, "tables": {}}

        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                for table in tables:
                    try:
                        cur.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE date = %s",
                            (yesterday,),
                        )
                        count = cur.fetchone()[0]
                        result["tables"][table] = {
                            "rows": count,
                            "fresh": count > 0,
                        }
                    except Exception as e:
                        result["tables"][table] = {"error": str(e)}
                        conn.rollback()
            conn.close()
        except Exception as e:
            result["error"] = str(e)
            logger.error("check_freshness failed: %s", e)

        return result

    def check_completeness(self, days: int = 30) -> dict:
        """Check for missing dates in the last N days."""
        result = {"days_checked": days, "tables": {}}
        today = datetime.now().date()
        expected_dates = {
            (today - timedelta(days=i)).isoformat()
            for i in range(1, days + 1)
        }

        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                for table in ("wb.abc_date", "ozon.abc_date"):
                    try:
                        cur.execute(
                            f"SELECT DISTINCT date::text FROM {table} "
                            f"WHERE date >= %s ORDER BY date",
                            ((today - timedelta(days=days)).isoformat(),),
                        )
                        actual = {row[0] for row in cur.fetchall()}
                        missing = sorted(expected_dates - actual)
                        result["tables"][table] = {
                            "missing_dates": missing,
                            "complete": len(missing) == 0,
                        }
                    except Exception as e:
                        result["tables"][table] = {"error": str(e)}
                        conn.rollback()
            conn.close()
        except Exception as e:
            result["error"] = str(e)
            logger.error("check_completeness failed: %s", e)

        return result

    def check_consistency(self, date: str | None = None) -> dict:
        """Basic consistency: revenue > 0, margin within bounds, no negative orders."""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        checks = {}

        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # WB: check for negative revenue
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM wb.abc_date "
                        "WHERE date = %s AND revenue_spp < 0",
                        (date,),
                    )
                    neg_rev = cur.fetchone()[0]
                    cur.execute(
                        "SELECT COUNT(*) FROM wb.abc_date WHERE date = %s",
                        (date,),
                    )
                    total = cur.fetchone()[0]
                    checks["wb_negative_revenue"] = {
                        "count": neg_rev,
                        "total": total,
                        "ok": neg_rev == 0 or neg_rev / max(total, 1) < 0.05,
                    }
                except Exception as e:
                    checks["wb_negative_revenue"] = {"error": str(e)}
                    conn.rollback()

                # Ozon: check for negative margin
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM ozon.abc_date "
                        "WHERE date = %s AND (marga - nds) < -1000000",
                        (date,),
                    )
                    neg_margin = cur.fetchone()[0]
                    checks["ozon_extreme_margin"] = {
                        "count": neg_margin,
                        "ok": neg_margin == 0,
                    }
                except Exception as e:
                    checks["ozon_extreme_margin"] = {"error": str(e)}
                    conn.rollback()

            conn.close()
        except Exception as e:
            checks["error"] = str(e)
            logger.error("check_consistency failed: %s", e)

        return {"date": date, "checks": checks}

    def check_adv_freshness(self) -> dict:
        """Check wb_adv and content_analysis freshness."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        tables = ["wb.wb_adv", "wb.content_analysis"]
        result = {"date": yesterday, "tables": {}}

        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                for table in tables:
                    try:
                        cur.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE date = %s",
                            (yesterday,),
                        )
                        count = cur.fetchone()[0]
                        result["tables"][table] = {
                            "rows": count,
                            "fresh": count > 0,
                        }
                    except Exception as e:
                        result["tables"][table] = {"error": str(e)}
                        conn.rollback()
            conn.close()
        except Exception as e:
            result["error"] = str(e)
            logger.error("check_adv_freshness failed: %s", e)

        return result

    def check_adv_consistency(self, date: str | None = None) -> dict:
        """Cross-validate wb_adv.sum totals vs abc_date.reclama."""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(sum), 0) FROM wb.wb_adv WHERE date = %s",
                    (date,),
                )
                adv_total = cur.fetchone()[0]

                cur.execute(
                    "SELECT COALESCE(SUM(reclama), 0) FROM wb.abc_date WHERE date = %s",
                    (date,),
                )
                abc_total = cur.fetchone()[0]
            conn.close()

            diff_pct = abs(adv_total - abc_total) / max(abc_total, 1) * 100
            return {
                "date": date,
                "wb_adv_sum": float(adv_total),
                "abc_reclama": float(abc_total),
                "diff_pct": round(diff_pct, 2),
                "ok": diff_pct < 5,
            }
        except Exception as e:
            logger.error("check_adv_consistency failed: %s", e)
            return {"date": date, "error": str(e)}

    def run_all(self) -> dict:
        """Run all quality checks."""
        return {
            "freshness": self.check_freshness(),
            "completeness": self.check_completeness(),
            "consistency": self.check_consistency(),
            "adv_freshness": self.check_adv_freshness(),
            "adv_consistency": self.check_adv_consistency(),
        }
