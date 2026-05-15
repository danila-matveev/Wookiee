"""Telegram alert handler — routes ERROR+ logs to @wookiee_alerts_bot.

So failures surface in chat instead of in `docker logs`. Throttling: same
(logger, first 80 chars of message) deduplicated within 300 seconds.

Format: human-friendly Russian — greeting, where it happened, what broke,
suggested fix. The hint is selected from `_HINTS` by matching keywords in the
logger name or message; unknown errors get a generic "пришли скрин" fallback.

Env:
- TELEGRAM_ALERTS_BOT_TOKEN — alerts bot token (shared with hygiene/autopull)
- ADMIN_CHAT_ID — chat to deliver to
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import traceback
from urllib import error as _urlerror
from urllib import parse as _urlparse
from urllib import request as _urlrequest

_THROTTLE_SECONDS = 300
_MAX_MSG_LEN = 3500
_HTTP_TIMEOUT = 10.0

# Keyword → user-readable hint. First match wins; checked against
# `<logger_name> <message>` lowercased. Order matters — more specific first.
_HINTS: tuple[tuple[str, str], ...] = (
    ("bitrix", "Bitrix24 не отвечает. Проверь, что BITRIX24_WEBHOOK_URL в .env живой — открой его в браузере, должен вернуть JSON."),
    ("speechkit", "Yandex SpeechKit упал. Проверь баланс/квоту в Yandex Cloud Console и валидность SPEECHKIT_API_KEY."),
    ("transcrib", "ASR-пайплайн упал. Скорее всего ffmpeg/ffprobe в контейнере или SpeechKit. Логи: `docker logs telemost_recorder_api --tail 100`."),
    ("openrouter", "OpenRouter не отвечает. Проверь баланс на openrouter.ai и валидность OPENROUTER_API_KEY."),
    ("llm", "LLM-постобработка упала. Возможно, OpenRouter вернул кривой JSON — попробуй перезапустить меньшую модель."),
    ("telegram", "Telegram Bot API ругается. Скорее всего rate-limit или невалидный TELEMOST_BOT_TOKEN — подожди минуту."),
    ("asyncpg", "База Supabase не отвечает. Проверь SUPABASE_HOST/PASSWORD в .env, или статус проекта на supabase.com."),
    ("pool", "Пул соединений к БД исчерпан или мёртв. Перезапусти контейнер: `docker restart telemost_recorder_api`."),
    ("notion", "Notion API упал. Проверь NOTION_API_KEY и что у интеграции есть доступ к нужной БД."),
    ("recorder", "Recorder-контейнер упал на этапе записи (Playwright/Xvfb/PulseAudio). Скинь логи: `docker logs <recorder-id>`."),
)
_GENERIC_HINT = "Скинь мне это сообщение скриншотом или текстом — разберёмся."

logger = logging.getLogger(__name__)


def _pick_hint(logger_name: str, message: str) -> str:
    haystack = f"{logger_name} {message}".lower()
    for needle, hint in _HINTS:
        if needle in haystack:
            return hint
    return _GENERIC_HINT


def _short_location(logger_name: str) -> str:
    """`services.telemost_recorder_api.bitrix_calendar` → `bitrix_calendar`."""
    return logger_name.rsplit(".", 1)[-1] or logger_name


def _format_alert(record: logging.LogRecord, service: str) -> str:
    location = _short_location(record.name)
    body = record.getMessage()
    hint = _pick_hint(record.name, body)

    parts = [
        f"🔴 Привет! В *{service}* упала ошибка.",
        "",
        f"📍 *Где:* `{location}`",
        f"💥 *Что:* {body[:1200]}",
    ]
    if record.exc_info:
        tb = "".join(traceback.format_exception(*record.exc_info))
        # last lines are the most informative (the actual exception)
        snippet = tb.strip().splitlines()[-3:]
        parts += ["", "```", *snippet, "```"]
    parts += ["", f"🔧 *Что делать:* {hint}"]
    return "\n".join(parts)


class TelegramAlertHandler(logging.Handler):
    def __init__(self, bot_token: str, chat_id: str, service: str) -> None:
        super().__init__(level=logging.ERROR)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.service = service
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < self.level:
            return
        try:
            key = f"{record.name}:{record.getMessage()[:80]}"
            now = time.time()
            with self._lock:
                last = self._last_sent.get(key)
                if last is not None and now - last < _THROTTLE_SECONDS:
                    return
                self._last_sent[key] = now
            text = _format_alert(record, self.service)
            threading.Thread(
                target=self._send, args=(text,), daemon=True, name="tg-alert"
            ).start()
        except Exception:
            self.handleError(record)

    def _send(self, text: str) -> None:
        payload = _urlparse.urlencode({
            "chat_id": self.chat_id,
            "text": text[:_MAX_MSG_LEN],
            "parse_mode": "Markdown",
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            req = _urlrequest.Request(url, data=payload, method="POST")
            with _urlrequest.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                resp.read()
        except (_urlerror.URLError, OSError):
            # Never let the alert path break — already in error-handling code
            pass


def install_telegram_alerts(service: str = "telemost-api", *, force: bool = False) -> bool:
    """Attach a Telegram alert handler to the root logger.

    Returns True if installed, False if env not configured (no-op, logs hint).
    Safe to call multiple times — won't double-install.

    No-op under pytest unless `force=True`. `app.py` calls this at import time,
    so any test that imports from the API package would otherwise leave the
    handler on the root logger for the whole pytest session and turn every
    mocked `logger.error(...)` into a real Telegram alert. Detect via
    `sys.modules` (works at import time) and `PYTEST_CURRENT_TEST` (set
    during execution). Tests that want to exercise install behaviour pass
    force=True explicitly.
    """
    if not force and ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ):
        return False

    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, TelegramAlertHandler):
            return True

    bot_token = os.environ.get("TELEGRAM_ALERTS_BOT_TOKEN")
    chat_id = os.environ.get("ADMIN_CHAT_ID")
    if not bot_token or not chat_id:
        logger.warning(
            "Telegram alerts disabled (TELEGRAM_ALERTS_BOT_TOKEN or ADMIN_CHAT_ID missing)"
        )
        return False

    handler = TelegramAlertHandler(bot_token, chat_id, service)
    root.addHandler(handler)
    logger.info("Telegram alerts installed (service=%s)", service)
    return True
