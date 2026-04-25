"""WB Promocodes weekly analytics sync.

Pulls reportDetailByPeriod v5 for both cabinets, aggregates by
uuid_promocode, joins with a manually maintained dictionary sheet,
and upserts rows into the analytics sheet (idempotent on
week_start + cabinet + uuid).
"""
from __future__ import annotations

from datetime import date, timedelta


def last_closed_iso_week(today: date | None = None) -> tuple[date, date]:
    """Return (Mon, Sun) of the most recent fully-closed ISO week.

    «Fully closed» means today is at least Monday of the next week,
    so the prior week's Sunday data is final at WB.
    """
    today = today or date.today()
    # Move to today's Monday, then jump back 7 days
    monday_this_week = today - timedelta(days=today.weekday())
    last_mon = monday_this_week - timedelta(days=7)
    last_sun = last_mon + timedelta(days=6)
    return last_mon, last_sun


def iso_weeks_back(n: int, today: date | None = None) -> list[tuple[date, date]]:
    """Return n most recent fully-closed ISO weeks, newest first."""
    last_mon, last_sun = last_closed_iso_week(today=today)
    weeks: list[tuple[date, date]] = []
    for i in range(n):
        mon = last_mon - timedelta(days=7 * i)
        sun = last_sun - timedelta(days=7 * i)
        weeks.append((mon, sun))
    return weeks


from collections import defaultdict


def aggregate_by_uuid(rows: list[dict]) -> dict[str, dict]:
    """Group reportDetailByPeriod rows by uuid_promocode.

    Skips rows where uuid_promocode is empty/0/None. Returns:
        {uuid: {
            'sales_rub': float,         # retail_amount sum, only «Продажа»
            'ppvz_rub': float,          # ppvz_for_pay sum, only «Продажа»
            'orders_count': int,        # sum(quantity) for «Продажа»
            'returns_count': int,       # sum(quantity) for «Возврат»
            'avg_discount_pct': float,  # mean of sale_price_promocode_discount_prc
            'top3_models': list[tuple[str, float]],  # by sales_rub desc
        }}
    """
    buckets: dict[str, dict] = defaultdict(lambda: {
        "sales_rub": 0.0,
        "ppvz_rub": 0.0,
        "orders_count": 0,
        "returns_count": 0,
        "_disc_sum": 0.0,
        "_disc_n": 0,
        "_models": defaultdict(float),
    })

    for row in rows:
        uuid = row.get("uuid_promocode")
        if not uuid:                # "", None, 0
            continue
        pid = str(uuid).strip()
        if not pid:
            continue

        doc = (row.get("doc_type_name") or "").strip()
        qty = int(row.get("quantity") or 0)
        retail = float(row.get("retail_amount") or 0.0)
        ppvz = float(row.get("ppvz_for_pay") or 0.0)
        sa = (row.get("sa_name") or "").strip().lower()

        b = buckets[pid]

        if doc == "Продажа":
            b["sales_rub"] += retail
            b["ppvz_rub"] += ppvz
            b["orders_count"] += qty or 1
            if sa:
                b["_models"][sa] += retail
        elif doc in ("Возврат", "Корректный возврат"):
            b["returns_count"] += qty or 1

        d = row.get("sale_price_promocode_discount_prc")
        if d is not None and d != "":
            try:
                b["_disc_sum"] += float(d)
                b["_disc_n"] += 1
            except (TypeError, ValueError):
                pass

    # Finalize
    out: dict[str, dict] = {}
    for pid, b in buckets.items():
        avg_d = (b["_disc_sum"] / b["_disc_n"]) if b["_disc_n"] else 0.0
        top3 = sorted(b["_models"].items(), key=lambda kv: kv[1], reverse=True)[:3]
        out[pid] = {
            "sales_rub": b["sales_rub"],
            "ppvz_rub": b["ppvz_rub"],
            "orders_count": b["orders_count"],
            "returns_count": b["returns_count"],
            "avg_discount_pct": avg_d,
            "top3_models": top3,
        }
    return out


def parse_dictionary(raw_rows: list[list[str]]) -> dict[str, dict]:
    """Parse the справочник sheet into {uuid_lower: {name, channel, discount_pct, ...}}.

    Expects header in row 0; rows with empty UUID are dropped.
    """
    if not raw_rows or len(raw_rows) < 2:
        return {}
    out: dict[str, dict] = {}
    for row in raw_rows[1:]:
        # pad missing cells
        cells = (row + [""] * 7)[:7]
        uuid_raw, name, channel, disc, start, end, note = cells
        uuid = (uuid_raw or "").strip().lower()
        if not uuid:
            continue
        try:
            disc_pct = float(disc) if disc not in ("", None) else None
        except ValueError:
            disc_pct = None
        out[uuid] = {
            "name": (name or "").strip(),
            "channel": (channel or "").strip(),
            "discount_pct": disc_pct,
            "start": (start or "").strip(),
            "end": (end or "").strip(),
            "note": (note or "").strip(),
        }
    return out


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
    """Build one row matching ANALYTICS_HEADERS order."""
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
        week_label,
        cabinet,
        name,
        uuid,
        discount,
        round(metrics["sales_rub"], 2),
        round(metrics["ppvz_rub"], 2),
        metrics["orders_count"],
        metrics["returns_count"],
        avg_check,
        top3_str,
        updated_at_iso,
    ]


def compute_dashboard_summary(
    week_aggs: dict[str, dict], dictionary: dict[str, dict]
) -> dict:
    """Return dashboard metrics for the most recent week (across both cabinets).

    Keys: promocodes_count, sales_total, orders_total,
          champion_name, champion_sales, unknown_uuids.
    """
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

    unknown = sorted(
        uuid for uuid in week_aggs.keys()
        if uuid.lower() not in dictionary
    )
    return {
        "promocodes_count": len(week_aggs),
        "sales_total": round(sales_total, 2),
        "orders_total": orders_total,
        "champion_name": champion_name,
        "champion_sales": round(champion["sales_rub"], 2),
        "unknown_uuids": unknown,
    }
