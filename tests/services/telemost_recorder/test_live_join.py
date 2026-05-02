"""
Live integration test: joins a real Telemost meeting.

Requires the host to create a Telemost meeting and pass its URL:
    pytest tests/services/telemost_recorder/test_live_join.py \
        --url="https://telemost.yandex.ru/j/XXXX" \
        -v -s

Outcomes:
  IN_MEETING    → test passes immediately, screenshot saved to data/telemost/<id>/
  WAITING_ROOM  → test prints admission instruction and passes (waiting room = Phase 1 success)
  FAILED        → test fails with reason

Phase 1 acceptance: both IN_MEETING and WAITING_ROOM count as success.
"""
from pathlib import Path

import pytest

from services.telemost_recorder.join import join_meeting
from services.telemost_recorder.state import MeetingStatus


@pytest.mark.anyio
async def test_live_join(telemost_url: str) -> None:
    print(f"\n→ Joining: {telemost_url}")
    meeting = await join_meeting(telemost_url)

    print(f"→ Status: {meeting.status.value}")
    if meeting.fail_reason:
        print(f"→ Fail reason: {meeting.fail_reason.value}")

    assert meeting.status in (MeetingStatus.IN_MEETING, MeetingStatus.WAITING_ROOM), (
        f"Expected IN_MEETING or WAITING_ROOM, got {meeting.status.value}"
        + (f" ({meeting.fail_reason.value})" if meeting.fail_reason else "")
    )

    if meeting.status == MeetingStatus.IN_MEETING:
        assert meeting.screenshot_path is not None, "Screenshot path must be set for IN_MEETING"
        assert Path(meeting.screenshot_path).exists(), (
            f"Screenshot file not found: {meeting.screenshot_path}"
        )
        print(f"✓ Bot is IN_MEETING")
        print(f"  Screenshot: {meeting.screenshot_path}")
    else:
        print("⏳ Bot is in WAITING_ROOM")
        print("  → Admit 'Wookiee Recorder' in Telemost interface to complete the phase")
        print(f"  Meeting ID: {meeting.meeting_id}")
