"""Logistics report data collector.

Usage:
    python scripts/logistics_report/collect_data.py --start 2026-04-07 --end 2026-04-13
    python scripts/logistics_report/collect_data.py --start 2026-03-01 --end 2026-03-31 --output /tmp/logistics.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv

from shared.tool_logger import ToolLogger

_load_dotenv(_Path(__file__).resolve().parents[2] / ".env")


def _collect_logistics_cost(start_date: str, end_date: str) -> tuple[dict, list[str]]:
    """Block 1: WB + OZON logistics costs and revenue (from abc_date tables)."""
    from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float

    errors: list[str] = []
    result: dict = {"wb": {}, "ozon": {}}

    # WB logistics from abc_date
    try:
        conn = _get_wb_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                SUM(logist) as logistics_cost,
                SUM(full_counts) as sales_count,
                SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue
            FROM abc_date
            WHERE date >= %s AND date < %s
        """, (start_date, end_date))
        row = cur.fetchone()
        if row and row[0]:
            revenue = to_float(row[2]) or 1.0
            logistics = to_float(row[0])
            sales = to_float(row[1]) or 1.0
            result["wb"] = {
                "logistics_cost": logistics,
                "sales_count": to_float(row[1]),
                "revenue": to_float(row[2]),
                "logistics_pct_revenue": round(logistics / revenue * 100, 2) if revenue else 0,
                "logistics_per_unit": round(logistics / sales, 2) if sales else 0,
            }
        cur.close()
        conn.close()
    except Exception as e:
        errors.append(f"wb_logistics: {e}")

    # Previous period WB
    try:
        d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        period_days = (d_end - d_start).days + 1
        prev_end = d_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)

        conn = _get_wb_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                SUM(logist) as logistics_cost,
                SUM(full_counts) as sales_count,
                SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue
            FROM abc_date
            WHERE date >= %s AND date < %s
        """, (prev_start.isoformat(), prev_end.isoformat()))
        row = cur.fetchone()
        if row and row[0]:
            result["wb"]["prev_logistics_cost"] = to_float(row[0])
            result["wb"]["prev_revenue"] = to_float(row[2])
        cur.close()
        conn.close()
    except Exception as e:
        errors.append(f"wb_logistics_prev: {e}")

    # OZON logistics from abc_date
    try:
        conn = _get_ozon_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                SUM(logist_end) as logistics_cost,
                SUM(count_end) - COALESCE(SUM(count_return), 0) as sales_count,
                SUM(price_end) + COALESCE(SUM(return_end), 0) as revenue
            FROM abc_date
            WHERE date >= %s AND date < %s
        """, (start_date, end_date))
        row = cur.fetchone()
        if row and row[0]:
            revenue = to_float(row[2]) or 1.0
            logistics = to_float(row[0])
            sales = to_float(row[1]) or 1.0
            result["ozon"] = {
                "logistics_cost": logistics,
                "sales_count": to_float(row[1]),
                "revenue": to_float(row[2]),
                "logistics_pct_revenue": round(logistics / revenue * 100, 2) if revenue else 0,
                "logistics_per_unit": round(logistics / sales, 2) if sales else 0,
            }
        cur.close()
        conn.close()
    except Exception as e:
        errors.append(f"ozon_logistics: {e}")

    return result, errors


def _collect_indices() -> tuple[dict, list[str]]:
    """Block 2: WB Localization Index — read latest from wb_logistics.db history."""
    errors: list[str] = []
    result: dict = {"cabinets": {}, "available": False}

    try:
        from services.wb_localization.history import History

        history = History()
        for cabinet_name in ("ИП", "ООО"):
            latest = history.get_latest(cabinet_name)
            if latest:
                result["cabinets"][cabinet_name] = {
                    "il_current": latest.get("overall_index", None),
                    "timestamp": latest.get("timestamp", None),
                    "sku_with_orders": latest.get("sku_with_orders", None),
                    "top_problems": latest.get("top_problems_json", None),
                }
                result["available"] = True
    except Exception as e:
        errors.append(f"localization_index: {e}")

    return result, errors


def _collect_returns(start_date: str, end_date: str) -> tuple[dict, list[str]]:
    """Block 3: Returns and buyout % — from closed period (30+ days lag).

    IMPORTANT: Uses closed_end = end_date - 30 days (lag 30+ days).
    """
    from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection

    errors: list[str] = []
    result: dict = {"wb": {}, "ozon": {}, "closed_period_note": ""}

    d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    closed_end = (d_end - timedelta(days=30)).isoformat()
    closed_start = (d_end - timedelta(days=60)).isoformat()
    result["closed_period"] = {"start": closed_start, "end": closed_end}
    result["closed_period_note"] = f"Данные выкупов из закрытого периода {closed_start}–{closed_end} (лаг 30+ дней)"

    # WB buyouts by model
    try:
        conn = _get_wb_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
                COUNT(*) as total_orders,
                SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyouts
            FROM orders
            WHERE date >= %s AND date < %s
                AND supplierarticle IS NOT NULL AND supplierarticle != ''
            GROUP BY LOWER(SPLIT_PART(supplierarticle, '/', 1))
            ORDER BY total_orders DESC
        """, (closed_start, closed_end))
        rows = cur.fetchall()
        for row in rows:
            model, total, buyouts = row[0], int(row[1]), int(row[2])
            buyout_pct = round(buyouts / total * 100, 1) if total > 0 else 0
            result["wb"][model] = {
                "orders": total,
                "buyouts": buyouts,
                "buyout_pct": buyout_pct,
                "return_pct": round(100 - buyout_pct, 1),
            }
        cur.close()
        conn.close()
    except Exception as e:
        errors.append(f"wb_returns: {e}")

    # OZON buyouts by model
    try:
        conn = _get_ozon_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                LOWER(SPLIT_PART(article, '/', 1)) as model,
                SUM(count_end) as sales,
                SUM(COALESCE(count_return, 0)) as returns
            FROM abc_date
            WHERE date >= %s AND date < %s
                AND article IS NOT NULL AND article != ''
            GROUP BY LOWER(SPLIT_PART(article, '/', 1))
            ORDER BY sales DESC
        """, (closed_start, closed_end))
        rows = cur.fetchall()
        for row in rows:
            model = row[0]
            sales = float(row[1] or 0)
            returns = float(row[2] or 0)
            total = sales + returns
            buyout_pct = round(sales / total * 100, 1) if total > 0 else 0
            result["ozon"][model] = {
                "sales": int(sales),
                "returns": int(returns),
                "buyout_pct": buyout_pct,
                "return_pct": round(100 - buyout_pct, 1),
            }
        cur.close()
        conn.close()
    except Exception as e:
        errors.append(f"ozon_returns: {e}")

    return result, errors


