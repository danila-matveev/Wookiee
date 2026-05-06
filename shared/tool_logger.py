"""Fire-and-forget tool run logger for Supabase.

Usage (context manager — recommended):
    from shared.tool_logger import ToolLogger
    tl = ToolLogger("finance-report")
    with tl.run(period_start="2026-05-01", period_end="2026-05-31") as run_meta:
        result = do_work()
        run_meta["url"] = result.notion_url   # optional Notion page URL
        run_meta["items"] = result.count       # optional items processed
    # trigger and user are auto-read from RUN_TRIGGER / USER_EMAIL env vars

Usage (manual):
    logger = ToolLogger("finance-report")
    run_id = logger.start(trigger="manual", user="danila@wookiee.shop")
    logger.finish(run_id, status="success", result_url="...", details={...})
    # or:
    logger.error(run_id, stage="data_collection", message="timeout")
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional

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

    @contextmanager
    def run(
        self,
        trigger: Optional[str] = None,
        user: Optional[str] = None,
        **kwargs,
    ) -> Generator[dict, None, None]:
        """Context manager that auto-logs start/finish/error.

        Reads USER_EMAIL and RUN_TRIGGER from env if not provided.
        Caller receives a dict to optionally set:
            run_meta["url"]   — Notion or other result URL
            run_meta["items"] — count of items processed
            run_meta["notes"] — free-form notes
            run_meta["stage"] — error stage name (used if exception raised)
        """
        _trigger = trigger or os.getenv("RUN_TRIGGER", "manual")
        _user = user or os.getenv("USER_EMAIL", "unknown")
        run_id = self.start(trigger=_trigger, user=_user, **kwargs)
        run_meta: dict = {}
        try:
            yield run_meta
            self.finish(
                run_id,
                status="success",
                result_url=run_meta.get("url", ""),
                items_processed=run_meta.get("items", 0),
                notes=run_meta.get("notes", ""),
            )
        except BaseException as e:
            # SystemExit(0) = success (caller explicitly chose clean exit)
            if isinstance(e, SystemExit) and e.code == 0:
                self.finish(run_id, status="success",
                            result_url=run_meta.get("url", ""),
                            items_processed=run_meta.get("items", 0),
                            notes=run_meta.get("notes", ""))
            else:
                self.error(run_id, stage=run_meta.get("stage", "main"), message=str(e))
            raise

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
