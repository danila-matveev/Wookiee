"""Tests for scripts/telemost_smoke.py — cron smoke-check on Telegram webhook URL."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest


def _fake_response(payload):
    return SimpleNamespace(json=lambda: payload)


def _make_get(payload):
    def _get(url, timeout):  # noqa: ARG001
        return _fake_response(payload)

    return _get


def _reset_module(monkeypatch):
    # Reload the script each time so cached env reads don't leak across cases.
    monkeypatch.delitem(sys.modules, "scripts.telemost_smoke", raising=False)


def test_smoke_succeeds_when_webhook_matches(monkeypatch):
    _reset_module(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEMOST_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "alert")
    monkeypatch.setattr(
        "httpx.get",
        _make_get({"result": {"url": "https://example.com/telegram/webhook"}}),
    )
    from scripts.telemost_smoke import main

    assert main() == 0


def test_smoke_alerts_on_mismatch(monkeypatch):
    _reset_module(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEMOST_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "alert")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(
        "httpx.get",
        _make_get({"result": {"url": ""}}),
    )
    alerts: list[dict] = []
    monkeypatch.setattr(
        "httpx.post",
        lambda url, json, timeout: alerts.append(json) or SimpleNamespace(),
    )
    from scripts.telemost_smoke import main

    assert main() == 1
    assert any("mismatch" in a["text"].lower() for a in alerts)


def test_smoke_returns_error_on_missing_env(monkeypatch):
    _reset_module(monkeypatch)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEMOST_PUBLIC_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_ALERTS_BOT_TOKEN", raising=False)
    from scripts.telemost_smoke import main

    assert main() == 1


def test_smoke_alerts_when_telegram_api_throws(monkeypatch):
    _reset_module(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEMOST_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "alert")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "12345")

    def _boom(url, timeout):  # noqa: ARG001
        raise RuntimeError("network down")

    monkeypatch.setattr("httpx.get", _boom)
    alerts: list[dict] = []
    monkeypatch.setattr(
        "httpx.post",
        lambda url, json, timeout: alerts.append(json) or SimpleNamespace(),
    )
    from scripts.telemost_smoke import main

    assert main() == 1
    assert any("getwebhookinfo failed" in a["text"].lower() for a in alerts)


@pytest.mark.parametrize("trailing", ["https://example.com/", "https://example.com"])
def test_smoke_strips_trailing_slash(monkeypatch, trailing):
    _reset_module(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEMOST_PUBLIC_URL", trailing)
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "alert")
    monkeypatch.setattr(
        "httpx.get",
        _make_get({"result": {"url": "https://example.com/telegram/webhook"}}),
    )
    from scripts.telemost_smoke import main

    assert main() == 0
