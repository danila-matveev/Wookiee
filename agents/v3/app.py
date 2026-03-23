"""Wookiee v3 — Main application entry point.

Usage:
    python -m agents.v3              # normal start
    python -m agents.v3 --dry-run   # list jobs and exit
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from agents.v3 import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configure_logging(level: str = "INFO") -> None:
    """Configure root logger with timestamps and level."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Quieten noisy third-party loggers
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _print_jobs(scheduler) -> None:
    """Print all scheduled jobs to stdout (dry-run mode)."""
    jobs = scheduler.get_jobs()
    print(f"\nWookiee v3 scheduler — {len(jobs)} job(s) configured:\n")
    for job in jobs:
        print(f"  [{job.id:40s}]  next_run={job.next_run_time}  trigger={job.trigger}")
    print()


# ---------------------------------------------------------------------------
# Main async run loop
# ---------------------------------------------------------------------------

async def run(dry_run: bool = False) -> None:
    """Start the Wookiee v3 agent system.

    Args:
        dry_run: If True, list all scheduled jobs and exit without running.
    """
    _configure_logging(config.LOG_LEVEL)
    logger.info("Wookiee v3 starting up...")

    # ── Build scheduler ─────────────────────────────────────────────────────
    from agents.v3.scheduler import create_scheduler
    scheduler = create_scheduler()

    if dry_run:
        _print_jobs(scheduler)
        logger.info("Dry-run mode — exiting.")
        return

    # ── Start scheduler ──────────────────────────────────────────────────────
    scheduler.start()
    logger.info("Scheduler started.")

    # ── Graceful shutdown handling ────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal(signum, frame):  # noqa: ARG001
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — initiating graceful shutdown...", sig_name)
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _on_signal)

    # ── Start Telegram bot polling (if token configured) ──────────────────────
    bot_task: asyncio.Task | None = None
    if config.TELEGRAM_BOT_TOKEN:
        bot_task = asyncio.create_task(_run_bot_polling(stop_event), name="bot_polling")
        logger.info("Telegram bot polling started.")
    else:
        logger.info("TELEGRAM_BOT_TOKEN not set — running without bot polling.")

    # ── Keep alive ────────────────────────────────────────────────────────────
    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down...")

        if bot_task is not None and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass

        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")

        logger.info("Wookiee v3 shutdown complete.")


async def _run_bot_polling(stop_event: asyncio.Event) -> None:
    """Run aiogram bot polling until stop_event is set."""
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()

        # Register handlers (to be expanded in later tasks)
        _register_handlers(dp)

        logger.info("Bot polling initialised.")

        async def _poll():
            await dp.start_polling(bot, handle_signals=False)

        poll_task = asyncio.create_task(_poll(), name="bot_poll_inner")
        await stop_event.wait()
        await dp.stop_polling()
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
    except Exception as exc:
        logger.exception("Bot polling error: %s", exc)


