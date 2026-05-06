# Telemost Recorder Phase 2 — Audio Capture + Transcription + Speaker Matching

**Date:** 2026-05-06
**Status:** Approved — ready for planning
**Scope:** Audio recording during meeting → SpeechKit transcription with diarization → speaker name resolution via Bitrix24 + LLM

---

## 1. Goal

Extend the Phase 1 browser bot so that after joining a meeting it:
1. Records all audio from the meeting into a file
2. After the meeting ends, transcribes the audio via SpeechKit v3 with speaker diarization
3. Resolves anonymous `Speaker 1 / Speaker 2` labels to real employee names using Bitrix24 roster + Telemost participant list + LLM
4. Outputs a clean, named transcript ready for Phase 3 (Notion publishing)

---

## 2. New FSM States

```
IN_MEETING
  → RECORDING        (ffmpeg started, audio being written)
    → TRANSCRIBING   (meeting ended, audio sent to SpeechKit)
      → DONE         (transcript ready)
      → FAILED(TRANSCRIPTION_FAILED)
    → FAILED(RECORDING_FAILED)
```

Phase 2 terminal success state: `DONE` with `transcript_path` set.

---

## 3. Architecture

```
run_session()
  │
  ├─ _execute_join() → IN_MEETING
  │
  ├─ AudioCapture.start()                   audio.py
  │    create_pulse_null_sink()             PulseAudio: virtual sink "telemost_<id>"
  │    ffmpeg -f pulse -i <monitor>         record from sink monitor
  │         → data/telemost/<id>/audio.opus (Opus, 48kHz mono, 64kbps)
  │    meeting.transition(RECORDING)
  │    emit {"status": "RECORDING", ...}
  │
  ├─ [meeting loop]
  │    screenshot every SCREENSHOT_INTERVAL seconds
  │    extract_participants() every 60s     → meeting.participants[]
  │    detect_meeting_ended() every 10s    → breaks loop when meeting ends
  │
  ├─ AudioCapture.stop()                    ffmpeg terminated, file finalized
  │
  └─ transcribe_audio()                     transcribe.py
       load_speakers()                      data/speakers.yml (Bitrix roster)
       POST SpeechKit v3 longRunningRecognize
           audioEncoding: OGG_OPUS
           diarizationConfig: {maxSpeakerCount: 10}
       poll every 5s until done
       parse_transcript()                   → [{speaker, start_ms, text}, ...]
       resolve_speakers()                   LLM: speakers.yml + participants + transcript
           → {Speaker 1: "Данила Матвеев", Speaker 2: "Лиля Петрова"}
       apply_speaker_names()
       write transcript.json + transcript.txt
       meeting.transition(DONE)
       emit {"status": "DONE", "transcript": "data/telemost/<id>/transcript.txt"}
```

---

## 4. New Files

| File | Responsibility |
|------|---------------|
| `services/telemost_recorder/audio.py` | PulseAudio null sink lifecycle + ffmpeg record/stop |
| `services/telemost_recorder/transcribe.py` | SpeechKit v3 REST async client + response parser |
| `services/telemost_recorder/speakers.py` | Bitrix24 roster sync + LLM speaker resolution |
| `scripts/sync_speakers.py` | CLI shim: refresh data/speakers.yml from Bitrix24 |

Modified files:
- `services/telemost_recorder/state.py` — add RECORDING, TRANSCRIBING, DONE states + RECORDING_FAILED, TRANSCRIPTION_FAILED reasons
- `services/telemost_recorder/join.py` — integrate AudioCapture into run_session; add extract_participants(), detect_meeting_ended()
- `services/telemost_recorder/config.py` — add SPEECHKIT_*, TELEMOST_CAPTURE, MAX_RECORDING_MINUTES
- `deploy/Dockerfile.telemost_recorder` — add PulseAudio + ffmpeg

---

## 5. Audio Capture Detail

### PulseAudio null sink
```bash
# Created before browser launch, destroyed after recording
pactl load-module module-null-sink sink_name=telemost_<id> sink_properties=device.description=TelemostCapture
# ffmpeg records from monitor (loopback of sink output)
ffmpeg -f pulse -i telemost_<id>.monitor -c:a libopus -b:a 64k -ar 48000 -ac 1 audio.opus
```

