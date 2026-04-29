"""Fire-and-forget tool run logger for Supabase.

Usage:
    from shared.tool_logger import ToolLogger
    logger = ToolLogger("finance-report")
    run_id = logger.start(trigger="manual", user="danila", version="v4")
    # ... work ...
    logger.finish(run_id, status="success", result_url="...", details={...})
    # or:
    logger.error(run_id, stage="data_collection", message="timeout")
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _get_connection():
    """Connect to Supabase PostgreSQL."""
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv("database/sku/.env")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


class ToolLogger:
    """Fire-and-forget logger. Never raises, never blocks."""

    def __init__(self, tool_slug: str) -> None:
        self.tool_slug = tool_slug

    def start(
        self,
        trigger: str = "manual",
        user: str = "unknown",
        version: str = "",
        environment: str = "local",
        period_start: str = "",
        period_end: str = "",
        depth: str = "",
    ) -> Optional[str]:
        """Record run start. Returns run_id or None on failure."""
        run_id = str(uuid.uuid4())
        try:
            conn = _get_connection()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO tool_runs
                (id, tool_slug, tool_version, status, trigger_type, triggered_by,
                 environment, period_start, period_end, depth)
                VALUES (%s, %s, %s, 'running', %s, %s, %s, %s, %s, %s)""",
                (
                    run_id, self.tool_slug, version or None,
                    trigger, f"user:{user}", environment,
                    period_start or None, period_end or None, depth or None,
                ),
            )
            cur.close()
            conn.close()
            return run_id
        except Exception as e:
            logger.warning("tool_logger.start failed: %s", e)
            return None

    def finish(
        self,
        run_id: Optional[str],
        status: str = "success",
        result_url: str = "",
        items_processed: int = 0,
        output_sections: int = 0,
        details: Optional[dict] = None,
        model_used: str = "",
        tokens_input: int = 0,
        tokens_output: int = 0,
        notes: str = "",
    ) -> None:
        """Record run completion."""
        if not run_id:
            return
        try:
            now = datetime.now(timezone.utc)
            conn = _get_connection()
            conn.autocommit = True
            cur = conn.cursor()

            cur.execute("SELECT started_at FROM tool_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            started_at = row[0] if row else now
            duration = (now - started_at).total_seconds()

            cur.execute(
                """UPDATE tool_runs SET
                    finished_at = %s, duration_sec = %s, status = %s,
                    result_url = %s, items_processed = %s, output_sections = %s,
                    details = %s, model_used = %s, tokens_input = %s,
                    tokens_output = %s, notes = %s
                WHERE id = %s""",
                (
                    now, duration, status,
                    result_url or None, items_processed or None, output_sections or None,
                    json.dumps(details) if details else None,
                    model_used or None, tokens_input or None, tokens_output or None,
                    notes or None, run_id,
                ),
            )

            cur.execute(
                """UPDATE tools SET
                    total_runs = total_runs + 1,
                    last_run_at = %s,
                    last_status = %s,
                    updated_at = %s
                WHERE slug = %s""",
                (now, status, now, self.tool_slug),
            )

            cur.close()
            conn.close()
        except Exception as e:
            logger.warning("tool_logger.finish failed: %s", e)

    def error(
        self,
        run_id: Optional[str],
        stage: str = "",
        message: str = "",
    ) -> None:
        """Record run error."""
        if not run_id:
            return
        try:
            now = datetime.now(timezone.utc)
            conn = _get_connection()
            conn.autocommit = True
            cur = conn.cursor()

            cur.execute("SELECT started_at FROM tool_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            started_at = row[0] if row else now
            duration = (now - started_at).total_seconds()

            cur.execute(
                """UPDATE tool_runs SET
                    finished_at = %s, duration_sec = %s, status = 'error',
                    error_stage = %s, error_message = %s
                WHERE id = %s""",
                (now, duration, stage or None, message or None, run_id),
            )

            cur.execute(
                """UPDATE tools SET
                    total_runs = total_runs + 1,
                    last_run_at = %s,
                    last_status = 'error',
                    updated_at = %s
                WHERE slug = %s""",
                (now, now, self.tool_slug),
            )

            cur.close()
            conn.close()
        except Exception as e:
            logger.warning("tool_logger.error failed: %s", e)
