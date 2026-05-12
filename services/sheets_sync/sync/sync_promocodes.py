"""WB Promocodes weekly analytics sync — pivot layout.

Pulls reportDetailByPeriod v5 for both cabinets, aggregates by uuid_promocode,
joins with a manually maintained dictionary sheet, and writes into a pivot
table where rows = (UUID × cabinet) and columns = ISO weeks.

This module is a thin facade over `services.sheets_sync.sync.promocodes.*`.
Public symbols are re-exported here so existing imports — and `unittest.mock.patch`
targets used by tests — keep working unchanged.
"""
from __future__ import annotations

import logging
import os
from datetime import date

from shared.clients.sheets_client import get_moscow_now

from .promocodes.aggregate import aggregate_by_uuid
from .promocodes.dashboard import compute_dashboard_summary, write_dashboard_header
from .promocodes.db_io import write_product_breakdown, write_weekly_metrics
from .promocodes.dictionary import _truthy, parse_dictionary
from .promocodes.legacy import ANALYTICS_HEADERS, format_analytics_row
from .promocodes.pivot import (
    _read_pivot_state,
    ensure_analytics_dict_rows,
    upsert_pivot,
)
from .promocodes.sheet_io import (
    ensure_analytics_sheet,
    read_dictionary_sheet,
)
from .promocodes.wb_api import fetch_report
from .promocodes.weeks import iso_weeks_back, last_closed_iso_week

__all__ = [
    # Pure helpers (tests import these)
    "last_closed_iso_week", "iso_weeks_back",
    "aggregate_by_uuid",
    "parse_dictionary", "_truthy",
    "compute_dashboard_summary",
    "ANALYTICS_HEADERS", "format_analytics_row",
    # Side-effecting helpers (tests patch these on this module)
    "fetch_report",
    "read_dictionary_sheet", "ensure_analytics_sheet",
    "_read_pivot_state", "ensure_analytics_dict_rows", "upsert_pivot",
    "write_dashboard_header",
    "write_weekly_metrics", "write_product_breakdown",
    # Orchestrator
    "run",
]

logger = logging.getLogger(__name__)


# ── Orchestrator helpers ─────────────────────────────────────────────────────

def _resolve_weeks(mode: str, week_from: date | None, week_to: date | None,
                   weeks_back: int) -> list[tuple[date, date]]:
    if mode == "last_week":
        return [last_closed_iso_week()]
    if mode == "specific":
        if not (week_from and week_to):
            raise ValueError("specific mode requires week_from and week_to")
        return [(week_from, week_to)]
    if mode == "bootstrap":
        return iso_weeks_back(weeks_back)
    raise ValueError(f"Unknown mode: {mode}")


def _cabinets_from_env() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, key_env in (("ИП", "WB_API_KEY_IP"), ("ООО", "WB_API_KEY_OOO")):
        key = os.getenv(key_env, "").strip()
        if key:
            out.append((name, key))
        else:
            logger.warning("Skip cabinet %s — %s not set", name, key_env)
    return out


# ── Main entry point ─────────────────────────────────────────────────────────

def _merge_for_db(
    week_data: dict[tuple[str, str], dict],
) -> dict[str, dict]:
    """Merge per-(uuid, cabinet) metrics into per-uuid totals for DB write.

    Both ИП and ООО cabinets share the same WB seller statistics, so the same
    order appears in both responses. To avoid double-counting, we take only the
    first occurrence of each uuid (preferring ООО over ИП).
    """
    # Prefer ООО data; fall back to any other cabinet for uuids not in ООО
    seen: set[str] = set()
    merged: dict[str, dict] = {}

    for preferred_cab in ("ООО", None):  # two passes: ООО first, then the rest
        for (uuid, cab), data in week_data.items():
            if uuid in seen:
                continue
            if preferred_cab is not None and cab != preferred_cab:
                continue
            seen.add(uuid)
            m = data["metrics"]
            merged[uuid] = {
                "sales_rub": m["sales_rub"],
                "ppvz_rub": m["ppvz_rub"],
                "orders_count": m["orders_count"],
                "returns_count": m["returns_count"],
                "avg_discount_pct": m["avg_discount_pct"],
            }

    return merged


