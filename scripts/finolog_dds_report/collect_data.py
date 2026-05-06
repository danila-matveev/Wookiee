"""Finolog DDS report data collector.

Usage:
    python scripts/finolog_dds_report/collect_data.py --start 2026-04-07 --end 2026-04-13
    python scripts/finolog_dds_report/collect_data.py --start 2026-04-07 --end 2026-04-13 --output /tmp/finolog.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import asyncio
import json
from datetime import datetime, timedelta

import os
from shared.tool_logger import ToolLogger
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).resolve().parents[2] / ".env")


async def _fetch_transactions_for_range(svc, date_from: str, date_to: str) -> list[dict]:
    """Fetch all transactions for an arbitrary date range, paginated."""
    all_txns: list[dict] = []
    page = 1
    while True:
        data = await svc._get(f"/biz/{svc.biz_id}/transaction", params={
            "report_date_from": date_from,
            "report_date_to": date_to,
            "per_page": 200,
            "page": page,
        })
        if not data:
            break
        all_txns.extend(data)
        if len(data) < 200:
            break
        page += 1
    return all_txns


def _group_transactions(txns: list[dict], cat_map: dict[int, str], cat_to_group: dict[str, str]) -> dict:
    """Group transactions by CATEGORY_GROUPS and compute totals."""
    groups: dict[str, dict] = {}
    income_total = 0.0
    expense_total = 0.0

    for t in txns:
        amount = float(t.get("value", 0) or 0)
        cat_id = t.get("category_id")
        cat_name = cat_map.get(cat_id, "Прочие")
        group = cat_to_group.get(cat_name, "Прочие")

        if group not in groups:
            groups[group] = {"income": 0.0, "expense": 0.0, "net": 0.0, "transactions": 0}

        groups[group]["transactions"] += 1
        if amount > 0:
            groups[group]["income"] += amount
            income_total += amount
        else:
            groups[group]["expense"] += amount
            expense_total += amount
        groups[group]["net"] = groups[group]["income"] + groups[group]["expense"]

    return {
        "groups": groups,
        "total_income": income_total,
        "total_expense": expense_total,
        "total_net": income_total + expense_total,
    }


async def _collect(start_date: str, end_date: str) -> dict:
    """Collect all Finolog data blocks for DDS report."""
    from shared.services.finolog_service import (
        FinologService,
        _CAT_TO_GROUP,
        COMPANY_ORDER,
        COMPANY_NAMES,
        _PURPOSE_ORDER,
        _PURPOSE_LABELS,
    )

    api_key = os.getenv("FINOLOG_API_KEY", "")
    if not api_key:
        return {"meta": {"errors": 1, "error_details": ["FINOLOG_API_KEY not set"], "quality_flags": []}}

    svc = FinologService(api_key=api_key)
    errors: list[str] = []
    quality_flags: list[str] = []

    # --- Category map ---
    try:
        cat_map = await svc._get_categories()
    except Exception as e:
        errors.append(f"categories: {e}")
        cat_map = {}

    # --- Balances ---
    try:
        balances_raw = await svc._build_balances()
        # Flatten to structured format for LLM consumption
        balances: dict = {}
        for cid in COMPANY_ORDER:
            cname = COMPANY_NAMES.get(cid, f"Company {cid}")
            accs = balances_raw.get(cid, {})
            company_data: dict = {"name": cname, "purposes": {}, "total_rub": 0.0}
            for purpose in _PURPOSE_ORDER:
                items = accs.get(purpose, [])
                if not items:
                    continue
                label = _PURPOSE_LABELS.get(purpose, purpose)
                total_base = sum(i["base_balance"] for i in items)
                company_data["total_rub"] += total_base
                company_data["purposes"][purpose] = {
                    "label": label,
                    "total_rub": total_base,
                    "accounts": items,
                }
            balances[str(cid)] = company_data
    except Exception as e:
        errors.append(f"balances: {e}")
        balances = {}

    # --- Cashflow current period ---
    try:
        txns_current = await _fetch_transactions_for_range(svc, start_date, end_date)
        cashflow_current = _group_transactions(txns_current, cat_map, _CAT_TO_GROUP)
    except Exception as e:
        errors.append(f"cashflow_current: {e}")
        cashflow_current = {}

    # --- Cashflow previous period (same length, shifted back) ---
    try:
        d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        period_days = (d_end - d_start).days + 1
        prev_end = d_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        txns_prev = await _fetch_transactions_for_range(svc, prev_start.isoformat(), prev_end.isoformat())
        cashflow_previous = _group_transactions(txns_prev, cat_map, _CAT_TO_GROUP)
        cashflow_previous["period"] = {"start": prev_start.isoformat(), "end": prev_end.isoformat()}
    except Exception as e:
        errors.append(f"cashflow_previous: {e}")
        cashflow_previous = {}

    # --- Forecast ---
    try:
        # Compute total RUB balance for forecast base
        total_balance_rub = sum(
            cdata.get("total_rub", 0.0)
            for cdata in balances.values()
        )
        forecast = await svc._build_forecast(total_balance_rub, months=12)
    except Exception as e:
        errors.append(f"forecast: {e}")
        forecast = []

    return {
        "balances": balances,
        "cashflow_current": cashflow_current,
        "cashflow_previous": cashflow_previous,
        "forecast": forecast,
        "period": {"start": start_date, "end": end_date},
        "meta": {
            "errors": len(errors),
            "error_details": errors,
            "quality_flags": quality_flags,
            "collected_at": datetime.now().isoformat(),
        },
    }


def collect_finolog_dds(start_date: str, end_date: str) -> dict:
    """Synchronous wrapper for the async collector."""
    return asyncio.run(_collect(start_date, end_date))


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Finolog DDS data")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    tl = ToolLogger("finolog-dds-report")
    with tl.run(period_start=args.start, period_end=args.end) as run_meta:
        data = collect_finolog_dds(args.start, args.end)

        output_path = args.output or f"/tmp/finolog-dds-{args.start}_{args.end}.json"
        _Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        print(f"Collected: {output_path}")
        print(f"Errors: {data['meta']['errors']}")
        if data["meta"]["error_details"]:
            for e in data["meta"]["error_details"]:
                print(f"  - {e}")

        run_meta["items"] = data["meta"].get("transactions_count", 0)
        if data["meta"]["errors"]:
            run_meta["notes"] = f"{data['meta']['errors']} errors"

        if data["meta"]["errors"] > 3:
            run_meta["stage"] = "gate_check"
            print("GATE FAILED: too many errors")
            sys.exit(1)


if __name__ == "__main__":
    main()
