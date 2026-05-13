"""/record <url> — auth, validate, enqueue with concurrent-recording uniqueness."""
from __future__ import annotations

import asyncio
import json
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
    """Surface Bitrix enrichment failures to the operator.

    Pre-fix the callback logged WARNING — invisible to the global
    TelegramAlertHandler (level=ERROR). Now we use logger.error with
    exc_info so failures actually reach @wookiee_alerts_bot, and the
    operator hears about a broken Bitrix integration instead of
    discovering it via users receiving empty-title meetings.
    """
    exc = task.exception()
    if exc is not None:
        logger.error(
            "Bitrix enrichment task failed: %s", exc, exc_info=exc
        )


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

_INSTANT_ACK = "⏳ Получил, проверяю…"

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

    # Immediate ack BEFORE the DB transaction (advisory lock + INSERT) and
    # the fire-and-forget Bitrix enrichment. Telegram itself can take
    # 100-300 ms to deliver; users panic if they see nothing back for a
    # full second after pasting the link.
    await tg_send_message(chat_id, _INSTANT_ACK)

    canonical = canonicalize_telemost_url(raw_url)
    # Seed invitees with the triggering user so the LLM has at least one real
    # name to attribute "Speaker N" against. Bitrix enrichment (fire-and-forget
    # below) overwrites this with the full calendar attendee list when the
    # meeting URL matches a Bitrix calendar event.
    seed_invitees = json.dumps([{
        "telegram_id": user["telegram_id"],
        "name": user["name"],
        "bitrix_id": user.get("bitrix_id"),
    }], ensure_ascii=False)
    pool = await get_pool()
    existing = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Telegram retries POST on 5xx, so two webhooks can hit this handler
            # within milliseconds for the same URL. The partial unique index on
            # meeting_url (WHERE status IN ('queued','recording','postprocessing'))
            # does not block parallel inserts of two different rows before either
            # is committed — gap allows ON CONFLICT DO NOTHING to succeed twice
            # and spawn two recorder containers.
            #
            # pg_advisory_xact_lock serializes on the URL hash for the duration
            # of this transaction; the second webhook waits, then sees the
            # already-inserted row via the SELECT below and exits cleanly.
            # Using the *xact* variant (auto-released on COMMIT/ROLLBACK) avoids
            # any chance of leaking session-level locks when a connection is
            # returned to the pool.
            #
            # IMPORTANT: keep ONLY DB operations inside the transaction.
            # tg_send_message is an HTTP call to Telegram (hundreds of ms — seconds);
            # awaiting it here would hold both the pool connection and the
            # advisory lock, throttling parallel webhooks. We collect the
            # decision (new vs duplicate vs failed) into locals, then send the
            # message after exiting the transaction.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                canonical,
            )
            new_id = await conn.fetchval(
                """
                INSERT INTO telemost.meetings
                    (source, triggered_by, meeting_url, organizer_id, invitees, status)
                VALUES ('telegram', $1, $2, $1, $3::jsonb, 'queued')
                ON CONFLICT (meeting_url)
                    WHERE status IN ('queued','recording','postprocessing')
                DO NOTHING
                RETURNING id
                """,
                user_id,
                canonical,
                seed_invitees,
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

    # Outside the transaction: pool connection returned, advisory lock released.
    # Now it's safe to do slow HTTP calls without throttling parallel webhooks.
    if new_id is None:
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
