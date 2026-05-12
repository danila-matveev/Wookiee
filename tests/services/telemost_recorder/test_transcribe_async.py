"""Async ASR — параллельные чанки + сохранение порядка по offset_ms."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from services.telemost_recorder.transcribe import (
    TranscriptSegment,
    transcribe_audio_async,
)


@pytest.mark.asyncio
async def test_async_chunks_preserved_in_order(tmp_path: Path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"x")  # ffmpeg stub will not read

    async def fake_split(_path, chunk_secs):
        return [
            (0, b"a"),
            (25000, b"b"),
            (50000, b"c"),
        ]

    async def fake_transcribe(_bytes, offset_ms, _client=None):
        await asyncio.sleep(0.01)
        return TranscriptSegment(
            speaker="Speaker 0",
            start_ms=offset_ms,
            end_ms=offset_ms + 25000,
            text=f"text-{offset_ms}",
        )

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = await transcribe_audio_async(audio)

    assert [s.start_ms for s in segments] == [0, 25000, 50000]
    assert [s.text for s in segments] == ["text-0", "text-25000", "text-50000"]


@pytest.mark.asyncio
async def test_async_semaphore_limits_concurrency(tmp_path: Path, monkeypatch):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"x")

    monkeypatch.setattr(
        "services.telemost_recorder.transcribe._ASR_PARALLEL", 2
    )

    in_flight = 0
    max_in_flight = 0

    async def fake_split(_path, chunk_secs):
        return [(i * 25000, b"x") for i in range(10)]

    async def fake_transcribe(_bytes, offset_ms, _client=None):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return TranscriptSegment("Speaker 0", offset_ms, offset_ms + 25000, "ok")

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        await transcribe_audio_async(audio)

    assert max_in_flight <= 2


@pytest.mark.asyncio
async def test_async_skips_empty_chunks(tmp_path: Path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"x")

    async def fake_split(_path, chunk_secs):
        return [(0, b"a"), (25000, b"b")]

    async def fake_transcribe(_bytes, offset_ms, _client=None):
        if offset_ms == 0:
            return None  # silence chunk → SpeechKit returned empty text
        return TranscriptSegment("Speaker 0", offset_ms, offset_ms + 25000, "ok")

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = await transcribe_audio_async(audio)
    assert len(segments) == 1
    assert segments[0].start_ms == 25000


@pytest.mark.asyncio
async def test_get_duration_raises_on_ffprobe_failure(monkeypatch):
    from services.telemost_recorder.transcribe import _get_duration_async

    class _Proc:
        returncode = 1

        async def communicate(self):
            return b"", b"ffprobe: No such file"

    async def fake_exec(*a, **kw):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(RuntimeError, match="ffprobe failed"):
        await _get_duration_async(Path("/nope"))
