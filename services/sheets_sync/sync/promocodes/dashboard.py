"""Dashboard summary computation and sheet header rendering."""
from __future__ import annotations

from datetime import date

import gspread

from shared.clients.sheets_client import get_moscow_now


def compute_dashboard_summary(
    week_aggs: dict[str, dict], dictionary: dict[str, dict]
) -> dict:
    """Return dashboard metrics for the most recent week (across both cabinets)."""
    if not week_aggs:
        return {
            "promocodes_count": 0,
            "sales_total": 0,
            "orders_total": 0,
            "champion_name": "—",
            "champion_sales": 0,
            "unknown_uuids": [],
        }

    sales_total = sum(b["sales_rub"] for b in week_aggs.values())
    orders_total = sum(b["orders_count"] for b in week_aggs.values())
    champion_uuid, champion = max(
        week_aggs.items(), key=lambda kv: kv[1]["sales_rub"]
    )
    champion_name = (
        dictionary.get(champion_uuid.lower(), {}).get("name") or "неизвестный"
    )
    unknown = sorted(uuid for uuid in week_aggs if uuid.lower() not in dictionary)
    return {
        "promocodes_count": len(week_aggs),
        "sales_total": round(sales_total, 2),
        "orders_total": orders_total,
        "champion_name": champion_name,
        "champion_sales": round(champion["sales_rub"], 2),
        "unknown_uuids": unknown,
    }


def write_dashboard_header(
    ws: gspread.Worksheet,
    summary: dict,
    weeks_processed: list[tuple[date, date]],
) -> None:
    """Render dashboard rows 2-7 with timestamp, status, and last-week metrics."""
    now_str = get_moscow_now().strftime("%Y-%m-%d %H:%M:%S МСК")
    weeks_label = "—" if not weeks_processed else (
        f"{weeks_processed[-1][0].strftime('%d.%m')}–"
        f"{weeks_processed[0][1].strftime('%d.%m')}"
    )
    status_line = (
        f"✅ {len(weeks_processed)} нед. ({weeks_label}), пропусков нет"
        if weeks_processed else "⚠️ Нет данных"
    )
    unknown_n = len(summary.get("unknown_uuids", []))
    unknown_line = (
        f"{unknown_n} (см. жёлтые строки ниже)" if unknown_n else "0 ✓"
    )
    last_week = weeks_processed[0] if weeks_processed else None
    last_week_label = (
        f"{last_week[0].strftime('%d.%m')}–{last_week[1].strftime('%d.%m')}"
        if last_week else "—"
    )
    block = [
        ["Последнее обновление:", now_str, "", "", ""],
        ["Статус полноты:", status_line, "", "", ""],
        ["Неизвестных UUID:", unknown_line, "", "", ""],
        ["", "", "", "", ""],
        [f"── За последнюю неделю ({last_week_label}) ──", "", "", "", ""],
        [
            f"Промокодов: {summary.get('promocodes_count', 0)}  │  "
            f"Продажи: {summary.get('sales_total', 0):,.0f} ₽  │  "
            f"Заказов: {summary.get('orders_total', 0)}  │  "
            f"Чемпион: {summary.get('champion_name', '—')} "
            f"({summary.get('champion_sales', 0):,.0f} ₽)".replace(",", " "),
            "", "", "", "",
        ],
    ]
    ws.update(range_name="A2:E7", values=block, value_input_option="USER_ENTERED")
