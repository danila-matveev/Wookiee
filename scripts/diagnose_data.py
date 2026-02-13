#!/usr/bin/env python3
"""
Диагностика расхождения данных SQL vs PowerBI.

Поле-за-полем сравнение для заданной даты.
Используй для выявления ТОЧНОГО поля, вызывающего расхождение.

Использование:
    python scripts/diagnose_data.py --date 2026-02-11
    python scripts/diagnose_data.py --date 2026-02-11 --pbi-wb-margin 262598
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", ""),
    "port": int(os.getenv("DB_PORT", "6433")),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
}
DB_WB = os.getenv("DB_NAME_WB", "pbi_wb_wookiee")
DB_OZON = os.getenv("DB_NAME_OZON", "pbi_ozon_wookiee")


def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def fmt(val):
    """Format number with spaces."""
    return f"{val:,.0f}".replace(",", " ")


def diagnose_wb(date_str: str):
    """Diagnostic query for WB — all fields separately."""
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) as row_count,
            SUM(marga) as sum_marga,
            SUM(nds) as sum_nds,
            SUM(reclama_vn) as sum_reclama_vn,
            SUM(marga) - SUM(nds) - SUM(reclama_vn) as margin_formula,
            SUM(revenue_spp) as sum_revenue_spp,
            COALESCE(SUM(revenue_return_spp), 0) as sum_revenue_return_spp,
            SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_net,
            SUM(revenue) as sum_revenue_after_spp,
            COALESCE(SUM(revenue_return), 0) as sum_revenue_return,
            SUM(full_counts) as sum_sales_count,
            SUM(count_orders) as sum_orders_count,
            SUM(reclama) as sum_reclama_internal,
            SUM(logist) as sum_logistics,
            SUM(sebes) as sum_sebes,
            SUM(storage) as sum_storage,
            SUM(comis_spp) as sum_commission,
            SUM(spp) as sum_spp,
            SUM(penalty) as sum_penalty,
            SUM(retention) as sum_retention,
            SUM(deduction) as sum_deduction
        FROM abc_date
        WHERE date = %s
    """, (date_str,))

    row = cur.fetchone()

    # Also get orders
    cur.execute("""
        SELECT SUM(pricewithdisc) as orders_rub
        FROM orders
        WHERE date = %s
    """, (date_str,))
    orders_row = cur.fetchone()

    conn.close()

    return {
        "row_count": int(row[0]),
        "sum_marga": to_float(row[1]),
        "sum_nds": to_float(row[2]),
        "sum_reclama_vn": to_float(row[3]),
        "margin_formula": to_float(row[4]),
        "sum_revenue_spp": to_float(row[5]),
        "sum_revenue_return_spp": to_float(row[6]),
        "revenue_net": to_float(row[7]),
        "sum_revenue_after_spp": to_float(row[8]),
        "sum_revenue_return": to_float(row[9]),
        "sum_sales_count": to_float(row[10]),
        "sum_orders_count": to_float(row[11]),
        "sum_reclama_internal": to_float(row[12]),
        "sum_logistics": to_float(row[13]),
        "sum_sebes": to_float(row[14]),
        "sum_storage": to_float(row[15]),
        "sum_commission": to_float(row[16]),
        "sum_spp": to_float(row[17]),
        "sum_penalty": to_float(row[18]),
        "sum_retention": to_float(row[19]),
        "sum_deduction": to_float(row[20]),
        "orders_rub": to_float(orders_row[0]) if orders_row and orders_row[0] else 0,
    }


