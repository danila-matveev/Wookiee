"""
Ibrahim Scheduler — APScheduler-based task runner.

Daily: ETL sync + reconciliation (05:00 MSK)
Weekly: API docs + schema analysis (Sunday 03:00 MSK)
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from agents.ibrahim.config import (
    TIMEZONE,
    SYNC_HOUR,
    SYNC_MINUTE,
    WEEKLY_DAY,
    WEEKLY_HOUR,
    WEEKLY_MINUTE,
)
from agents.ibrahim.ibrahim_service import IbrahimService

logger = logging.getLogger(__name__)


class IbrahimScheduler:
    """Manages scheduled Ibrahim tasks."""

    def __init__(self):
        self.tz = pytz.timezone(TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        self.ibrahim = IbrahimService()

    def setup(self) -> None:
        """Configure scheduled jobs."""
        # Daily: sync + reconcile
        daily_trigger = CronTrigger(
            hour=SYNC_HOUR,
            minute=SYNC_MINUTE,
            timezone=self.tz,
        )
        self.scheduler.add_job(
            self.ibrahim.daily_routine,
            trigger=daily_trigger,
            id="ibrahim_daily",
            name=f"Daily ETL ({SYNC_HOUR:02d}:{SYNC_MINUTE:02d} MSK)",
            replace_existing=True,
        )

        # Weekly: API + schema analysis
        weekly_trigger = CronTrigger(
            day_of_week=WEEKLY_DAY,
            hour=WEEKLY_HOUR,
            minute=WEEKLY_MINUTE,
            timezone=self.tz,
        )
        self.scheduler.add_job(
            self.ibrahim.weekly_routine,
            trigger=weekly_trigger,
            id="ibrahim_weekly",
            name=f"Weekly Analysis ({WEEKLY_DAY} {WEEKLY_HOUR:02d}:{WEEKLY_MINUTE:02d} MSK)",
            replace_existing=True,
        )

        daily_job = self.scheduler.get_job("ibrahim_daily")
        weekly_job = self.scheduler.get_job("ibrahim_weekly")
        logger.info(
            "Scheduled: daily at %02d:%02d MSK (next: %s)",
            SYNC_HOUR, SYNC_MINUTE,
            daily_job.next_run_time if daily_job else "?",
        )
        logger.info(
            "Scheduled: weekly %s at %02d:%02d MSK (next: %s)",
            WEEKLY_DAY, WEEKLY_HOUR, WEEKLY_MINUTE,
            weekly_job.next_run_time if weekly_job else "?",
        )

    async def start(self, run_now: bool = False) -> None:
        """Start scheduler, optionally run daily routine immediately.

        Args:
            run_now: If True, run daily routine before entering loop.
        """
        self.setup()
        self.scheduler.start()
        logger.info("Ibrahim scheduler started")

        if run_now:
            logger.info("Running daily routine now...")
            await self.ibrahim.daily_routine()

        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Stopping Ibrahim scheduler...")
            self.scheduler.shutdown()
