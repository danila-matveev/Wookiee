"""Telegram alert handler — routes ERROR+ logs to @wookiee_alerts_bot.

So failures surface in chat instead of in `docker logs`. Throttling: same
(logger, first 80 chars of message) deduplicated within 300 seconds.

Env:
- TELEGRAM_ALERTS_BOT_TOKEN — alerts bot token (shared with hygiene/autopull)
- ADMIN_CHAT_ID — chat to deliver to
"""
from __future__ import annotations

import logging
import os
import threading
import time
from urllib import error as _urlerror
from urllib import parse as _urlparse
from urllib import request as _urlrequest

_THROTTLE_SECONDS = 300
_MAX_MSG_LEN = 3500
_HTTP_TIMEOUT = 10.0

logger = logging.getLogger(__name__)


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
            msg = self.format(record)
            key = f"{record.name}:{msg[:80]}"
            now = time.time()
            with self._lock:
                last = self._last_sent.get(key)
                if last is not None and now - last < _THROTTLE_SECONDS:
                    return
                self._last_sent[key] = now
            threading.Thread(
                target=self._send, args=(msg,), daemon=True, name="tg-alert"
            ).start()
        except Exception:
            self.handleError(record)

    def _send(self, msg: str) -> None:
        text = f"🔴 [{self.service}]\n{msg[:_MAX_MSG_LEN]}"
        payload = _urlparse.urlencode(
            {"chat_id": self.chat_id, "text": text}
        ).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            req = _urlrequest.Request(url, data=payload, method="POST")
            with _urlrequest.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                resp.read()
        except (_urlerror.URLError, OSError):
            # Never let the alert path break — already in error-handling code
            pass


def install_telegram_alerts(service: str = "telemost-api") -> bool:
    """Attach a Telegram alert handler to the root logger.

    Returns True if installed, False if env not configured (no-op, logs hint).
    Safe to call multiple times — won't double-install.
    """
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
    handler.setFormatter(
        logging.Formatter("%(name)s\n%(levelname)s: %(message)s")
    )
    root.addHandler(handler)
    logger.info("Telegram alerts installed (service=%s)", service)
    return True
