"""Daily Brief — сборщик метрик.

Собирает метрики за один день и весь месяц-до-даты из Supabase.
НЕ делает прогнозы и не форматирует narrative — только числа.
"""
from __future__ import annotations
from datetime import date, timedelta
from calendar import monthrange
from typing import Any

from shared.data_layer import finance, planning

from scripts.daily_brief import funnel as funnel_mod
from scripts.daily_brief import marketing_sheets as marketing_sheets_mod


def _prev_day(d: date) -> date:
    return d - timedelta(days=1)


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    last = monthrange(d.year, d.month)[1]
    return d.replace(day=last)


def _parse_row(row: tuple, columns: list[str]) -> dict:
    return dict(zip(columns, row))


def _merge_orders(parsed: dict, orders_rows: list) -> None:
    """finance.get_wb/ozon_finance возвращают второй tuple: [(period, orders_count, orders_rub)].
    Мёрджим и orders_count, и orders_rub в parsed[period] — иначе по OZON заказы
    штучно всегда 0 (в OZON_FINANCE_COLUMNS нет orders_count)."""
    for row in orders_rows or []:
        period = row[0]
        orders_count = int(row[1]) if len(row) > 1 and row[1] is not None else 0
        orders_rub = float(row[2]) if len(row) > 2 and row[2] is not None else 0.0
        if period in parsed:
            parsed[period]["orders_count"] = orders_count
            parsed[period]["orders_rub"] = orders_rub