def _register_handlers(dp) -> None:  # noqa: ANN001
    """Register Telegram command handlers on the dispatcher."""
    from aiogram import types
    from aiogram.filters import Command

    from agents.v3 import orchestrator, monitor
    from agents.v3.scheduler import _yesterday_msk, _last_week_msk, _last_month_msk, _day_before

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message) -> None:
        await message.answer(
            "Wookiee v3 — аналитический агент.\n\n"
            "Команды:\n"
            "/report_daily — дневной финансовый отчёт\n"
            "/report_weekly — недельный финансовый отчёт\n"
            "/report_monthly — месячный финансовый отчёт\n"
            "/marketing_daily — дневной маркетинговый отчёт\n"
            "/marketing_weekly — недельный маркетинговый отчёт\n"
            "/marketing_monthly — месячный маркетинговый отчёт\n"
            "/health — проверка здоровья системы\n"
            "/feedback — отправить ОС по отчёту\n"
            "/ping — проверка связи"
        )

    @dp.message(Command("ping"))
    async def cmd_ping(message: types.Message) -> None:
        await message.answer("pong")

    @dp.message(Command("health"))
    async def cmd_health(message: types.Message) -> None:
        llm_ok = await monitor._check_llm()
        db_ok = await monitor._check_db()
        last_run_ok = await monitor._check_last_run()
        status = "✅" if all([llm_ok, db_ok, last_run_ok]) else "⚠️"
        await message.answer(
            f"{status} Wookiee v3 Health\n\n"
            f"LLM API: {'✅' if llm_ok else '❌'}\n"
            f"Database: {'✅' if db_ok else '❌'}\n"
            f"Last run: {'✅' if last_run_ok else '❌'}"
        )

    @dp.message(Command("report_daily"))
    async def cmd_report_daily(message: types.Message) -> None:
        await message.answer("⏳ Запускаю дневной отчёт...")
        date_to = _yesterday_msk()
        date_from = date_to
        comparison_to = _day_before(date_to)
        comparison_from = comparison_to
        result = await orchestrator.run_daily_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comparison_from, comparison_to=comparison_to,
            trigger="telegram_manual",
        )
        status = result.get("status", "unknown")
        await message.answer(f"Дневной отчёт: {status}")

    @dp.message(Command("report_weekly"))
    async def cmd_report_weekly(message: types.Message) -> None:
        await message.answer("⏳ Запускаю недельный отчёт...")
        date_from, date_to = _last_week_msk()
        comparison_to = _day_before(date_from)
        from datetime import datetime, timedelta
        comparison_from = (
            datetime.strptime(comparison_to, "%Y-%m-%d") - timedelta(days=6)
        ).strftime("%Y-%m-%d")
        result = await orchestrator.run_weekly_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comparison_from, comparison_to=comparison_to,
            trigger="telegram_manual",
        )
        status = result.get("status", "unknown")
        await message.answer(f"Недельный отчёт: {status}")

    @dp.message(Command("report_monthly"))
    async def cmd_report_monthly(message: types.Message) -> None:
        await message.answer("⏳ Запускаю месячный отчёт...")
        date_from, date_to = _last_month_msk()
        from datetime import date as date_cls
        prev_year_start = date_cls.fromisoformat(date_from).replace(
            year=date_cls.fromisoformat(date_from).year - 1
        )
        prev_year_end = date_cls.fromisoformat(date_to).replace(
            year=date_cls.fromisoformat(date_to).year - 1
        )
        result = await orchestrator.run_monthly_report(
            date_from=date_from, date_to=date_to,
            comparison_from=str(prev_year_start), comparison_to=str(prev_year_end),
            trigger="telegram_manual",
        )
        status = result.get("status", "unknown")
        await message.answer(f"Месячный отчёт: {status}")

    @dp.message(Command("marketing_daily"))
    async def cmd_marketing_daily(message: types.Message) -> None:
        await message.answer("⏳ Запускаю дневной маркетинговый отчёт...")
        date_to = _yesterday_msk()
        date_from = date_to
        comparison_to = _day_before(date_to)
        comparison_from = comparison_to
        result = await orchestrator.run_marketing_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comparison_from, comparison_to=comparison_to,
            report_period="daily", trigger="telegram_manual",
        )
        status = result.get("status", "unknown")
        await message.answer(f"Маркетинговый отчёт (daily): {status}")

    @dp.message(Command("marketing_weekly"))
    async def cmd_marketing_weekly(message: types.Message) -> None:
        await message.answer("⏳ Запускаю недельный маркетинговый отчёт...")
        date_from, date_to = _last_week_msk()
        comparison_to = _day_before(date_from)
        from datetime import datetime, timedelta
        comparison_from = (
            datetime.strptime(comparison_to, "%Y-%m-%d") - timedelta(days=6)
        ).strftime("%Y-%m-%d")
        result = await orchestrator.run_marketing_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comparison_from, comparison_to=comparison_to,
            report_period="weekly", trigger="telegram_manual",
        )
        status = result.get("status", "unknown")
        await message.answer(f"Маркетинговый отчёт (weekly): {status}")

    @dp.message(Command("marketing_monthly"))
    async def cmd_marketing_monthly(message: types.Message) -> None:
        await message.answer("⏳ Запускаю месячный маркетинговый отчёт...")
        date_from, date_to = _last_month_msk()
        from datetime import date as date_cls
        prev_year_start = date_cls.fromisoformat(date_from).replace(
            year=date_cls.fromisoformat(date_from).year - 1
        )
        prev_year_end = date_cls.fromisoformat(date_to).replace(
            year=date_cls.fromisoformat(date_to).year - 1
        )
        result = await orchestrator.run_marketing_report(
            date_from=date_from, date_to=date_to,
            comparison_from=str(prev_year_start), comparison_to=str(prev_year_end),
            report_period="monthly", trigger="telegram_manual",
        )
        status = result.get("status", "unknown")
        await message.answer(f"Маркетинговый отчёт (monthly): {status}")

    @dp.message(Command("feedback"))
    async def cmd_feedback(message: types.Message) -> None:
        text = (message.text or "").replace("/feedback", "", 1).strip()
        if not text:
            await message.answer("Использование: /feedback <текст обратной связи>")
            return
        try:
            from agents.v3.state import StateStore
            state = StateStore(config.STATE_DB_PATH)
            state.set(f"feedback:{message.date.isoformat()}", text)
            await message.answer("✅ Обратная связь сохранена. Спасибо!")
        except Exception as exc:
            logger.error("Failed to save feedback: %s", exc)
            await message.answer("❌ Не удалось сохранить ОС. Попробуйте позже.")

    @dp.message()
    async def cmd_free_text(message: types.Message) -> None:
        """Handle free-text messages — route through data-navigator agent."""
        text = (message.text or "").strip()
        if not text:
            return
        await message.answer("⏳ Обрабатываю запрос...")
        try:
            from agents.v3.runner import run_agent
            result = await run_agent(
                agent_name="data-navigator",
                task=text,
                trigger="telegram_free_text",
                task_type="ad_hoc_query",
            )
            output = result.get("raw_output", "Нет ответа")
            # Telegram limit is 4096 chars
            if len(output) > 4000:
                output = output[:4000] + "..."
            await message.answer(output)
        except Exception as exc:
            logger.error("Free text handler failed: %s", exc)
            await message.answer("❌ Ошибка при обработке запроса.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run the application."""
    parser = argparse.ArgumentParser(
        prog="python -m agents.v3",
        description="Wookiee v3 — analytics agent system",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List all scheduled jobs and exit without running.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(dry_run=args.dry_run))
    except KeyboardInterrupt:
        pass
