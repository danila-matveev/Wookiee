import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.finance import get_wb_by_model, get_ozon_by_model
from shared.data_layer.finance import get_wb_orders_by_model, get_ozon_orders_by_model
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_models.json")


def _empty_model() -> dict:
    return {
        "revenue": 0.0, "margin": 0.0, "cost_of_goods": 0.0,
        "adv_internal": 0.0, "adv_external": 0.0,
        "sales_count": 0, "orders_count": 0, "orders_rub": 0.0,
    }


def _aggregate(rows: list, orders_rows: list) -> dict:
    data: dict = {}

    for row in rows:
        period, model = row[0], row[1].lower()
        key = (period, model)
        if key not in data:
            data[key] = _empty_model()
        data[key]["sales_count"] += int(row[2] or 0)
        data[key]["revenue"] += float(row[3] or 0)
        data[key]["adv_internal"] += float(row[4] or 0)
        data[key]["adv_external"] += float(row[5] or 0)
        data[key]["margin"] += float(row[6] or 0)
        data[key]["cost_of_goods"] += float(row[7] or 0)

    for row in orders_rows:
        period, model = row[0], row[1].lower()
        key = (period, model)
        if key not in data:
            data[key] = _empty_model()
        data[key]["orders_count"] += int(row[2] or 0)
        data[key]["orders_rub"] += float(row[3] or 0)

    return data


def collect(ref_date: date = None) -> dict:
    current_start, current_end, prev_start, _ = get_week_bounds(ref_date)

    wb_data = _aggregate(
        get_wb_by_model(current_start, prev_start, current_end),
        get_wb_orders_by_model(current_start, prev_start, current_end),
    )
    ozon_data = _aggregate(
        get_ozon_by_model(current_start, prev_start, current_end),
        get_ozon_orders_by_model(current_start, prev_start, current_end),
    )

    all_keys = set(wb_data.keys()) | set(ozon_data.keys())
    merged: dict = {}
    for key in all_keys:
        wb = wb_data.get(key, _empty_model())
        oz = ozon_data.get(key, _empty_model())
        merged[key] = {
            "revenue": round(wb["revenue"] + oz["revenue"], 2),
            "margin": round(wb["margin"] + oz["margin"], 2),
            "cost_of_goods": round(wb["cost_of_goods"] + oz["cost_of_goods"], 2),
            "adv_internal": round(wb["adv_internal"] + oz["adv_internal"], 2),
            "adv_external": round(wb["adv_external"] + oz["adv_external"], 2),
            "sales_count": wb["sales_count"] + oz["sales_count"],
            "orders_count": wb["orders_count"] + oz["orders_count"],
            "orders_rub": round(wb["orders_rub"] + oz["orders_rub"], 2),
        }

    by_period: dict = {"current": {}, "previous": {}}
    for (period, model), data in merged.items():
        orders_rub = data["orders_rub"]
        revenue = data["revenue"]
        adv_total = data["adv_internal"] + data["adv_external"]
        data["drr_pct"] = round(adv_total / orders_rub * 100, 2) if orders_rub > 0 else 0.0
        data["drr_rub"] = round(adv_total, 2)
        data["margin_pct"] = round(data["margin"] / revenue * 100, 2) if revenue > 0 else 0.0
        if period in by_period:
            by_period[period][model] = data

    for model in list(by_period["current"].keys()):
        curr_rev = by_period["current"][model]["revenue"]
        prev_rev = by_period["previous"].get(model, {}).get("revenue", 0)
        if prev_rev > 0:
            trend = round((curr_rev - prev_rev) / prev_rev * 100, 1)
        else:
            trend = 0.0
        by_period["current"][model]["trend_pct"] = trend

    return {
        "current": by_period["current"],
        "previous": by_period["previous"],
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
            "prev_start": str(prev_start),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Модели сохранены → {OUTPUT_PATH}")
    for model, stats in sorted(data["current"].items(), key=lambda x: -x[1]["revenue"]):
        print(f"  {model:15s}  {stats['revenue']:>10,.0f} ₽  маржа {stats['margin_pct']:.1f}%  ДРР {stats['drr_pct']:.1f}%  тренд {stats.get('trend_pct', 0):+.1f}%")
