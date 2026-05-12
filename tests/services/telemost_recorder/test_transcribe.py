"""Legacy transcribe tests — обновлены под async-API (httpx.AsyncClient вместо requests).

Сохраняем те же поведения: TranscriptSegment dataclass, _transcribe_chunk_async
возвращает None на пустой/whitespace/HTTP-error ответ, sync wrapper transcribe_audio
работает end-to-end.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.telemost_recorder.transcribe import (
    TranscriptSegment,
    _CHUNK_SECS,
    _transcribe_chunk_async,
    transcribe_audio,
)


def _mock_response(ok: bool, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.is_success = ok
    resp.status_code = 200 if ok else 500
    resp.text = ""
    resp.json.return_value = json_data or {}
    return resp


def _fake_client(resp: MagicMock) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    return client


def test_transcript_segment_dataclass():
    seg = TranscriptSegment(speaker="Speaker 0", start_ms=1000, end_ms=2000, text="Привет")
    assert seg.speaker == "Speaker 0"
    assert seg.start_ms == 1000
    assert seg.end_ms == 2000
    assert seg.text == "Привет"


@pytest.mark.asyncio
async def test_transcribe_chunk_returns_segment():
    resp = _mock_response(ok=True, json_data={"result": "Добрый день команда"})
    client = _fake_client(resp)
    seg = await _transcribe_chunk_async(b"audiodata", offset_ms=5000, client=client)
    assert seg is not None
    assert seg.text == "Добрый день команда"
    assert seg.start_ms == 5000
    assert seg.end_ms == 5000 + _CHUNK_SECS * 1000
    assert seg.speaker == "Speaker 0"


@pytest.mark.asyncio
async def test_transcribe_chunk_empty_result_returns_none():
    resp = _mock_response(ok=True, json_data={"result": ""})
    client = _fake_client(resp)
    seg = await _transcribe_chunk_async(b"audiodata", offset_ms=0, client=client)
    assert seg is None


@pytest.mark.asyncio
async def test_transcribe_chunk_whitespace_result_returns_none():
    resp = _mock_response(ok=True, json_data={"result": "   "})
    client = _fake_client(resp)
    seg = await _transcribe_chunk_async(b"audiodata", offset_ms=0, client=client)
    assert seg is None


@pytest.mark.asyncio
async def test_transcribe_chunk_http_error_returns_none():
    resp = _mock_response(ok=False)
    client = _fake_client(resp)
    seg = await _transcribe_chunk_async(b"audiodata", offset_ms=0, client=client)
    assert seg is None


def test_transcribe_audio_sync_wrapper_two_chunks(tmp_path):
    """Sync wrapper transcribe_audio → asyncio.run(transcribe_audio_async)."""
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")

    async def fake_split(_path, chunk_secs):
        return [(0, b"chunk0"), (_CHUNK_SECS * 1000, b"chunk1")]

    async def fake_transcribe(_bytes, offset_ms, _client=None):
        text = "Привет мир" if offset_ms == 0 else "Пока мир"
        return TranscriptSegment(
            speaker="Speaker 0",
            start_ms=offset_ms,
            end_ms=offset_ms + _CHUNK_SECS * 1000,
            text=text,
        )

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = transcribe_audio(audio)

    assert len(segments) == 2
    assert segments[0].text == "Привет мир"
    assert segments[0].start_ms == 0
    assert segments[1].text == "Пока мир"
    assert segments[1].start_ms == _CHUNK_SECS * 1000


def test_transcribe_audio_sync_wrapper_skips_silent_chunks(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")

    async def fake_split(_path, chunk_secs):
        return [(0, b"chunk0"), (_CHUNK_SECS * 1000, b"chunk1")]

    async def fake_transcribe(_bytes, offset_ms, _client=None):
        if offset_ms == 0:
            return None  # silent chunk
        return TranscriptSegment(
            speaker="Speaker 0",
            start_ms=offset_ms,
            end_ms=offset_ms + _CHUNK_SECS * 1000,
            text="Текст",
        )

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = transcribe_audio(audio)

    assert len(segments) == 1
    assert segments[0].text == "Текст"
    assert segments[0].start_ms == _CHUNK_SECS * 1000


def test_transcribe_audio_sync_wrapper_one_chunk(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")

    async def fake_split(_path, chunk_secs):
        return [(0, b"chunk0")]

    async def fake_transcribe(_bytes, offset_ms, _client=None):
        return TranscriptSegment(
            speaker="Speaker 0",
            start_ms=offset_ms,
            end_ms=offset_ms + _CHUNK_SECS * 1000,
            text="Тест",
        )

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = transcribe_audio(audio)

    assert len(segments) == 1
    assert segments[0].start_ms == 0
