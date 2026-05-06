"""
Live Phase 2 integration test: joins a real Telemost meeting, records audio,
transcribes via SpeechKit. Run on Linux with PulseAudio.

Usage:
    pytest tests/services/telemost_recorder/test_live_phase2.py \
        --url="https://telemost.360.yandex.ru/j/XXXX" \
        -v -s

Linux only — audio capture requires PulseAudio.
"""
import asyncio
import platform

import pytest

from services.telemost_recorder.join import run_session


@pytest.mark.anyio
@pytest.mark.skipif(platform.system() != "Linux", reason="PulseAudio required")
async def test_live_phase2(telemost_url: str) -> None:
    print(f"\n→ Starting Phase 2 session: {telemost_url}")
    print("→ Bot will record. End the meeting or press Ctrl+C to trigger transcription.")

    await asyncio.wait_for(run_session(telemost_url), timeout=300)
