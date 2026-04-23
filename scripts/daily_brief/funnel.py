"""Daily Brief — воронка WB по дням.

Собирает содержимое воронки за последние N дней:
- Просмотры карточки (card_opens)
- Добавления в корзину (add_to_cart)
- Заказы (funnel_orders)
- Выкупы (buyouts)

Плюс расчёт конверсий:
- Корзины / Просмотры (CR_to_cart)
- Заказы / Корзины (CR_to_order)
- Выкупы / Заказы (CR_to_buyout, выкуп %)
"""
from __future__ import annotations
from datetime import date, timedelta

from shared.data_layer import traffic


def _percent(num: float, den: float) -> float | None:
    if not den:
        return None
    return round(num / den * 100, 2)


def collect_funnel_day(target: date) -> dict:
    """Воронка за один день."""
    start = target.isoformat()
    end = (target + timedelta(days=1)).isoformat()
    content, adv = traffic.get_wb_traffic(
        current_start=start,
        prev_start=start,
        current_end=end,
    )
    # content: (period, card_opens, add_to_cart, funnel_orders, buyouts)
    card_opens = add_to_cart = funnel_orders = buyouts = 0.0
    for row in content or []:
        if row[0] != "current":
            continue
        card_opens = float(row[1] or 0)
        add_to_cart = float(row[2] or 0)
        funnel_orders = float(row[3] or 0)
        buyouts = float(row[4] or 0)
        break

    return {
        "date": target.isoformat(),
        "card_opens": round(card_opens),
        "add_to_cart": round(add_to_cart),
        "funnel_orders": round(funnel_orders),
        "buyouts": round(buyouts),
        "cr_to_cart_pct": _percent(add_to_cart, card_opens),
        "cr_to_order_pct": _percent(funnel_orders, add_to_cart),
        "cr_end_to_end_pct": _percent(funnel_orders, card_opens),  # сквозная: просмотр → заказ (CRO)
        "buyout_pct": _percent(buyouts, funnel_orders),
    }


def collect_funnel_series(target: date, days_back: int = 5) -> list[dict]:
    """Воронка за последние N дней включая target."""
    series = []
    for i in range(days_back - 1, -1, -1):
        d = target - timedelta(days=i)
        try:
            series.append(collect_funnel_day(d))
        except Exception as e:  # noqa: BLE001
            series.append({"date": d.isoformat(), "error": str(e)})
    return series


def collect_ozon_ad_funnel_day(target: date) -> dict:
    """OZON — рекламная воронка за один день.

    В БД OZON нет аналога content_analysis (органическая воронка), поэтому показываем
    только данные по рекламе: просмотры, клики, заказы из рекламы, расход.
    """
    start = target.isoformat()
    end = (target + timedelta(days=1)).isoformat()
    rows = traffic.get_ozon_traffic(current_start=start, prev_start=start, current_end=end)
    ad_views = ad_clicks = ad_orders = ad_spend = 0.0
    for row in rows or []:
        # row: (period, ad_views, ad_clicks, ad_orders, ad_spend, ctr, cpc)
        if row[0] != "current":
            continue
        ad_views = float(row[1] or 0)
        ad_clicks = float(row[2] or 0)
        ad_orders = float(row[3] or 0)
        ad_spend = float(row[4] or 0)
        break
    return {
        "date": target.isoformat(),
        "ad_views": round(ad_views),
        "ad_clicks": round(ad_clicks),
        "ad_orders": round(ad_orders),
        "ad_spend": round(ad_spend),
        "ctr_pct": _percent(ad_clicks, ad_views),
        "cr_click_to_order_pct": _percent(ad_orders, ad_clicks),
    }


def collect_ozon_ad_funnel_series(target: date, days_back: int = 5) -> list[dict]:
    series = []
    for i in range(days_back - 1, -1, -1):
        d = target - timedelta(days=i)
        try:
            series.append(collect_ozon_ad_funnel_day(d))
        except Exception as e:  # noqa: BLE001
            series.append({"date": d.isoformat(), "error": str(e)})
    return series
