from __future__ import annotations
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
        auth_service=None,
    ):
        self.orchestrator = orchestrator
        self.pipeline = pipeline
        self.watchdog = watchdog
        self.state_store = state_store
        self.auth_service = auth_service

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

            # Auto-register user for notifications
            if self.auth_service and not self.auth_service.is_authenticated(user_id):
                self.auth_service.register_user(user_id)
                logger.info(f"Auto-registered user {user_id} for notifications")

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
                    "/report_daily — дневной финансовый отчёт\n"
                    "/report_weekly — недельный финансовый отчёт\n"
                    "/report_monthly — месячный финансовый отчёт\n"
                    "/marketing_daily — дневной маркетинговый отчёт\n"
                    "/marketing_weekly — недельный маркетинговый отчёт\n"
                    "/marketing_monthly — месячный маркетинговый отчёт\n"
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

            if text.startswith("/report_monthly"):
                await self._handle_report_monthly(message)
                return

            if text.startswith("/marketing_daily"):
                await self._handle_marketing_daily(message)
                return

            if text.startswith("/marketing_weekly"):
                await self._handle_marketing_weekly(message)
                return

            if text.startswith("/marketing_monthly"):
                await self._handle_marketing_monthly(message)
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

    async def _save_to_notion(self, result, request) -> str | None:
        """Save report to Notion, return page URL or None."""
        try:
            from agents.oleg.services.notion_service import NotionService
            notion = NotionService(
                token=config.NOTION_TOKEN,
                database_id=config.NOTION_DATABASE_ID,
            )
            if not notion.enabled:
                return None
            return await notion.sync_report(
                start_date=request.start_date if request else "",
                end_date=request.end_date if request else "",
                report_md=result.detailed_report or result.brief_summary,
                report_type=result.report_type.value if hasattr(result, 'report_type') else "Ежедневный фин анализ",
                chain_steps=result.chain_steps,
            )
        except Exception as e:
            logger.warning(f"Notion save failed (non-critical): {e}")
            return None

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

                page_url = await self._save_to_notion(result, request)

                parts = []
                if page_url:
                    parts.append(f'<a href="{page_url}">📊 Подробный отчёт в Notion</a>\n')
                if result.caveats:
                    parts.append(add_caveats_header("", result.caveats))
                parts.append(self._short_tg_body(result))
                parts.append(format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                ))
                text = "\n".join(parts)
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

                page_url = await self._save_to_notion(result, request)

                parts = []
                if page_url:
                    parts.append(f'<a href="{page_url}">📊 Подробный отчёт в Notion</a>\n')
                if result.caveats:
                    parts.append(add_caveats_header("", result.caveats))
                parts.append(self._short_tg_body(result))
                parts.append(format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                ))
                text = "\n".join(parts)
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Weekly report command error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    async def _handle_report_monthly(self, message) -> None:
        """Handle /report_monthly command."""
        if not self.pipeline:
            await message.answer("Pipeline не настроен.")
            return

        await message.answer("Генерирую месячный отчёт...")

        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_month_bounds_msk

        first, last = get_last_month_bounds_msk()
        request = ReportRequest(
            report_type=ReportType.MONTHLY,
            start_date=str(first),
            end_date=str(last),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                from agents.oleg.bot.formatter import (
                    split_html_message, format_cost_footer, add_caveats_header,
                )

                page_url = await self._save_to_notion(result, request)

                parts = []
                if page_url:
                    parts.append(f'<a href="{page_url}">📊 Подробный отчёт в Notion</a>\n')
                if result.caveats:
                    parts.append(add_caveats_header("", result.caveats))
                parts.append(self._short_tg_body(result))
                parts.append(format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                ))
                text = "\n".join(parts)
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Monthly report command error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    async def _handle_marketing_daily(self, message) -> None:
        """Handle /marketing_daily command."""
        if not self.pipeline:
            await message.answer("Pipeline не настроен.")
            return

        await message.answer("Генерирую дневной маркетинговый отчёт...")

        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_yesterday_msk

        yesterday = get_yesterday_msk()
        request = ReportRequest(
            report_type=ReportType.MARKETING_DAILY,
            start_date=str(yesterday),
            end_date=str(yesterday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                from agents.oleg.bot.formatter import (
                    split_html_message, format_cost_footer, add_caveats_header,
                )

                page_url = await self._save_to_notion(result, request)

                tg_body = self._short_tg_body(result)
                parts = []
                if page_url:
                    parts.append(f'<a href="{page_url}">📈 Подробный отчёт в Notion</a>\n')
                if result.caveats:
                    parts.append(add_caveats_header("", result.caveats))
                parts.append(tg_body)
                parts.append(format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                ))
                text = "\n".join(parts)
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Marketing daily report error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    async def _handle_marketing_weekly(self, message) -> None:
        """Handle /marketing_weekly command."""
        if not self.pipeline:
            await message.answer("Pipeline не настроен.")
            return

        await message.answer("Генерирую недельный маркетинговый отчёт...")

        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_week_bounds_msk

        monday, sunday = get_last_week_bounds_msk()
        request = ReportRequest(
            report_type=ReportType.MARKETING_WEEKLY,
            start_date=str(monday),
            end_date=str(sunday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                from agents.oleg.bot.formatter import (
                    split_html_message, format_cost_footer, add_caveats_header,
                )

                page_url = await self._save_to_notion(result, request)

                tg_body = self._short_tg_body(result)
                parts = []
                if page_url:
                    parts.append(f'<a href="{page_url}">📈 Подробный отчёт в Notion</a>\n')
                if result.caveats:
                    parts.append(add_caveats_header("", result.caveats))
                parts.append(tg_body)
                parts.append(format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                ))
                text = "\n".join(parts)
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Marketing weekly report error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    async def _handle_marketing_monthly(self, message) -> None:
        """Handle /marketing_monthly command."""
        if not self.pipeline:
            await message.answer("Pipeline не настроен.")
            return

        await message.answer("Генерирую месячный маркетинговый отчёт...")

        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_month_bounds_msk

        first, last = get_last_month_bounds_msk()
        request = ReportRequest(
            report_type=ReportType.MARKETING_MONTHLY,
            start_date=str(first),
            end_date=str(last),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                from agents.oleg.bot.formatter import (
                    split_html_message, format_cost_footer, add_caveats_header,
                )

                page_url = await self._save_to_notion(result, request)

                tg_body = self._short_tg_body(result)
                parts = []
                if page_url:
                    parts.append(f'<a href="{page_url}">📈 Подробный отчёт в Notion</a>\n')
                if result.caveats:
                    parts.append(add_caveats_header("", result.caveats))
                parts.append(tg_body)
                parts.append(format_cost_footer(
                    result.cost_usd, result.chain_steps, result.duration_ms,
                ))
                text = "\n".join(parts)
                for chunk in split_html_message(text):
                    await message.answer(chunk, parse_mode="HTML")
            else:
                await message.answer("Отчёт не сгенерирован: hard gates failed. Проверьте /health.")
        except Exception as e:
            logger.error(f"Marketing monthly report error: {e}", exc_info=True)
            await message.answer(f"Ошибка генерации отчёта: {e}")

    @staticmethod
    def _short_tg_body(result) -> str:
        """Extract short TG body from report result (max 1500 chars)."""
        tg = result.telegram_summary
        if tg and len(tg) <= 1500:
            return tg
        return result.brief_summary[:500]

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
