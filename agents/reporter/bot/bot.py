# agents/reporter/bot/bot.py
"""Telegram bot setup — aiogram 3.x polling."""
from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher

from agents.reporter.bot.handlers import register_handlers
from agents.reporter.config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


async def start_bot(state, gate_checker) -> None:
    """Start bot polling. Blocks until stopped."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("REPORTER_V4_BOT_TOKEN not set, bot disabled")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    register_handlers(dp, state, gate_checker)

    logger.info("Starting Reporter V4 Telegram bot")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
