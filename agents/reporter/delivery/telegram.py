# agents/reporter/delivery/telegram.py
"""Telegram delivery — send or edit message."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot

from agents.reporter.config import ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN
from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


async def send_or_edit_telegram(
    html: str,
    scope: ReportScope,
    state: ReporterState,
    notion_url: str | None = None,
) -> int | None:
    """Send new message or edit existing for this scope. Returns message_id."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return None

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        existing_msg_id = state.get_telegram_message_id(scope)

        if existing_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=existing_msg_id,
                    text=html,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                logger.info("Telegram message edited: %d", existing_msg_id)
                return existing_msg_id
            except Exception as e:
                logger.warning("Edit failed, sending new: %s", e)

        msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=html,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info("Telegram message sent: %d", msg.message_id)
        return msg.message_id

    except Exception as e:
        logger.error("Telegram delivery failed: %s", e)
        return None
    finally:
        await bot.session.close()


async def send_error_notification(
    scope: ReportScope,
    issues: list[str],
    state: ReporterState,
) -> None:
    """Send error notification — max 1 per report type per day."""
    from datetime import date

    key = f"error:{scope.report_type.value}:{date.today().isoformat()}"
    if state.was_notified(key):
        return  # Already notified today

    if not TELEGRAM_BOT_TOKEN:
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        text = (
            f"⚠️ <b>Ошибка: {scope.report_type.human_name}</b>\n"
            f"Период: {scope.period_str}\n\n"
            + "\n".join(f"• {i}" for i in issues[:5])
        )
        msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML"
        )
        state.mark_notified(key, telegram_message_id=msg.message_id)
    except Exception as e:
        logger.error("Error notification failed: %s", e)
    finally:
        await bot.session.close()


async def send_data_ready_notification(
    marketplace: str,
    state: ReporterState,
) -> None:
    """Send data-ready notification — max 1 per marketplace per day."""
    from datetime import date

    key = f"data_ready:{marketplace}:{date.today().isoformat()}"
    if state.was_notified(key):
        return

    if not TELEGRAM_BOT_TOKEN:
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ Данные {marketplace.upper()} готовы, начинаю генерацию отчётов",
        )
        state.mark_notified(key)
    except Exception as e:
        logger.error("Data-ready notification failed: %s", e)
    finally:
        await bot.session.close()
