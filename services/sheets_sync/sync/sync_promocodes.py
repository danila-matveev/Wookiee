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
