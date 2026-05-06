# Telemost Recorder Phase 2 — Audio Capture + Transcription + Speaker Matching

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record audio during a Telemost meeting, transcribe it via SpeechKit v3 with speaker diarization, and resolve anonymous "Speaker N" labels to real employee names using Bitrix24 + LLM.

**Architecture:** `AudioCapture` (audio.py) creates a PulseAudio null sink and runs ffmpeg to record Chromium's audio output during the meeting. After the meeting ends (auto-detected), `transcribe_audio()` (transcribe.py) sends the Opus file to SpeechKit v3 long-running recognition. `resolve_speakers()` (speakers.py) maps Speaker labels to real names using the Bitrix24 roster + Telemost participant list + Gemini Flash. Participant names are scraped from the Telemost UI via Playwright during the meeting. On macOS, audio capture is disabled via `TELEMOST_CAPTURE=false`; the transcription module can be tested independently with a pre-recorded file.

**Tech Stack:** Python 3.11, Playwright async, PulseAudio (`pactl`), ffmpeg (Opus), SpeechKit v3 REST API, OpenRouter (Gemini Flash), PyYAML, Bitrix24 REST API webhook

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `services/telemost_recorder/state.py` | Add RECORDING, TRANSCRIBING, DONE + new FailReasons; add `participants`, `transcript_path` fields |
| Modify | `services/telemost_recorder/config.py` | Add SPEECHKIT_API_KEY, YANDEX_FOLDER_ID, TELEMOST_CAPTURE, MAX_RECORDING_MINUTES, AUDIO_BITRATE, SPEAKERS_FILE, BITRIX_REST_API |
| Create | `services/telemost_recorder/audio.py` | `AudioCapture` class: PulseAudio null sink lifecycle + ffmpeg record/stop |
| Create | `services/telemost_recorder/transcribe.py` | SpeechKit v3 REST async client + response parser → `list[TranscriptSegment]` |
| Create | `services/telemost_recorder/speakers.py` | Bitrix24 roster sync, YAML read/write, LLM speaker resolution |
| Modify | `services/telemost_recorder/join.py` | Add `extract_participants()`, `detect_meeting_ended()`, `_write_transcript()`; integrate AudioCapture + transcription into `run_session()` |
| Modify | `services/telemost_recorder/requirements.txt` | Add `pyyaml>=6.0` |
| Create | `scripts/sync_speakers.py` | CLI: refresh `data/speakers.yml` from Bitrix24 |
| Modify | `deploy/Dockerfile.telemost_recorder` | Add `pulseaudio`, `ffmpeg`, `libopus0` |
| Create | `tests/services/telemost_recorder/test_state_machine_phase2.py` | FSM transitions for new states |
| Create | `tests/services/telemost_recorder/test_audio.py` | AudioCapture unit tests (mocked subprocess) |
| Create | `tests/services/telemost_recorder/test_transcribe.py` | SpeechKit client unit tests (mocked HTTP) |
| Create | `tests/services/telemost_recorder/test_speakers.py` | Bitrix sync + LLM resolution unit tests |
| Create | `tests/services/telemost_recorder/fixtures/speechkit_response.json` | Mock SpeechKit done-response fixture |

---

## Task 1: State Machine Extension

**Files:**
- Modify: `services/telemost_recorder/state.py`
- Create: `tests/services/telemost_recorder/test_state_machine_phase2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/telemost_recorder/test_state_machine_phase2.py
import pytest
from services.telemost_recorder.state import FailReason, Meeting, MeetingStatus


def test_in_meeting_to_recording() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    assert m.status == MeetingStatus.RECORDING


def test_recording_to_transcribing() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    m.transition(MeetingStatus.TRANSCRIBING)
    assert m.status == MeetingStatus.TRANSCRIBING


def test_transcribing_to_done() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    m.transition(MeetingStatus.TRANSCRIBING)
    m.transition(MeetingStatus.DONE)
    assert m.status == MeetingStatus.DONE


def test_done_is_terminal() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    m.transition(MeetingStatus.TRANSCRIBING)
    m.transition(MeetingStatus.DONE)
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.FAILED)


def test_recording_to_failed() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    m.transition(MeetingStatus.FAILED, FailReason.RECORDING_FAILED)
    assert m.status == MeetingStatus.FAILED
    assert m.fail_reason == FailReason.RECORDING_FAILED


def test_transcribing_to_failed() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    m.transition(MeetingStatus.TRANSCRIBING)
    m.transition(MeetingStatus.FAILED, FailReason.TRANSCRIPTION_FAILED)
    assert m.fail_reason == FailReason.TRANSCRIPTION_FAILED


def test_in_meeting_cannot_go_directly_to_done() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.DONE)


def test_meeting_has_participants_field() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    assert m.participants == []
    m.participants = ["Данила Матвеев", "Лиля Петрова"]
    assert len(m.participants) == 2


def test_meeting_has_transcript_path_field() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    assert m.transcript_path is None
```

