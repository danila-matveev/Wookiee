import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.finance import get_wb_finance, get_ozon_finance
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_finance.json")


def _parse_wb_row(row: tuple) -> dict:
    return {
        "orders_count_abc": int(row[1] or 0),
        "sales_count": int(row[2] or 0),
        "revenue_before_spp": float(row[3] or 0),
        "revenue_after_spp": float(row[4] or 0),
        "adv_internal": float(row[5] or 0),
        "adv_external": float(row[6] or 0),
        "cost_of_goods": float(row[7] or 0),
        "logistics": float(row[8] or 0),
        "storage": float(row[9] or 0),
        "commission": float(row[10] or 0),
        "spp_amount": float(row[11] or 0),
        "nds": float(row[12] or 0),
        "penalty": float(row[13] or 0),
        "retention": float(row[14] or 0),
        "deduction": float(row[15] or 0),
        "margin": float(row[16] or 0),
        "returns_revenue": float(row[17] or 0),
    }


def _parse_ozon_row(row: tuple) -> dict:
    return {
        "sales_count": int(row[1] or 0),
        "revenue_before_spp": float(row[2] or 0),
        "revenue_after_spp": float(row[3] or 0),
        "adv_internal": float(row[4] or 0),
        "adv_external": float(row[5] or 0),
        "margin": float(row[6] or 0),
        "cost_of_goods": float(row[7] or 0),
        "logistics": float(row[8] or 0),
        "storage": float(row[9] or 0),
        "commission": float(row[10] or 0),
        "spp_amount": float(row[11] or 0),
        "nds": float(row[12] or 0),
    }


def _add_drr(channel_data: dict, orders_rub: float) -> dict:
    data = dict(channel_data)
    adv_int = data.get("adv_internal", 0)
    adv_ext = data.get("adv_external", 0)
    if orders_rub > 0:
        data["drr_internal_pct"] = round(adv_int / orders_rub * 100, 2)
        data["drr_external_pct"] = round(adv_ext / orders_rub * 100, 2)
        data["drr_total_pct"] = round((adv_int + adv_ext) / orders_rub * 100, 2)
    else:
        data["drr_internal_pct"] = 0.0
        data["drr_external_pct"] = 0.0
        data["drr_total_pct"] = 0.0
    data["orders_rub"] = orders_rub
    return data


def collect(ref_date: date = None) -> dict:
    current_start, current_end, prev_start, _ = get_week_bounds(ref_date)

    wb_rows, wb_orders_rows = get_wb_finance(current_start, prev_start, current_end)
    ozon_rows, ozon_orders_rows = get_ozon_finance(current_start, prev_start, current_end)

    wb_by_period = {row[0]: _parse_wb_row(row) for row in wb_rows}
    wb_orders = {row[0]: {"orders_count": int(row[1] or 0), "orders_rub": float(row[2] or 0)}
                 for row in wb_orders_rows}
    for period, data in wb_by_period.items():
        orders_rub = wb_orders.get(period, {}).get("orders_rub", 0)
        orders_cnt = wb_orders.get(period, {}).get("orders_count", 0)
        data["orders_count"] = orders_cnt
        wb_by_period[period] = _add_drr(data, orders_rub)

    ozon_by_period = {row[0]: _parse_ozon_row(row) for row in ozon_rows}
    ozon_orders = {row[0]: {"orders_count": int(row[1] or 0), "orders_rub": float(row[2] or 0)}
                   for row in ozon_orders_rows}
    for period, data in ozon_by_period.items():
        orders_rub = ozon_orders.get(period, {}).get("orders_rub", 0)
        orders_cnt = ozon_orders.get(period, {}).get("orders_count", 0)
        data["orders_count"] = orders_cnt
        ozon_by_period[period] = _add_drr(data, orders_rub)

    combined = {}
    for period in set(list(wb_by_period.keys()) + list(ozon_by_period.keys())):
        wb = wb_by_period.get(period, {})
        oz = ozon_by_period.get(period, {})
        total_orders_rub = wb.get("orders_rub", 0) + oz.get("orders_rub", 0)
        combined_row = {
            "orders_count": wb.get("orders_count", 0) + oz.get("orders_count", 0),
            "sales_count": wb.get("sales_count", 0) + oz.get("sales_count", 0),
            "revenue_after_spp": wb.get("revenue_after_spp", 0) + oz.get("revenue_after_spp", 0),
            "revenue_before_spp": wb.get("revenue_before_spp", 0) + oz.get("revenue_before_spp", 0),
            "adv_internal": wb.get("adv_internal", 0) + oz.get("adv_internal", 0),
            "adv_external": wb.get("adv_external", 0) + oz.get("adv_external", 0),
            "logistics": wb.get("logistics", 0) + oz.get("logistics", 0),
            "storage": wb.get("storage", 0) + oz.get("storage", 0),
            "commission": wb.get("commission", 0) + oz.get("commission", 0),
            "margin": wb.get("margin", 0) + oz.get("margin", 0),
            "spp_amount": wb.get("spp_amount", 0) + oz.get("spp_amount", 0),
        }
        combined[period] = _add_drr(combined_row, total_orders_rub)

    return {
        "wb": wb_by_period,
        "ozon": ozon_by_period,
        "combined": combined,
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
            "prev_start": str(prev_start),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Финансы сохранены → {OUTPUT_PATH}")
    current = data.get("combined", {}).get("current", {})
    print(f"  Выручка после СПП: {current.get('revenue_after_spp', 0):,.0f} ₽")
    print(f"  Маржа: {current.get('margin', 0):,.0f} ₽")
    print(f"  ДРР общий: {current.get('drr_total_pct', 0):.1f}%")
