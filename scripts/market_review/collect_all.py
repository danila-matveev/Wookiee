#!/usr/bin/env python3
"""Market Review — parallel data collection orchestrator.

Usage:
    python scripts/market_review/collect_all.py \
        --month 2026-03 \
        --sections "categories,our,competitors,models_ours,models_rivals,new_items" \
        --output /tmp/market_review_data.json
"""
from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from shared.tool_logger import ToolLogger

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ALL_SECTIONS = "categories,our,competitors,competitor_deep,discovery,models_ours,models_rivals,new_items"


def _month_range(month_str: str) -> tuple[str, str]:
    """Convert 'YYYY-MM' to (start, end) date strings.

    >>> _month_range('2026-03')
    ('2026-03-01', '2026-03-31')
    """
    dt = datetime.strptime(month_str, "%Y-%m")
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return f"{month_str}-01", f"{month_str}-{last_day:02d}"


def _prev_month(month_str: str) -> str:
    """Return previous month as 'YYYY-MM'.

    >>> _prev_month('2026-03')
    '2026-02'
    >>> _prev_month('2026-01')
    '2025-12'
    """
    dt = datetime.strptime(month_str, "%Y-%m")
    if dt.month == 1:
        return f"{dt.year - 1}-12"
    return f"{dt.year}-{dt.month - 1:02d}"


def run_collector(name: str, func, kwargs: dict) -> tuple[str, dict | None, str | None]:
    """Run a single collector, return (name, result, error)."""
    try:
        result = func(**kwargs)
        return name, result, None
    except Exception as e:
        return name, None, f"{type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Market Review data collector")
    parser.add_argument("--month", required=True, help="Month to analyse: YYYY-MM")
    parser.add_argument("--sections", default=ALL_SECTIONS,
                        help="Comma-separated sections to collect")
    parser.add_argument("--output", default="/tmp/market_review_data.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    period_start, period_end = _month_range(args.month)
    prev = _prev_month(args.month)
    prev_start, prev_end = _month_range(prev)
    sections = [s.strip() for s in args.sections.split(",")]

    tl = ToolLogger("/market-review")
    with tl.run(period_start=period_start, period_end=period_end) as run_meta:
        shared_kwargs = {
            "period_start": period_start,
            "period_end": period_end,
            "prev_start": prev_start,
            "prev_end": prev_end,
        }

        # Import collectors based on requested sections
        collectors: dict[str, tuple] = {}

        if "categories" in sections:
            from scripts.market_review.collectors.market_categories import collect_market_categories
            collectors["categories"] = (collect_market_categories, shared_kwargs)

        if "our" in sections:
            from scripts.market_review.collectors.our_performance import collect_our_performance
            collectors["our"] = (collect_our_performance, shared_kwargs)

        if "competitors" in sections:
            from scripts.market_review.collectors.competitors_brands import collect_competitors_brands
            collectors["competitors"] = (collect_competitors_brands, shared_kwargs)

        if "models_ours" in sections:
            from scripts.market_review.collectors.top_models_ours import collect_top_models_ours
            collectors["models_ours"] = (collect_top_models_ours, shared_kwargs)

        if "models_rivals" in sections:
            from scripts.market_review.collectors.top_models_rivals import collect_top_models_rivals
            collectors["models_rivals"] = (collect_top_models_rivals, shared_kwargs)

        if "competitor_deep" in sections:
            from scripts.market_review.collectors.competitor_deep_dive import collect_competitor_deep_dive
            collectors["competitor_deep"] = (collect_competitor_deep_dive, shared_kwargs)

        if "discovery" in sections:
            from scripts.market_review.collectors.discovery_brands import collect_discovery_brands
            collectors["discovery"] = (collect_discovery_brands, shared_kwargs)

        if "new_items" in sections:
            from scripts.market_review.collectors.new_items import collect_new_items
            collectors["new_items"] = (collect_new_items, shared_kwargs)

        # Run collectors in parallel
        t0 = time.time()
        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(run_collector, name, func, kwargs): name
                for name, (func, kwargs) in collectors.items()
            }
            for future in as_completed(futures):
                name, result, error = future.result()
                if error:
                    errors[name] = error
                    print(f"[WARN] Collector {name} failed: {error}", file=sys.stderr)
                else:
                    results[name] = result
                    print(f"[OK] Collector {name} done")

        duration = round(time.time() - t0, 1)

        # Build output
        output = {
            **results,
            "meta": {
                "month": args.month,
                "period": {"start": period_start, "end": period_end},
                "prev_period": {"start": prev_start, "end": prev_end},
                "sections": sections,
                "errors": errors,
                "collection_duration_sec": duration,
            },
        }

        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        print(f"\nData saved to {args.output} ({duration}s, {len(errors)} errors)")

        run_meta["items"] = len(results)
        if errors:
            run_meta["notes"] = f"collector errors: {', '.join(errors.keys())}"
            sys.exit(1)


if __name__ == "__main__":
    main()