def collect_day(target: date) -> dict[str, Any]:
    """Собирает все метрики за указанный день.

    Args:
        target: день, за который нужен анализ (обычно вчера)

    Returns:
        dict со всеми числами: день, MTD, история по дням месяца, план.
    """
    prev_day = _prev_day(target)
    month_start = _month_start(target)
    month_end = _month_end(target)
    next_day = target + timedelta(days=1)

    result: dict[str, Any] = {
        "target_date": target.isoformat(),
        "prev_date": prev_day.isoformat(),
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "days_in_month": monthrange(target.year, target.month)[1],
        "day_of_month": target.day,
    }

    # Day-level: target vs prev day (for yesterday comparison)
    wb_day, wb_day_orders = finance.get_wb_finance(
        current_start=target.isoformat(),
        prev_start=prev_day.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["wb_day"] = _parse_finance_rows(wb_day, "wb")
    _merge_orders(result["wb_day"], wb_day_orders)

    ozon_day, ozon_day_orders = finance.get_ozon_finance(
        current_start=target.isoformat(),
        prev_start=prev_day.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["ozon_day"] = _parse_finance_rows(ozon_day, "ozon")
    _merge_orders(result["ozon_day"], ozon_day_orders)

    # MTD: month start → target (inclusive)
    wb_mtd, _ = finance.get_wb_finance(
        current_start=month_start.isoformat(),
        prev_start=month_start.isoformat(),  # no prev, just get current
        current_end=next_day.isoformat(),
    )
    result["wb_mtd"] = _parse_finance_rows(wb_mtd, "wb")

    ozon_mtd, _ = finance.get_ozon_finance(
        current_start=month_start.isoformat(),
        prev_start=month_start.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["ozon_mtd"] = _parse_finance_rows(ozon_mtd, "ozon")

    # Daily series for the month (for trends + forecast)
    result["daily_series"] = _collect_daily_series(month_start, target)

    # Plan for the month
    result["plan"] = _collect_plan(month_start, month_end)

    # Model breakdown for the target day
    wb_models_day = finance.get_wb_by_model(
        current_start=target.isoformat(),
        prev_start=prev_day.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["wb_models_day"] = _parse_model_rows(wb_models_day)

    ozon_models_day = finance.get_ozon_by_model(
        current_start=target.isoformat(),
        prev_start=prev_day.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["ozon_models_day"] = _parse_model_rows(ozon_models_day)

    # Model breakdown MTD
    wb_models_mtd = finance.get_wb_by_model(
        current_start=month_start.isoformat(),
        prev_start=month_start.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["wb_models_mtd"] = _parse_model_rows(wb_models_mtd)

    ozon_models_mtd = finance.get_ozon_by_model(
        current_start=month_start.isoformat(),
        prev_start=month_start.isoformat(),
        current_end=next_day.isoformat(),
    )
    result["ozon_models_mtd"] = _parse_model_rows(ozon_models_mtd)

    # Воронка WB: последние 5 дней
    result["funnel_series"] = funnel_mod.collect_funnel_series(target, days_back=5)

    # Маркетинг из Google Sheets: блогеры (7 дней назад + 3 дня план), ВК, СММ
    try:
        result["marketing_sheets"] = marketing_sheets_mod.collect_marketing_sheets(
            target=target, past_days=7, future_days=3,
        )
    except Exception as e:  # noqa: BLE001
        result["marketing_sheets"] = {"error": str(e)}

    return result


WB_FINANCE_COLUMNS = [
    "period", "orders_count", "sales_count",
    "revenue_before_spp", "revenue_after_spp",
    "adv_internal", "adv_external",
    "cost_of_goods", "logistics", "storage",
    "commission", "spp_amount", "nds",
    "penalty", "retention", "deduction",
    "margin", "returns_revenue", "revenue_before_spp_gross",
]

# OZON finance: period, sales_count, revenue_before_spp, revenue_after_spp,
# adv_internal, adv_external, margin, cost_of_goods, logistics, storage,
# commission, spp_amount, nds (13 cols, no orders_count)
OZON_FINANCE_COLUMNS = [
    "period", "sales_count",
    "revenue_before_spp", "revenue_after_spp",
    "adv_internal", "adv_external",
    "margin", "cost_of_goods",
    "logistics", "storage",
    "commission", "spp_amount", "nds",
]

# get_wb_by_model / get_ozon_by_model: 8 columns
MODEL_COLUMNS = [
    "period", "model", "sales_count",
    "revenue_before_spp", "adv_internal", "adv_external",
    "margin", "cost_of_goods",
]


def _parse_finance_rows(rows: list, channel: str = "wb") -> dict[str, dict]:
    """finance.get_wb_finance / get_ozon_finance возвращает (current, previous) строки."""
    columns = WB_FINANCE_COLUMNS if channel == "wb" else OZON_FINANCE_COLUMNS
    out = {}
    for row in rows or []:
        parsed = _parse_row(row, columns)
        period = parsed.pop("period")
        out[period] = {k: (float(v) if v is not None else None) for k, v in parsed.items()}
    return out


def _parse_model_rows(rows: list) -> list[dict]:
    """finance.get_wb_by_model / get_ozon_by_model — 8 колонок."""
    out = []
    for row in rows or []:
        parsed = dict(zip(MODEL_COLUMNS, row))
        if not parsed.get("model"):
            continue
        for k in list(parsed.keys()):
            if k in ("period", "model"):
                continue
            v = parsed[k]
            parsed[k] = float(v) if v is not None else None
        out.append(parsed)
    return out


def _collect_daily_series(month_start: date, target: date) -> list[dict]:
    """Собирает метрики по каждому дню месяца до target включительно.

    Для прогноза нужна история по дням — объём заказов, выручки, маржи, рекламы.
    """
    series = []
    d = month_start
    while d <= target:
        next_d = d + timedelta(days=1)
        try:
            wb_rows, wb_ord = finance.get_wb_finance(
                current_start=d.isoformat(),
                prev_start=d.isoformat(),
                current_end=next_d.isoformat(),
            )
            ozon_rows, ozon_ord = finance.get_ozon_finance(
                current_start=d.isoformat(),
                prev_start=d.isoformat(),
                current_end=next_d.isoformat(),
            )
            wb_parsed = _parse_finance_rows(wb_rows, "wb")
            ozon_parsed = _parse_finance_rows(ozon_rows, "ozon")
            _merge_orders(wb_parsed, wb_ord)
            _merge_orders(ozon_parsed, ozon_ord)
            wb = wb_parsed.get("current", {})
            ozon = ozon_parsed.get("current", {})

            series.append({
                "date": d.isoformat(),
                "wb_margin": wb.get("margin", 0) or 0,
                "wb_revenue": wb.get("revenue_before_spp", 0) or 0,
                "wb_orders": int(wb.get("orders_count", 0) or 0),
                "wb_orders_rub": wb.get("orders_rub", 0) or 0,
                "wb_sales": wb.get("sales_count", 0) or 0,
                "wb_ad_internal": wb.get("adv_internal", 0) or 0,
                "wb_ad_external": wb.get("adv_external", 0) or 0,
                "ozon_margin": ozon.get("margin", 0) or 0,
                "ozon_revenue": ozon.get("revenue_before_spp", 0) or 0,
                "ozon_orders": int(ozon.get("orders_count", 0) or 0),
                "ozon_orders_rub": ozon.get("orders_rub", 0) or 0,
                "ozon_sales": ozon.get("sales_count", 0) or 0,
                "ozon_ad_internal": ozon.get("adv_internal", 0) or 0,
            })
        except Exception as e:  # noqa: BLE001
            series.append({
                "date": d.isoformat(),
                "error": str(e),
            })
        d = next_d
    return series


def _collect_plan(month_start: date, month_end: date) -> dict:
    """Агрегирует план из plan_article по месяцу."""
    try:
        rows = planning.get_plan_by_period(
            month_start.isoformat(),
            month_end.isoformat(),
        )
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "margin": None, "revenue": None, "orders_rub": None, "orders_qty": None}

    def _parse_val(v) -> float:
        if v is None:
            return 0.0
        s = str(v).replace("\xa0", "").replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    totals = {"margin": 0.0, "revenue": 0.0, "orders_rub": 0.0, "orders_qty": 0.0}
    for row in rows or []:
        # row: (МП, ЛК, Артикул, Показатель, Значение)
        indicator = (row[3] or "").strip().lower()
        value = _parse_val(row[4])
        if "маржин" in indicator:
            totals["margin"] += value
        elif "выруч" in indicator:
            totals["revenue"] += value
        elif "заказ" in indicator and "руб" in indicator:
            totals["orders_rub"] += value
        elif "заказ" in indicator and ("шт" in indicator or "кол" in indicator):
            totals["orders_qty"] += value
    return totals
