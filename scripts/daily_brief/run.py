"""Daily Brief — orchestrator.

Собирает данные, считает прогнозы, детектирует паттерны,
сохраняет итоговый JSON для LLM-narrative.

Usage:
    python scripts/daily_brief/run.py                  # вчера
    python scripts/daily_brief/run.py 2026-04-15       # конкретный день
"""
from __future__ import annotations
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.daily_brief import collector, forecast, patterns
from shared.tool_logger import ToolLogger


def parse_date_arg(arg: str | None) -> date:
    if not arg:
        return date.today() - timedelta(days=1)
    return datetime.strptime(arg, "%Y-%m-%d").date()


def build_brief(target: date) -> dict:
    """Главный pipeline: данные → прогноз → паттерны → итоговый JSON."""
    raw = collector.collect_day(target)

    # Brand day metrics (WB + OZON current period)
    wb_cur = raw["wb_day"].get("current", {})
    ozon_cur = raw["ozon_day"].get("current", {})
    wb_prev = raw["wb_day"].get("previous", {})
    ozon_prev = raw["ozon_day"].get("previous", {})

    # Orders in rubles (важный показатель: реклама влияет именно на сумму заказов)
    wb_orders_rub_cur = float(wb_cur.get("orders_rub") or 0)
    ozon_orders_rub_cur = float(ozon_cur.get("orders_rub") or 0)
    wb_orders_rub_prev = float(wb_prev.get("orders_rub") or 0)
    ozon_orders_rub_prev = float(ozon_prev.get("orders_rub") or 0)
    orders_rub_today = wb_orders_rub_cur + ozon_orders_rub_cur
    orders_rub_yesterday = wb_orders_rub_prev + ozon_orders_rub_prev
    orders_rub_delta_pct = ((orders_rub_today - orders_rub_yesterday) / orders_rub_yesterday * 100) if orders_rub_yesterday else None

    # Ad share of orders (а не от выручки — реклама формирует заказы, выручка = выкупы позже)
    ad_total_today = float(wb_cur.get("adv_internal", 0) or 0) + float(wb_cur.get("adv_external", 0) or 0) + float(ozon_cur.get("adv_internal", 0) or 0)
    ad_share_of_orders_today = (ad_total_today / orders_rub_today * 100) if orders_rub_today else None

    def _brand_total(key: str) -> tuple[float, float, float | None]:
        """Суммирует метрику по бренду (WB + OZON) для current и previous
        и возвращает (today, yesterday, delta_pct)."""
        today = float(wb_cur.get(key, 0) or 0) + float(ozon_cur.get(key, 0) or 0)
        yday = float(wb_prev.get(key, 0) or 0) + float(ozon_prev.get(key, 0) or 0)
        delta = ((today - yday) / abs(yday) * 100) if yday else None
        return today, yday, delta

    margin_today, margin_yesterday, margin_delta = _brand_total("margin")
    revenue_today, revenue_yesterday, revenue_delta = _brand_total("revenue_before_spp")
    orders_today, orders_yesterday, orders_delta = _brand_total("orders_count")
    ad_today_wb = float(wb_cur.get("adv_internal", 0) or 0)
    ad_yesterday_wb = float(wb_prev.get("adv_internal", 0) or 0)
    ad_delta_pct = ((ad_today_wb - ad_yesterday_wb) / ad_yesterday_wb * 100) if ad_yesterday_wb else None

    marginality_today = (margin_today / revenue_today * 100) if revenue_today else None
    marginality_yesterday = (margin_yesterday / revenue_yesterday * 100) if revenue_yesterday else None

    # Forecasts (margin, revenue, orders)
    fc_margin = forecast.compute_forecast(
        raw["daily_series"], raw["days_in_month"], metric="margin",
    )
    fc_revenue = forecast.compute_forecast(
        raw["daily_series"], raw["days_in_month"], metric="revenue",
    )
    fc_orders = forecast.compute_forecast(
        raw["daily_series"], raw["days_in_month"], metric="orders",
    )

    # GAP vs plan
    plan = raw.get("plan") or {}
    plan_margin = plan.get("margin") or 0
    plan_revenue = plan.get("revenue") or 0
    plan_orders_rub = plan.get("orders_rub") or 0

    gap_margin = forecast.compute_gap(fc_margin, plan_margin, raw["days_in_month"])
    plan_day_margin = forecast.compute_plan_day(plan_margin, raw["days_in_month"])

    # Model radar (WB + OZON combined)
    wb_radar = patterns.detect_model_radar(raw["wb_models_day"], raw["wb_models_mtd"])
    ozon_radar = patterns.detect_model_radar(raw["ozon_models_day"], raw["ozon_models_mtd"])

    # Flags
    flags = []
    flags += patterns.detect_marginality_flags({"marginality_pct": marginality_today})
    flags += patterns.detect_pace_flag(gap_margin)
    flags += patterns.detect_ad_anomaly(raw["daily_series"], target.isoformat())
    flags += patterns.detect_funnel_flags(raw.get("funnel_series") or [])

    # Trends
    trends = patterns.compute_trends(raw["daily_series"])

    # Last 5 days table (для визуальной динамики)
    last5 = patterns.build_last_days_table(raw["daily_series"], days=5)

    # Маркетинговый контекст
    marketing_ctx = patterns.build_marketing_context(raw.get("marketing_sheets") or {})

    # OZON рекламная воронка (последние 5 дней)
    from scripts.daily_brief import funnel as funnel_mod
    ozon_ad_funnel = funnel_mod.collect_ozon_ad_funnel_series(target, days_back=5)

    # Прогноз по динамике заказов (опережающий индикатор)
    orders_momentum = patterns.compute_orders_momentum(raw["daily_series"])

    return {
        "meta": {
            "target_date": target.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "month_start": raw["month_start"],
            "month_end": raw["month_end"],
            "days_in_month": raw["days_in_month"],
            "day_of_month": raw["day_of_month"],
            "days_remaining": raw["days_in_month"] - raw["day_of_month"],
        },
        "yesterday": {
            "margin_brand": round(margin_today),
            "margin_yesterday": round(margin_yesterday),
            "margin_delta_pct": round(margin_delta, 1) if margin_delta is not None else None,
            "revenue_brand": round(revenue_today),
            "revenue_yesterday": round(revenue_yesterday),
            "revenue_delta_pct": round(revenue_delta, 1) if revenue_delta is not None else None,
            "orders_brand": round(orders_today),
            "orders_yesterday": round(orders_yesterday),
            "orders_delta_pct": round(orders_delta, 1) if orders_delta is not None else None,
            "marginality_pct": round(marginality_today, 1) if marginality_today is not None else None,
            "marginality_yesterday": round(marginality_yesterday, 1) if marginality_yesterday is not None else None,
            "ad_internal_wb": round(ad_today_wb),
            "ad_delta_pct_wb": round(ad_delta_pct, 1) if ad_delta_pct is not None else None,
            "orders_rub_brand": round(orders_rub_today),
            "orders_rub_yesterday": round(orders_rub_yesterday),
            "orders_rub_delta_pct": round(orders_rub_delta_pct, 1) if orders_rub_delta_pct is not None else None,
            "ad_share_of_orders_pct": round(ad_share_of_orders_today, 2) if ad_share_of_orders_today is not None else None,
            "wb_margin": round(wb_cur.get("margin", 0) or 0),
            "ozon_margin": round(ozon_cur.get("margin", 0) or 0),
            "wb_orders_rub": round(wb_orders_rub_cur),
            "ozon_orders_rub": round(ozon_orders_rub_cur),
        },
        "plan_day": {
            "margin": round(plan_day_margin),
            "_note": "плановая маржинальная прибыль в день",
        },
        "forecast": {
            "margin": fc_margin,
            "revenue": fc_revenue,
            "orders": fc_orders,
        },
        "gap": {
            "margin": gap_margin,
        },
        "plan_month": {
            "margin": round(plan_margin),
            "revenue": round(plan_revenue),
            "orders_rub": round(plan_orders_rub),
            "_note": "план по маржинальной прибыли, выручке и сумме заказов в рублях",
        },
        "trends_monthly": trends,
        "orders_momentum": orders_momentum,
        "last_5_days": last5,
        "funnel_series_wb": raw.get("funnel_series") or [],
        "ozon_ad_funnel_series": ozon_ad_funnel,
        "marketing_context": marketing_ctx,
        "model_radar": {
            "wb": wb_radar,
            "ozon": ozon_radar,
        },
        "flags": flags,
    }


def main():
    target = parse_date_arg(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"[daily-brief] target date: {target.isoformat()}")

    tl = ToolLogger("/daily-brief")
    with tl.run(period_start=target.isoformat(), period_end=target.isoformat()) as run_meta:
        brief = build_brief(target)

        # Save JSON
        out_dir = ROOT / "data" / "daily_brief"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target.isoformat()}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(brief, f, ensure_ascii=False, indent=2)
        print(f"[daily-brief] saved: {out_path}")

        run_meta["items"] = sum(
            len(v) if isinstance(v, list) else 1
            for v in brief.values()
            if not isinstance(v, (str, int, float, bool))
        )

        # Print a short summary to stdout (for skill to pick up)
        print(json.dumps(brief, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
