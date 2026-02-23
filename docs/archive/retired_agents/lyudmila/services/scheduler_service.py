"""
Scheduler для Людмилы — утренний дайджест по таймзону пользователя
"""
import logging
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

logger = logging.getLogger(__name__)


class LyudmilaScheduler:
    """
    Планировщик для бота Людмилы.

    - Персональный дайджест: каждому пользователю — своя джоба с учётом таймзона
    - Обновление кеша сотрудников: каждые 30 минут
    - Проверка уволенных: каждые 6 часов
    """

    def __init__(self, default_timezone: str = "Europe/Moscow"):
        self.default_tz = pytz.timezone(default_timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.default_tz)
        self.is_running = False

    def schedule_digest(
        self,
        telegram_id: int,
        callback: Callable,
        hour: int = 9,
        minute: int = 0,
        timezone: str = "Europe/Moscow",
    ) -> None:
        """
        Запланировать утренний дайджест для пользователя.

        Args:
            telegram_id: ID пользователя (для уникальности job)
            callback: Async-функция для вызова
            hour: Час дайджеста
            minute: Минута
            timezone: Таймзон пользователя
        """
        job_id = f"digest_{telegram_id}"
        tz = pytz.timezone(timezone)

        trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)

        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            name=f"Digest for {telegram_id}",
            replace_existing=True,
            kwargs={"telegram_id": telegram_id},
        )

        logger.info(f"Digest scheduled: {telegram_id} at {hour:02d}:{minute:02d} {timezone}")

    def reschedule_digest(
        self,
        telegram_id: int,
        hour: int,
        minute: int,
        timezone: str,
    ) -> None:
        """Перепланировать дайджест (при смене таймзона/времени)"""
        job_id = f"digest_{telegram_id}"
        tz = pytz.timezone(timezone)

        try:
            self.scheduler.reschedule_job(
                job_id,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            )
            logger.info(f"Digest rescheduled: {telegram_id} → {hour:02d}:{minute:02d} {timezone}")
        except Exception as e:
            logger.warning(f"Reschedule failed for {telegram_id}: {e}")

    def remove_digest(self, telegram_id: int) -> None:
        """Удалить дайджест пользователя"""
        job_id = f"digest_{telegram_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Digest removed: {telegram_id}")
        except Exception:
            pass

    def schedule_cache_refresh(self, callback: Callable, minutes: int = 30) -> None:
        """Обновление кеша сотрудников"""
        self.scheduler.add_job(
            callback,
            trigger=IntervalTrigger(minutes=minutes),
            id="user_cache_refresh",
            name="User cache refresh",
            replace_existing=True,
        )
        logger.info(f"Cache refresh scheduled: every {minutes} min")

    def schedule_deactivation_check(self, callback: Callable, hours: int = 6) -> None:
        """Проверка уволенных сотрудников"""
        self.scheduler.add_job(
            callback,
            trigger=IntervalTrigger(hours=hours),
            id="deactivation_check",
            name="Deactivation check",
            replace_existing=True,
        )
        logger.info(f"Deactivation check scheduled: every {hours} hours")

    def schedule_sync(
        self,
        job_id: str,
        callback: Callable,
        minutes: Optional[int] = None,
        hour: Optional[int] = None,
    ) -> None:
        """
        Расписание синхронизации Bitrix → Supabase.

        Args:
            job_id: Уникальный ID задачи
            callback: Async-функция для вызова
            minutes: Интервал в минутах (IntervalTrigger)
            hour: Час для ежедневного запуска (CronTrigger)
        """
        if minutes:
            trigger = IntervalTrigger(minutes=minutes)
            desc = f"every {minutes} min"
        elif hour is not None:
            trigger = CronTrigger(hour=hour, minute=0, timezone=self.default_tz)
            desc = f"daily at {hour:02d}:00"
        else:
            return

        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            name=f"Sync: {job_id}",
            replace_existing=True,
        )
        logger.info(f"Sync scheduled: {job_id} ({desc})")

    def schedule_weekly(
        self,
        job_id: str,
        callback: Callable,
        day_of_week: str = "mon",
        hour: int = 9,
        minute: int = 0,
        kwargs: Optional[dict] = None,
    ) -> None:
        """
        Еженедельная задача (например, понедельник 09:00).

        Args:
            job_id: Уникальный ID
            callback: Async-функция
            day_of_week: День недели (mon/tue/wed/...)
            hour: Час
            minute: Минута
            kwargs: Именованные аргументы для callback
        """
        trigger = CronTrigger(
            day_of_week=day_of_week, hour=hour, minute=minute, timezone=self.default_tz,
        )
        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            name=f"Weekly: {job_id}",
            replace_existing=True,
            kwargs=kwargs or {},
        )
        logger.info(f"Weekly scheduled: {job_id} ({day_of_week} at {hour:02d}:{minute:02d})")

    def start(self) -> None:
        """Запуск планировщика"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Lyudmila scheduler started")

    def shutdown(self) -> None:
        """Остановка планировщика"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Lyudmila scheduler shutdown")
