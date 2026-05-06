from __future__ import annotations

"""CLI runner for sync scripts.

Usage:
    python -m services.sheets_sync.runner <name|all>
    python -m services.sheets_sync.runner --list
    python -m services.sheets_sync.runner --test wb_stocks

Examples:
    python -m services.sheets_sync.runner wb_stocks
    python -m services.sheets_sync.runner all
    python -m services.sheets_sync.runner fin_data --start 01.01.2026 --end 07.01.2026
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass

from services.sheets_sync.config import LOG_LEVEL, TEST_MODE, SPREADSHEET_IDS, set_active_spreadsheet_id

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    name: str
    sheet_name: str
    status: str  # "ok", "error", "skipped"
    rows: int
    duration_sec: float
    error: str


# Registry of available sync scripts
SYNC_REGISTRY: dict[str, dict] = {
    "wb_stocks": {
        "module": "services.sheets_sync.sync.sync_wb_stocks",
        "sheet": "WB остатки",
        "description": "WB warehouse remains (async report)",
    },
    "wb_prices": {
        "module": "services.sheets_sync.sync.sync_wb_prices",
        "sheet": "WB Цены",
        "description": "WB prices (paginated)",
    },
    "moysklad": {
        "module": "services.sheets_sync.sync.sync_moysklad",
        "sheet": "МойСклад_АПИ",
        "description": "MoySklad assortment + additional data",
    },
    "ozon": {
        "module": "services.sheets_sync.sync.sync_ozon_stocks_prices",
        "sheet": "Ozon остатки и цены",
        "description": "OZON stocks & prices (report-based)",
    },
    "wb_feedbacks": {
        "module": "services.sheets_sync.sync.sync_wb_feedbacks",
        "sheet": "Отзывы ООО / Отзывы ИП",
        "description": "WB feedbacks rating aggregation",
    },
    "fin_data": {
        "module": "services.sheets_sync.sync.sync_fin_data",
        "sheet": "Фин данные",
        "description": "Financial data (WB+OZON) per barcode for period",
    },
    "wb_bundles": {
        "module": "services.sheets_sync.sync.sync_wb_bundles",
        "sheet": "Склейки WB",
        "description": "WB bundle prices update",
    },
    "ozon_bundles": {
        "module": "services.sheets_sync.sync.sync_ozon_bundles",
        "sheet": "Склейки Озон",
        "description": "OZON bundle prices update",
    },
    "search_analytics": {
        "module": "services.sheets_sync.sync.sync_search_analytics",
        "sheet": "Аналитика по запросам",
        "description": "WB search analytics (keywords + per-article)",
    },
    "search_queries": {
        "module": "services.sheets_sync.sync.sync_search_queries",
        "sheet": "Аналитика по запросам",
        "description": "WB search query analytics with batching (GAS replacement)",
    },
    "fin_data_new": {
        "module": "services.sheets_sync.sync.sync_fin_data_new",
        "sheet": "Фин данные NEW",
        "description": "Financial data NEW (simplified 21 columns, WB+OZON) per barcode",
    },
}


def run_sync(name: str, start_date: str | None = None, end_date: str | None = None,
             spreadsheet_id: str | None = None) -> SyncResult:
    """Run a single sync by name, optionally targeting a specific spreadsheet."""
    info = SYNC_REGISTRY.get(name)
    if not info:
        return SyncResult(name=name, sheet_name="", status="error", rows=0, duration_sec=0, error=f"Unknown sync: {name}")

    module_path = info["module"]
    sheet = info["sheet"]

    logger.info("Running sync: %s -> %s", name, sheet)
    t0 = time.time()

    # Temporarily override active spreadsheet ID if a specific one is requested
    if spreadsheet_id:
        set_active_spreadsheet_id(spreadsheet_id)

    try:
        mod = __import__(module_path, fromlist=["sync"])
        sync_fn = mod.sync

        # Pass date arguments for scripts that support period selection
        if name in ("fin_data", "fin_data_new", "wb_feedbacks") and (start_date or end_date):
            rows = sync_fn(start_date=start_date, end_date=end_date)
        else:
            rows = sync_fn()

        duration = time.time() - t0
        return SyncResult(name=name, sheet_name=sheet, status="ok", rows=rows, duration_sec=round(duration, 1), error="")

    except Exception as e:
        duration = time.time() - t0
        logger.exception("Sync %s failed", name)
        return SyncResult(name=name, sheet_name=sheet, status="error", rows=0, duration_sec=round(duration, 1), error=str(e))

    finally:
        if spreadsheet_id:
            set_active_spreadsheet_id(None)


def run_all(start_date: str | None = None, end_date: str | None = None) -> list[SyncResult]:
    """Run all syncs sequentially for every configured spreadsheet."""
    results = []
    for sid in SPREADSHEET_IDS:
        short_id = sid[:8]
        logger.info("Running all syncs for spreadsheet %s...", short_id)
        for name in SYNC_REGISTRY:
            result = run_sync(name, start_date=start_date, end_date=end_date, spreadsheet_id=sid)
            results.append(result)
            logger.info("  [%s] %s: %s (%d rows, %.1fs)", short_id, result.name, result.status, result.rows, result.duration_sec)
    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run sync scripts for WB/OZON/MoySklad -> Google Sheets")
    parser.add_argument("sync_name", nargs="?", help="Sync name or 'all'")
    parser.add_argument("--list", action="store_true", help="List available syncs")
    parser.add_argument("--test", action="store_true", help="Force test mode")
    parser.add_argument("--start", help="Start date DD.MM.YYYY (for fin_data, wb_feedbacks)")
    parser.add_argument("--end", help="End date DD.MM.YYYY (for fin_data, wb_feedbacks)")

    args = parser.parse_args()

    if args.list:
        print(f"\nAvailable syncs (TEST_MODE={'ON' if TEST_MODE else 'OFF'}):\n")
        for name, info in SYNC_REGISTRY.items():
            suffix = "_TEST" if TEST_MODE else ""
            print(f"  {name:<20} -> {info['sheet']}{suffix}")
            print(f"  {'':20}    {info['description']}")
        print("\nUsage: python -m services.sheets_sync.runner <name|all>")
        return

    if not args.sync_name:
        parser.print_help()
        sys.exit(1)

    mode_str = "TEST" if TEST_MODE else "PRODUCTION"
    print(f"\nMode: {mode_str}")
    print(f"{'=' * 50}")

    # Tool logging
    try:
        from shared.tool_logger import ToolLogger
        _tl = ToolLogger("sheets-sync")
        _run_id = _tl.start(trigger=os.getenv("RUN_TRIGGER", "manual"), user=os.getenv("USER_EMAIL", "unknown"), environment=os.getenv("ENVIRONMENT", "local"))
    except Exception:
        _tl, _run_id = None, None

    if args.sync_name == "all":
        results = run_all(start_date=args.start, end_date=args.end)
        print(f"\n{'=' * 50}")
        print(f"{'Sync':<20} {'Status':<8} {'Rows':<8} {'Time':<8}")
        print(f"{'-' * 50}")
        for r in results:
            print(f"{r.name:<20} {r.status:<8} {r.rows:<8} {r.duration_sec:.1f}s")
            if r.error:
                print(f"  ERROR: {r.error[:80]}")

        # Update status sheet
        try:
            from services.sheets_sync.status import update_status
            update_status(results)
        except Exception as e:
            logger.error("Failed to update status sheet: %s", e)
    else:
        if args.sync_name not in SYNC_REGISTRY:
            print(f"Unknown sync: {args.sync_name}")
            print("Use --list to see available syncs")
            sys.exit(1)

        result = run_sync(args.sync_name, start_date=args.start, end_date=args.end)
        print(f"\nResult: {result.status} | {result.rows} rows | {result.duration_sec:.1f}s")
        if result.error:
            print(f"Error: {result.error}")

        # Update status sheet
        try:
            from services.sheets_sync.status import update_status
            update_status([result])
        except Exception as e:
            logger.error("Failed to update status sheet: %s", e)

        if result.status == "error":
            if _tl and _run_id:
                _tl.error(_run_id, stage=args.sync_name, message=result.error or "unknown")
            sys.exit(1)

    # Finish logging
    if _tl and _run_id:
        total_rows = sum(r.rows for r in (results if args.sync_name == "all" else [result]))
        errors = [r for r in (results if args.sync_name == "all" else [result]) if r.status == "error"]
        _tl.finish(
            _run_id,
            status="success" if not errors else "error",
            items_processed=total_rows,
            details={"sync_name": args.sync_name, "errors": len(errors)},
        )


if __name__ == "__main__":
    main()
