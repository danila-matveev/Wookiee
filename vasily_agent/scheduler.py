"""Standalone scheduler for periodic localization reports.

Can be started independently:
    python -m vasily_agent

Or imported and started from another process:
    from vasily_agent.scheduler import VasilyScheduler
    scheduler = VasilyScheduler()
    asyncio.run(scheduler.start())
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from vasily_agent.config import (
    REPORT_DAY_OF_WEEK,
    REPORT_PERIOD_DAYS,
    REPORT_HOUR,
    REPORT_MINUTE,
    CABINETS,
    TIMEZONE,
    VASILY_SPREADSHEET_ID,
    BITRIX_CHAT_ID,
)
from vasily_agent.service import VasilyService
from vasily_agent.sheets_export import export_to_sheets
from vasily_agent.bitrix_notify import VasilyBitrixNotifier

logger = logging.getLogger(__name__)


class VasilyScheduler:
    """Manages periodic localization report generation and distribution."""

    def __init__(self):
        self.tz = pytz.timezone(TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vasily")
        self.vasily = VasilyService()
        self.notifier = VasilyBitrixNotifier()

    def _run_single_cabinet(self, cabinet: str) -> dict:
        """Run report for one cabinet (synchronous, runs in thread)."""
        logger.info("Запуск расчёта для %s...", cabinet)

        result = self.vasily.run_report(cabinet, days=REPORT_PERIOD_DAYS)
        logger.info(
            "Расчёт %s завершён: индекс=%.1f%%",
            result["cabinet"],
            result["summary"]["overall_index"],
        )

        # Export to Google Sheets
        sheets_url = ""
        if VASILY_SPREADSHEET_ID:
            try:
                sheets_url = export_to_sheets(result)
            except Exception as e:
                logger.error("Ошибка экспорта в Sheets для %s: %s", cabinet, e)

        # Notify Bitrix chat
        if BITRIX_CHAT_ID:
            try:
                self.notifier.notify_report(result, sheets_url)
            except Exception as e:
                logger.error("Ошибка уведомления Bitrix для %s: %s", cabinet, e)

        return result

    async def run_all_reports(self) -> None:
        """Run reports for all configured cabinets."""
        logger.info("=" * 60)
        logger.info("Запуск отчётов по локализации для: %s", ", ".join(CABINETS))
        logger.info("=" * 60)

        loop = asyncio.get_event_loop()

        for cabinet in CABINETS:
            cab = cabinet.strip()
            if not cab:
                continue
            try:
                await loop.run_in_executor(self.executor, self._run_single_cabinet, cab)
            except Exception as e:
                logger.error("Ошибка расчёта для %s: %s", cab, e, exc_info=True)
                # Notify about failure
                if BITRIX_CHAT_ID:
                    try:
                        self.notifier.send_message(
                            f"[B]ОШИБКА[/B] Отчёт по локализации ({cab}): {e}"
                        )
                    except Exception:
                        pass

        logger.info("Все отчёты завершены")

    def setup(self) -> None:
        """Configure scheduled jobs."""
        trigger = CronTrigger(
            day_of_week=REPORT_DAY_OF_WEEK,
            hour=REPORT_HOUR,
            minute=REPORT_MINUTE,
            timezone=self.tz,
        )
        self.scheduler.add_job(
            self.run_all_reports,
            trigger=trigger,
            id="vasily_localization_report",
            name=f"Localization Report ({REPORT_DAY_OF_WEEK} {REPORT_HOUR:02d}:{REPORT_MINUTE:02d})",
            replace_existing=True,
        )
        logger.info(
            "Расписание: %s в %02d:%02d МСК, следующий запуск — %s",
            REPORT_DAY_OF_WEEK,
            REPORT_HOUR,
            REPORT_MINUTE,
            self.scheduler.get_job("vasily_localization_report").next_run_time,
        )

    async def start(self, run_now: bool = True) -> None:
        """Start the scheduler and optionally run immediately.

        Args:
            run_now: If True, run all reports immediately before scheduling.
        """
        self.setup()
        self.scheduler.start()
        logger.info("Vasily scheduler запущен")

        if run_now:
            logger.info("Первый расчёт — сейчас")
            await self.run_all_reports()

        # Keep alive
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Остановка Vasily scheduler...")
            self.scheduler.shutdown()
            self.executor.shutdown(wait=False)

    async def run_once(self) -> None:
        """Run all reports once without scheduling (for manual/testing use)."""
        await self.run_all_reports()
