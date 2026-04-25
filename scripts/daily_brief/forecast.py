"""Daily Brief — прогноз и GAP-анализ.

3 модели прогноза (как у финансового аналитика):
- baseline: среднее за все прошедшие дни × дней в месяце
- trend: среднее за последние 5 дней × дней в месяце
- weighted: 70% trend + 30% baseline
"""
from __future__ import annotations


TREND_WINDOW_DAYS = 5


def compute_forecast(series: list[dict], days_in_month: int, metric: str = "margin") -> dict:
    """Три модели прогноза для указанной метрики по бренду (WB+OZON).

    Args:
        series: daily_series из collector
        days_in_month: всего дней в месяце (28-31)
        metric: 'margin' | 'revenue' | 'orders'

    Returns:
        dict с тремя прогнозами + MTD + daily pace.
    """
    # Take only valid days (no errors, numbers present)
    valid = [d for d in series if "error" not in d]
    if not valid:
        return {
            "baseline": 0, "trend": 0, "weighted": 0,
            "mtd": 0, "pace_per_day": 0, "days_elapsed": 0,
        }

    # metric → which keys to sum
    wb_key = f"wb_{metric}"
    ozon_key = f"ozon_{metric}"

    def _day_total(d: dict) -> float:
        return float(d.get(wb_key, 0) or 0) + float(d.get(ozon_key, 0) or 0)

    days_elapsed = len(valid)
    mtd_total = sum(_day_total(d) for d in valid)
    pace_per_day = mtd_total / days_elapsed if days_elapsed else 0

    # Baseline: mtd / days_elapsed * days_in_month
    baseline = pace_per_day * days_in_month

    # Trend: avg over last N days * days_in_month
    trend_slice = valid[-TREND_WINDOW_DAYS:] if days_elapsed >= TREND_WINDOW_DAYS else valid
    trend_avg = sum(_day_total(d) for d in trend_slice) / len(trend_slice) if trend_slice else 0
    trend_forecast = trend_avg * days_in_month

    # Weighted: 70% trend + 30% baseline (как у аналитика)
    weighted = 0.7 * trend_forecast + 0.3 * baseline

    return {
        "baseline": round(baseline),
        "trend": round(trend_forecast),
        "weighted": round(weighted),
        "mtd": round(mtd_total),
        "pace_per_day": round(pace_per_day),
        "trend_per_day": round(trend_avg),
        "days_elapsed": days_elapsed,
    }


def compute_gap(forecast: dict, plan: float, days_in_month: int) -> dict:
    """GAP-анализ: что нужно, чтобы выйти на план.

    Args:
        forecast: результат compute_forecast (используем weighted)
        plan: плановое значение за месяц
        days_in_month: всего дней в месяце

    Returns:
        dict с разрывом и требуемым темпом.
    """
    mtd = forecast["mtd"]
    days_elapsed = forecast["days_elapsed"]
    days_remaining = days_in_month - days_elapsed

    forecast_value = forecast["weighted"]
    gap_abs = forecast_value - plan
    gap_pct = (gap_abs / plan * 100) if plan else 0

    needed_remaining = plan - mtd
    needed_per_day = (needed_remaining / days_remaining) if days_remaining > 0 else 0
    current_pace = forecast["pace_per_day"]
    gap_per_day = needed_per_day - current_pace

    return {
        "plan_month": round(plan),
        "forecast_month": round(forecast_value),
        "gap_abs": round(gap_abs),
        "gap_pct": round(gap_pct, 1),
        "mtd_pct_of_plan": round(mtd / plan * 100, 1) if plan else 0,
        "needed_remaining": round(needed_remaining),
        "needed_per_day": round(needed_per_day),
        "current_pace_per_day": round(current_pace),
        "gap_per_day": round(gap_per_day),
        "days_remaining": days_remaining,
    }


def compute_plan_day(plan_month: float, days_in_month: int) -> float:
    """Плановый показатель за один день (простое деление)."""
    return plan_month / days_in_month if days_in_month else 0
