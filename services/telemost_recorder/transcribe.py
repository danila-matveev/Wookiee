"""SpeechKit v1 sync REST — параллельная транскрибация через asyncio.

Sequential pipeline на 1h аудио = ~10 мин walltime. Async + semaphore (8)
сокращает до ~1 мин на той же оплате (SpeechKit чарджит за длительность,
не за количество запросов).
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from services.telemost_recorder.config import SPEECHKIT_API_KEY, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)

_SYNC_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
_CHUNK_SECS = 25
_ASR_PARALLEL = 8
_HTTP_TIMEOUT = 60.0


@dataclass
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


async def _get_duration_async(audio_path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode()[:500]}")
    try:
        return float(stdout.decode().strip())
    except ValueError as e:
        raise RuntimeError(
            f"ffprobe returned unparseable duration: {stdout.decode()[:200]}"
        ) from e


async def _split_into_chunks_async(
    audio_path: Path,
    chunk_secs: int,
) -> list[tuple[int, bytes]]:
    """Split audio into Opus chunks in one ffmpeg pass via -f segment.

    Returns [(offset_ms, opus_bytes), ...] in offset order.
    """
    duration = await _get_duration_async(audio_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="tmasr-"))
    try:
        pattern = tmp_dir / "chunk_%04d.ogg"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(chunk_secs),
            "-c:a", "libopus",
            "-b:a", "64k",
            "-ar", "48000",
            "-ac", "1",
            "-reset_timestamps", "1",
            str(pattern),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg split failed: {err.decode()[:500]}")

        chunks: list[tuple[int, bytes]] = []
        for i, f in enumerate(sorted(tmp_dir.glob("chunk_*.ogg"))):
            offset_ms = i * chunk_secs * 1000
            if offset_ms >= duration * 1000:
                break
            chunks.append((offset_ms, f.read_bytes()))
        return chunks
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _transcribe_chunk_async(
    chunk_bytes: bytes,
    offset_ms: int,
    client: httpx.AsyncClient,
) -> Optional[TranscriptSegment]:
    headers = {
        "Authorization": f"Api-Key {SPEECHKIT_API_KEY}",
        "x-folder-id": YANDEX_FOLDER_ID,
    }
    params = {"lang": "ru-RU", "format": "oggopus", "sampleRateHertz": "48000"}

    resp = await client.post(_SYNC_URL, headers=headers, params=params, content=chunk_bytes)
    if not resp.is_success:
        logger.warning(
            "SpeechKit chunk %dms failed: %d %s",
            offset_ms, resp.status_code, resp.text[:200],
        )
        return None
    data = resp.json()
    text = data.get("result", "").strip()
    if not text:
        return None
    return TranscriptSegment(
        speaker="Speaker 0",
        start_ms=offset_ms,
        end_ms=offset_ms + _CHUNK_SECS * 1000,
        text=text,
    )


async def transcribe_audio_async(audio_path: Path) -> list[TranscriptSegment]:
    """Parallel SpeechKit calls bounded by _ASR_PARALLEL."""
    chunks = await _split_into_chunks_async(audio_path, _CHUNK_SECS)
    if not chunks:
        return []

    sem = asyncio.Semaphore(_ASR_PARALLEL)

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        async def _bounded(chunk: bytes, offset_ms: int) -> Optional[TranscriptSegment]:
            async with sem:
                return await _transcribe_chunk_async(chunk, offset_ms, client)

        results = await asyncio.gather(*(_bounded(b, o) for o, b in chunks))

    return [r for r in results if r is not None]


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    """Sync wrapper kept for the recorder container's main entrypoint."""
    return asyncio.run(transcribe_audio_async(audio_path))
