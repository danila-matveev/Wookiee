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


from services.sheets_sync.sync.sync_promocodes import parse_dictionary


def test_parse_dictionary_uses_uuid_as_key_and_lowercases():
    raw = [
        ["UUID", "Название", "Канал", "Скидка %", "Старт", "Окончание", "Примечание"],
        ["BE6900F2-c9e9-4963-9ad1-27d10d9492d6", "CHARLOTTE10",
         "Соцсети", "10", "02.03.2026", "12.03.2026", "wendy"],
        ["", "broken row", "", "", "", "", ""],
        ["abc", "X", "Блогер", "", "", "", ""],   # missing discount ok
    ]
    d = parse_dictionary(raw)
    assert "be6900f2-c9e9-4963-9ad1-27d10d9492d6" in d
    assert d["be6900f2-c9e9-4963-9ad1-27d10d9492d6"]["name"] == "CHARLOTTE10"
    assert d["be6900f2-c9e9-4963-9ad1-27d10d9492d6"]["channel"] == "Соцсети"
    assert d["be6900f2-c9e9-4963-9ad1-27d10d9492d6"]["discount_pct"] == 10.0
    assert d["abc"]["name"] == "X"
    # broken row dropped
    assert len(d) == 2


from services.sheets_sync.sync.sync_promocodes import format_analytics_row


def test_format_analytics_row_uses_dictionary_when_uuid_known():
    metrics = {
        "sales_rub": 12433.0, "ppvz_rub": 13866.0,
        "orders_count": 8, "returns_count": 0, "avg_discount_pct": 10.0,
        "top3_models": [("charlotte/black", 6131.0), ("charlotte/brown", 3200.0)],
    }
    dictionary = {"be6900f2": {"name": "CHARLOTTE10", "channel": "Соцсети",
                               "discount_pct": 10.0, "start": "", "end": "", "note": ""}}
    row = format_analytics_row(
        week_start=date(2026, 3, 9), week_end=date(2026, 3, 15),
        cabinet="ООО", uuid="be6900f2", metrics=metrics, dictionary=dictionary,
        updated_at_iso="2026-04-25T11:05:00",
    )
    assert row[0] == "09.03–15.03.2026"
    assert row[1] == "ООО"
    assert row[2] == "CHARLOTTE10"
    assert row[3] == "be6900f2"
    assert row[4] == 10.0
    assert row[5] == 12433.0
    assert row[7] == 8
    assert "charlotte/black" in row[10]


def test_format_analytics_row_marks_unknown_when_uuid_missing():
    row = format_analytics_row(
        week_start=date(2026, 4, 13), week_end=date(2026, 4, 19),
        cabinet="ИП", uuid="zzzz",
        metrics={"sales_rub": 100, "ppvz_rub": 90, "orders_count": 1,
                 "returns_count": 0, "avg_discount_pct": 0, "top3_models": []},
        dictionary={},
        updated_at_iso="2026-04-25T11:05:00",
    )
    assert row[2] == "неизвестный"


from services.sheets_sync.sync.sync_promocodes import compute_dashboard_summary


def test_compute_dashboard_summary_picks_champion_by_sales():
    week_aggs = {
        "u1": {"sales_rub": 1000, "ppvz_rub": 900, "orders_count": 5,
               "returns_count": 0, "avg_discount_pct": 5, "top3_models": []},
        "u2": {"sales_rub": 5000, "ppvz_rub": 4500, "orders_count": 3,
               "returns_count": 0, "avg_discount_pct": 10, "top3_models": []},
    }
    dictionary = {"u2": {"name": "MYALICE5"}}
    s = compute_dashboard_summary(week_aggs=week_aggs, dictionary=dictionary)
    assert s["promocodes_count"] == 2
    assert s["sales_total"] == 6000
    assert s["orders_total"] == 8
    assert s["champion_name"] == "MYALICE5"
    assert s["champion_sales"] == 5000
    assert s["unknown_uuids"] == ["u1"]


def test_compute_dashboard_summary_handles_empty():
    s = compute_dashboard_summary(week_aggs={}, dictionary={})
    assert s["promocodes_count"] == 0
    assert s["sales_total"] == 0
    assert s["champion_name"] == "—"
