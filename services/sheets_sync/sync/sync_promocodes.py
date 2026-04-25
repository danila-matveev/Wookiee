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
