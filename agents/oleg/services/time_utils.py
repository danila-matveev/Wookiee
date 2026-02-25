"""
Time utilities — MSK timezone helpers.

Reused from v1 agents/oleg/services/time_utils.py.
"""
from datetime import datetime, timedelta, date
import pytz

MSK = pytz.timezone("Europe/Moscow")


def get_now_msk() -> datetime:
    """Get current datetime in MSK timezone."""
    return datetime.now(MSK)


def get_today_msk() -> date:
    """Get today's date in MSK timezone."""
    return get_now_msk().date()


def get_yesterday_msk() -> date:
    """Get yesterday's date in MSK."""
    return get_today_msk() - timedelta(days=1)


def get_week_bounds_msk(reference_date: date = None) -> tuple[date, date]:
    """Get Monday-Sunday bounds for the week containing reference_date."""
    if reference_date is None:
        reference_date = get_today_msk()
    monday = reference_date - timedelta(days=reference_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_last_week_bounds_msk() -> tuple[date, date]:
    """Get Monday-Sunday bounds for last week."""
    today = get_today_msk()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday


def get_last_month_bounds_msk() -> tuple[date, date]:
    """Get first and last day of previous month."""
    today = get_today_msk()
    first_of_this_month = today.replace(day=1)
    last_of_prev = first_of_this_month - timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)
    return first_of_prev, last_of_prev
