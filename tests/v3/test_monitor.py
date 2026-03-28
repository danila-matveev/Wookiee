"""Tests for admin notification rate limiting."""
import pytest
from unittest.mock import AsyncMock, patch

from agents.v3.monitor import _send_admin, _recent_messages

# Use a large fake time so that the default "last_sent = 0" sentinel is
# treated as "never sent" even when time.monotonic() is near 0 (e.g. in CI).
_FAKE_TIME = 10_000.0


@pytest.fixture(autouse=True)
def clear_rate_limit():
    """Clear rate limit state between tests."""
    _recent_messages.clear()
    yield
    _recent_messages.clear()


@pytest.mark.asyncio
async def test_identical_messages_rate_limited():
    """Same text within 5 min window is suppressed."""
    with patch("agents.v3.monitor.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test"
        mock_config.ADMIN_CHAT_ID = "123"

        with patch("agents.v3.monitor.time") as mock_time:
            mock_time.monotonic.return_value = _FAKE_TIME

            with patch("aiogram.Bot") as mock_bot_cls:
                mock_bot = AsyncMock()
                mock_bot_cls.return_value = mock_bot

                await _send_admin("test message")
                await _send_admin("test message")

        assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_different_messages_not_rate_limited():
    """Different text is NOT suppressed."""
    with patch("agents.v3.monitor.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test"
        mock_config.ADMIN_CHAT_ID = "123"

        with patch("agents.v3.monitor.time") as mock_time:
            mock_time.monotonic.return_value = _FAKE_TIME

            with patch("aiogram.Bot") as mock_bot_cls:
                mock_bot = AsyncMock()
                mock_bot_cls.return_value = mock_bot

                await _send_admin("message A")
                await _send_admin("message B")

        assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_error_category_rate_limiting():
    """Error messages with same prefix but different details should be suppressed.

    e.g. prompt-tuner errors with different raw_output must be rate-limited together.
    """
    msg1 = "❌ Ошибка «prompt-tuner»:\nError code: 403 - {'error': 'details A'}"
    msg2 = "❌ Ошибка «prompt-tuner»:\nError code: 403 - {'error': 'details B'}"

    with patch("agents.v3.monitor.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test"
        mock_config.ADMIN_CHAT_ID = "123"

        with patch("agents.v3.monitor.time") as mock_time:
            mock_time.monotonic.return_value = _FAKE_TIME

            with patch("aiogram.Bot") as mock_bot_cls:
                mock_bot = AsyncMock()
                mock_bot_cls.return_value = mock_bot

                await _send_admin(msg1)
                await _send_admin(msg2)

        # Both have same first line "❌ Ошибка «prompt-tuner»:" — second suppressed
        assert mock_bot.send_message.call_count == 1
