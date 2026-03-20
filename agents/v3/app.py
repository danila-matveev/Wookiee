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
    """Register Telegram command handlers on the dispatcher.

    Handlers for /report, /status etc. will be added in later tasks.
    This stub keeps the dispatcher from crashing on startup.
    """
    from aiogram import types
    from aiogram.filters import Command

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message) -> None:
        await message.answer(
            "Wookiee v3 — аналитический агент.\n"
            "Команды появятся в следующих версиях."
        )

    @dp.message(Command("ping"))
    async def cmd_ping(message: types.Message) -> None:
        await message.answer("pong")


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
