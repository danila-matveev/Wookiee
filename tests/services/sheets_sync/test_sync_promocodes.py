"""Unit tests for sync_promocodes (pure functions)."""
from datetime import date

from services.sheets_sync.sync.sync_promocodes import (
    last_closed_iso_week,
    iso_weeks_back,
)


def test_last_closed_iso_week_returns_previous_mon_sun():
    # Friday 24.04.2026 → previous full ISO week is 13.04 (Mon) – 19.04 (Sun)
    today = date(2026, 4, 24)
    start, end = last_closed_iso_week(today=today)
    assert start == date(2026, 4, 13)
    assert end == date(2026, 4, 19)


def test_last_closed_iso_week_when_today_is_monday():
    # Monday 27.04.2026 → previous full ISO week is 20.04 – 26.04
    today = date(2026, 4, 27)
    start, end = last_closed_iso_week(today=today)
    assert start == date(2026, 4, 20)
    assert end == date(2026, 4, 26)


def test_iso_weeks_back_returns_n_weeks_descending():
    today = date(2026, 4, 24)
    weeks = iso_weeks_back(n=3, today=today)
    assert weeks == [
        (date(2026, 4, 13), date(2026, 4, 19)),
        (date(2026, 4, 6),  date(2026, 4, 12)),
        (date(2026, 3, 30), date(2026, 4, 5)),
    ]


from services.sheets_sync.sync.sync_promocodes import aggregate_by_uuid


def _row(uuid="u1", sa="charlotte/black", retail=1000.0, ppvz=900.0,
         disc=10, qty=1, doc="Продажа") -> dict:
    return {
        "uuid_promocode": uuid,
        "sa_name": sa,
        "retail_amount": retail,
        "ppvz_for_pay": ppvz,
        "sale_price_promocode_discount_prc": disc,
        "quantity": qty,
        "doc_type_name": doc,
    }


def test_aggregate_skips_rows_without_uuid():
    rows = [_row(uuid=""), _row(uuid=None), _row(uuid=0), _row(uuid="u1")]
    out = aggregate_by_uuid(rows)
    assert list(out.keys()) == ["u1"]


def test_aggregate_sums_sales_and_counts_orders():
    rows = [
        _row(uuid="u1", retail=1000, ppvz=900, qty=1),
        _row(uuid="u1", retail=500,  ppvz=450, qty=2),
        _row(uuid="u1", doc="Возврат", retail=300, ppvz=270, qty=1),
    ]
    agg = aggregate_by_uuid(rows)["u1"]
    assert agg["sales_rub"] == 1500.0       # only «Продажа» retail
    assert agg["ppvz_rub"] == 1350.0
    assert agg["orders_count"] == 3         # sum(quantity) for «Продажа»
    assert agg["returns_count"] == 1


def test_aggregate_top3_models_by_sales():
    rows = [
        _row(uuid="u1", sa="charlotte/black", retail=600),
        _row(uuid="u1", sa="charlotte/brown", retail=400),
        _row(uuid="u1", sa="charlotte/beige", retail=200),
        _row(uuid="u1", sa="audrey/pink",     retail=100),
    ]
    agg = aggregate_by_uuid(rows)["u1"]
    assert agg["top3_models"] == [
        ("charlotte/black", 600.0),
        ("charlotte/brown", 400.0),
        ("charlotte/beige", 200.0),
    ]


def test_aggregate_average_discount():
    rows = [
        _row(uuid="u1", disc=10),
        _row(uuid="u1", disc=20),
    ]
    assert aggregate_by_uuid(rows)["u1"]["avg_discount_pct"] == 15.0
