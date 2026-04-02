#!/usr/bin/env python3
"""Financial Overview — parallel data collection orchestrator.

Usage:
    python scripts/financial_overview/collect_all.py \
        --period-a "2026-01-01:2026-03-31" \
        --period-b "2025-10-01:2025-12-31" \
        --sections "finance,organic,ads,performance,smm,bloggers" \
        --output /tmp/financial_overview_data.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def parse_period(period_str: str) -> tuple[str, str]:
    """Parse 'YYYY-MM-DD:YYYY-MM-DD' into (start, end) strings."""
    start, end = period_str.split(":")
    return start.strip(), end.strip()


def run_collector(name: str, func, kwargs: dict) -> tuple[str, dict | None, str | None]:
    """Run a single collector, return (name, result, error)."""
    try:
        result = func(**kwargs)
        return name, result, None
    except Exception as e:
        return name, None, f"{type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Financial Overview data collector")
    parser.add_argument("--period-a", required=True, help="Current period: YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--period-b", required=True, help="Comparison period: YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--sections", default="finance,organic,ads,performance,smm,bloggers",
                        help="Comma-separated sections to collect")
    parser.add_argument("--output", default="/tmp/financial_overview_data.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    a_start, a_end = parse_period(args.period_a)
    b_start, b_end = parse_period(args.period_b)
    sections = [s.strip() for s in args.sections.split(",")]

    # Import collectors based on requested sections
    collectors = {}
    if "finance" in sections or "ads" in sections:
        from scripts.financial_overview.collectors.wb_ozon_finance import collect_finance
        collectors["wb_ozon_finance"] = (collect_finance, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "organic" in sections:
        from scripts.financial_overview.collectors.wb_funnel import collect_funnel
        collectors["wb_funnel"] = (collect_funnel, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "performance" in sections:
        from scripts.financial_overview.collectors.sheets_performance import collect_performance
        collectors["sheets_performance"] = (collect_performance, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "smm" in sections:
        from scripts.financial_overview.collectors.sheets_smm import collect_smm
        collectors["sheets_smm"] = (collect_smm, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })
    if "bloggers" in sections:
        from scripts.financial_overview.collectors.sheets_bloggers import collect_bloggers
        collectors["sheets_bloggers"] = (collect_bloggers, {
            "a_start": a_start, "a_end": a_end,
            "b_start": b_start, "b_end": b_end,
        })

    # Run collectors in parallel
    t0 = time.time()
    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=5) as pool:
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
            "period_a": {"start": a_start, "end": a_end},
            "period_b": {"start": b_start, "end": b_end},
            "sections": sections,
            "errors": errors,
            "quality_flags": {},
            "collection_duration_sec": duration,
        },
    }

    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nData saved to {args.output} ({duration}s, {len(errors)} errors)")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
