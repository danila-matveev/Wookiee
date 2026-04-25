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
