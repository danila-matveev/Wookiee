"""ISO-week date helpers."""
from __future__ import annotations

from datetime import date, timedelta


def last_closed_iso_week(today: date | None = None) -> tuple[date, date]:
    """Return (Mon, Sun) of the most recent fully-closed ISO week."""
    today = today or date.today()
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