def diagnose_ozon(date_str: str):
    """Diagnostic query for OZON — all fields separately."""
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) as row_count,
            SUM(marga) as sum_marga,
            SUM(nds) as sum_nds,
            SUM(marga) - SUM(nds) as margin_formula,
            SUM(price_end) as sum_revenue_before_spp,
            SUM(price_end_spp) as sum_revenue_after_spp,
            SUM(count_end) as sum_sales_count,
            SUM(reclama_end) as sum_reclama_internal,
            COALESCE(SUM(adv_vn), 0) as sum_reclama_external,
            SUM(logist_end) as sum_logistics,
            SUM(sebes_end) as sum_sebes,
            SUM(storage_end) as sum_storage,
            SUM(comission_end) as sum_commission,
            SUM(spp) as sum_spp
        FROM abc_date
        WHERE date = %s
    """, (date_str,))

    row = cur.fetchone()

    # OZON orders
    cur.execute("""
        SELECT
            COALESCE(SUM(count_init), 0) as orders_count,
            COALESCE(SUM(price_init), 0) as orders_rub
        FROM orders
        WHERE date = %s
    """, (date_str,))
    orders_row = cur.fetchone()

    conn.close()

    return {
        "row_count": int(row[0]),
        "sum_marga": to_float(row[1]),
        "sum_nds": to_float(row[2]),
        "margin_formula": to_float(row[3]),
        "sum_revenue_before_spp": to_float(row[4]),
        "sum_revenue_after_spp": to_float(row[5]),
        "sum_sales_count": to_float(row[6]),
        "sum_reclama_internal": to_float(row[7]),
        "sum_reclama_external": to_float(row[8]),
        "sum_logistics": to_float(row[9]),
        "sum_sebes": to_float(row[10]),
        "sum_storage": to_float(row[11]),
        "sum_commission": to_float(row[12]),
        "sum_spp": to_float(row[13]),
        "orders_count": to_float(orders_row[0]) if orders_row else 0,
        "orders_rub": to_float(orders_row[1]) if orders_row else 0,
    }


def print_wb_report(wb: dict, pbi: dict):
    """Print WB diagnostic report with PowerBI comparison."""
    print("\n" + "=" * 70)
    print("  WB (Wildberries) — Диагностика")
    print("=" * 70)
    print(f"  Строк в abc_date: {wb['row_count']}")
    print()

    print("  --- Компоненты формулы маржи ---")
    print(f"  SUM(marga)         = {fmt(wb['sum_marga'])}")
    print(f"  SUM(nds)           = {fmt(wb['sum_nds'])}")
    print(f"  SUM(reclama_vn)    = {fmt(wb['sum_reclama_vn'])}")
    print(f"  MARGIN = marga - nds - reclama_vn = {fmt(wb['margin_formula'])}")
    if pbi.get("wb_margin"):
        pbi_m = pbi["wb_margin"]
        diff = wb["margin_formula"] - pbi_m
        pct = diff / pbi_m * 100 if pbi_m else 0
        print(f"  PowerBI маржа      = {fmt(pbi_m)}")
        print(f"  РАСХОЖДЕНИЕ        = {fmt(diff)} ({pct:+.2f}%)")
    print()

    print("  --- Выручка ---")
    print(f"  SUM(revenue_spp)            = {fmt(wb['sum_revenue_spp'])}")
    print(f"  SUM(revenue_return_spp)     = {fmt(wb['sum_revenue_return_spp'])}")
    print(f"  Revenue NET = rev - returns = {fmt(wb['revenue_net'])}")
    if pbi.get("wb_revenue"):
        pbi_r = pbi["wb_revenue"]
        diff = wb["revenue_net"] - pbi_r
        pct = diff / pbi_r * 100 if pbi_r else 0
        print(f"  PowerBI выручка до СПП     = {fmt(pbi_r)}")
        print(f"  РАСХОЖДЕНИЕ                = {fmt(diff)} ({pct:+.2f}%)")
    print()

    print("  --- Продажи / Заказы ---")
    print(f"  SUM(full_counts)    = {fmt(wb['sum_sales_count'])} шт (продажи)")
    print(f"  SUM(count_orders)   = {fmt(wb['sum_orders_count'])} шт (заказы)")
    print(f"  orders.pricewithdisc = {fmt(wb['orders_rub'])} руб (заказы ₽)")
    if pbi.get("wb_sales"):
        print(f"  PowerBI продажи шт  = {fmt(pbi['wb_sales'])}")
        print(f"  РАСХОЖДЕНИЕ         = {wb['sum_sales_count'] - pbi['wb_sales']:+.0f}")
    if pbi.get("wb_orders"):
        print(f"  PowerBI заказы шт   = {fmt(pbi['wb_orders'])}")
        print(f"  РАСХОЖДЕНИЕ         = {wb['sum_orders_count'] - pbi['wb_orders']:+.0f}")
    print()

    print("  --- Расходы ---")
    print(f"  Реклама внутр     = {fmt(wb['sum_reclama_internal'])}")
    print(f"  Реклама внешн     = {fmt(wb['sum_reclama_vn'])}")
    print(f"  Логистика         = {fmt(wb['sum_logistics'])}")
    print(f"  Себестоимость     = {fmt(wb['sum_sebes'])}")
    print(f"  Хранение          = {fmt(wb['sum_storage'])}")
    print(f"  Комиссия (SPP)    = {fmt(wb['sum_commission'])}")
    print(f"  SPP сумма         = {fmt(wb['sum_spp'])}")
    print(f"  НДС               = {fmt(wb['sum_nds'])}")
    print(f"  Штрафы            = {fmt(wb['sum_penalty'])}")
    print(f"  Retention         = {fmt(wb['sum_retention'])}")
    print(f"  Deduction         = {fmt(wb['sum_deduction'])}")

    if wb["sum_retention"] != 0 and wb["sum_retention"] == wb["sum_deduction"]:
        print(f"\n  ⚠️  ВНИМАНИЕ: retention == deduction ({fmt(wb['sum_retention'])})")
        print(f"      Возможна дубликация пайплайна! Маржа может быть занижена.")

    # Margin% check
    rev = wb["revenue_net"]
    margin = wb["margin_formula"]
    if rev > 0:
        margin_pct = margin / rev * 100
        print(f"\n  Маржинальность = {margin_pct:.1f}%")
        if pbi.get("wb_margin_pct"):
            print(f"  PowerBI маржа% = {pbi['wb_margin_pct']:.1f}%")


def print_ozon_report(ozon: dict, pbi: dict):
    """Print OZON diagnostic report with PowerBI comparison."""
    print("\n" + "=" * 70)
    print("  OZON — Диагностика")
    print("=" * 70)
    print(f"  Строк в abc_date: {ozon['row_count']}")
    print()

    print("  --- Компоненты формулы маржи ---")
    print(f"  SUM(marga)       = {fmt(ozon['sum_marga'])}")
    print(f"  SUM(nds)         = {fmt(ozon['sum_nds'])}")
    print(f"  MARGIN = marga - nds = {fmt(ozon['margin_formula'])}")
    if pbi.get("ozon_margin"):
        pbi_m = pbi["ozon_margin"]
        diff = ozon["margin_formula"] - pbi_m
        pct = diff / pbi_m * 100 if pbi_m else 0
        print(f"  PowerBI маржа    = {fmt(pbi_m)}")
        print(f"  РАСХОЖДЕНИЕ      = {fmt(diff)} ({pct:+.2f}%)")
    print()

    print("  --- Выручка ---")
    print(f"  SUM(price_end)       = {fmt(ozon['sum_revenue_before_spp'])} (до СПП)")
    print(f"  SUM(price_end_spp)   = {fmt(ozon['sum_revenue_after_spp'])} (после СПП)")
    if pbi.get("ozon_revenue"):
        pbi_r = pbi["ozon_revenue"]
        diff = ozon["sum_revenue_before_spp"] - pbi_r
        pct = diff / pbi_r * 100 if pbi_r else 0
        print(f"  PowerBI продажи до СПП = {fmt(pbi_r)}")
        print(f"  РАСХОЖДЕНИЕ            = {fmt(diff)} ({pct:+.2f}%)")
    print()

    print("  --- Продажи / Заказы ---")
    print(f"  SUM(count_end)    = {fmt(ozon['sum_sales_count'])} шт (продажи)")
    print(f"  orders.count_init = {fmt(ozon['orders_count'])} шт (заказы)")
    print(f"  orders.price_init = {fmt(ozon['orders_rub'])} руб (заказы ₽)")
    if pbi.get("ozon_sales"):
        print(f"  PowerBI продажи шт = {fmt(pbi['ozon_sales'])}")
        print(f"  РАСХОЖДЕНИЕ        = {ozon['sum_sales_count'] - pbi['ozon_sales']:+.0f}")
    print()

    print("  --- Расходы ---")
    print(f"  Реклама внутр     = {fmt(ozon['sum_reclama_internal'])}")
    print(f"  Реклама внешн     = {fmt(ozon['sum_reclama_external'])}")
    print(f"  Логистика         = {fmt(ozon['sum_logistics'])}")
    print(f"  Себестоимость     = {fmt(ozon['sum_sebes'])}")
    print(f"  Хранение          = {fmt(ozon['sum_storage'])}")
    print(f"  Комиссия          = {fmt(ozon['sum_commission'])}")
    print(f"  SPP сумма         = {fmt(ozon['sum_spp'])}")
    print(f"  НДС               = {fmt(ozon['sum_nds'])}")

    # Margin% check
    rev = ozon["sum_revenue_before_spp"]
    margin = ozon["margin_formula"]
    if rev > 0:
        margin_pct = margin / rev * 100
        print(f"\n  Маржинальность (от price_end) = {margin_pct:.1f}%")
        if pbi.get("ozon_margin_pct"):
            print(f"  PowerBI маржа% = {pbi['ozon_margin_pct']:.1f}%")
            if abs(margin_pct - pbi["ozon_margin_pct"]) > 0.3:
                # Check with after-spp revenue
                margin_pct_spp = margin / ozon["sum_revenue_after_spp"] * 100 if ozon["sum_revenue_after_spp"] else 0
                print(f"  Маржинальность (от price_end_spp) = {margin_pct_spp:.1f}%")
                print(f"  → PowerBI может считать маржу% от другого знаменателя")


def main():
    parser = argparse.ArgumentParser(description="Диагностика данных SQL vs PowerBI")
    parser.add_argument("--date", required=True, help="Дата для проверки (YYYY-MM-DD)")
    parser.add_argument("--pbi-wb-margin", type=float, default=None, help="PowerBI WB маржа")
    parser.add_argument("--pbi-wb-revenue", type=float, default=None, help="PowerBI WB выручка до СПП")
    parser.add_argument("--pbi-wb-sales", type=float, default=None, help="PowerBI WB продажи шт")
    parser.add_argument("--pbi-wb-orders", type=float, default=None, help="PowerBI WB заказы шт")
    parser.add_argument("--pbi-wb-margin-pct", type=float, default=None, help="PowerBI WB маржа %")
    parser.add_argument("--pbi-ozon-margin", type=float, default=None, help="PowerBI OZON маржа")
    parser.add_argument("--pbi-ozon-revenue", type=float, default=None, help="PowerBI OZON выручка до СПП")
    parser.add_argument("--pbi-ozon-sales", type=float, default=None, help="PowerBI OZON продажи шт")
    parser.add_argument("--pbi-ozon-margin-pct", type=float, default=None, help="PowerBI OZON маржа %")
    args = parser.parse_args()

    pbi = {
        "wb_margin": args.pbi_wb_margin,
        "wb_revenue": args.pbi_wb_revenue,
        "wb_sales": args.pbi_wb_sales,
        "wb_orders": args.pbi_wb_orders,
        "wb_margin_pct": args.pbi_wb_margin_pct,
        "ozon_margin": args.pbi_ozon_margin,
        "ozon_revenue": args.pbi_ozon_revenue,
        "ozon_sales": args.pbi_ozon_sales,
        "ozon_margin_pct": args.pbi_ozon_margin_pct,
    }
    # Remove None values
    pbi = {k: v for k, v in pbi.items() if v is not None}

    print(f"\n{'=' * 70}")
    print(f"  ДИАГНОСТИКА ДАННЫХ за {args.date}")
    print(f"{'=' * 70}")

    try:
        wb = diagnose_wb(args.date)
        print_wb_report(wb, pbi)
    except Exception as e:
        print(f"\n  ❌ Ошибка WB: {e}")

    try:
        ozon = diagnose_ozon(args.date)
        print_ozon_report(ozon, pbi)
    except Exception as e:
        print(f"\n  ❌ Ошибка OZON: {e}")

    # Summary
    if "wb" in dir() and "ozon" in dir():
        print("\n" + "=" * 70)
        print("  ИТОГО (Бренд)")
        print("=" * 70)
        total_margin = wb["margin_formula"] + ozon["margin_formula"]
        total_revenue = wb["revenue_net"] + ozon["sum_revenue_before_spp"]
        total_sales = wb["sum_sales_count"] + ozon["sum_sales_count"]
        print(f"  Маржа:    {fmt(total_margin)}")
        print(f"  Выручка:  {fmt(total_revenue)}")
        print(f"  Продажи:  {fmt(total_sales)} шт")
        if pbi.get("wb_margin") and pbi.get("ozon_margin"):
            pbi_total = pbi["wb_margin"] + pbi["ozon_margin"]
            diff = total_margin - pbi_total
            pct = diff / pbi_total * 100
            print(f"  PowerBI итого маржа: {fmt(pbi_total)}")
            print(f"  РАСХОЖДЕНИЕ: {fmt(diff)} ({pct:+.2f}%)")

    print()


if __name__ == "__main__":
    main()
