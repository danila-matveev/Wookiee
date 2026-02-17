"""
Oleg Bot — Telegram UI + delivery poller.

Отвечает за:
- Telegram polling (авторизация, меню, интерактивные запросы)
- Доставка отчётов из delivery_queue (агент кладёт, бот отправляет)

Генерацией отчётов по расписанию занимается agent_runner.py.

Точка входа: python -m agents.oleg [bot]
"""
import asyncio
import logging
import os
import sys
import time
from typing import Optional
from pathlib import Path

import psycopg2

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup

from agents.oleg import config
from agents.oleg.services.auth_service import AuthService
from shared.clients.openrouter_client import OpenRouterClient
from agents.oleg.services.oleg_agent import OlegAgent
from agents.oleg.services.report_storage import ReportStorage
from agents.oleg.services.feedback_service import FeedbackService
from agents.oleg.services.notion_service import NotionService
from agents.oleg.services.scheduler_service import SchedulerService
from agents.oleg.services.data_freshness_service import DataFreshnessService

from agents.oleg.services.price_analysis.learning_store import LearningStore
from agents.oleg.services.price_tools import set_learning_store

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
    """Telegram-бот Олега — UI + доставка отчётов из delivery_queue."""

    def __init__(self):
        logger.info("Initializing Oleg Bot (UI + delivery mode)...")

        # Bot & Dispatcher
        self.bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher(storage=MemoryStorage())

        # Services (needed for on-demand interactive queries)
        self.auth_service = AuthService(
            config.HASHED_PASSWORD,
            persistence_path=config.USERS_FILE_PATH,
        )
        self.llm_client = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model=config.ANALYTICS_MODEL,
            fallback_model=config.FALLBACK_MODEL,
        )
        logger.info(f"LLM: OpenRouter (main={config.ANALYTICS_MODEL}, classify={config.CLASSIFY_MODEL})")
        self.oleg_agent = OlegAgent(
            zai_client=self.llm_client,
            playbook_path=config.PLAYBOOK_PATH,
            model=config.ANALYTICS_MODEL,
        )
        # LLM-based query understanding (uses LIGHT model)
        from agents.oleg.services.query_understanding import QueryUnderstandingService
        self.query_understanding = QueryUnderstandingService(
            zai_client=self.llm_client,
            model=config.CLASSIFY_MODEL,
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

        # Price analysis: learning store (needed for on-demand price tools)
        self.learning_store = LearningStore(config.SQLITE_DB_PATH)
        set_learning_store(self.learning_store)
        logger.info("LearningStore initialized and injected into price_tools")

        # Register middleware & routers
        self._setup_middleware()
        self._register_routers()

        logger.info("Oleg Bot initialized (UI + delivery mode)")

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
            data['data_freshness'] = self.data_freshness
            return await handler(event, data)

        @self.dp.callback_query.middleware()
        async def inject_services_callback(handler, event, data):
            data['auth_service'] = self.auth_service
            data['oleg_agent'] = self.oleg_agent
            data['report_storage'] = self.report_storage
            data['feedback_service'] = self.feedback_service
            data['notion_service'] = self.notion_service
            data['query_understanding'] = self.query_understanding
            data['data_freshness'] = self.data_freshness
            return await handler(event, data)

    def _register_routers(self) -> None:
        """Регистрация роутеров"""
        self.dp.include_router(auth.router)
        self.dp.include_router(menu.router)
        self.dp.include_router(scheduled_reports.router)
        self.dp.include_router(custom_queries.router)

        logger.info("Routers registered")

    # ── Delivery poller ──────────────────────────────────────

    def _setup_delivery_poller(self) -> None:
        """Poll delivery_queue every 30s and send to Telegram."""
        from apscheduler.triggers.interval import IntervalTrigger

        async def poll_delivery_queue():
            try:
                pending = self.report_storage.get_pending_deliveries()
                if not pending:
                    return

                logger.info(f"Delivery poller: {len(pending)} pending messages")
                for item in pending:
                    try:
                        keyboard = None
                        if item.get('keyboard_json'):
                            keyboard = InlineKeyboardMarkup.model_validate_json(
                                item['keyboard_json']
                            )
                        await self._send_html(
                            item['user_id'], item['html_text'], keyboard,
                        )
                        self.report_storage.mark_delivered(item['id'])
                        logger.info(
                            f"Delivered queue_id={item['id']} "
                            f"to user {item['user_id']}"
                        )
                    except Exception as e:
                        self.report_storage.mark_delivery_failed(
                            item['id'], str(e),
                        )
                        logger.error(
                            f"Delivery failed queue_id={item['id']}: {e}"
                        )
            except Exception as e:
                logger.error(f"Delivery poller error: {e}")

        self.scheduler.scheduler.add_job(
            poll_delivery_queue,
            trigger=IntervalTrigger(seconds=30),
            id="delivery_poller",
            name="Delivery Queue Poller (every 30s)",
            replace_existing=True,
        )
        logger.info("Delivery poller configured (every 30s)")

    # ── Send HTML ────────────────────────────────────────────

    async def _send_html(self, user_id: int, html_text: str, keyboard=None) -> None:
        """Send HTML message, splitting by paragraphs if needed."""
        MAX_LEN = 4000
        if len(html_text) <= MAX_LEN:
            await self.bot.send_message(
                chat_id=user_id, text=html_text,
                parse_mode="HTML", reply_markup=keyboard,
            )
        else:
            # Split by paragraph breaks to avoid cutting HTML tags
            paragraphs = html_text.split('\n\n')
            chunks = []
            current = ""
            for p in paragraphs:
                if len(current) + len(p) + 2 > MAX_LEN:
                    if current:
                        chunks.append(current)
                    current = p[:MAX_LEN]  # safety trim
                else:
                    current = current + "\n\n" + p if current else p
            if current:
                chunks.append(current)

            for i, chunk in enumerate(chunks):
                kb = keyboard if i == len(chunks) - 1 else None
                await self.bot.send_message(
                    chat_id=user_id, text=chunk,
                    parse_mode="HTML", reply_markup=kb,
                )

    # ── Preflight checks ────────────────────────────────────

    async def _preflight_checks(self) -> bool:
        """Pre-flight проверки: LLM + PostgreSQL + Telegram."""
        all_ok = True

        # 1. LLM API (OpenRouter)
        try:
            health = await self.llm_client.health_check()
            if health:
                logger.info("Pre-flight: LLM API — OK")
            else:
                logger.error("Pre-flight: LLM API — FAIL (health=False)")
                all_ok = False
        except Exception as e:
            logger.error(f"Pre-flight: LLM API — FAIL ({e})")
            all_ok = False

        # 2. PostgreSQL WB
        try:
            conn = psycopg2.connect(
                host=config.DB_HOST, port=config.DB_PORT,
                user=config.DB_USER, password=config.DB_PASSWORD,
                database=config.DB_NAME_WB, connect_timeout=10,
            )
            conn.cursor().execute("SELECT 1")
            conn.close()
            logger.info("Pre-flight: PostgreSQL WB — OK")
        except Exception as e:
            logger.error(f"Pre-flight: PostgreSQL WB — FAIL ({e})")
            all_ok = False

        # 3. PostgreSQL OZON
        try:
            conn = psycopg2.connect(
                host=config.DB_HOST, port=config.DB_PORT,
                user=config.DB_USER, password=config.DB_PASSWORD,
                database=config.DB_NAME_OZON, connect_timeout=10,
            )
            conn.cursor().execute("SELECT 1")
            conn.close()
            logger.info("Pre-flight: PostgreSQL OZON — OK")
        except Exception as e:
            logger.error(f"Pre-flight: PostgreSQL OZON — FAIL ({e})")
            all_ok = False

        # 4. Telegram Bot API
        try:
            me = await self.bot.get_me()
            logger.info(f"Pre-flight: Telegram Bot API — OK (@{me.username})")
        except Exception as e:
            logger.error(f"Pre-flight: Telegram Bot API — FAIL ({e})")
            all_ok = False

        # 5. Notion (non-critical)
        if config.NOTION_TOKEN:
            logger.info("Pre-flight: Notion token — present")

        return all_ok

    # ── Run ──────────────────────────────────────────────────

    async def run(self) -> None:
        """Запуск бота (UI + delivery poller)."""
        preflight_ok = await self._preflight_checks()
        if not preflight_ok:
            logger.critical("Pre-flight checks FAILED — бот не может стартовать")
            sys.exit(1)

        self.scheduler.start()
        self._setup_delivery_poller()

        # Clear any stale polling sessions to avoid ConflictError
        try:
            await self.bot.delete_webhook(drop_pending_updates=False)
            logger.info("Cleared previous webhook/polling session")
        except Exception as e:
            logger.warning(f"Failed to clear webhook: {e}")

        logger.info("Oleg Bot started (UI + delivery mode)!")

        try:
            await self._start_polling_with_conflict_timeout()
        finally:
            await self.shutdown()

    async def _start_polling_with_conflict_timeout(
        self, conflict_timeout: int = 60,
    ) -> None:
        """
        Запускает polling с таймаутом на TelegramConflictError.

        Если ConflictError не разрешается за conflict_timeout секунд,
        бот завершается с exit(1). Docker restart policy перезапустит.
        """
        conflict_first_seen: Optional[float] = None
        shutdown_requested = asyncio.Event()

        async def monitor_conflict():
            nonlocal conflict_first_seen
            while not shutdown_requested.is_set():
                if conflict_first_seen is not None:
                    elapsed = time.time() - conflict_first_seen
                    if elapsed > conflict_timeout:
                        logger.critical(
                            f"TelegramConflictError persisted for {elapsed:.0f}s "
                            f"— exiting. Another bot instance is likely running."
                        )
                        os._exit(1)
                await asyncio.sleep(5)

        # Intercept ConflictError via aiogram's error handler
        from aiogram.types import ErrorEvent
        from aiogram.exceptions import TelegramConflictError

        @self.dp.errors()
        async def on_polling_error(event: ErrorEvent):
            nonlocal conflict_first_seen
            if isinstance(event.exception, TelegramConflictError):
                if conflict_first_seen is None:
                    conflict_first_seen = time.time()
                    logger.warning(
                        f"TelegramConflictError detected. "
                        f"Will exit if not resolved in {conflict_timeout}s"
                    )
            else:
                # Reset timer on non-conflict errors (polling is alive)
                conflict_first_seen = None

        monitor_task = asyncio.create_task(monitor_conflict())

        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types(),
            )
        finally:
            shutdown_requested.set()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

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

    if not config.OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
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
