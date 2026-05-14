"""Hub → Sheets mirror sync trigger endpoints.

POST /api/catalog/sync-mirror  — kick off the Hub → Google Sheets mirror sync
                                  for a single tab or for everything; logs the
                                  run into public.tool_runs under the slug
                                  `catalog-sheets-mirror`.

Auth: Supabase JWT (Bearer) OR X-Api-Key (cron) — re-uses analytics_api.auth.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.analytics_api.auth import require_auth
from services.sheets_sync.hub_to_sheets.config import SHEET_SPECS
from services.sheets_sync.hub_to_sheets.runner import sync_all, sync_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

TOOL_SLUG = "catalog-sheets-mirror"

VALID_SHEETS = {s.sheet_name for s in SHEET_SPECS}
ALL_TOKEN = "all"  # noqa: S105 — sheet selector, not a credential


class SyncMirrorRequest(BaseModel):
    sheet: str = Field(
        default=ALL_TOKEN,
        description='"all" or one of the 6 mirror tab names (e.g. "Все модели")',
    )


class SyncMirrorResponse(BaseModel):
    status:         Literal["ok", "error"]
    sheet:          str
    duration_ms:    int
    cells_updated:  int
    rows_appended:  int
    rows_deleted:   int
    sheets_synced:  list[str]
    errors:         list[dict]
    run_id:         Optional[str] = None


# ---------------------------------------------------------------------------
# tool_runs helpers — direct psycopg2 so we don't reload shared.tool_logger's
# global state on each request.
# ---------------------------------------------------------------------------

def _start_run(triggered_by: str) -> Optional[str]:
    from shared.data_layer._connection import _get_supabase_connection

    run_id = str(uuid.uuid4())
    conn = None
    try:
        conn = _get_supabase_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tool_runs (id, tool_slug, status, started_at, triggered_by)
                VALUES (%s, %s, 'running', NOW(), %s)
                """,
                (run_id, TOOL_SLUG, triggered_by),
            )
        conn.commit()
        return run_id
    except Exception as exc:
        logger.warning("tool_runs insert failed for %s: %s", TOOL_SLUG, exc)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _finish_run(
    run_id: Optional[str],
    *,
    status: str,
    started_at: float,
    summary: dict,
    error: Optional[str] = None,
) -> None:
    if not run_id:
        return
    from shared.data_layer._connection import _get_supabase_connection

    duration_ms = int((time.time() - started_at) * 1000)
    output_summary = (
        f"sheets={summary.get('sheets_synced', [])} "
        f"cells={summary.get('cells_updated', 0)} "
        f"appended={summary.get('rows_appended', 0)} "
        f"deleted={summary.get('rows_deleted', 0)}"
    )
    conn = None
    try:
        conn = _get_supabase_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tool_runs
                SET status = %s,
                    finished_at = NOW(),
                    duration_ms = %s,
                    output_summary = %s,
                    error_message = %s
                WHERE id = %s
                """,
                (status, duration_ms, output_summary, error, run_id),
            )
        conn.commit()
    except Exception as exc:
        logger.warning("tool_runs update failed for %s: %s", run_id, exc)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/sync-mirror", response_model=SyncMirrorResponse, dependencies=[Depends(require_auth)])
def sync_mirror(payload: SyncMirrorRequest) -> SyncMirrorResponse:
    sheet = payload.sheet.strip() or ALL_TOKEN
    if sheet != ALL_TOKEN and sheet not in VALID_SHEETS:
        raise HTTPException(400, f"Unknown sheet '{sheet}'. Use 'all' or one of: {sorted(VALID_SHEETS)}")

    started_at = time.time()
    run_id = _start_run(triggered_by=f"hub:{sheet}")

    try:
        if sheet == ALL_TOKEN:
            summary = sync_all()
            sheets_synced = summary.get("sheets_synced", [])
            errors = summary.get("errors", [])
            status = summary.get("status", "ok")
        else:
            per = sync_one(sheet)
            summary = {
                "cells_updated": per.get("cells_updated", 0),
                "rows_appended": per.get("rows_appended", 0),
                "rows_deleted":  per.get("rows_deleted", 0),
                "sheets_synced": [per["sheet"]],
            }
            sheets_synced = summary["sheets_synced"]
            errors = []
            status = "ok"
    except Exception as exc:
        logger.exception("sync_mirror failed (sheet=%s)", sheet)
        _finish_run(run_id, status="error", started_at=started_at, summary={}, error=str(exc)[:500])
        raise HTTPException(500, f"Sync failed: {exc}")

    duration_ms = int((time.time() - started_at) * 1000)
    _finish_run(
        run_id,
        status="error" if status == "error" else "success",
        started_at=started_at,
        summary={
            "sheets_synced": sheets_synced,
            "cells_updated": summary.get("cells_updated", 0),
            "rows_appended": summary.get("rows_appended", 0),
            "rows_deleted":  summary.get("rows_deleted", 0),
        },
        error="; ".join(e.get("error", "") for e in errors) or None,
    )

    return SyncMirrorResponse(
        status="ok" if status == "ok" else "error",
        sheet=sheet,
        duration_ms=duration_ms,
        cells_updated=summary.get("cells_updated", 0),
        rows_appended=summary.get("rows_appended", 0),
        rows_deleted=summary.get("rows_deleted", 0),
        sheets_synced=sheets_synced,
        errors=errors,
        run_id=run_id,
    )


@router.get("/sync-mirror/status", dependencies=[Depends(require_auth)])
def sync_mirror_status() -> dict:
    """Return the most recent tool_runs entry for the catalog mirror."""
    from shared.data_layer._connection import _get_supabase_connection

    conn = _get_supabase_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, started_at, finished_at,
                       duration_ms, output_summary, error_message, triggered_by
                FROM tool_runs
                WHERE tool_slug = %s
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (TOOL_SLUG,),
            )
            row = cur.fetchone()
    except Exception as exc:
        logger.exception("sync_mirror_status read failed")
        raise HTTPException(500, f"DB error: {exc}")
    finally:
        conn.close()

    if not row:
        return {"status": "never_run"}

    rid, status, started, finished, duration_ms, summary, error, triggered_by = row
    return {
        "run_id":         str(rid),
        "status":         status,
        "started_at":     started.isoformat() if started else None,
        "finished_at":    finished.isoformat() if finished else None,
        "duration_ms":    duration_ms,
        "output_summary": summary,
        "error_message":  error,
        "triggered_by":   triggered_by,
    }
