"""Tests for postprocess_worker.process_one()."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.workers.postprocess_worker import (
    _update_meeting,
    process_one,
)


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_empty_segments_marks_done_without_llm():
    pick = {
        "id": _MEETING_ID, "raw_segments": [], "triggered_by": 555,
        "title": None, "invitees": [],
    }

    llm_called = False

    async def fake_llm(*a, **k):
        nonlocal llm_called
        llm_called = True
        return {}

    captured_update = {}

    async def fake_update(meeting_id, status, **fields):
        captured_update["meeting_id"] = meeting_id
        captured_update["status"] = status
        captured_update["fields"] = fields

    notify_called = False

    async def fake_notify(*a, **k):
        nonlocal notify_called
        notify_called = True

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(side_effect=fake_llm),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=fake_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(side_effect=fake_notify),
    ):
        result = await process_one()

    assert result is True
    assert llm_called is False
    assert captured_update["status"] == "done"
    assert captured_update["fields"]["summary"] == {"empty": True, "note": "no_speech_detected"}
    assert notify_called is True


@pytest.mark.asyncio
async def test_normal_segments_runs_llm_and_updates_done():
    pick = {
        "id": _MEETING_ID,
        "raw_segments": [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 25000, "text": "Привет"}],
        "triggered_by": 555, "title": "Test", "invitees": [],
    }

    llm_result = {
        "paragraphs": [{"speaker": "Полина", "start_ms": 0, "text": "Привет"}],
        "speakers_map": {"Speaker 0": "Полина"},
        "tags": ["прочее"],
        "summary": {
            "participants": ["Полина"], "topics": [], "decisions": [], "tasks": [],
        },
    }

    captured_update = {}

    async def fake_update(meeting_id, status, **fields):
        captured_update["status"] = status
        captured_update["fields"] = fields

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(return_value=llm_result),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=fake_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(),
    ):
        await process_one()

    assert captured_update["status"] == "done"
    assert captured_update["fields"]["tags"] == ["прочее"]
    assert captured_update["fields"]["speakers_map"] == {"Speaker 0": "Полина"}


@pytest.mark.asyncio
async def test_llm_failure_marks_failed():
    pick = {
        "id": _MEETING_ID,
        "raw_segments": [{"speaker": "S0", "start_ms": 0, "end_ms": 1, "text": "x"}],
        "triggered_by": 555, "title": None, "invitees": [],
    }
    captured_update = {}

    async def fake_update(meeting_id, status, **fields):
        captured_update["status"] = status
        captured_update["fields"] = fields

    from services.telemost_recorder_api.llm_postprocess import LLMPostprocessError

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(side_effect=LLMPostprocessError("bad json")),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=fake_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(),
    ):
        await process_one()

    assert captured_update["status"] == "failed"
    assert "bad json" in captured_update["fields"]["error"]


@pytest.mark.asyncio
async def test_unexpected_exception_marks_failed_and_notifies():
    """Non-LLM exception path: e.g. _update_meeting raises during the 'done' update.

    The except Exception branch should still flip status to 'failed' (via a second
    _update_meeting call) and call notify_meeting_result.
    """
    pick = {
        "id": _MEETING_ID,
        "raw_segments": [{"speaker": "S0", "start_ms": 0, "end_ms": 1, "text": "x"}],
        "triggered_by": 555, "title": None, "invitees": [],
    }

    llm_result = {
        "paragraphs": [],
        "speakers_map": {},
        "tags": [],
        "summary": {"participants": [], "topics": [], "decisions": [], "tasks": []},
    }

    update_calls: list[dict] = []

    async def flaky_update(meeting_id, status, **fields):
        # First call (status='done') — boom. Second call (status='failed') — succeeds.
        update_calls.append({"status": status, "fields": fields})
        if status == "done":
            raise RuntimeError("db went away")

    notify_calls: list = []

    async def fake_notify(meeting_id):
        notify_calls.append(meeting_id)

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(return_value=llm_result),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=flaky_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(side_effect=fake_notify),
    ):
        result = await process_one()

    assert result is True
    # Two update attempts: the failing 'done' and the recovery 'failed'.
    assert [c["status"] for c in update_calls] == ["done", "failed"]
    assert "unexpected" in update_calls[1]["fields"]["error"]
    assert "db went away" in update_calls[1]["fields"]["error"]
    assert notify_calls == [_MEETING_ID]


@pytest.mark.asyncio
async def test_status_back_to_postprocessing_resets_notified_at():
    """When _update_meeting flips status to 'postprocessing' (manual recovery
    / LLM retry), the SQL must clear notified_at so the notifier can re-send.

    Without this, notifier._claim_notification (UPDATE ... WHERE notified_at
    IS NULL RETURNING) returns None forever and the user is stuck with the
    stale DM.
    """
    captured: dict = {}

    class FakeConn:
        async def execute(self, query, *args):
            captured["query"] = query
            captured["args"] = args

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker.get_pool",
        AsyncMock(return_value=FakePool()),
    ):
        await _update_meeting(_MEETING_ID, "postprocessing", error=None)

    query = captured["query"]
    assert "notified_at = NULL" in query, (
        f"expected 'notified_at = NULL' clause in query when flipping to "
        f"postprocessing, got: {query!r}"
    )
    # Sanity: status placeholder still present.
    assert "status = $2" in query
    # Args: (meeting_id, 'postprocessing', None) — notified_at clause must NOT
    # consume a placeholder (it's a literal NULL), so error remains $3.
    assert captured["args"] == (_MEETING_ID, "postprocessing", None)


@pytest.mark.asyncio
async def test_update_to_done_does_not_touch_notified_at():
    """Regression guard: the notified_at reset must be scoped to
    status='postprocessing' only. Normal done/failed transitions must leave
    notified_at alone so the idempotency-gate keeps working.
    """
    captured: dict = {}

    class FakeConn:
        async def execute(self, query, *args):
            captured["query"] = query

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker.get_pool",
        AsyncMock(return_value=FakePool()),
    ):
        await _update_meeting(_MEETING_ID, "done", tags=["прочее"])

    assert "notified_at" not in captured["query"], (
        f"notified_at must not appear in done-transition query, got: "
        f"{captured['query']!r}"
    )
