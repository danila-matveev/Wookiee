# agents/reporter/scheduler.py
"""APScheduler setup — 3 cron jobs replacing 15 in V3."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agents.reporter.config import (
    DATA_READY_CHECK_HOURS,
    DEADLINE_HOUR,
    HEARTBEAT_INTERVAL_HOURS,
    TIMEZONE,
)

logger = logging.getLogger(__name__)


def create_scheduler(gate_checker, state) -> AsyncIOScheduler:
    """Create scheduler with 3 jobs."""
    from agents.reporter.conductor import data_ready_check, deadline_check, heartbeat

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Job 1: data_ready_check — hourly 06:00-12:00
    scheduler.add_job(
        data_ready_check,
        trigger=CronTrigger(
            hour=f"{min(DATA_READY_CHECK_HOURS)}-{max(DATA_READY_CHECK_HOURS)}",
            minute=0,
            timezone=TIMEZONE,
        ),
        kwargs={"gate_checker": gate_checker, "state": state},
        id="data_ready_check",
        name="Check data readiness and generate reports",
        replace_existing=True,
    )

    # Job 2: deadline_check — 13:00
    scheduler.add_job(
        deadline_check,
        trigger=CronTrigger(
            hour=DEADLINE_HOUR,
            minute=0,
            timezone=TIMEZONE,
        ),
        kwargs={"state": state},
        id="deadline_check",
        name="Alert if daily report missing",
        replace_existing=True,
    )

    # Job 3: heartbeat — every 6 hours
    scheduler.add_job(
        heartbeat,
        trigger=IntervalTrigger(hours=HEARTBEAT_INTERVAL_HOURS),
        kwargs={"state": state},
        id="heartbeat",
        name="Health status heartbeat",
        replace_existing=True,
    )

    logger.info("Scheduler created with 3 jobs")
    return scheduler
