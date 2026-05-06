"""Monthly plan data collection orchestrator.

Usage:
    python scripts/monthly_plan/collect_all.py --month 2026-05
    python scripts/monthly_plan/collect_all.py --month 2026-05 --output /tmp/data.json
    python scripts/monthly_plan/collect_all.py --month 2026-05 --cached /tmp/data.json
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from scripts.monthly_plan.utils import compute_date_params, build_quality_flags
from shared.tool_logger import ToolLogger
from scripts.monthly_plan.collectors.pnl import collect_pnl
from scripts.monthly_plan.collectors.pricing import collect_pricing
from scripts.monthly_plan.collectors.advertising import collect_advertising
from scripts.monthly_plan.collectors.inventory import collect_inventory
from scripts.monthly_plan.collectors.abc import collect_abc
from scripts.monthly_plan.collectors.traffic import collect_traffic
from scripts.monthly_plan.collectors.sheets import collect_sheets


def run_collection(plan_month: str) -> dict:
    """Run all collectors and merge results into single dict.

    Args:
        plan_month: target month "YYYY-MM" to plan for.

    Returns:
        Complete data bundle as JSON-serializable dict.
    """
    t0 = time.time()
    params = compute_date_params(plan_month)

    cs = params["current_month_start"]
    ce = params["current_month_end"]
    ps = params["prev_month_start"]
    es = params["elasticity_start"]
    ss = params["stock_window_start"]

    # Define collection tasks
    tasks = {
        "pnl": lambda: collect_pnl(cs, ps, ce),
        "pricing": lambda: collect_pricing(es, ce),
        "advertising": lambda: collect_advertising(cs, ps, ce),
        "inventory": lambda: collect_inventory(ss, ce, cs, ce),
        "abc": lambda: collect_abc(cs, ce),
        "traffic": lambda: collect_traffic(cs, ps, ce),
        "sheets": lambda: collect_sheets(plan_month),
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

    # Compute quality flags
    # Estimate data months per model from pricing data
    pricing_data = merged.get("pricing", {}).get("by_article", [])
    models_data = {}
    for art in pricing_data:
        model = art.get("model", "")
        days = art.get("days_with_data", 0)
        months_approx = days / 30
        if model not in models_data or months_approx > models_data[model].get("data_months", 0):
            models_data[model] = {"data_months": months_approx}

    duration = round(time.time() - t0, 1)

    merged["meta"] = {
        "plan_month": plan_month,
        "base_month": cs[:7],
        "prev_month": ps[:7],
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "collection_duration_sec": duration,
        "quality_flags": build_quality_flags(models_data),
        "date_params": params,
        "errors": errors,
    }

    return merged


def main():
    parser = argparse.ArgumentParser(description="Collect data for monthly business plan")
    parser.add_argument("--month", required=True, help="Plan month YYYY-MM (e.g., 2026-05)")
    parser.add_argument("--output", help="Save JSON to file (default: stdout)")
    parser.add_argument("--cached", help="Use cached JSON file instead of collecting")
    args = parser.parse_args()

    if args.cached:
        with open(args.cached) as f:
            data = json.load(f)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    month_start = args.month + "-01"
    tl = ToolLogger("/monthly-plan")
    with tl.run(period_start=month_start, period_end=month_start) as run_meta:
        data = run_collection(args.month)

        output = json.dumps(data, ensure_ascii=False, default=str)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Saved to {args.output} ({len(output)} bytes, {data['meta']['collection_duration_sec']}s)",
                  file=sys.stderr)
        else:
            print(output)

        run_meta["items"] = len(data) - 1  # keys minus "meta"
        run_meta["notes"] = f"duration={data['meta']['collection_duration_sec']}s"


if __name__ == "__main__":
    main()
