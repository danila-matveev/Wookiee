"""Legacy flat-format helpers — kept solely for unit-test compatibility.

The pivot pipeline does not use these. They predate the pivot redesign and
remain importable so existing tests keep passing without touching them.
"""
from __future__ import annotations

from datetime import date

ANALYTICS_HEADERS = [
    "Неделя", "Кабинет", "Название", "UUID", "Скидка %",
    "Продажи (retail), ₽", "К перечислению, ₽",
    "Заказов, шт", "Возвратов, шт", "Ср. чек, ₽",
    "Топ-3 модели", "Обновлено",
]


def format_analytics_row(
    week_start: date, week_end: date, cabinet: str, uuid: str,
    metrics: dict, dictionary: dict[str, dict], updated_at_iso: str,
) -> list:
    """Build one flat-format row (legacy, not used by pivot run())."""
    info = dictionary.get(uuid.lower(), {})
    name = info.get("name") or "неизвестный"
    discount = info.get("discount_pct")
    if discount is None:
        discount = round(metrics.get("avg_discount_pct", 0.0), 2)
    avg_check = (
        round(metrics["sales_rub"] / metrics["orders_count"], 2)
        if metrics["orders_count"] else 0.0
    )
    top3_str = ", ".join(
        f"{m} ({v:,.0f}₽)".replace(",", " ")
        for m, v in metrics.get("top3_models", [])
    ) or "—"
    week_label = f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"
    return [
        week_label, cabinet, name, uuid, discount,
        round(metrics["sales_rub"], 2), round(metrics["ppvz_rub"], 2),
        metrics["orders_count"], metrics["returns_count"], avg_check,
        top3_str, updated_at_iso,
    ]
