"""Hub → Sheets mirror sync entrypoint.

CLI:
    python -m services.sheets_sync.hub_to_sheets.runner --all
    python -m services.sheets_sync.hub_to_sheets.runner --sheet "Все модели"
    python -m services.sheets_sync.hub_to_sheets.runner --smoke
    python -m services.sheets_sync.hub_to_sheets.runner --sheet "Все товары" --dry-run

Programmatic:
    from services.sheets_sync.hub_to_sheets.runner import sync_all, sync_one
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

from dataclasses import replace

from services.sheets_sync.hub_to_sheets.batch import SheetsBatchWriter
from services.sheets_sync.hub_to_sheets.config import (
    ARCHIVE_STATUS_VALUE,
    SHEET_SPECS,
    SheetSpec,
    get_spec,
)
from services.sheets_sync.hub_to_sheets.diff import diff_sheet
from services.sheets_sync.hub_to_sheets.exporter import fetch_view

logger = logging.getLogger(__name__)


def _retarget_view(spec: SheetSpec, views_schema: str) -> SheetSpec:
    """Re-point a SheetSpec at a non-default Postgres schema (e.g. test fixtures).

    Default views live in `public.vw_export_*`. With `views_schema='test_catalog_sync'`
    the spec is rewritten to `test_catalog_sync.vw_export_*`.
    """
    if not views_schema or views_schema == "public":
        return spec
    qualified = spec.view_name.split(".", 1)
    view = qualified[1] if len(qualified) == 2 else qualified[0]
    return replace(spec, view_name=f"{views_schema}.{view}")


def _sync_one(spec: SheetSpec, writer: SheetsBatchWriter) -> dict:
    """Sync a single tab. Returns a metrics dict."""
    started = time.time()
    logger.info("→ %s (view=%s)", spec.sheet_name, spec.view_name)

    db_columns, db_rows = fetch_view(spec.view_name)
    sheet_columns, sheet_rows = writer.read_sheet(spec.sheet_name)
    if not sheet_columns:
        raise RuntimeError(f"Sheet '{spec.sheet_name}' has no header row")

    diff = diff_sheet(
        sheet_name=spec.sheet_name,
        db_columns=db_columns,
        db_rows=db_rows,
        sheet_columns=sheet_columns,
        sheet_rows=sheet_rows,
        anchor_cols=spec.anchor_cols,
        status_col=spec.status_col,
        archive_value=ARCHIVE_STATUS_VALUE,
    )

    metrics = writer.apply_updates(diff.cell_updates, diff.row_appends, diff.row_deletes)
    duration_ms = int((time.time() - started) * 1000)
    metrics.update(
        sheet=spec.sheet_name,
        view=spec.view_name,
        duration_ms=duration_ms,
        db_rows=len(db_rows),
        matched=diff.matched,
        appended=diff.appended,
        archived=diff.archived,
        deleted=diff.deleted,
    )
    logger.info(
        "✓ %s: db=%d matched=%d appended=%d archived=%d deleted=%d cells=%d in %dms",
        spec.sheet_name,
        len(db_rows),
        diff.matched,
        diff.appended,
        diff.archived,
        diff.deleted,
        metrics["cells_updated"],
        duration_ms,
    )
    return metrics


def sync_one(
    sheet_name: str,
    *,
    dry_run: bool = False,
    spreadsheet_id: str = "",
    views_schema: str = "public",
) -> dict:
    """Public API: sync a single tab by name."""
    writer = SheetsBatchWriter(spreadsheet_id=spreadsheet_id, dry_run=dry_run)
    return _sync_one(_retarget_view(get_spec(sheet_name), views_schema), writer)


def sync_all(
    *,
    dry_run: bool = False,
    spreadsheet_id: str = "",
    views_schema: str = "public",
) -> dict:
    """Public API: sync all 6 tabs in a single connection."""
    writer = SheetsBatchWriter(spreadsheet_id=spreadsheet_id, dry_run=dry_run)
    started = time.time()
    per_sheet: list[dict] = []
    errors: list[dict] = []
    for spec in SHEET_SPECS:
        try:
            per_sheet.append(_sync_one(_retarget_view(spec, views_schema), writer))
        except Exception as exc:
            logger.exception("sync failed for %s", spec.sheet_name)
            errors.append({"sheet": spec.sheet_name, "error": str(exc)})

    total_cells = sum(m.get("cells_updated", 0) for m in per_sheet)
    total_rows  = sum(m.get("rows_appended", 0) for m in per_sheet)
    total_del   = sum(m.get("rows_deleted", 0) for m in per_sheet)

    summary = {
        "duration_ms":    int((time.time() - started) * 1000),
        "cells_updated":  total_cells,
        "rows_appended":  total_rows,
        "rows_deleted":   total_del,
        "sheets_synced":  [m["sheet"] for m in per_sheet],
        "per_sheet":      per_sheet,
        "errors":         errors,
        "status":         "error" if errors else "ok",
    }
    logger.info(
        "Σ %s: cells=%d appended=%d deleted=%d in %dms (errors=%d)",
        summary["status"],
        total_cells,
        total_rows,
        total_del,
        summary["duration_ms"],
        len(errors),
    )
    return summary


def smoke(*, spreadsheet_id: str = "") -> dict:
    """Read-only check: ensure mirror is reachable and headers look sane."""
    writer = SheetsBatchWriter(spreadsheet_id=spreadsheet_id, dry_run=True)
    out: dict = {"spreadsheet_id": writer.spreadsheet_id, "sheets": {}}
    for spec in SHEET_SPECS:
        header, rows = writer.read_sheet(spec.sheet_name)
        out["sheets"][spec.sheet_name] = {
            "header_cols":   len(header),
            "data_rows":     len(rows),
            "anchor_ok":     all(c in header for c in spec.anchor_cols),
            "status_col_ok": (spec.status_col is None) or (spec.status_col in header),
        }
        logger.info(
            "smoke %s: cols=%d rows=%d anchor_ok=%s status_col_ok=%s",
            spec.sheet_name,
            len(header),
            len(rows),
            out["sheets"][spec.sheet_name]["anchor_ok"],
            out["sheets"][spec.sheet_name]["status_col_ok"],
        )
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hub_to_sheets")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="sync every tab")
    grp.add_argument("--sheet", help="sync a single tab (e.g. 'Все модели')")
    grp.add_argument("--smoke", action="store_true", help="read-only smoke check")
    p.add_argument("--dry-run", action="store_true", help="compute diff but skip writes")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument(
        "--spreadsheet-id",
        default="",
        help="override CATALOG_MIRROR_SHEET_ID env var (used for QA against a test mirror)",
    )
    p.add_argument(
        "--views-schema",
        default="public",
        help="Postgres schema for vw_export_* views (default: public)",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.smoke:
        result = smoke(spreadsheet_id=args.spreadsheet_id)
    elif args.all:
        result = sync_all(
            dry_run=args.dry_run,
            spreadsheet_id=args.spreadsheet_id,
            views_schema=args.views_schema,
        )
    else:
        result = sync_one(
            args.sheet,
            dry_run=args.dry_run,
            spreadsheet_id=args.spreadsheet_id,
            views_schema=args.views_schema,
        )

    import json
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if isinstance(result, dict) and result.get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
