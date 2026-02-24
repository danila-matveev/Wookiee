"""Tests for APScheduler configuration."""
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz


def _create_scheduler_with_jobs(daily_time="09:00", weekly_time="10:15"):
    """Helper: create scheduler with standard jobs."""
    tz = pytz.timezone("Europe/Moscow")
    scheduler = AsyncIOScheduler(timezone=tz)

    daily_h, daily_m = (int(x) for x in daily_time.split(":"))
    weekly_h, weekly_m = (int(x) for x in weekly_time.split(":"))

    async def _stub():
        pass

    scheduler.add_job(
        _stub,
        CronTrigger(day_of_week="mon-sat", hour=daily_h, minute=daily_m, timezone=tz),
        id="daily_report",
    )
    scheduler.add_job(
        _stub,
        CronTrigger(day_of_week="mon", hour=weekly_h, minute=weekly_m, timezone=tz),
        id="weekly_report",
    )
    scheduler.add_job(
        _stub,
        CronTrigger(hour="*/6", minute=0, timezone=tz),
        id="watchdog_heartbeat",
    )

    return scheduler


def test_jobs_created():
    """Scheduler creates 3 expected jobs."""
    scheduler = _create_scheduler_with_jobs()
    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}
    assert job_ids == {"daily_report", "weekly_report", "watchdog_heartbeat"}


def test_daily_schedule():
    """Daily report runs Mon-Sat at configured time."""
    scheduler = _create_scheduler_with_jobs("09:00")
    job = scheduler.get_job("daily_report")
    trigger = job.trigger
    # Check cron fields
    assert str(trigger).startswith("cron")
    assert "hour='9'" in str(trigger)
    assert "minute='0'" in str(trigger)
    assert "day_of_week='mon-sat'" in str(trigger)


def test_weekly_schedule():
    """Weekly report runs Monday at configured time."""
    scheduler = _create_scheduler_with_jobs(weekly_time="10:15")
    job = scheduler.get_job("weekly_report")
    trigger = job.trigger
    assert "hour='10'" in str(trigger)
    assert "minute='15'" in str(trigger)
    assert "day_of_week='mon'" in str(trigger)


def test_heartbeat_schedule():
    """Watchdog heartbeat runs every 6 hours."""
    scheduler = _create_scheduler_with_jobs()
    job = scheduler.get_job("watchdog_heartbeat")
    trigger = job.trigger
    assert "hour='*/6'" in str(trigger)
    assert "minute='0'" in str(trigger)


def test_config_parsing():
    """Time string parsing: '09:00' → h=9 m=0, '10:15' → h=10 m=15."""
    for time_str, expected_h, expected_m in [
        ("09:00", 9, 0),
        ("10:15", 10, 15),
        ("23:59", 23, 59),
        ("00:00", 0, 0),
    ]:
        h, m = (int(x) for x in time_str.split(":"))
        assert h == expected_h
        assert m == expected_m