def _collect_inventory(start_date: str, end_date: str) -> tuple[dict, list[str]]:
    """Block 4: Stock levels and turnover from inventory.py."""
    errors: list[str] = []
    result: dict = {}

    try:
        from shared.data_layer.inventory import (
            get_wb_avg_stock,
            get_ozon_avg_stock,
            get_wb_turnover_by_model,
            get_ozon_turnover_by_model,
            get_moysklad_stock_by_model,
        )

        wb_stock = get_wb_avg_stock(start_date, end_date)
        result["wb_stock"] = wb_stock
    except Exception as e:
        errors.append(f"wb_stock: {e}")
        result["wb_stock"] = {}

    try:
        from shared.data_layer.inventory import get_ozon_avg_stock
        ozon_stock = get_ozon_avg_stock(start_date, end_date)
        result["ozon_stock"] = ozon_stock
    except Exception as e:
        errors.append(f"ozon_stock: {e}")
        result["ozon_stock"] = {}

    try:
        from shared.data_layer.inventory import get_wb_turnover_by_model
        wb_turnover = get_wb_turnover_by_model(start_date, end_date)
        result["wb_turnover"] = wb_turnover
    except Exception as e:
        errors.append(f"wb_turnover: {e}")
        result["wb_turnover"] = {}

    try:
        from shared.data_layer.inventory import get_ozon_turnover_by_model
        ozon_turnover = get_ozon_turnover_by_model(start_date, end_date)
        result["ozon_turnover"] = ozon_turnover
    except Exception as e:
        errors.append(f"ozon_turnover: {e}")
        result["ozon_turnover"] = {}

    try:
        from shared.data_layer.inventory import get_moysklad_stock_by_model
        ms_stock = get_moysklad_stock_by_model()
        result["moysklad_stock"] = ms_stock
    except Exception as e:
        errors.append(f"moysklad_stock: {e}")
        result["moysklad_stock"] = {}

    return result, errors


def _collect_resupply() -> tuple[dict, list[str]]:
    """Block 5: MoySklad office stock for resupply recommendations."""
    errors: list[str] = []
    result: dict = {}

    moysklad_token = os.getenv("MOYSKLAD_TOKEN", "")
    if not moysklad_token:
        errors.append("MOYSKLAD_TOKEN not set")
        return result, errors

    try:
        from shared.clients.moysklad_client import MoySkladClient
        client = MoySkladClient(token=moysklad_token)
        office_stock = client.fetch_stock_by_store(MoySkladClient.STORE_MAIN)
        result["office_stock"] = office_stock
    except Exception as e:
        errors.append(f"resupply_office_stock: {e}")

    return result, errors


def collect_logistics(start_date: str, end_date: str) -> dict:
    """Main collector: gathers all 5 blocks."""
    all_errors: list[str] = []

    logistics_cost, errs = _collect_logistics_cost(start_date, end_date)
    all_errors.extend(errs)

    indices, errs = _collect_indices()
    all_errors.extend(errs)

    returns, errs = _collect_returns(start_date, end_date)
    all_errors.extend(errs)

    inventory, errs = _collect_inventory(start_date, end_date)
    all_errors.extend(errs)

    resupply, errs = _collect_resupply()
    all_errors.extend(errs)

    d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    closed_end = (d_end - timedelta(days=30)).isoformat()

    return {
        "logistics_cost": logistics_cost,
        "indices": indices,
        "returns": returns,
        "inventory": inventory,
        "resupply": resupply,
        "period": {
            "start": start_date,
            "end": end_date,
            "closed_end": closed_end,
        },
        "meta": {
            "errors": len(all_errors),
            "error_details": all_errors,
            "quality_flags": [],
            "collected_at": datetime.now().isoformat(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect logistics report data")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    tl = ToolLogger("/logistics-report")
    with tl.run(period_start=args.start, period_end=args.end) as run_meta:
        data = collect_logistics(args.start, args.end)

        output_path = args.output or f"/tmp/logistics-{args.start}_{args.end}.json"
        _Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        print(f"Collected: {output_path}")
        print(f"Errors: {data['meta']['errors']}")
        if data["meta"]["error_details"]:
            for e in data["meta"]["error_details"]:
                print(f"  - {e}")

        run_meta["items"] = data["meta"].get("sku_count", 0)
        if data["meta"]["errors"]:
            run_meta["notes"] = f"{data['meta']['errors']} errors"

        if data["meta"]["errors"] > 3:
            run_meta["stage"] = "gate_check"
            print("GATE FAILED: too many errors")
            sys.exit(1)


if __name__ == "__main__":
    main()
