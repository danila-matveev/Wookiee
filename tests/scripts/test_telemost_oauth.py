"""Tests for check_telemost_oauth() in scripts/telemost_check_cookies.py.

Four scenarios:
    1. OAuth OK — list_conferences succeeds → no alert sent.
    2. 401 + refresh OK — TelemostTokenExpired → refresh_oauth_token() →
       alert with first-8-char hints of new tokens.
    3. 401 + refresh fail — TelemostTokenExpired → refresh_oauth_token()
       raises RuntimeError → critical alert.
    4. Unexpected error — any other exception from list_conferences →
       alert with error message.

All external calls (yandex_telemost.*, _alert) are mocked — no network access.
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide minimum env so main() doesn't exit early with code 2."""
    monkeypatch.setenv("TELEMOST_STORAGE_STATE_PATH", "/fake/state.json")
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "fake-bot-token")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "99999")
    # OAuth env vars read by shared.yandex_telemost at import time
    monkeypatch.setenv("YANDEX_TELEMOST_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("YANDEX_TELEMOST_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("YANDEX_TELEMOST_OAUTH_TOKEN", "fake-oauth-token-xxxx")
    monkeypatch.setenv("YANDEX_TELEMOST_REFRESH_TOKEN", "fake-refresh-token-xxxx")


def _fresh_import(monkeypatch: pytest.MonkeyPatch):
    """Evict cached module so env changes and patches take effect."""
    for mod in list(sys.modules):
        if "telemost_check_cookies" in mod or "yandex_telemost" in mod:
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import shared.yandex_telemost  # noqa: PLC0415 — need fresh import
    from scripts.telemost_check_cookies import check_telemost_oauth  # noqa: PLC0415

    return check_telemost_oauth, shared.yandex_telemost


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oauth_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """list_conferences success → no alert is sent."""
    _set_required_env(monkeypatch)
    check_telemost_oauth, yandex_telemost = _fresh_import(monkeypatch)

    captured_alerts: list[str] = []

    with (
        patch.object(yandex_telemost, "list_conferences", new=AsyncMock(return_value=[])),
        patch(
            "scripts.telemost_check_cookies._alert",
            side_effect=lambda token, chat, text: captured_alerts.append(text),
        ),
    ):
        await check_telemost_oauth()

    assert captured_alerts == [], f"No alerts expected, got: {captured_alerts}"


@pytest.mark.asyncio
async def test_oauth_401_refresh_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 → refresh succeeds → alert shows first-8 chars of new tokens."""
    _set_required_env(monkeypatch)
    check_telemost_oauth, yandex_telemost = _fresh_import(monkeypatch)

    new_access = "NEWACC12345678"
    new_refresh = "NEWREF12345678"
    captured_alerts: list[str] = []

    with (
        patch.object(
            yandex_telemost,
            "list_conferences",
            new=AsyncMock(side_effect=yandex_telemost.TelemostTokenExpired("401")),
        ),
        patch.object(
            yandex_telemost,
            "refresh_oauth_token",
            new=AsyncMock(return_value=(new_access, new_refresh)),
        ),
        patch(
            "scripts.telemost_check_cookies._alert",
            side_effect=lambda token, chat, text: captured_alerts.append(text),
        ),
    ):
        await check_telemost_oauth()

    assert len(captured_alerts) == 1, f"Expected 1 alert, got: {captured_alerts}"
    alert_text = captured_alerts[0]

    # Alert must show first-8 chars of both tokens (masked for safety)
    assert new_access[:8] in alert_text, (
        f"Expected new_access prefix in alert: {alert_text}"
    )
    assert new_refresh[:8] in alert_text, (
        f"Expected new_refresh prefix in alert: {alert_text}"
    )
    # Must indicate successful refresh ("обновлён" / "обновлен")
    assert "обновлён" in alert_text or "обновлен" in alert_text, (
        f"Expected refresh-success phrasing in alert: {alert_text}"
    )


@pytest.mark.asyncio
async def test_oauth_401_refresh_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 → refresh_oauth_token() raises → critical alert about revoked token."""
    _set_required_env(monkeypatch)
    check_telemost_oauth, yandex_telemost = _fresh_import(monkeypatch)

    captured_alerts: list[str] = []

    with (
        patch.object(
            yandex_telemost,
            "list_conferences",
            new=AsyncMock(side_effect=yandex_telemost.TelemostTokenExpired("401")),
        ),
        patch.object(
            yandex_telemost,
            "refresh_oauth_token",
            new=AsyncMock(
                side_effect=RuntimeError(
                    'Telemost refresh_oauth_token failed: 400 {"error":"invalid_grant"}'
                )
            ),
        ),
        patch(
            "scripts.telemost_check_cookies._alert",
            side_effect=lambda token, chat, text: captured_alerts.append(text),
        ),
    ):
        await check_telemost_oauth()

    assert len(captured_alerts) == 1, f"Expected 1 alert, got: {captured_alerts}"
    alert_text = captured_alerts[0]

    # Must be a critical / revoke message
    assert any(
        keyword in alert_text.lower()
        for keyword in ("revoke", "отозван", "переавториз", "refresh", "критич")
    ), f"Expected revoke/critical phrasing in alert: {alert_text}"


@pytest.mark.asyncio
async def test_oauth_unexpected_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any non-401 exception from list_conferences → alert with error text."""
    _set_required_env(monkeypatch)
    check_telemost_oauth, yandex_telemost = _fresh_import(monkeypatch)

    captured_alerts: list[str] = []
    boom_msg = "Connection timeout to cloud-api.yandex.net"

    with (
        patch.object(
            yandex_telemost,
            "list_conferences",
            new=AsyncMock(side_effect=RuntimeError(boom_msg)),
        ),
        patch(
            "scripts.telemost_check_cookies._alert",
            side_effect=lambda token, chat, text: captured_alerts.append(text),
        ),
    ):
        await check_telemost_oauth()

    assert len(captured_alerts) == 1, f"Expected 1 alert, got: {captured_alerts}"
    alert_text = captured_alerts[0]
    assert boom_msg in alert_text, (
        f"Expected error message in alert. Got: {alert_text}"
    )
