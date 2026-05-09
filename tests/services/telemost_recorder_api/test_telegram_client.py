"""Tests for the Telegram API client."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_call,
    tg_send_document,
    tg_send_message,
)


@pytest.mark.asyncio
async def test_tg_call_returns_result():
    mock_resp = httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        result = await tg_call("sendMessage", chat_id=123, text="hi")
    assert result == {"message_id": 42}


@pytest.mark.asyncio
async def test_tg_call_raises_on_error():
    mock_resp = httpx.Response(400, json={"ok": False, "description": "bad request"})
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        with pytest.raises(TelegramAPIError) as exc:
            await tg_call("sendMessage", chat_id=123, text="hi")
        assert "bad request" in str(exc.value)


@pytest.mark.asyncio
async def test_tg_send_message_short_text_no_chunking():
    sent = []

    async def fake_call(method, **payload):
        sent.append(payload)
        return {"message_id": len(sent)}

    with patch(
        "services.telemost_recorder_api.telegram_client.tg_call",
        AsyncMock(side_effect=fake_call),
    ):
        await tg_send_message(chat_id=999, text="short message")

    assert len(sent) == 1
    assert sent[0]["text"] == "short message"
    assert sent[0]["chat_id"] == 999


@pytest.mark.asyncio
async def test_tg_send_message_chunks_long_text():
    sent = []

    async def fake_call(method, **payload):
        sent.append(payload)
        return {"message_id": len(sent)}

    with patch(
        "services.telemost_recorder_api.telegram_client.tg_call",
        AsyncMock(side_effect=fake_call),
    ):
        long_text = "x" * 5000
        await tg_send_message(chat_id=999, text=long_text)

    # 5000 chars, chunk size = 4000 → 2 messages
    assert len(sent) == 2
    assert sent[0]["text"].startswith("(1/2) ")
    assert sent[1]["text"].startswith("(2/2) ")


@pytest.mark.asyncio
async def test_tg_send_message_passes_reply_markup():
    sent = []

    async def fake_call(method, **payload):
        sent.append(payload)
        return {"message_id": len(sent)}

    markup = {"inline_keyboard": [[{"text": "Test", "callback_data": "x"}]]}
    with patch(
        "services.telemost_recorder_api.telegram_client.tg_call",
        AsyncMock(side_effect=fake_call),
    ):
        await tg_send_message(chat_id=999, text="hi", reply_markup=markup)
    assert len(sent) == 1
    assert sent[0]["reply_markup"] == markup


@pytest.mark.asyncio
async def test_tg_send_message_chunked_attaches_markup_to_last_chunk_only():
    sent = []

    async def fake_call(method, **payload):
        sent.append(payload)
        return {"message_id": len(sent)}

    markup = {"inline_keyboard": [[{"text": "Test", "callback_data": "x"}]]}
    with patch(
        "services.telemost_recorder_api.telegram_client.tg_call",
        AsyncMock(side_effect=fake_call),
    ):
        await tg_send_message(chat_id=999, text="x" * 5000, reply_markup=markup)
    assert len(sent) == 2
    assert "reply_markup" not in sent[0]
    assert sent[1]["reply_markup"] == markup


@pytest.mark.asyncio
async def test_tg_answer_callback_query_dismisses_spinner():
    sent = []

    async def fake_call(method, **payload):
        sent.append((method, payload))
        return True

    from services.telemost_recorder_api.telegram_client import tg_answer_callback_query

    with patch(
        "services.telemost_recorder_api.telegram_client.tg_call",
        AsyncMock(side_effect=fake_call),
    ):
        await tg_answer_callback_query("cq-42", text="hi", show_alert=True)
    assert len(sent) == 1
    method, payload = sent[0]
    assert method == "answerCallbackQuery"
    assert payload["callback_query_id"] == "cq-42"
    assert payload["text"] == "hi"
    assert payload["show_alert"] is True


@pytest.mark.asyncio
async def test_tg_send_document_uses_multipart():
    captured = {}

    async def fake_post(url, files=None, data=None, **kwargs):
        captured["url"] = url
        captured["files"] = files
        captured["data"] = data
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        await tg_send_document(
            chat_id=1,
            file_bytes=b"hello",
            filename="t.txt",
            caption="cap",
        )

    assert "sendDocument" in captured["url"]
    assert "document" in captured["files"]
    assert captured["data"]["chat_id"] == 1
    assert captured["data"]["caption"] == "cap"


@pytest.mark.asyncio
async def test_tg_send_document_raises_on_error():
    mock_resp = httpx.Response(400, json={"ok": False, "description": "file too big"})
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        with pytest.raises(TelegramAPIError) as exc:
            await tg_send_document(
                chat_id=1, file_bytes=b"x", filename="t.txt", caption=None
            )
        assert "file too big" in str(exc.value)
