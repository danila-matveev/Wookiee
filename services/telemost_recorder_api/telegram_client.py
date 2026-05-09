"""Thin httpx wrapper around Telegram Bot API.

Raises ``TelegramAPIError`` on non-ok responses. Handles message chunking
(4096 char limit -> 4000 to leave room for the (n/m) prefix) and multipart
document upload.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from services.telemost_recorder_api.config import TELEMOST_BOT_TOKEN

logger = logging.getLogger(__name__)

_BASE_URL = f"https://api.telegram.org/bot{TELEMOST_BOT_TOKEN}"
_CHUNK_SIZE = 4000  # 4096 - prefix headroom


class TelegramAPIError(RuntimeError):
    """Raised when Telegram API returns ok=false."""


async def tg_call(method: str, **payload: Any) -> dict:
    """POST a JSON Bot API method, return the ``result`` field. Raise on error."""
    url = f"{_BASE_URL}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
    body = resp.json()
    if not body.get("ok"):
        raise TelegramAPIError(f"{method} failed: {body.get('description')}")
    return body["result"]


async def tg_send_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = "Markdown",
    disable_web_page_preview: bool = True,
    reply_markup: Optional[dict] = None,
) -> None:
    """Send a text message to a chat. Auto-chunks if longer than 4000 chars.

    If reply_markup is provided and chunking happens, the markup is attached
    only to the final chunk so navigation buttons appear at the bottom.
    """
    if len(text) <= _CHUNK_SIZE:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await tg_call("sendMessage", **payload)
        return

    chunks = [text[i : i + _CHUNK_SIZE] for i in range(0, len(text), _CHUNK_SIZE)]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        prefixed = f"({idx}/{total}) {chunk}"
        payload = {
            "chat_id": chat_id,
            "text": prefixed,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if idx == total and reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await tg_call("sendMessage", **payload)


async def tg_answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> None:
    """Dismiss the spinner on an inline button. Call within ~10s of receipt."""
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True
    await tg_call("answerCallbackQuery", **payload)


async def tg_send_document(
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    caption: Optional[str] = None,
) -> None:
    """Upload a file as a Telegram document via multipart/form-data."""
    url = f"{_BASE_URL}/sendDocument"
    files = {"document": (filename, file_bytes, "text/plain; charset=utf-8")}
    data: dict[str, Any] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, files=files, data=data)
    body = resp.json()
    if not body.get("ok"):
        raise TelegramAPIError(f"sendDocument failed: {body.get('description')}")
