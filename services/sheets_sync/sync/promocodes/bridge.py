"""DB→Sheets bridge for wb-promocodes sync.

Before pulling weekly metrics from the WB API, ensure all active promo codes
from `crm.promo_codes` are present in the analytics sheet's dictionary section
(col A — «Название», starting at DATA_START_ROW = 11). Codes added through the
Marketing Hub UI (Phase 2A: AddPromoPanel) live only in the DB — without this
bridge they'd be invisible until the next operator-driven manual edit, even
though the WB API may already have started returning data for them under a
matching `uuid_promocode`.

Match key: code string (case-insensitive) against col A. UUIDs are filled in
later when the WB API call discovers the row via `upsert_pivot`.
"""
from __future__ import annotations

import logging

import psycopg2.extras

from services.sheets_etl.loader import get_conn

from .sheet_layout import DATA_START_ROW, FIXED_NCOLS, STATUS_NEW

logger = logging.getLogger(__name__)


def fetch_db_promocodes() -> list[str]:
    """Fetch all active promo codes from `crm.promo_codes`.

    Returns a list of code strings (uppercased / trimmed as stored). Only
    `status = 'active'` rows are returned — paused/expired/archived codes are
    intentionally excluded so retired promos don't pollute the dictionary.

    Raises whatever psycopg2 raises on connection / query failure — caller
    decides whether to abort the sync.
    """
    rows: list[str] = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT code
                FROM crm.promo_codes
                WHERE status = 'active'
                  AND code IS NOT NULL
                  AND TRIM(code) <> ''
                ORDER BY code
                """
            )
            for (code,) in cur.fetchall():
                rows.append(code.strip())
    finally:
        conn.close()
    return rows


def plan_promo_inserts(db_codes: list[str], sheet_codes: set[str]) -> list[str]:
    """Return the subset of db_codes not yet present in sheet_codes.

    Matching is case-insensitive on the code label (col A in the analytics
    sheet). Result preserves db_codes order so callers can append rows in a
    deterministic — usually sorted — sequence.
    """
    sheet_lower = {(c or "").strip().lower() for c in sheet_codes if c}
    inserts: list[str] = []
    seen_lower: set[str] = set()
    for code in db_codes:
        if not code:
            continue
        norm = code.strip()
        if not norm:
            continue
        key = norm.lower()
        if key in sheet_lower or key in seen_lower:
            continue
        seen_lower.add(key)
        inserts.append(norm)
    return inserts


def ensure_db_promos_in_sheets(ws, db_codes: list[str] | None = None) -> int:
    """Append missing DB promo codes to the analytics sheet's dictionary section.

    Args:
        ws: gspread Worksheet — `Промокоды_аналитика` (the pivot table; cols
            A-E hold the dictionary).
        db_codes: optional pre-fetched list (test injection point); when None,
            the function calls `fetch_db_promocodes()` itself.

    Returns count of rows inserted (0 if everything is already in sync).

    Each insert writes a single row with code in col A and `STATUS_NEW`
    («требует review») in col E so the operator can fill in UUID / channel /
    discount manually. Subsequent WB pulls will populate weekly metrics once
    the row's UUID matches a `uuid_promocode` from the API.

    Raises on DB / Sheets failures so the caller can abort the WB pull rather
    than silently drift.
    """
    try:
        col_a = ws.col_values(1)
    except Exception:
        logger.exception("Promo bridge: failed to read sheet col A")
        raise

    # Existing dictionary entries start at DATA_START_ROW (11). Values above
    # that row are dashboard / header text and must not be diffed against.
    sheet_codes: set[str] = {
        (c or "").strip() for c in col_a[DATA_START_ROW - 1:] if c and (c or "").strip()
    }

    if db_codes is None:
        try:
            db_codes = fetch_db_promocodes()
        except Exception:
            logger.exception("Promo bridge: failed to fetch crm.promo_codes")
            raise

    inserts = plan_promo_inserts(db_codes, sheet_codes)
    if not inserts:
        logger.info(
            "Promo bridge: no new codes to insert (sheet=%d, db=%d)",
            len(sheet_codes), len(db_codes),
        )
        return 0

    # Append at the bottom of the dictionary section. Each row is exactly
    # FIXED_NCOLS wide so col E (Статус) lands on the right column.
    try:
        for code in sorted(inserts):
            row_values = [code, "", "", "", STATUS_NEW]
            # Pad to FIXED_NCOLS in case STATUS column index changes later.
            row_values = (row_values + [""] * FIXED_NCOLS)[:FIXED_NCOLS]
            ws.append_row(row_values, value_input_option="USER_ENTERED")
    except Exception:
        logger.exception("Promo bridge: failed to append rows to sheet")
        raise

    logger.info(
        "Promo bridge: inserted %d new codes into Sheets (db=%d)",
        len(inserts), len(db_codes),
    )
    return len(inserts)


__all__ = [
    "ensure_db_promos_in_sheets",
    "fetch_db_promocodes",
    "plan_promo_inserts",
]