- [ ] **Step 2: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_machine_phase2.py -v 2>&1 | head -20
```

Expected: multiple failures or `ImportError` (new states don't exist yet)

- [ ] **Step 3: Update state.py**

Replace `services/telemost_recorder/state.py` entirely:

```python
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional


class MeetingStatus(str, Enum):
    PENDING = "PENDING"
    JOINING = "JOINING"
    WAITING_ROOM = "WAITING_ROOM"
    IN_MEETING = "IN_MEETING"
    RECORDING = "RECORDING"
    TRANSCRIBING = "TRANSCRIBING"
    DONE = "DONE"
    FAILED = "FAILED"


class FailReason(str, Enum):
    INVALID_URL = "INVALID_URL"
    MEETING_NOT_FOUND = "MEETING_NOT_FOUND"
    JOIN_TIMEOUT = "JOIN_TIMEOUT"
    UI_DETECTION_FAILED = "UI_DETECTION_FAILED"
    NOT_ADMITTED = "NOT_ADMITTED"
    RECORDING_FAILED = "RECORDING_FAILED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"


_VALID_TRANSITIONS: dict[MeetingStatus, set[MeetingStatus]] = {
    MeetingStatus.PENDING: {MeetingStatus.JOINING, MeetingStatus.FAILED},
    MeetingStatus.JOINING: {MeetingStatus.IN_MEETING, MeetingStatus.WAITING_ROOM, MeetingStatus.FAILED},
    MeetingStatus.WAITING_ROOM: {MeetingStatus.IN_MEETING, MeetingStatus.FAILED},
    MeetingStatus.IN_MEETING: {MeetingStatus.RECORDING, MeetingStatus.FAILED},
    MeetingStatus.RECORDING: {MeetingStatus.TRANSCRIBING, MeetingStatus.FAILED},
    MeetingStatus.TRANSCRIBING: {MeetingStatus.DONE, MeetingStatus.FAILED},
    MeetingStatus.DONE: set(),
    MeetingStatus.FAILED: set(),
}


@dataclass
class Meeting:
    url: str
    meeting_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: MeetingStatus = field(default=MeetingStatus.PENDING)
    fail_reason: Optional[FailReason] = field(default=None)
    screenshot_path: Optional[str] = field(default=None)
    transcript_path: Optional[str] = field(default=None)
    participants: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition(self, new_status: MeetingStatus, fail_reason: Optional[FailReason] = None) -> None:
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}. "
                f"Allowed from {self.status.value}: {[s.value for s in allowed]}"
            )
        self.status = new_status
        self.fail_reason = fail_reason
        self.updated_at = datetime.now(UTC)
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_machine_phase2.py \
                 tests/services/telemost_recorder/test_state_machine.py -v
```

Expected: all pass (original state machine tests must still pass)

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder/state.py \
        tests/services/telemost_recorder/test_state_machine_phase2.py
git commit -m "feat(telemost): extend FSM — RECORDING, TRANSCRIBING, DONE states + participants field"
```

---

## Task 2: Config + Requirements

**Files:**
- Modify: `services/telemost_recorder/config.py`
- Modify: `services/telemost_recorder/requirements.txt`

- [ ] **Step 1: Update config.py**

Add to `services/telemost_recorder/config.py` after existing vars:

```python
# Phase 2 — audio + transcription
SPEECHKIT_API_KEY: str = os.getenv("SPEECHKIT_API_KEY", "")
YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
TELEMOST_CAPTURE: bool = os.getenv("TELEMOST_CAPTURE", "true").lower() != "false"
MAX_RECORDING_MINUTES: int = int(os.getenv("MAX_RECORDING_MINUTES", "240"))
AUDIO_BITRATE: str = os.getenv("TELEMOST_AUDIO_BITRATE", "64k")
SPEAKERS_FILE: Path = _PROJECT_ROOT / "data" / "speakers.yml"
BITRIX_REST_API: str = os.getenv("Bitrix_rest_api", "")
```

- [ ] **Step 2: Update requirements.txt**

```
playwright>=1.45
python-dotenv>=1.0
pyyaml>=6.0
```

- [ ] **Step 3: Install pyyaml**

```bash
.venv/bin/pip install "pyyaml>=6.0"
```

Expected: `Successfully installed pyyaml-6.x`

- [ ] **Step 4: Smoke check**

```bash
.venv/bin/python -c "
from services.telemost_recorder.config import (
    SPEECHKIT_API_KEY, YANDEX_FOLDER_ID, TELEMOST_CAPTURE,
    MAX_RECORDING_MINUTES, SPEAKERS_FILE
)
print('SPEECHKIT_API_KEY set:', bool(SPEECHKIT_API_KEY))
print('YANDEX_FOLDER_ID set:', bool(YANDEX_FOLDER_ID))
print('TELEMOST_CAPTURE:', TELEMOST_CAPTURE)
print('MAX_RECORDING_MINUTES:', MAX_RECORDING_MINUTES)
print('SPEAKERS_FILE:', SPEAKERS_FILE)
"
```

