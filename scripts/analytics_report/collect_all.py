"""Analytics report data collection orchestrator.

Usage:
    python scripts/analytics_report/collect_all.py --start 2026-04-05
    python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05
    python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05 --output /tmp/data.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from scripts.analytics_report.utils import compute_date_params, build_quality_flags
from scripts.analytics_report.collectors.finance import collect_finance
from scripts.analytics_report.collectors.advertising import collect_advertising
from scripts.analytics_report.collectors.external_marketing import collect_external_marketing
from scripts.analytics_report.collectors.traffic import collect_traffic
from scripts.analytics_report.collectors.inventory import collect_inventory
from scripts.analytics_report.collectors.pricing import collect_pricing
from scripts.analytics_report.collectors.plan_fact import collect_plan_fact
from scripts.analytics_report.collectors.sku_statuses import collect_sku_statuses


def run_collection(start_str: str, end_str: str | None = None) -> dict:
    """Run all 8 collectors in parallel and merge results.

    Args:
        start_str: period start date "YYYY-MM-DD".
        end_str: period end date "YYYY-MM-DD" (optional, defaults to start_str).

    Returns:
        Complete data bundle as JSON-serializable dict.
    """
    t0 = time.time()
    params = compute_date_params(start_str, end_str)

    cs = params["start_date"]       # current start
    ce = params["end_date"]         # current end (inclusive)
    ps = params["prev_start"]       # previous period start
    depth = params["depth"]
    month_start = params["month_start"]

    # data_layer uses EXCLUSIVE end dates
    ce_exclusive = (date.fromisoformat(ce) + timedelta(days=1)).isoformat()

    # Define 8 collector tasks
    tasks = {
        "finance": lambda: collect_finance(cs, ps, ce_exclusive, depth),
        "advertising": lambda: collect_advertising(cs, ps, ce_exclusive),
        "external_marketing": lambda: collect_external_marketing(cs, ce),  # Sheets: inclusive end
        "traffic": lambda: collect_traffic(cs, ps, ce_exclusive),
        "inventory": lambda: collect_inventory(cs, ce_exclusive),
        "pricing": lambda: collect_pricing(cs, ps, ce_exclusive),
        "plan_fact": lambda: collect_plan_fact(cs, ce, month_start),  # Sheets: inclusive end
        "sku_statuses": lambda: collect_sku_statuses(),
    }

    # Run collectors in parallel
    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                errors[name] = str(e)
                results[name] = {}

    # Merge all results into flat structure
    merged = {}
    for block_result in results.values():
        merged.update(block_result)

    # Ad totals cross-check (if advertising data present)
    ad_data = merged.get("advertising", {})
    ad_totals_check = ad_data.get("ad_totals_check") if ad_data else None

    duration = round(time.time() - t0, 1)

    merged["meta"] = {
        "start_date": cs,
        "end_date": ce,
        "prev_start": params["prev_start"],
        "prev_end": params["prev_end"],
        "depth": depth,
        "period_label": params["period_label"],
        "prev_period_label": params["prev_period_label"],
        "month_start": month_start,
        "days_in_period": params["days_in_period"],
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "duration_sec": duration,
        "errors": errors,
        "quality_flags": build_quality_flags(errors, ad_totals_check),
    }

    return merged


def main():
    parser = argparse.ArgumentParser(description="Collect data for analytics report")
    parser.add_argument("--start", required=True, help="Period start date YYYY-MM-DD")
    parser.add_argument("--end", help="Period end date YYYY-MM-DD (default: same as start)")
    parser.add_argument("--output", help="Save JSON to file (default: stdout)")
    args = parser.parse_args()

    data = run_collection(args.start, args.end)

    output = json.dumps(data, ensure_ascii=False, default=str)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(
            f"Saved to {args.output} ({len(output)} bytes, {data['meta']['duration_sec']}s)",
            file=sys.stderr,
        )
    else:
        print(output)


if __name__ == "__main__":
    main()
