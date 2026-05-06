import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from services.telemost_recorder.config import SPEECHKIT_API_KEY, YANDEX_FOLDER_ID

_SPEECHKIT_SUBMIT_URL = "https://stt.api.cloud.yandex.net/speech/v3/stt:longRunningRecognize"
_OPERATIONS_URL = "https://operation.api.cloud.yandex.net/operations"


@dataclass
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    """Send audio file to SpeechKit v3 async, return parsed segments."""
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()
    operation_id = _submit_job(audio_b64)
    raw = _poll_until_done(operation_id, timeout_seconds=1800)
    return _parse_response(raw)


def _submit_job(audio_b64: str) -> str:
    payload = json.dumps({
        "config": {
            "specification": {
                "languageCode": "ru-RU",
                "model": "general",
                "audioEncoding": "OGG_OPUS",
                "sampleRateHertz": 48000,
                "audioChannelCount": 1,
            },
            "speechAnalysis": {
                "enableSpeakerAnalysis": True,
            },
        },
        "audio": {"content": audio_b64},
    }).encode()

    req = urllib.request.Request(_SPEECHKIT_SUBMIT_URL, data=payload, method="POST")
    req.add_header("Authorization", f"Api-Key {SPEECHKIT_API_KEY}")
    req.add_header("x-folder-id", YANDEX_FOLDER_ID)
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["id"]


def _poll_until_done(operation_id: str, timeout_seconds: int = 1800) -> dict:
    deadline = time.monotonic() + timeout_seconds
    url = f"{_OPERATIONS_URL}/{operation_id}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Api-Key {SPEECHKIT_API_KEY}")

    while time.monotonic() < deadline:
        time.sleep(5)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data.get("done"):
            return data

    raise TimeoutError(f"SpeechKit operation {operation_id} did not complete in {timeout_seconds}s")


def _parse_response(raw: dict) -> list[TranscriptSegment]:
    segments = []
    for chunk in raw.get("response", {}).get("chunks", []):
        for alt in chunk.get("alternatives", []):
            words = alt.get("words", [])
            if not words or not alt.get("text", "").strip():
                continue
            start_ms = int(float(words[0].get("startTime", "0s").rstrip("s")) * 1000)
            end_ms = int(float(words[-1].get("endTime", "0s").rstrip("s")) * 1000)
            # speakerTag preferred; fall back to channelTag
            tag = chunk.get("speakerTag") or chunk.get("channelTag", "0")
            try:
                speaker_num = int(tag)
            except (ValueError, TypeError):
                speaker_num = 0
            segments.append(TranscriptSegment(
                speaker=f"Speaker {speaker_num}",
                start_ms=start_ms,
                end_ms=end_ms,
                text=alt["text"].strip(),
            ))
    return sorted(segments, key=lambda s: s.start_ms)