Expected: `SPEECHKIT_API_KEY set: True`, `YANDEX_FOLDER_ID set: True`

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder/config.py services/telemost_recorder/requirements.txt
git commit -m "feat(telemost): phase 2 config — SpeechKit, audio capture, speakers file"
```

---

## Task 3: AudioCapture Module

**Files:**
- Create: `services/telemost_recorder/audio.py`
- Create: `tests/services/telemost_recorder/test_audio.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/telemost_recorder/test_audio.py
import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.telemost_recorder.audio import AudioCapture


def test_audio_path_property(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    assert cap.audio_path == tmp_path / "audio.opus"


def test_start_returns_false_when_capture_disabled(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", False):
        result = cap.start()
    assert result is False


def test_start_returns_false_on_macos(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", True), \
         patch("platform.system", return_value="Darwin"):
        result = cap.start()
    assert result is False


def test_stop_without_start_returns_none(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    result = cap.stop()
    assert result is None


def test_stop_returns_none_when_audio_file_missing(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    mock_proc = MagicMock()
    cap._ffmpeg_proc = mock_proc
    result = cap.stop()
    mock_proc.terminate.assert_called_once()
    assert result is None


def test_stop_returns_path_when_audio_file_exists(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake opus data")
    mock_proc = MagicMock()
    mock_sink_id = 5
    cap._ffmpeg_proc = mock_proc
    cap._sink_module_id = mock_sink_id
    with patch("subprocess.run") as mock_run:
        result = cap.stop()
    mock_run.assert_called_once_with(
        ["pactl", "unload-module", "5"],
        capture_output=True,
    )
    assert result == audio_file


def test_start_on_linux_creates_sink_and_ffmpeg(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="test-id-123", output_dir=tmp_path)
    mock_pactl = MagicMock()
    mock_pactl.returncode = 0
    mock_pactl.stdout = "42\n"
    mock_ffmpeg = MagicMock()

    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", True), \
         patch("platform.system", return_value="Linux"), \
         patch("subprocess.run", return_value=mock_pactl) as mock_run, \
         patch("subprocess.Popen", return_value=mock_ffmpeg) as mock_popen:
        result = cap.start()

    assert result is True
    assert cap._sink_module_id == 42
    assert cap._ffmpeg_proc is mock_ffmpeg
    # pactl called with correct sink name
    call_args = mock_run.call_args[0][0]
    assert "module-null-sink" in call_args
    assert "telemost_test-id" in " ".join(call_args)
```

- [ ] **Step 2: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_audio.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'AudioCapture'`

- [ ] **Step 3: Create audio.py**

```python
# services/telemost_recorder/audio.py
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.telemost_recorder.config import AUDIO_BITRATE, MAX_RECORDING_MINUTES, TELEMOST_CAPTURE


@dataclass
class AudioCapture:
    meeting_id: str
    output_dir: Path
    _sink_module_id: Optional[int] = field(default=None, init=False, repr=False)
    _ffmpeg_proc: Optional[subprocess.Popen] = field(default=None, init=False, repr=False)
    _sink_name: str = field(default="", init=False, repr=False)

    @property
    def audio_path(self) -> Path:
        return self.output_dir / "audio.opus"

    def start(self) -> bool:
        """Start recording. Returns False if capture disabled or not on Linux."""
        if not TELEMOST_CAPTURE or platform.system() != "Linux":
            return False

        self._sink_name = f"telemost_{self.meeting_id[:8]}"
        result = subprocess.run(
            [
                "pactl", "load-module", "module-null-sink",
                f"sink_name={self._sink_name}",
                f"sink_properties=device.description=TelemostCapture",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"PulseAudio sink creation failed: {result.stderr}")
        self._sink_module_id = int(result.stdout.strip())

        self._ffmpeg_proc = subprocess.Popen(
            [
                "ffmpeg", "-y",
                "-f", "pulse", "-i", f"{self._sink_name}.monitor",
                "-c:a", "libopus",
                "-b:a", AUDIO_BITRATE,
                "-ar", "48000",
                "-ac", "1",
                "-t", str(MAX_RECORDING_MINUTES * 60),
                str(self.audio_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    def stop(self) -> Optional[Path]:
        """Stop recording. Returns audio path if file is non-empty, else None."""
        if self._ffmpeg_proc is not None:
            self._ffmpeg_proc.terminate()
            try:
                self._ffmpeg_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._ffmpeg_proc.kill()
                self._ffmpeg_proc.wait()
            self._ffmpeg_proc = None

        if self._sink_module_id is not None:
            subprocess.run(
                ["pactl", "unload-module", str(self._sink_module_id)],
                capture_output=True,
            )
            self._sink_module_id = None

        if self.audio_path.exists() and self.audio_path.stat().st_size > 0:
            return self.audio_path
        return None
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_audio.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder/audio.py \
        tests/services/telemost_recorder/test_audio.py
git commit -m "feat(telemost): AudioCapture — PulseAudio null sink + ffmpeg record/stop"
```

---

## Task 4: SpeechKit Transcription Module

**Files:**
- Create: `services/telemost_recorder/transcribe.py`
- Create: `tests/services/telemost_recorder/fixtures/speechkit_response.json`
- Create: `tests/services/telemost_recorder/test_transcribe.py`

- [ ] **Step 1: Create fixture**

```json
{
  "id": "op-123",
  "done": true,
  "response": {
    "chunks": [
      {
        "alternatives": [
          {
            "words": [
              {"text": "Добрый", "startTime": "0.480s", "endTime": "0.720s"},
              {"text": "день", "startTime": "0.720s", "endTime": "1.050s"}
            ],
            "text": "Добрый день",
            "confidence": 0.98
          }
        ],
        "channelTag": "0",
        "speakerTag": "1"
      },
      {
        "alternatives": [
          {
            "words": [
              {"text": "Привет", "startTime": "3.100s", "endTime": "3.500s"}
            ],
            "text": "Привет",
            "confidence": 0.95
          }
        ],
        "channelTag": "0",
        "speakerTag": "2"
      }
    ]
  }
}
```

Save to: `tests/services/telemost_recorder/fixtures/speechkit_response.json`

- [ ] **Step 2: Write failing tests**

```python
# tests/services/telemost_recorder/test_transcribe.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.telemost_recorder.transcribe import (
    TranscriptSegment,
    _parse_response,
    _poll_until_done,
    _submit_job,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


def test_parse_response_returns_segments() -> None:
    raw = _load_fixture("speechkit_response.json")
    segments = _parse_response(raw)
    assert len(segments) == 2
    assert segments[0].speaker == "Speaker 1"
    assert segments[0].text == "Добрый день"
    assert segments[0].start_ms == 480
    assert segments[1].speaker == "Speaker 2"
    assert segments[1].text == "Привет"


def test_parse_response_sorted_by_start_ms() -> None:
    raw = _load_fixture("speechkit_response.json")
    segments = _parse_response(raw)
    times = [s.start_ms for s in segments]
    assert times == sorted(times)


def test_parse_response_empty_chunks() -> None:
    segments = _parse_response({"response": {"chunks": []}})
    assert segments == []


def test_parse_response_missing_response_key() -> None:
    segments = _parse_response({})
    assert segments == []


def test_submit_job_returns_operation_id() -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"id": "op-456"}'
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        op_id = _submit_job("base64audiodata")

    assert op_id == "op-456"


def test_poll_until_done_returns_when_done() -> None:
    done_response = _load_fixture("speechkit_response.json")
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(done_response).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("time.sleep"):
        result = _poll_until_done("op-123", timeout_seconds=30)

    assert result["done"] is True
    assert "response" in result


def test_transcript_segment_dataclass() -> None:
    seg = TranscriptSegment(speaker="Speaker 1", start_ms=1000, end_ms=2000, text="Привет")
    assert seg.speaker == "Speaker 1"
    assert seg.start_ms == 1000
```

- [ ] **Step 3: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_transcribe.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'TranscriptSegment'`

- [ ] **Step 4: Create transcribe.py**

```python
# services/telemost_recorder/transcribe.py
import base64
import json
import time
import urllib.request
import urllib.error
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
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_transcribe.py -v
```

Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder/transcribe.py \
        tests/services/telemost_recorder/test_transcribe.py \
        tests/services/telemost_recorder/fixtures/speechkit_response.json
git commit -m "feat(telemost): SpeechKit v3 transcription client + response parser"
```

---

## Task 5: Speakers Module (Bitrix Sync + LLM Resolution)

**Files:**
- Create: `services/telemost_recorder/speakers.py`
- Create: `scripts/sync_speakers.py`
- Create: `tests/services/telemost_recorder/test_speakers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/telemost_recorder/test_speakers.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from services.telemost_recorder.speakers import (
    load_speakers,
    resolve_speakers,
    save_speakers,
    sync_from_bitrix,
)
from services.telemost_recorder.transcribe import TranscriptSegment


def test_load_speakers_returns_empty_when_file_missing(tmp_path: Path) -> None:
    with patch("services.telemost_recorder.speakers.SPEAKERS_FILE", tmp_path / "speakers.yml"):
        result = load_speakers()
    assert result == []


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    employees = [
        {"bitrix_id": "1", "name": "Данила Матвеев", "short_name": "Данила"},
        {"bitrix_id": "2", "name": "Лиля Петрова", "short_name": "Лиля"},
    ]
    speakers_file = tmp_path / "speakers.yml"
    with patch("services.telemost_recorder.speakers.SPEAKERS_FILE", speakers_file):
        save_speakers(employees)
        loaded = load_speakers()
    assert len(loaded) == 2
    assert loaded[0]["name"] == "Данила Матвеев"


def test_save_speakers_creates_parent_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "speakers.yml"
    with patch("services.telemost_recorder.speakers.SPEAKERS_FILE", nested):
        save_speakers([{"bitrix_id": "1", "name": "Test", "short_name": "Test"}])
    assert nested.exists()


def test_resolve_speakers_returns_empty_without_participants() -> None:
    segments = [TranscriptSegment(speaker="Speaker 1", start_ms=0, end_ms=1000, text="Привет")]
    result = resolve_speakers(segments, participants=[], employees=[])
    assert result == {}


def test_resolve_speakers_returns_empty_without_segments() -> None:
    result = resolve_speakers([], participants=["Данила Матвеев"], employees=[])
    assert result == {}


def test_resolve_speakers_calls_llm_and_returns_mapping() -> None:
    segments = [
        TranscriptSegment(speaker="Speaker 1", start_ms=0, end_ms=1000, text="Привет, это Данила"),
        TranscriptSegment(speaker="Speaker 2", start_ms=1000, end_ms=2000, text="Привет, это Лиля"),
    ]
    participants = ["Данила Матвеев", "Лиля Петрова"]
    employees = [
        {"bitrix_id": "1", "name": "Данила Матвеев", "short_name": "Данила"},
        {"bitrix_id": "2", "name": "Лиля Петрова", "short_name": "Лиля"},
    ]
    llm_response = json.dumps({"Speaker 1": "Данила Матвеев", "Speaker 2": "Лиля Петрова"})
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "choices": [{"message": {"content": llm_response}}]
    }).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = resolve_speakers(segments, participants, employees)

    assert result == {"Speaker 1": "Данила Матвеев", "Speaker 2": "Лиля Петрова"}


def test_resolve_speakers_returns_empty_on_llm_error() -> None:
    segments = [TranscriptSegment(speaker="Speaker 1", start_ms=0, end_ms=1000, text="Текст")]
    with patch("urllib.request.urlopen", side_effect=Exception("network error")):
        result = resolve_speakers(segments, ["Данила Матвеев"], [])
    assert result == {}


def test_sync_from_bitrix_parses_users() -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "result": [
            {"ID": "1", "NAME": "Данила", "LAST_NAME": "Матвеев"},
            {"ID": "2", "NAME": "Лиля", "LAST_NAME": "Петрова"},
        ]
    }).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("services.telemost_recorder.speakers.BITRIX_REST_API", "https://example.bitrix24.ru/rest/1/key/"):
        employees = sync_from_bitrix()

    assert len(employees) == 2
    assert employees[0]["name"] == "Данила Матвеев"
    assert employees[0]["short_name"] == "Данила"
```

- [ ] **Step 2: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_speakers.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'load_speakers'`

- [ ] **Step 3: Create speakers.py**

```python
# services/telemost_recorder/speakers.py
import json
import urllib.request
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import yaml

from services.telemost_recorder.config import BITRIX_REST_API, SPEAKERS_FILE
from services.telemost_recorder.transcribe import TranscriptSegment

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def sync_from_bitrix() -> list[dict]:
    """Fetch active users from Bitrix24 REST API webhook."""
    employees = []
    start = 0
    while True:
        url = f"{BITRIX_REST_API}user.get?ACTIVE=Y&start={start}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        for user in data.get("result", []):
            name = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}".strip()
            employees.append({
                "bitrix_id": str(user["ID"]),
                "name": name,
                "short_name": user.get("NAME", name),
            })
        if data.get("next"):
            start = data["next"]
        else:
            break
    return employees


def load_speakers() -> list[dict]:
    """Load speakers.yml. Returns empty list if file missing."""
    if not SPEAKERS_FILE.exists():
        return []
    with open(SPEAKERS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("employees", [])


def save_speakers(employees: list[dict]) -> None:
    """Write employees list to speakers.yml."""
    SPEAKERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEAKERS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(
            {"updated_at": datetime.now(UTC).isoformat(), "employees": employees},
            f,
            allow_unicode=True,
            default_flow_style=False,
        )


def resolve_speakers(
    segments: list[TranscriptSegment],
    participants: list[str],
    employees: list[dict],
) -> dict[str, str]:
    """Map Speaker N labels to real names via Gemini Flash. Returns {Speaker N: name}."""
    if not segments or not participants:
        return {}

    speaker_labels = sorted({s.speaker for s in segments})
    participant_names = [p for p in participants if p != "Wookiee Recorder"]
    if not participant_names:
        return {}

    excerpt = "\n".join(f"[{s.speaker}]: {s.text}" for s in segments[:60])

    from services.telemost_recorder.config import SPEECHKIT_API_KEY  # avoid circular
    import os
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        return {}

    payload = json.dumps({
        "model": "google/gemini-flash-1.5",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Meeting participants: {participant_names}\n"
                    f"Speaker labels in transcript: {speaker_labels}\n\n"
                    f"Transcript excerpt:\n{excerpt}\n\n"
                    "Map each speaker label to a participant name based on context clues "
                    "(names mentioned, topics, greeting phrases). "
                    'Return ONLY valid JSON like: {"Speaker 1": "Full Name", "Speaker 2": "Full Name"}. '
                    "If you cannot confidently match a speaker, keep the original label."
                ),
            }
        ],
        "max_tokens": 300,
    }).encode()

    req = urllib.request.Request(_OPENROUTER_URL, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {openrouter_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"].strip()
        if "```" in content:
            content = content.split("```")[1].lstrip("json").strip()
        mapping = json.loads(content)
        return {k: v for k, v in mapping.items() if k in speaker_labels}
    except Exception:
        return {}
```

- [ ] **Step 4: Create sync_speakers.py**

```python
#!/usr/bin/env python3
"""Refresh data/speakers.yml from Bitrix24.

Usage:
    python scripts/sync_speakers.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.telemost_recorder.speakers import save_speakers, sync_from_bitrix  # noqa: E402
from services.telemost_recorder.config import BITRIX_REST_API, SPEAKERS_FILE  # noqa: E402


def main() -> None:
    if not BITRIX_REST_API:
        print("ERROR: Bitrix_rest_api not set in .env")
        sys.exit(1)
    print("Fetching employees from Bitrix24...")
    employees = sync_from_bitrix()
    save_speakers(employees)
    print(f"Saved {len(employees)} employees to {SPEAKERS_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_speakers.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder/speakers.py \
        scripts/sync_speakers.py \
        tests/services/telemost_recorder/test_speakers.py
git commit -m "feat(telemost): speakers module — Bitrix sync, YAML roster, LLM speaker resolution"
```

---

## Task 6: Join Flow Integration

**Files:**
- Modify: `services/telemost_recorder/join.py`

Add `extract_participants()`, `detect_meeting_ended()`, `_write_transcript()` helpers, then integrate `AudioCapture` and transcription into `run_session()`.

- [ ] **Step 1: Add helpers to join.py**

After the existing `_mute_bot` function, append:

```python
async def extract_participants(page: Page) -> list[str]:
    """Open Participants panel and scrape display names."""
    names: list[str] = []
    try:
        btn = page.locator(
            "button:has-text('Участники'), [data-testid='participants-button']"
        ).first
        if await btn.is_visible(timeout=2_000):
            await btn.click()
            await asyncio.sleep(0.5)
            items = page.locator(
                "[data-testid='participant-name'], "
                ".participant-name, "
                "[class*='participant'][class*='name']"
            )
            count = await items.count()
            for i in range(count):
                name = (await items.nth(i).text_content() or "").strip()
                if name and name != "Wookiee Recorder":
                    names.append(name)
            await btn.click()  # close panel
    except Exception:
        pass

    # Fallback: video tile labels
    if not names:
        try:
            tiles = page.locator("[class*='tile'][class*='name'], .video-tile-name")
            count = await tiles.count()
            for i in range(count):
                name = (await tiles.nth(i).text_content() or "").strip()
                if name and name != "Wookiee Recorder":
                    names.append(name)
        except Exception:
            pass

    return list(dict.fromkeys(names))  # deduplicate, preserve order


async def detect_meeting_ended(page: Page) -> bool:
    """Return True when Telemost signals the meeting has ended."""
    selectors = [
        "text=Встреча завершена",
        "text=Meeting ended",
        "text=Конференция завершена",
        "[data-testid='meeting-ended']",
    ]
    for selector in selectors:
        try:
            if await page.locator(selector).first.is_visible(timeout=200):
                return True
        except Exception:
            continue
    try:
        if "telemost" not in page.url:
            return True
    except Exception:
        pass
    return False


def _format_ms(ms: int) -> str:
    total_s = ms // 1000
    h, remainder = divmod(total_s, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _write_transcript(segments: list, output_dir: Path) -> None:
    """Write transcript.txt and transcript.json to output_dir."""
    import json as _json
    from services.telemost_recorder.transcribe import TranscriptSegment

    txt_lines = [
        f"[{_format_ms(s.start_ms)}] {s.speaker}: {s.text}"
        for s in segments
    ]
    (output_dir / "transcript.txt").write_text("\n".join(txt_lines), encoding="utf-8")

    json_data = [
        {"speaker": s.speaker, "start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text}
        for s in segments
    ]
    (output_dir / "transcript.json").write_text(
        _json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

- [ ] **Step 2: Update run_session() in join.py**

Replace the entire `run_session()` function:

```python
async def run_session(url: str, bot_name: str = BOT_NAME) -> None:
    """
    Join a meeting, record audio, transcribe after meeting ends.
    Holds the browser open until meeting ends or Ctrl+C.
    """
    from services.telemost_recorder.audio import AudioCapture
    from services.telemost_recorder.config import SCREENSHOT_INTERVAL, WAITING_ROOM_TIMEOUT

    meeting = Meeting(url=url)
    if not validate_url(url):
        meeting.transition(MeetingStatus.FAILED, FailReason.INVALID_URL)
        _emit({"status": "FAILED", "reason": "INVALID_URL", "message": "Ссылка не похожа на Яндекс Телемост"})
        return

    screenshot_dir = Path("data/telemost") / meeting.meeting_id
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    capture = AudioCapture(meeting_id=meeting.meeting_id, output_dir=screenshot_dir)

    async with launch_browser() as (_, __, page):
        await _execute_join(page, meeting, bot_name, screenshot_dir)

        if meeting.status == MeetingStatus.FAILED:
            _emit({
                "status": "FAILED",
                "reason": meeting.fail_reason.value if meeting.fail_reason else "UNKNOWN",
                "meeting_id": meeting.meeting_id,
            })
            return

        if meeting.status == MeetingStatus.WAITING_ROOM:
            state = await _wait_for_admission(page, timeout=WAITING_ROOM_TIMEOUT)
            if state != ScreenState.IN_MEETING:
                meeting.transition(MeetingStatus.FAILED, FailReason.NOT_ADMITTED)
                _emit({"status": "FAILED", "reason": "NOT_ADMITTED", "meeting_id": meeting.meeting_id})
                return
            await _dismiss_modals(page)
            await _mute_bot(page)
            screenshot = await _save_screenshot(page, screenshot_dir, "screenshot_001")
            meeting.screenshot_path = str(screenshot)
            meeting.transition(MeetingStatus.IN_MEETING)
            _emit({"status": "IN_MEETING", "meeting_id": meeting.meeting_id, "screenshot": meeting.screenshot_path})

        # Start audio recording
        recording_active = capture.start()
        if recording_active:
            meeting.transition(MeetingStatus.RECORDING)
            _emit({"status": "RECORDING", "meeting_id": meeting.meeting_id})
        else:
            meeting.transition(MeetingStatus.RECORDING)  # FSM still advances; no actual audio

        # Meeting loop
        screenshot_n = 2
        participant_tick = 0
        try:
            while True:
                await asyncio.sleep(SCREENSHOT_INTERVAL)
                await _save_screenshot(page, screenshot_dir, f"screenshot_{screenshot_n:03d}")
                screenshot_n += 1

                participant_tick += SCREENSHOT_INTERVAL
                if participant_tick >= 60:
                    meeting.participants = await extract_participants(page)
                    participant_tick = 0

                if await detect_meeting_ended(page):
                    _emit({"status": "MEETING_ENDED_DETECTED", "meeting_id": meeting.meeting_id})
                    break
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    # Stop recording (browser already closed)
    audio_path = capture.stop()

    # Transcribe
    meeting.transition(MeetingStatus.TRANSCRIBING)
    _emit({"status": "TRANSCRIBING", "meeting_id": meeting.meeting_id})

    if not audio_path:
        _emit({"status": "TRANSCRIBING_SKIPPED", "reason": "no audio file", "meeting_id": meeting.meeting_id})
        meeting.transition(MeetingStatus.DONE)
        return

    try:
        from services.telemost_recorder.transcribe import transcribe_audio
        from services.telemost_recorder.speakers import load_speakers, resolve_speakers

        segments = transcribe_audio(audio_path)
        employees = load_speakers()
        speaker_map = resolve_speakers(segments, meeting.participants, employees)
        for seg in segments:
            seg.speaker = speaker_map.get(seg.speaker, seg.speaker)

        _write_transcript(segments, screenshot_dir)
        meeting.transcript_path = str(screenshot_dir / "transcript.txt")
        meeting.transition(MeetingStatus.DONE)
        _emit({
            "status": "DONE",
            "meeting_id": meeting.meeting_id,
            "transcript": meeting.transcript_path,
            "segments": len(segments),
        })
    except Exception as exc:
        meeting.transition(MeetingStatus.FAILED, FailReason.TRANSCRIPTION_FAILED)
        _emit({
            "status": "FAILED",
            "reason": "TRANSCRIPTION_FAILED",
            "meeting_id": meeting.meeting_id,
            "error": str(exc),
        })
```

- [ ] **Step 3: Add missing import at top of join.py**

The file already imports `asyncio`, `json`, `re`, `time`, `Path`. Verify these imports exist at the top — no new imports needed since the new helpers use the same deps.

- [ ] **Step 4: Run all unit tests**

```bash
.venv/bin/pytest \
  tests/services/telemost_recorder/test_state_machine.py \
  tests/services/telemost_recorder/test_state_machine_phase2.py \
  tests/services/telemost_recorder/test_url_validation.py \
  tests/services/telemost_recorder/test_state_detection.py \
  tests/services/telemost_recorder/test_audio.py \
  tests/services/telemost_recorder/test_transcribe.py \
  tests/services/telemost_recorder/test_speakers.py \
  -v
```

Expected: all pass (previously 31 + new ones)

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder/join.py
git commit -m "feat(telemost): integrate audio capture, meeting-end detection, and transcription into run_session"
```

---

## Task 7: Dockerfile Update

**Files:**
- Modify: `deploy/Dockerfile.telemost_recorder`

- [ ] **Step 1: Add PulseAudio and ffmpeg to Dockerfile**

In `deploy/Dockerfile.telemost_recorder`, extend the existing `apt-get install` block to include:

```dockerfile
    pulseaudio \
    ffmpeg \
```

The full apt-get line should look like (add after existing packages):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    pulseaudio \
    ffmpeg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libx11-6 \
    libxcb1 \
    libx11-xcb1 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*
```

Also add pyyaml to the requirements copy/install step — it's already in `requirements.txt` so no Dockerfile change needed beyond the system packages.

- [ ] **Step 2: Add PulseAudio daemon startup to container entrypoint**

PulseAudio must be started before `run_session` on Linux. Add to Dockerfile:

```dockerfile
ENV PULSE_SERVER=unix:/tmp/pulse/native

# Startup script that launches pulseaudio before the main command
COPY deploy/telemost_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "scripts/telemost_record.py", "--help"]
```

Create `deploy/telemost_entrypoint.sh`:

```bash
#!/bin/bash
set -e
# Start PulseAudio in background (daemon mode)
pulseaudio --start --exit-idle-time=-1 --daemon 2>/dev/null || true
# Launch whatever command was passed
exec "$@"
```

- [ ] **Step 3: Verify Docker build**

```bash
docker build -f deploy/Dockerfile.telemost_recorder -t telemost_recorder:phase2 . 2>&1 | tail -5
```

Expected: successful build. First run takes ~5 min (downloads Chromium).

- [ ] **Step 4: Smoke test in container**

```bash
docker run --rm telemost_recorder:phase2 \
  python -c "import subprocess; r = subprocess.run(['ffmpeg', '-version'], capture_output=True); print(r.stdout.decode()[:50])"
```

Expected: `ffmpeg version ...`

- [ ] **Step 5: Commit**

```bash
git add deploy/Dockerfile.telemost_recorder deploy/telemost_entrypoint.sh
git commit -m "feat(telemost): add pulseaudio + ffmpeg to Dockerfile + entrypoint"
```

---

## Task 8: Live Integration Test

**Files:**
- Create: `tests/services/telemost_recorder/test_live_phase2.py`

- [ ] **Step 1: Create live test**

```python
# tests/services/telemost_recorder/test_live_phase2.py
"""
Live Phase 2 integration test: joins a real Telemost meeting, records audio,
transcribes via SpeechKit. Run on Linux with PulseAudio.

Usage:
    pytest tests/services/telemost_recorder/test_live_phase2.py \
        --url="https://telemost.360.yandex.ru/j/XXXX" \
        -v -s

Linux only — audio capture requires PulseAudio.
"""
import platform
from pathlib import Path

import pytest

from services.telemost_recorder.join import run_session


@pytest.mark.anyio
@pytest.mark.skipif(platform.system() != "Linux", reason="PulseAudio required")
async def test_live_phase2(telemost_url: str) -> None:
    import asyncio

    print(f"\n→ Starting Phase 2 session: {telemost_url}")
    print("→ Bot will record for up to 30s then you can Ctrl+C to trigger transcription")

    await asyncio.wait_for(run_session(telemost_url), timeout=300)
```

- [ ] **Step 2: Run all unit tests one final time**

```bash
.venv/bin/pytest \
  tests/services/telemost_recorder/test_state_machine.py \
  tests/services/telemost_recorder/test_state_machine_phase2.py \
  tests/services/telemost_recorder/test_url_validation.py \
  tests/services/telemost_recorder/test_state_detection.py \
  tests/services/telemost_recorder/test_audio.py \
  tests/services/telemost_recorder/test_transcribe.py \
  tests/services/telemost_recorder/test_speakers.py \
  -v
```

Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add tests/services/telemost_recorder/test_live_phase2.py
git commit -m "feat(telemost): phase 2 live integration test"
```

---

## Phase 2 Acceptance Checklist

Run on server (Linux) with a real meeting:

```bash
# 1. Sync speakers from Bitrix
python scripts/sync_speakers.py
# Expected: "Saved N employees to data/speakers.yml"

# 2. Full session (join → record → transcribe)
python scripts/telemost_record.py join https://telemost.360.yandex.ru/j/XXXX
# Expected JSON events in order:
# {"status": "IN_MEETING", ...}
# {"status": "RECORDING", ...}
# (end meeting or Ctrl+C)
# {"status": "TRANSCRIBING", ...}
# {"status": "DONE", "transcript": "data/telemost/<id>/transcript.txt", ...}
```

Phase 2 is **done** when:
- [ ] All unit tests pass
- [ ] `data/telemost/<id>/audio.opus` is non-empty after meeting
- [ ] `transcript.txt` contains speaker-labeled lines with real names
- [ ] `transcript.json` contains structured segments with start/end timestamps
- [ ] Meeting end is detected automatically (no manual Ctrl+C required for normal flow)

---

## .env Keys Required

```bash
SPEECHKIT_API_KEY=YOUR_SPEECHKIT_API_KEY_HERE
YANDEX_FOLDER_ID=b1gabkp48fg6cu6tqsec
TELEMOST_CAPTURE=true          # false on macOS
MAX_RECORDING_MINUTES=240
TELEMOST_AUDIO_BITRATE=64k
```

---

## Notes on SpeechKit Response Format

The exact diarization field names (`speakerTag` vs `channelTag`) depend on the SpeechKit API version and config. The parser in `transcribe.py` tries `speakerTag` first and falls back to `channelTag`. If the response structure differs from the fixture, adjust `_parse_response()` based on the actual response logged during the first live run. Add a debug log: `print(json.dumps(raw, ensure_ascii=False)[:2000])` temporarily in `_poll_until_done` to inspect the real response.
