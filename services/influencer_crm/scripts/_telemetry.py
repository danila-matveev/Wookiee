"""Direct telemetry writer for crm.etl_runs.

Why not tool_telemetry.log_agent_run? It became a no-op on 2026-04-13
(audit remediation deprecated agent_runs writes). The CRM owns its own
ops telemetry via crm.etl_runs (migration 012).

Fire-and-forget: never raises. The cron job's exit code reflects ETL
correctness; telemetry-write failure must not turn a green run red.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import psycopg2.extras

from services.sheets_etl.loader import get_conn

logger = logging.getLogger("influencer_crm.etl_runs")


def insert_etl_run(
    *,
    agent: str,
    version: str,
    mode: str,
    started_at: datetime,
    finished_at: datetime,
    duration_ms: int,
    status: str,
    error_message: str | None = None,
    rows_loaded: dict[str, Any] | None = None,
) -> None:
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO crm.etl_runs
                        (agent, version, mode, started_at, finished_at,
                         duration_ms, status, error_message, rows_loaded)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        agent,
                        version,
                        mode,
                        started_at,
                        finished_at,
                        duration_ms,
                        status,
                        error_message,
                        psycopg2.extras.Json(rows_loaded) if rows_loaded else None,
                    ),
                )
                conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — fire-and-forget by design
        logger.error("etl_runs INSERT failed: %s", exc)
