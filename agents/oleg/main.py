"""
Oleg Bot — ИИ финансовый аналитик Wookiee

Точка входа: python -m oleg_bot.main
"""
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from agents.oleg import config
from agents.oleg.services.auth_service import AuthService
from shared.clients.zai_client import ZAIClient
from agents.oleg.services.oleg_agent import OlegAgent
from agents.oleg.services.report_storage import ReportStorage
from agents.oleg.services.report_formatter import ReportFormatter
from agents.oleg.services.feedback_service import FeedbackService
from agents.oleg.services.notion_service import NotionService
from agents.oleg.services.scheduler_service import SchedulerService
from agents.oleg.services.data_freshness_service import DataFreshnessService

from agents.oleg.handlers import auth, menu, scheduled_reports, custom_queries

# ─── Logging ──────────────────────────────────────────────────
Path(config.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class OlegBot:
    """Главный класс бота Олега — ИИ финансовый аналитик"""

    def __init__(self):
        logger.info("Initializing Oleg Bot...")

        # Bot & Dispatcher
        self.bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher(storage=MemoryStorage())

        # Services
        self.auth_service = AuthService(config.HASHED_PASSWORD)
        self.zai_client = ZAIClient(
            api_key=config.ZAI_API_KEY,
            model=config.ZAI_MODEL,
        )
        self.oleg_agent = OlegAgent(
            zai_client=self.zai_client,
            playbook_path=config.PLAYBOOK_PATH,
            model=config.OLEG_MODEL,
        )
        # LLM-based query understanding (uses cheap glm-4.5-flash)
        from agents.oleg.services.query_understanding import QueryUnderstandingService
        self.query_understanding = QueryUnderstandingService(
            zai_client=self.zai_client,
        )
        self.report_storage = ReportStorage(config.SQLITE_DB_PATH)
        self.feedback_service = FeedbackService(notion_token=config.NOTION_TOKEN)
        self.notion_service = NotionService(
            token=config.NOTION_TOKEN,
            database_id=config.NOTION_DATABASE_ID,
        )
        self.scheduler = SchedulerService(config.TIMEZONE)
        self.data_freshness = DataFreshnessService(
            db_host=config.DB_HOST,
            db_port=config.DB_PORT,
            db_user=config.DB_USER,
            db_password=config.DB_PASSWORD,
            db_name_wb=config.DB_NAME_WB,
            db_name_ozon=config.DB_NAME_OZON,
        )

        # Register middleware & routers
        self._setup_middleware()
        self._register_routers()

        logger.info("Oleg Bot initialized")

    def _setup_middleware(self) -> None:
        """DI middleware — инжектирует сервисы в хендлеры"""

        @self.dp.message.middleware()
        async def inject_services(handler, event, data):
            data['auth_service'] = self.auth_service
            data['oleg_agent'] = self.oleg_agent
            data['report_storage'] = self.report_storage
            data['feedback_service'] = self.feedback_service
            data['notion_service'] = self.notion_service
            data['query_understanding'] = self.query_understanding
            return await handler(event, data)

        @self.dp.callback_query.middleware()
        async def inject_services_callback(handler, event, data):
            data['auth_service'] = self.auth_service
            data['oleg_agent'] = self.oleg_agent
            data['report_storage'] = self.report_storage
            data['feedback_service'] = self.feedback_service
            data['notion_service'] = self.notion_service
            data['query_understanding'] = self.query_understanding
            return await handler(event, data)

    def _register_routers(self) -> None:
        """Регистрация роутеров"""
        self.dp.include_router(auth.router)
        self.dp.include_router(menu.router)
        self.dp.include_router(scheduled_reports.router)
        self.dp.include_router(custom_queries.router)

        logger.info("Routers registered")

    def _setup_scheduler(self) -> None:
        """Schedule automatic reports: daily, weekly, monthly + data freshness"""

        # ─── Daily report (Oleg via tool-use) ────────────────
        async def send_daily_report():
            logger.info("Sending scheduled daily report (Oleg)")
            try:
                # Проверяем готовность данных перед генерацией
                freshness = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(freshness):
                    wb_detail = freshness['wb']['details']
                    ozon_detail = freshness['ozon']['details']
                    logger.warning(
                        f"Daily report SKIPPED: data not ready. "
                        f"WB: {wb_detail}, OZON: {ozon_detail}"
                    )
                    # Уведомить пользователей что отчёт отложен
                    for user_id in self.auth_service.authenticated_users:
                        try:
                            await self.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "⏳ Дневной отчёт отложен — данные ещё не готовы.\n\n"
                                    f"WB: {wb_detail}\n"
                                    f"OZON: {ozon_detail}\n\n"
                                    "Отчёт будет сформирован автоматически, "
                                    "как только данные загрузятся."
                                ),
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify {user_id} about delay: {e}")
                    return

                yesterday = datetime.now() - timedelta(days=1)
                date_str = yesterday.strftime("%Y-%m-%d")

                result = await self.oleg_agent.analyze_deep(
                    user_query="Ежедневная аналитическая сводка",
                    params={
                        "start_date": date_str,
                        "end_date": date_str,
                        "channels": ["wb", "ozon"],
                        "report_type": "daily",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    error_detail = result.get("error", "нет brief_summary")
                    logger.error(f"Daily report failed: {error_detail}")
                    for user_id in self.auth_service.authenticated_users:
                        try:
                            await self.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    f"Дневной отчёт не сформирован.\n\n"
                                    f"Причина: {error_detail}\n\n"
                                    f"Попробуйте запросить отчёт вручную через меню."
                                ),
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify {user_id} about report error: {e}")
                    return

                # Sync to Notion
                notion_url = await self.notion_service.sync_report(
                    start_date=date_str,
                    end_date=date_str,
                    report_md=result.get("detailed_report", ""),
                    source="Telegram Bot",
                )

                # Build cost info
                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )
                keyboard = ReportFormatter.create_report_keyboard("daily")

                for user_id in self.auth_service.authenticated_users:
                    try:
                        self.report_storage.save_report(
                            user_id=user_id,
                            report_type="daily_auto",
                            title=f"Ежедневная сводка за {yesterday.strftime('%d.%m.%Y')}",
                            content=result.get("detailed_report", ""),
                            start_date=yesterday,
                            end_date=yesterday,
                        )
                        await self._send_html(user_id, html_text, keyboard)
                        logger.info(f"Sent daily report to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send report to user {user_id}: {e}")

                # Пометить что отчёт за сегодня отправлен
                self._daily_report_sent_date = date.today()

            except Exception as e:
                logger.error(f"Daily report job failed: {e}", exc_info=True)

        # ─── Weekly report (Monday) ────────────────
        async def send_weekly_report():
            logger.info("Sending scheduled weekly report (Oleg)")
            try:
                end = datetime.now() - timedelta(days=1)
                start = end - timedelta(days=6)
                s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

                result = await self.oleg_agent.analyze_deep(
                    user_query="Еженедельная аналитическая сводка",
                    params={
                        "start_date": s,
                        "end_date": e,
                        "channels": ["wb", "ozon"],
                        "report_type": "weekly",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    logger.error(f"Weekly report failed: {result.get('error', 'no brief_summary')}")
                    return

                notion_url = await self.notion_service.sync_report(
                    start_date=s, end_date=e,
                    report_md=result.get("detailed_report", ""),
                )

                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )
                keyboard = ReportFormatter.create_report_keyboard("weekly")

                for user_id in self.auth_service.authenticated_users:
                    try:
                        await self._send_html(user_id, html_text, keyboard)
                        logger.info(f"Sent weekly report to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send weekly report to {user_id}: {e}")

            except Exception as e:
                logger.error(f"Weekly report job failed: {e}", exc_info=True)

        # ─── Monthly check (every Monday — sends if new month started) ──
        async def check_and_send_monthly():
            today = datetime.now()
            if today.day > 7:
                return

            first_of_month = today.replace(day=1)
            last_month_end = first_of_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            month_str = last_month_end.strftime("%Y-%m")

            if self.report_storage.has_report_for_period("monthly_auto", month_str):
                logger.info(f"Monthly report for {month_str} already sent, skipping")
                return

            logger.info(f"Sending monthly report for {month_str}")

            try:
                s = last_month_start.strftime("%Y-%m-%d")
                e = last_month_end.strftime("%Y-%m-%d")

                result = await self.oleg_agent.analyze_deep(
                    user_query=f"Месячный аналитический отчёт за {month_str}",
                    params={
                        "start_date": s,
                        "end_date": e,
                        "channels": ["wb", "ozon"],
                        "report_type": "monthly",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    logger.error(f"Monthly report failed: {result.get('error', 'no brief_summary')}")
                    return

                notion_url = await self.notion_service.sync_report(
                    start_date=s, end_date=e,
                    report_md=result.get("detailed_report", ""),
                )

                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )
                keyboard = ReportFormatter.create_report_keyboard("monthly")

                for user_id in self.auth_service.authenticated_users:
                    try:
                        self.report_storage.save_report(
                            user_id=user_id,
                            report_type="monthly_auto",
                            title=f"Месячный отчёт за {month_str}",
                            content=result.get("detailed_report", ""),
                            metadata={"month": month_str},
                        )
                        await self._send_html(user_id, html_text, keyboard)
                        logger.info(f"Sent monthly report to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send monthly report to {user_id}: {e}")

            except Exception as e:
                logger.error(f"Monthly report job failed: {e}", exc_info=True)

        # ─── Data freshness monitor ────────────────
        # Флаг: дневной отчёт за сегодня уже отправлен?
        self._daily_report_sent_date: Optional[date] = None

        async def check_data_freshness():
            if self.data_freshness.already_notified_today():
                # Данные уже были объявлены готовыми сегодня.
                # Проверяем, не нужно ли догенерировать отчёт
                # (если send_daily_report пропустил из-за неготовности данных).
                today = date.today()
                if self._daily_report_sent_date != today:
                    logger.info("Data ready, but daily report not yet sent — triggering now")
                    await send_daily_report()
                    if self._daily_report_sent_date != today:
                        # send_daily_report пометит дату если успешно (см. ниже)
                        pass
                return
            try:
                status = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(status):
                    return

                self.data_freshness.mark_notified()
                msg = self.data_freshness.format_notification(status)
                for user_id in self.auth_service.authenticated_users:
                    try:
                        await self.bot.send_message(chat_id=user_id, text=msg)
                    except Exception as e:
                        logger.error(f"Failed to send freshness notification to {user_id}: {e}")

                # Если дневной отчёт ещё не был отправлен — отправить сейчас
                today = date.today()
                if self._daily_report_sent_date != today:
                    logger.info("Data just became ready — generating daily report")
                    await send_daily_report()
            except Exception as e:
                logger.error(f"Data freshness check failed: {e}")

        # ─── Schedule all jobs ────────────────
        d_hour, d_minute = map(int, config.DAILY_REPORT_TIME.split(":"))
        self.scheduler.add_daily_report(
            callback=send_daily_report, hour=d_hour, minute=d_minute,
        )

        w_hour, w_minute = map(int, config.WEEKLY_REPORT_TIME.split(":"))
        self.scheduler.add_weekly_report(
            callback=send_weekly_report,
            day_of_week=0, hour=w_hour, minute=w_minute,
        )

        m_hour, m_minute = map(int, config.MONTHLY_REPORT_TIME.split(":"))
        self.scheduler.add_weekly_report(
            callback=check_and_send_monthly,
            day_of_week=0, hour=m_hour, minute=m_minute,
            job_id="monthly_check",
        )

        from apscheduler.triggers.cron import CronTrigger
        self.scheduler.scheduler.add_job(
            check_data_freshness,
            trigger=CronTrigger(
                minute="*/5", hour="6-12",
                timezone=self.scheduler.timezone,
            ),
            id="data_freshness_check",
            name="Data Freshness Check (every 5 min, 06:00–12:00)",
            replace_existing=True,
        )

        logger.info("Scheduler configured: daily/weekly/monthly/freshness")

    async def _send_html(self, user_id: int, html_text: str, keyboard=None) -> None:
        """Send HTML message, splitting into chunks if needed."""
        if len(html_text) <= 4000:
            await self.bot.send_message(
                chat_id=user_id, text=html_text,
                parse_mode="HTML", reply_markup=keyboard,
            )
        else:
            chunks = [html_text[i:i + 4000] for i in range(0, len(html_text), 4000)]
            for i, chunk in enumerate(chunks):
                kb = keyboard if i == len(chunks) - 1 else None
                await self.bot.send_message(
                    chat_id=user_id, text=chunk,
                    parse_mode="HTML", reply_markup=kb,
                )

    async def run(self) -> None:
        """Запуск бота"""
        self.scheduler.start()
        self._setup_scheduler()

        # Health check
        health = await self.zai_client.health_check()
        logger.info(f"z.ai health: {health}")

        # Clear any stale polling sessions to avoid ConflictError
        try:
            await self.bot.delete_webhook(drop_pending_updates=False)
            logger.info("Cleared previous webhook/polling session")
        except Exception as e:
            logger.warning(f"Failed to clear webhook: {e}")

        logger.info("Oleg Bot started!")

        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types(),
            )
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        logger.info("Shutting down Oleg Bot...")
        self.scheduler.shutdown()
        await self.bot.session.close()
        deleted = self.report_storage.cleanup_old_reports(config.REPORT_RETENTION_DAYS)
        logger.info(f"Cleaned up {deleted} old reports")
        logger.info("Shutdown complete")


def _acquire_pid_lock() -> Optional[Path]:
    """Acquire PID lock file. Returns lock path on success, None if another instance is running."""
    lock_path = Path(config.LOG_FILE).parent / "oleg_bot.pid"
    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            # Check if old process is still alive
            os.kill(old_pid, 0)
            # Process is alive — refuse to start
            return None
        except (ValueError, ProcessLookupError, PermissionError):
            # PID file is stale (process dead or invalid) — safe to overwrite
            pass

    lock_path.write_text(str(os.getpid()))
    return lock_path


def _release_pid_lock():
    """Remove PID lock file."""
    lock_path = Path(config.LOG_FILE).parent / "oleg_bot.pid"
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    """Entry point"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not config.ZAI_API_KEY:
        print("ERROR: ZAI_API_KEY not set in .env")
        sys.exit(1)

    lock = _acquire_pid_lock()
    if lock is None:
        print("ERROR: Another Oleg Bot instance is already running. Exiting.")
        logger.critical("Refused to start: another instance is already running (PID lock)")
        sys.exit(1)

    bot = OlegBot()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        _release_pid_lock()


if __name__ == "__main__":
    main()