Chromium uses system default PulseAudio sink → all WebRTC audio output (other participants' voices) goes to this sink → ffmpeg captures it.

The bot's own microphone is already muted at the WebRTC level (Phase 1 `_MEDIA_MUTE_SCRIPT`), so only incoming audio is recorded.

### macOS (local dev)
`TELEMOST_CAPTURE=false` disables audio capture. Transcription module can accept a pre-recorded `.opus` file via CLI for local testing:
```bash
python scripts/telemost_record.py transcribe data/telemost/<id>/audio.opus
```

### Safety limits
- `MAX_RECORDING_MINUTES=240` (4 hours) — hard stop to prevent runaway recording
- Opus 64kbps × 4h = ~115 MB — within SpeechKit inline upload limit

---

## 6. Meeting End Detection

`detect_meeting_ended()` checks every 10 seconds for one of:
- Telemost "meeting ended" overlay (text: "Встреча завершена", "Meeting ended")
- Page redirected away from meeting URL
- No participants left (participant count == 1, only the bot)

When detected: sets a flag, breaks the screenshot loop, triggers `AudioCapture.stop()`.

---

## 7. SpeechKit Transcription Detail

### Endpoint
```
POST https://stt.api.cloud.yandex.net/speech/v3/stt:longRunningRecognize
Authorization: Api-Key <SPEECHKIT_API_KEY>
x-folder-id: <YANDEX_FOLDER_ID>
```

### Request
```json
{
  "config": {
    "specification": {
      "languageCode": "ru-RU",
      "model": "general",
      "audioEncoding": "OGG_OPUS",
      "sampleRateHertz": 48000,
      "audioChannelCount": 1
    },
    "speechAnalysis": {
      "enableSpeakerAnalysis": true,
      "speakerLabeling": {}
    }
  },
  "audio": {
    "content": "<base64-encoded audio>"
  }
}
```

### Polling
```
GET https://operation.api.cloud.yandex.net/operations/{operation_id}
Authorization: Api-Key <key>
```
Poll every 5s, timeout 30 min.

### Response parsing
SpeechKit returns chunks with `channelTag` or `speakerTag` identifying the speaker cluster. Parse into:
```python
[{"speaker": "Speaker 1", "start_ms": 15000, "end_ms": 18000, "text": "Добрый день"}]
```

---

## 8. Speakers.yml Sync (Bitrix24)

### Format
```yaml
# data/speakers.yml — synced from Bitrix24, do not edit manually
updated_at: "2026-05-06T14:00:00"
employees:
  - bitrix_id: 1
    name: "Данила Матвеев"
    short_name: "Данила"
  - bitrix_id: 2223
    name: "Лиля Петрова"
    short_name: "Лиля"
```

### Sync script
```bash
python scripts/sync_speakers.py        # one-shot refresh
```
Calls `Bitrix_rest_api/user.get` with `ACTIVE=Y`, writes `data/speakers.yml`.
Intended to run as a weekly cron or on-demand before a meeting.

---

## 9. Speaker Name Resolution (LLM)

After transcription:
1. Load `data/speakers.yml` (full roster)
2. `meeting.participants` = names extracted from Telemost UI during meeting
3. Intersect: filter roster to participants who were in this meeting
4. Prompt Gemini Flash (MAIN tier, OpenRouter):
   > "Given this meeting had participants: [Данила Матвеев, Лиля Петрова].
   > The transcript has Speaker 1, Speaker 2.
   > Based on the transcript content, map each speaker to a participant name.
   > Return JSON: {Speaker 1: name, Speaker 2: name}"
5. Apply mapping to all transcript segments

If LLM confidence is low or participant count doesn't match speaker count: keep `Speaker N` labels and log a warning. Never hallucinate names.

---

## 10. Output Files

```
data/telemost/<meeting_id>/
  audio.opus              raw recording
  screenshot_001.png      ...
  screenshot_NNN.png
  transcript.json         structured: [{speaker, start_ms, end_ms, text}, ...]
  transcript.txt          human-readable:
                            [00:00:15] Данила Матвеев: Добрый день
                            [00:00:18] Лиля Петрова: Да, начнём
```

---

## 11. Participant Extraction from Telemost UI

`extract_participants()` called every 60 seconds during meeting:
1. Click "Участники" button in Telemost toolbar
2. Scrape participant names from the panel
3. Close panel
4. Update `meeting.participants` (deduplicated, excluding "Wookiee Recorder")

Fallback: if panel can't be opened, use names from video tile labels (visible in screenshots).

---

## 12. Config Changes

```python
# services/telemost_recorder/config.py additions
SPEECHKIT_API_KEY: str = os.getenv("SPEECHKIT_API_KEY", "")
YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
TELEMOST_CAPTURE: bool = os.getenv("TELEMOST_CAPTURE", "true").lower() != "false"
MAX_RECORDING_MINUTES: int = int(os.getenv("MAX_RECORDING_MINUTES", "240"))
AUDIO_BITRATE: str = os.getenv("TELEMOST_AUDIO_BITRATE", "64k")
SPEAKERS_FILE: Path = _PROJECT_ROOT / "data" / "speakers.yml"
```

---

## 13. Dockerfile Changes

Add to `deploy/Dockerfile.telemost_recorder`:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    pulseaudio \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

---

## 14. Testing Strategy

| Test | Type | Requires |
|------|------|---------|
| `test_state_machine_phase2.py` | Unit | — |
| `test_transcribe_mock.py` | Unit | pre-recorded `.opus` fixture |
| `test_sync_speakers.py` | Unit | mock Bitrix API |
| `test_speaker_resolution.py` | Unit | mock LLM response |
| `test_live_recording.py` | Integration | real meeting + Linux server |

---

## 15. Phase 2 Acceptance Criteria

1. Bot records audio during a real Telemost meeting
2. After meeting ends (detected automatically), SpeechKit returns transcript
3. `transcript.txt` contains speaker-labeled segments with real names from Bitrix
4. All unit tests pass
5. `data/telemost/<id>/audio.opus` file is non-empty and playable

---

## 16. Out of Scope for Phase 2

- Notion publishing (Phase 3)
- LLM summary (Phase 3)
- Supabase persistence (Phase 3)
- Bitrix24 Calendar auto-join (Phase 4)
- Parallel meetings (Phase 5)
