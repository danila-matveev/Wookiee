"""
ETL Operator — wrapper over services/marketplace_etl.

Runs WB + Ozon ETL sync, monitors results, logs to SQLite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from services.marketplace_etl.config.database import (
    get_db_connection,
    get_accounts,
)

logger = logging.getLogger(__name__)


class ETLOperator:
    """Orchestrates marketplace ETL sync."""

    def sync_yesterday(self) -> dict:
        """Run ETL for yesterday's data.

        Returns:
            dict with 'wb' and 'ozon' sync results.
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return self.sync_range(yesterday, yesterday)

    def sync_range(self, date_from: str, date_to: str) -> dict:
        """Run ETL for a date range.

        Args:
            date_from: Start date YYYY-MM-DD.
            date_to: End date YYYY-MM-DD.

        Returns:
            dict with sync results per marketplace.
        """
        from services.marketplace_etl.etl.wb_etl import WildberriesETL
        from services.marketplace_etl.etl.ozon_etl import OzonETL

        accounts = get_accounts()
        results = {"wb": [], "ozon": [], "date_from": date_from, "date_to": date_to}

        # WB accounts
        for acc in accounts.get("wb", []):
            lk = acc.get("lk", "WB")
            logger.info("WB sync [%s]: %s -> %s", lk, date_from, date_to)
            try:
                etl = WildberriesETL(
                    api_key=acc["api_key"],
                    lk=lk,
                )
                etl.run(date_from, date_to)
                results["wb"].append({"lk": lk, "status": "ok"})
                logger.info("WB sync [%s] completed", lk)
            except Exception as e:
                logger.error("WB sync [%s] failed: %s", lk, e, exc_info=True)
                results["wb"].append({"lk": lk, "status": "error", "error": str(e)})

        # Ozon accounts
        for acc in accounts.get("ozon", []):
            lk = acc.get("lk", "Ozon")
            logger.info("Ozon sync [%s]: %s -> %s", lk, date_from, date_to)
            try:
                etl = OzonETL(
                    client_id=acc["client_id"],
                    api_key=acc["api_key"],
                    lk=lk,
                )
                etl.run(date_from, date_to)
                results["ozon"].append({"lk": lk, "status": "ok"})
                logger.info("Ozon sync [%s] completed", lk)
            except Exception as e:
                logger.error("Ozon sync [%s] failed: %s", lk, e, exc_info=True)
                results["ozon"].append({"lk": lk, "status": "error", "error": str(e)})

        return results

    def get_status(self) -> dict:
        """Get managed DB status: table row counts, last dates.

        Returns:
            dict with table stats.
        """
        status = {"tables": {}}
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                for schema in ("wb", "ozon"):
                    cur.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = %s ORDER BY table_name",
                        (schema,),
                    )
                    tables = [row[0] for row in cur.fetchall()]
                    for table in tables:
                        fqn = f"{schema}.{table}"
                        try:
                            cur.execute(f"SELECT COUNT(*) FROM {fqn}")
                            count = cur.fetchone()[0]
                            # Try to get latest date
                            last_date = None
                            cur.execute(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_schema = %s AND table_name = %s "
                                "AND column_name = 'date'",
                                (schema, table),
                            )
                            if cur.fetchone():
                                cur.execute(f"SELECT MAX(date) FROM {fqn}")
                                row = cur.fetchone()
                                if row and row[0]:
                                    last_date = str(row[0])
                            status["tables"][fqn] = {
                                "rows": count,
                                "last_date": last_date,
                            }
                        except Exception as e:
                            status["tables"][fqn] = {"error": str(e)}
                            conn.rollback()
            conn.close()
        except Exception as e:
            status["error"] = str(e)
            logger.error("get_status failed: %s", e)

        return status
