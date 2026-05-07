import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from services.telemost_recorder.config import SPEECHKIT_API_KEY, YANDEX_FOLDER_ID

_SYNC_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
_CHUNK_SECS = 30
_REQUEST_DELAY = 0.1


@dataclass
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


def _get_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _transcribe_chunk(chunk_bytes: bytes, offset_ms: int) -> Optional[TranscriptSegment]:
    headers = {
        "Authorization": f"Api-Key {SPEECHKIT_API_KEY}",
        "x-folder-id": YANDEX_FOLDER_ID,
    }
    params = {
        "lang": "ru-RU",
        "format": "oggopus",
        "sampleRateHertz": "48000",
    }
    resp = requests.post(_SYNC_URL, headers=headers, params=params, data=chunk_bytes, timeout=30)
    if not resp.ok:
        return None
    data = resp.json()
    text = data.get("result", "").strip()
    if not text:
        return None
    end_ms = offset_ms + _CHUNK_SECS * 1000
    return TranscriptSegment(speaker="Speaker 0", start_ms=offset_ms, end_ms=end_ms, text=text)


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    """Split audio into 30s chunks, transcribe each via SpeechKit v1 sync REST API."""
    duration = _get_duration(audio_path)
    segments: list[TranscriptSegment] = []

    offset = 0.0
    while offset < duration:
        chunk_end = min(offset + _CHUNK_SECS, duration)

        fd, tmp_path = tempfile.mkstemp(suffix=".ogg")
        os.close(fd)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(audio_path),
                    "-ss", str(offset),
                    "-t", str(chunk_end - offset),
                    "-c:a", "libopus",
                    "-b:a", "64k",
                    "-ar", "48000",
                    "-ac", "1",
                    tmp_path,
                ],
                capture_output=True,
                check=True,
            )
            chunk_bytes = Path(tmp_path).read_bytes()
        finally:
            os.unlink(tmp_path)

        segment = _transcribe_chunk(chunk_bytes, int(offset * 1000))
        if segment:
            segments.append(segment)

        offset = chunk_end
        if offset < duration:
            time.sleep(_REQUEST_DELAY)

    return segments
