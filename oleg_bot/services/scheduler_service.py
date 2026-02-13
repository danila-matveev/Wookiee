"""
Scheduler Service for Automatic Daily Reports
Sends daily analytics at 10:05 AM Moscow time
"""
import logging
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from typing import List, Callable

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for scheduling automatic reports"""

    def __init__(self, timezone: str = "Europe/Moscow"):
        """
        Initialize scheduler

        Args:
            timezone: Timezone for scheduling (default: Europe/Moscow)
        """
        self.timezone = pytz.timezone(timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self.is_running = False

    def add_daily_report(
        self,
        callback: Callable,
        hour: int = 10,
        minute: int = 5,
        job_id: str = "daily_report"
    ) -> None:
        """
        Add daily report job to scheduler

        Args:
            callback: Async function to call daily
            hour: Hour to run (default: 10)
            minute: Minute to run (default: 5)
            job_id: Unique job identifier
        """
        # Create cron trigger for daily execution
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=self.timezone
        )

        # Add job
        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            name=f"Daily Report ({hour:02d}:{minute:02d} {self.timezone})",
            replace_existing=True
        )

        logger.info(
            f"Daily report scheduled: {hour:02d}:{minute:02d} {self.timezone}"
        )

    def add_weekly_report(
        self,
        callback: Callable,
        day_of_week: int = 0,  # Monday
        hour: int = 10,
        minute: int = 0,
        job_id: str = "weekly_report"
    ) -> None:
        """
        Add weekly report job to scheduler

        Args:
            callback: Async function to call weekly
            day_of_week: Day of week (0=Monday, 6=Sunday)
            hour: Hour to run
            minute: Minute to run
            job_id: Unique job identifier
        """
        trigger = CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone=self.timezone
        )

        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            name=f"Weekly Report ({day_of_week} {hour:02d}:{minute:02d})",
            replace_existing=True
        )

        logger.info(f"Weekly report scheduled: day {day_of_week}, {hour:02d}:{minute:02d}")

    def add_monthly_report(
        self,
        callback: Callable,
        day: int = 1,
        hour: int = 10,
        minute: int = 0,
        job_id: str = "monthly_report"
    ) -> None:
        """
        Add monthly report job to scheduler

        Args:
            callback: Async function to call monthly
            day: Day of month (1-31)
            hour: Hour to run
            minute: Minute to run
            job_id: Unique job identifier
        """
        trigger = CronTrigger(
            day=day,
            hour=hour,
            minute=minute,
            timezone=self.timezone
        )

        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            name=f"Monthly Report (day {day}, {hour:02d}:{minute:02d})",
            replace_existing=True
        )

        logger.info(f"Monthly report scheduled: day {day}, {hour:02d}:{minute:02d}")

    def remove_job(self, job_id: str) -> bool:
        """
        Remove scheduled job

        Args:
            job_id: Job identifier to remove

        Returns:
            True if removed, False if not found
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    def start(self) -> None:
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Scheduler started")

    def shutdown(self) -> None:
        """Shutdown the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler shutdown")

    def list_jobs(self) -> List[dict]:
        """
        List all scheduled jobs

        Returns:
            List of job info dicts
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return jobs

    def get_next_run_time(self, job_id: str) -> datetime:
        """
        Get next run time for a job

        Args:
            job_id: Job identifier

        Returns:
            Next run datetime or None if not found
        """
        job = self.scheduler.get_job(job_id)
        return job.next_run_time if job else None
