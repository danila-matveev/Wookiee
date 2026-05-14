"""Marketing sync trigger endpoints.

POST /api/marketing/sync/{job_name}        — start sync subprocess in background
GET  /api/marketing/sync/{job_name}/status — read latest marketing.sync_log row

Uses psycopg2 via shared.data_layer._connection._get_supabase_connection (the
project-wide pattern); no separate supabase Python client is needed.
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from services.analytics_api.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketing", tags=["marketing"])

# Job name -> script path (relative to project root).
JOB_SCRIPTS: dict[str, str] = {
    "search-queries": "scripts/run_search_queries_sync.py",
    "promocodes":     "scripts/run_wb_promocodes_sync.py",
}

# URL slug → canonical sync_log job_name (snake_case used by cron scripts).
# We keep the URL slug hyphenated for REST hygiene but persist the canonical
# snake_case name in marketing.sync_log so cron-driven and manually-triggered
# runs share a single history (frontend reads by canonical name too).
JOB_LOG_NAMES: dict[str, str] = {
    "search-queries": "search_queries_sync",
    "promocodes":     "promo_codes_sync",
}

# 15-minute hard cap for any single sync subprocess.
SUBPROCESS_TIMEOUT_SECONDS = 900

# Regex to pull "rows_processed" hint from script stdout (best-effort).
# Matches lines like "rows_processed=1234", "wrote 1234 rows", etc.
_ROWS_PATTERNS = [
    re.compile(r"rows_processed[=:\s]+(\d+)", re.IGNORECASE),
    re.compile(r"wrote\s+(\d+)\s+rows?", re.IGNORECASE),
    re.compile(r"(\d+)\s+rows?\s+written", re.IGNORECASE),
]


def _project_root() -> Path:
    """Return absolute path to project root (parent of services/)."""
    return Path(__file__).resolve().parent.parent.parent


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_sync_log_entry(job_name: str, triggered_by: str = "analytics_api") -> int:
    """Insert a 'running' row into marketing.sync_log and return its id.

    Persists the canonical snake_case name (`search_queries_sync` / `promo_codes_sync`)
    regardless of the API URL slug, so manual triggers and cron history share a
    single timeline (see JOB_LOG_NAMES).
    """
    from shared.data_layer._connection import _get_supabase_connection

    log_name = JOB_LOG_NAMES.get(job_name, job_name)
    conn = _get_supabase_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marketing.sync_log (job_name, status, started_at, triggered_by)
                VALUES (%s, 'running', NOW(), %s)
                RETURNING id
                """,
                (log_name, triggered_by),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to insert sync_log row")
            new_id = int(row[0])
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_sync_log(
    sync_log_id: int,
    status: str,
    rows_processed: int | None = None,
    error_message: str | None = None,
) -> None:
    from shared.data_layer._connection import _get_supabase_connection

    conn = _get_supabase_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE marketing.sync_log
                SET status = %s,
                    finished_at = NOW(),
                    rows_processed = COALESCE(%s, rows_processed),
                    error_message = %s
                WHERE id = %s
                """,
                (status, rows_processed, error_message, sync_log_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _parse_rows_processed(text: str) -> int | None:
    """Best-effort extract of rows_processed from script stdout."""
    if not text:
        return None
    for pat in _ROWS_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


def run_sync_subprocess(job_name: str, sync_log_id: int) -> None:
    """Run the sync script in a subprocess and update sync_log on exit.

    Always updates marketing.sync_log row with status 'success' or 'failed';
    never raises (background-task contract). Errors are logged + written to DB.
    """
    script = JOB_SCRIPTS.get(job_name)
    if not script:
        _update_sync_log(sync_log_id, "failed", error_message=f"Unknown job: {job_name}")
        return

    cwd = _project_root()
    cmd = [sys.executable, script, "--mode", "last_week"]
    logger.info("Starting sync subprocess: %s (cwd=%s, sync_log_id=%d)", cmd, cwd, sync_log_id)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.error("Sync %s timed out after %ds", job_name, SUBPROCESS_TIMEOUT_SECONDS)
        try:
            _update_sync_log(
                sync_log_id,
                "failed",
                error_message=f"Timeout after {SUBPROCESS_TIMEOUT_SECONDS}s",
            )
        except Exception as e:
            logger.exception("Failed to mark sync_log %d as timed-out: %s", sync_log_id, e)
        return
    except Exception as e:
        logger.exception("Sync %s subprocess crashed: %s", job_name, e)
        try:
            _update_sync_log(sync_log_id, "failed", error_message=str(e)[:500])
        except Exception as inner:
            logger.exception("Failed to mark sync_log %d as failed: %s", sync_log_id, inner)
        return

    if result.returncode == 0:
        rows = _parse_rows_processed((result.stdout or "") + "\n" + (result.stderr or ""))
        try:
            _update_sync_log(sync_log_id, "success", rows_processed=rows)
        except Exception as e:
            logger.exception("Failed to mark sync_log %d as success: %s", sync_log_id, e)
    else:
        err = (result.stderr or result.stdout or "").strip()[-500:]
        logger.error("Sync %s exited %d: %s", job_name, result.returncode, err)
        try:
            _update_sync_log(sync_log_id, "failed", error_message=err or f"Exit code {result.returncode}")
        except Exception as e:
            logger.exception("Failed to mark sync_log %d as failed: %s", sync_log_id, e)


@router.post("/sync/{job_name}", dependencies=[Depends(require_auth)])
async def trigger_sync(job_name: str, bg: BackgroundTasks) -> dict:
    """Start a marketing sync job in the background.

    Returns immediately with the sync_log row id; the actual subprocess runs
    via FastAPI BackgroundTasks (in-process).
    """
    if job_name not in JOB_SCRIPTS:
        raise HTTPException(404, f"Unknown job: {job_name}")

    try:
        sync_log_id = create_sync_log_entry(job_name)
    except Exception as e:
        logger.exception("Failed to create sync_log entry for %s: %s", job_name, e)
        raise HTTPException(500, f"DB error: {e}")

    bg.add_task(run_sync_subprocess, job_name, sync_log_id)

    return {
        "job_name":    job_name,
        "status":      "running",
        "sync_log_id": sync_log_id,
        "started_at":  _now_iso(),
    }


@router.get("/sync/{job_name}/status", dependencies=[Depends(require_auth)])
async def sync_status(job_name: str) -> dict:
    """Return the latest sync_log row for the given job."""
    if job_name not in JOB_SCRIPTS:
        raise HTTPException(404, f"Unknown job: {job_name}")

    from shared.data_layer._connection import _get_supabase_connection

    log_name = JOB_LOG_NAMES.get(job_name, job_name)
    conn = _get_supabase_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, started_at, finished_at,
                       rows_processed, error_message
                FROM marketing.sync_log
                WHERE job_name = %s
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (log_name,),
            )
            row = cur.fetchone()
    except Exception as e:
        logger.exception("Failed to read sync_log for %s: %s", job_name, e)
        raise HTTPException(500, f"DB error: {e}")
    finally:
        conn.close()

    if not row:
        return {"status": "never_run", "job_name": job_name}

    sid, status, started_at, finished_at, rows_processed, error_message = row
    return {
        "id":             sid,
        "job_name":       job_name,
        "status":         status,
        "started_at":     started_at.isoformat() if started_at else None,
        "finished_at":    finished_at.isoformat() if finished_at else None,
        "rows_processed": rows_processed,
        "error_message":  error_message,
    }
