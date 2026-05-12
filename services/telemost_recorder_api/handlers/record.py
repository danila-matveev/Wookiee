"""/record <url> — auth, validate, enqueue with concurrent-recording uniqueness."""
from __future__ import annotations

import asyncio
import logging

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.bitrix_calendar import enrich_meeting_from_bitrix
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.handlers._format import status_emoji
from services.telemost_recorder_api.telegram_client import tg_send_message
from services.telemost_recorder_api.url_canon import (
    canonicalize_telemost_url,
    is_valid_telemost_url,
)

logger = logging.getLogger(__name__)


def _log_enrichment_failure(task: asyncio.Task) -> None:
    exc = task.exception()
    if exc is not None:
        logger.warning("Bitrix enrichment task failed: %s", exc, exc_info=exc)


_USAGE = (
    "📎 *Использование:* `/record <ссылка>`\n\n"
    "Пример: `/record https://telemost.yandex.ru/j/abc-def-ghi`\n\n"
    "💡 Можешь просто прислать ссылку без команды."
)
_BAD_URL = (
    "🤔 Это не похоже на ссылку Я.Телемоста.\n\n"
    "Жду формат:\n"
    "• `https://telemost.yandex.ru/j/<id>`\n"
    "• `https://telemost.360.yandex.ru/j/<id>`"
)
_NOT_AUTHED = "🔒 Сначала /start — нужно проверить доступ."

_ACK = (
    "✅ *Принял ссылку*\n\n"
    "🚀 Иду на встречу — зайду через ~30 сек как «Wookiee Recorder».\n\n"
    "⏱ После завершения через ~5 мин получишь:\n"
    "• Summary с темами, решениями и задачами\n"
    "• Полный transcript как `.txt` файл"
)


def _duplicate_message(status: str) -> str:
    return (
        "ℹ️ *Эта встреча уже в работе*\n\n"
        "Кто-то (возможно ты) уже поставил её на запись. "
        "Пришлю summary тому, кто её поставил.\n\n"
        f"Статус: {status_emoji(status)} `{status}`"
    )


async def handle_record(chat_id: int, user_id: int, args: str) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, _NOT_AUTHED)
        return

    args = args.strip()
    if not args:
        await tg_send_message(chat_id, _USAGE)
        return

    raw_url = args.split()[0]
    if not is_valid_telemost_url(raw_url):
        await tg_send_message(chat_id, _BAD_URL)
        return

    canonical = canonicalize_telemost_url(raw_url)
    pool = await get_pool()
    async with pool.acquire() as conn:
        new_id = await conn.fetchval(
            """
            INSERT INTO telemost.meetings
                (source, triggered_by, meeting_url, organizer_id, invitees, status)
            VALUES ('telegram', $1, $2, $1, '[]'::jsonb, 'queued')
            ON CONFLICT (meeting_url)
                WHERE status IN ('queued','recording','postprocessing')
            DO NOTHING
            RETURNING id
            """,
            user_id,
            canonical,
        )
        if new_id is None:
            existing = await conn.fetchrow(
                """
                SELECT id, status FROM telemost.meetings
                WHERE meeting_url = $1
                  AND status IN ('queued','recording','postprocessing')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                canonical,
            )
            if existing is not None:
                await tg_send_message(chat_id, _duplicate_message(existing["status"]))
                return
            await tg_send_message(
                chat_id,
                "⚠️ Не удалось поставить запись в очередь. Попробуй ещё раз через минуту.",
            )
            return

    await tg_send_message(chat_id, _ACK)
    logger.info(
        "Enqueued meeting %s by user %d for url %s",
        new_id,
        user_id,
        canonical,
    )

    # Fire-and-forget Bitrix calendar enrichment: fills title + invitees from
    # the matching calendar event so the final DM shows the real subject and
    # participants instead of "(без названия)" + Speaker 0/1/2.
    bitrix_id = user.get("bitrix_id")
    if bitrix_id:
        enrichment_task = asyncio.create_task(
            enrich_meeting_from_bitrix(
                meeting_id=new_id,
                meeting_url=canonical,
                triggered_by_bitrix_id=str(bitrix_id),
            )
        )
        enrichment_task.add_done_callback(_log_enrichment_failure)
