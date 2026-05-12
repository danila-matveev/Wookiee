"""TelegramAlertHandler — throttling, formatting, send behavior."""
from __future__ import annotations

import logging
import time
from unittest.mock import patch

from services.telemost_recorder_api.error_alerts import (
    TelegramAlertHandler,
    _format_alert,
    _pick_hint,
    install_telegram_alerts,
)


def _record(name: str, msg: str, level: int = logging.ERROR) -> logging.LogRecord:
    return logging.LogRecord(
        name=name, level=level, pathname=__file__, lineno=1,
        msg=msg, args=None, exc_info=None,
    )


def test_handler_throttles_duplicate_messages():
    handler = TelegramAlertHandler("tok", "chat", "svc")
    sent = []
    with patch.object(handler, "_send", side_effect=lambda m: sent.append(m)):
        handler.emit(_record("foo", "boom"))
        handler.emit(_record("foo", "boom"))
        handler.emit(_record("foo", "boom different tail " + "x" * 100))
    time.sleep(0.05)
    assert len(sent) == 2


def test_handler_ignores_below_error():
    handler = TelegramAlertHandler("tok", "chat", "svc")
    with patch.object(handler, "_send") as mock_send:
        handler.emit(_record("foo", "info-level", level=logging.INFO))
        handler.emit(_record("foo", "warn-level", level=logging.WARNING))
    time.sleep(0.05)
    mock_send.assert_not_called()


def test_install_skips_when_env_missing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALERTS_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_CHAT_ID", raising=False)
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, TelegramAlertHandler):
            root.removeHandler(h)
    try:
        assert install_telegram_alerts() is False
        installed = [h for h in root.handlers if isinstance(h, TelegramAlertHandler)]
        assert installed == []
    finally:
        for h in list(root.handlers):
            if isinstance(h, TelegramAlertHandler):
                root.removeHandler(h)


def test_install_attaches_handler_when_env_present(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "tok")
    monkeypatch.setenv("ADMIN_CHAT_ID", "42")
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, TelegramAlertHandler):
            root.removeHandler(h)
    try:
        assert install_telegram_alerts(service="test-svc") is True
        installed = [h for h in root.handlers if isinstance(h, TelegramAlertHandler)]
        assert len(installed) == 1
        # Idempotent
        assert install_telegram_alerts(service="test-svc") is True
        assert len([h for h in root.handlers if isinstance(h, TelegramAlertHandler)]) == 1
    finally:
        for h in list(root.handlers):
            if isinstance(h, TelegramAlertHandler):
                root.removeHandler(h)


def test_alert_format_is_human_readable():
    rec = _record(
        "services.telemost_recorder_api.bitrix_calendar",
        "calendar.event.get returned 500",
    )
    text = _format_alert(rec, "telemost-api")
    assert "Привет" in text
    assert "telemost-api" in text
    assert "bitrix_calendar" in text  # short location
    assert "calendar.event.get returned 500" in text
    assert "Bitrix24" in text  # picked hint


def test_pick_hint_falls_back_to_generic():
    hint = _pick_hint("unknown.module", "something unexpected")
    assert "разберёмся" in hint or "разберёмся" in hint.lower()


def test_pick_hint_recognizes_speechkit():
    hint = _pick_hint("services.telemost_recorder.transcribe", "SpeechKit chunk failed")
    # "transcribe" comes before "speechkit" in scan; either is acceptable
    assert "SpeechKit" in hint or "ASR" in hint


def test_alert_includes_traceback_excerpt_when_exc_info():
    try:
        raise ValueError("test traceback")
    except ValueError:
        import sys
        rec = logging.LogRecord(
            name="x", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="boom", args=None, exc_info=sys.exc_info(),
        )
    text = _format_alert(rec, "svc")
    assert "ValueError" in text
    assert "test traceback" in text