def run(
    mode: str = "last_week",
    week_from: date | None = None,
    week_to: date | None = None,
    weeks_back: int = 12,
    cabinets: list[tuple[str, str]] | None = None,
    write_to_db: bool = True,
    write_to_sheets: bool = True,
) -> dict:
    """Main entry point. Returns status dict.

    Each side-effecting helper is referenced by its module-level name so tests
    can substitute them with `unittest.mock.patch` against this module.

    write_to_sheets=False is used for long historical backfills so we don't
    pollute the live pivot with many weeks of legacy data. Dictionary lookups
    still happen — only the per-week pivot UPSERT and dashboard header are
    skipped.
    """
    started = get_moscow_now()
    cabs = cabinets or _cabinets_from_env()
    if not cabs:
        return {"status": "error", "error": "No cabinets configured",
                "started_at": started.isoformat(timespec="seconds")}

    weeks = _resolve_weeks(mode, week_from, week_to, weeks_back)
    dictionary = read_dictionary_sheet()
    ws = ensure_analytics_sheet() if write_to_sheets else None
    if write_to_sheets:
        week_col_map, uuid_row_map = _read_pivot_state(ws)
    else:
        week_col_map, uuid_row_map = {}, {}

    # Dictionary IS the main sheet (single source of truth) — no pre-population.
    # Unknown UUIDs from WB are auto-appended by upsert_pivot with status="требует review".
    rows_added = 0
    rows_updated = 0
    db_rows_written = 0
    unknown_set: set[str] = set()
    last_week_aggs: dict[str, dict] = {}

    # Process oldest week first so columns grow left→right chronologically
    pb_rows_written = 0
    for week_start, week_end in reversed(weeks):
        week_data: dict[tuple[str, str], dict] = {}
        api_rows_by_cab: dict[str, list[dict]] = {}

        for cab_name, api_key in cabs:
            api_rows = fetch_report(api_key, cab_name, week_start, week_end)
            api_rows_by_cab[cab_name] = api_rows
            agg = aggregate_by_uuid(api_rows)
            # Always record everything the API returns — dictionary cabinet
            # flags only drive pre-population, not API filtering. Unknown
            # UUIDs are tracked separately so the team can add them later.
            for uuid, m in agg.items():
                info = dictionary.get(uuid.lower()) or {}
                if not info:
                    unknown_set.add(uuid)
                week_data[(uuid, cab_name)] = {
                    "metrics": m,
                    "name": info.get("name") or "неизвестный",
                    "channel": cab_name,
                    "discount": (
                        info["discount_pct"]
                        if info.get("discount_pct") is not None
                        else round(m["avg_discount_pct"], 2)
                    ),
                }

            # Accumulate latest-week summary (weeks[0] is the most recent)
            if (week_start, week_end) == weeks[0]:
                for uuid, m in agg.items():
                    if uuid not in last_week_aggs:
                        last_week_aggs[uuid] = dict(m)
                    else:
                        last_week_aggs[uuid]["sales_rub"] += m["sales_rub"]
                        last_week_aggs[uuid]["orders_count"] += m["orders_count"]

        if write_to_sheets:
            a, u = upsert_pivot(ws, week_start, week_end, week_data,
                                week_col_map, uuid_row_map)
            rows_added += a
            rows_updated += u

        if write_to_db and week_data:
            merged = _merge_for_db(week_data)
            written = write_weekly_metrics(week_start, merged)
            db_rows_written += written
            pb_written = write_product_breakdown(week_start, api_rows_by_cab)
            pb_rows_written += pb_written
            logger.info(
                "DB: wrote %d weekly + %d product_breakdown for week %s",
                written, pb_written, week_start,
            )

    if write_to_sheets:
        summary = compute_dashboard_summary(last_week_aggs, dictionary)
        write_dashboard_header(ws, summary, weeks)

    finished = get_moscow_now()
    return {
        "status": "ok",
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "weeks_processed": [(s.isoformat(), e.isoformat()) for s, e in weeks],
        "cabinets": [c[0] for c in cabs],
        "rows_added": rows_added,
        "rows_updated": rows_updated,
        "product_breakdown_rows": pb_rows_written,
        "db_rows_written": db_rows_written,
        "unknown_uuids": sorted(unknown_set),
    }
