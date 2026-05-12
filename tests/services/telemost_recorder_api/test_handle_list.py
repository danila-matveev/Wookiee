"""/list builds inline keyboard, one button per meeting."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.handlers.list_meetings import handle_list


def _fake_pool(fake_conn):
    fake_pool = MagicMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_pool.acquire = MagicMock(return_value=acquire_ctx)
    return fake_pool


@pytest.mark.asyncio
async def test_list_renders_one_button_per_meeting():
    mid1, mid2 = uuid4(), uuid4()
    fake_conn = AsyncMock()
    fake_conn.fetch.return_value = [
        {"id": mid1, "status": "done", "title": "Sync 1",
         "started_at": datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)},
        {"id": mid2, "status": "failed", "title": "Sync 2",
         "started_at": datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc)},
    ]
    fake_pool = _fake_pool(fake_conn)

    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append({"text": text, "reply_markup": reply_markup})

    with patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_pool",
        AsyncMock(return_value=fake_pool),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_user_by_telegram_id",
        AsyncMock(return_value={"telegram_id": 111}),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_list(chat_id=999, user_id=111)

    assert len(sent) == 1
    kb = sent[0]["reply_markup"]
    assert kb is not None
    rows = kb["inline_keyboard"]
    assert len(rows) == 2
    cbs = [rows[0][0]["callback_data"], rows[1][0]["callback_data"]]
    assert cbs[0] == f"meet:{str(mid1)[:8]}:show"
    assert cbs[1] == f"meet:{str(mid2)[:8]}:show"
