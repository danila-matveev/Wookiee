"""
Telegram Bot — aiogram setup, middleware, direct delivery.

Single process: bot receives messages → orchestrator processes → bot.send_message().
No delivery queue, no polling.
"""
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage

from agents.oleg import config

logger = logging.getLogger(__name__)


class OlegTelegramBot:
    """Telegram bot for Oleg v2."""

    def __init__(
        self,
        orchestrator=None,
        pipeline=None,
        watchdog=None,
        state_store=None,
    ):
        self.orchestrator = orchestrator
        self.pipeline = pipeline
        self.watchdog = watchdog
        self.state_store = state_store

        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None

    async def setup(self) -> None:
        """Initialize bot and handlers."""
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not set")
            return

        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        storage = MemoryStorage()
        self.dp = Dispatcher(storage=storage)

        # Register handlers
        self._register_handlers()

        logger.info("Telegram bot initialized")

    def _register_handlers(self) -> None:
        """Register message handlers."""
        router = Router()

        @router.message()
        async def handle_message(message):
            """Handle all incoming messages."""
            if not message.text:
                return

            user_id = message.from_user.id
            text = message.text.strip()

            # Simple routing
            if text.startswith("/start"):
                await message.answer(
                    "Привет! Я Олег v2, финансовый AI-аналитик Wookiee.\n"
                    "Задайте вопрос или используйте /help."
                )
                return

            if text.startswith("/help"):
                await message.answer(
                    "Доступные команды:\n"
                    "/report_daily — дневной отчёт\n"
                    "/report_weekly — недельный отчёт\n"
                    "/feedback — отправить ОС по отчёту\n"
                    "/health — проверка здоровья системы\n"
                    "Или просто задайте вопрос."
                )
                return

            if text.startswith("/report_daily"):
                await self._handle_report_daily(message)
                return

            if text.startswith("/report_weekly"):
                await self._handle_report_weekly(message)
                return

            if text.startswith("/health"):
                if self.watchdog:
                    health = await self.watchdog.check_health()
                    status = "✅ Здоров" if health["healthy"] else "❌ Проблемы"
                    details = "\n".join(
                        f"  {c['status']}: {c['component']}"
                        for c in health["checks"]
                    )
                    await message.answer(f"{status}\n{details}")
                else:
                    await message.answer("Watchdog не настроен.")
                return

            # For all other messages — route through orchestrator
            if self.orchestrator:
                await message.answer("Анализирую...")
                try:
                    from agents.oleg.orchestrator.chain import ChainResult
                    result = await self.orchestrator.run_chain(
                        task=text,
                        task_type="query",
                    )

                    from agents.oleg.bot.formatter import (
                        split_html_message, format_cost_footer,
                    )
                    response = result.summary
                    response += format_cost_footer(
                        result.total_cost,
                        result.total_steps,
                        result.total_duration_ms,
                    )

                    for chunk in split_html_message(response):
                        await message.answer(chunk, parse_mode="HTML")

                except Exception as e:
                    logger.error(f"Query processing error: {e}", exc_info=True)
                    await message.answer(f"Ошибка: {e}")
            else:
                await message.answer("Оркестратор не настроен.")

        self.dp.include_router(router)

    async def start_polling(self) -> None:
        """Start polling for messages."""
        if self.dp and self.bot:
            logger.info("Starting Telegram polling...")
            await self.dp.start_polling(self.bot)

    async def stop(self) -> None:
        """Stop the bot."""
        if self.bot:
            await self.bot.session.close()
            logger.info("Telegram bot stopped")

    async def _handle_report_daily(self, message) -> None:
        """Handle /report_daily command."""
        if not self.pipeline:
            await message.answer("Pipeline не настроен.")
            return

        await message.answer("Генерирую дневной отчёт...")

        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_yesterday_msk

        yesterday = get_yesterday_msk()
        request = ReportRequest(
            report_type=ReportType.DAILY,
            start_date=str(yesterday),
            end_date=str(yesterday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                from agents.oleg.bot.formatter import (
                    split_html_message, format_cost_footer, add_caveats_header,
                )
                text = result.brief_summary
                if result.caveats:
                    text = add_caveats_header(text, result.caveats)
                text += format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                )
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Daily report command error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    async def _handle_report_weekly(self, message) -> None:
        """Handle /report_weekly command."""
        if not self.pipeline:
            await message.answer("Pipeline не настроен.")
            return

        await message.answer("Генерирую недельный отчёт...")

        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_week_bounds_msk

        monday, sunday = get_last_week_bounds_msk()
        request = ReportRequest(
            report_type=ReportType.WEEKLY,
            start_date=str(monday),
            end_date=str(sunday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                from agents.oleg.bot.formatter import (
                    split_html_message, format_cost_footer, add_caveats_header,
                )
                text = result.brief_summary
                if result.caveats:
                    text = add_caveats_header(text, result.caveats)
                text += format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                )
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Weekly report command error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        """Send a message directly (for scheduled reports)."""
        if self.bot:
            from agents.oleg.bot.formatter import split_html_message
            for chunk in split_html_message(text):
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=kwargs.get("parse_mode", "HTML"),
                )
