"""Tests for the recorder worker loop."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.workers.recorder_worker import process_one


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")
_MEETING_URL = "https://telemost.yandex.ru/j/abc"


@pytest.mark.asyncio
async def test_process_one_picks_queued_and_spawns():
    pick = {"id": _MEETING_ID, "meeting_url": _MEETING_URL, "triggered_by": 555}
    spawned: dict = {}

    def fake_spawn(*, meeting_id, meeting_url, data_dir, **kwargs):
        spawned["meeting_id"] = meeting_id
        spawned["url"] = meeting_url
        spawned["data_dir"] = data_dir
        return "container_abc"

    async def fake_finalize(meeting_id, exit_code, logs, timed_out):
        spawned["finalized"] = (meeting_id, exit_code, timed_out)

    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.spawn_recorder_container",
        side_effect=fake_spawn,
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.monitor_container",
        AsyncMock(return_value={"exit_code": 0, "logs": "done", "timed_out": False}),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker._finalize_recording",
        AsyncMock(side_effect=fake_finalize),
    ):
        result = await process_one()

    assert result is True
    assert spawned["meeting_id"] == _MEETING_ID
    assert spawned["url"] == _MEETING_URL
    assert spawned["finalized"] == (_MEETING_ID, 0, False)


@pytest.mark.asyncio
async def test_process_one_returns_false_when_queue_empty():
    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(return_value=None),
    ):
        result = await process_one()
    assert result is False


@pytest.mark.asyncio
async def test_process_one_marks_failed_on_nonzero_exit():
    pick = {"id": _MEETING_ID, "meeting_url": _MEETING_URL, "triggered_by": 555}
    finalize_args: dict = {}

    async def fake_finalize(meeting_id, exit_code, logs, timed_out):
        finalize_args.update(exit_code=exit_code, logs=logs, timed_out=timed_out)

    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.spawn_recorder_container",
        return_value="cid",
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.monitor_container",
        AsyncMock(return_value={"exit_code": 1, "logs": "boom", "timed_out": False}),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker._finalize_recording",
        AsyncMock(side_effect=fake_finalize),
    ):
        await process_one()

    assert finalize_args["exit_code"] == 1
    assert finalize_args["timed_out"] is False


@pytest.mark.asyncio
async def test_process_one_stops_container_on_timeout():
    pick = {"id": _MEETING_ID, "meeting_url": _MEETING_URL, "triggered_by": 555}
    stopped: list[str] = []

    def fake_stop(cid: str) -> None:
        stopped.append(cid)

    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.spawn_recorder_container",
        return_value="cid_xyz",
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.monitor_container",
        AsyncMock(return_value={"exit_code": -1, "logs": "tail", "timed_out": True}),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.stop_container",
        side_effect=fake_stop,
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker._finalize_recording",
        AsyncMock(),
    ):
        await process_one()

    assert stopped == ["cid_xyz"]


@pytest.mark.asyncio
async def test_finalize_marks_postprocessing_on_clean_exit_with_artefacts(tmp_path):
    """When recorder exits 0 and raw_segments.json exists, status -> postprocessing."""
    from services.telemost_recorder_api.workers import recorder_worker

    artefact_dir = tmp_path / str(_MEETING_ID)
    artefact_dir.mkdir()
    (artefact_dir / "raw_segments.json").write_text(
        '[{"speaker":"Speaker 0","start_ms":0,"end_ms":1000,"text":"hi"}]'
    )
    (artefact_dir / "audio.opus").write_bytes(b"opus_bytes")

    captured: dict = {}

    class FakeConn:
        async def execute(self, query, *args):
            captured["query"] = query
            captured["args"] = args

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch.object(recorder_worker, "DATA_DIR", tmp_path), patch(
        "services.telemost_recorder_api.workers.recorder_worker.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.upload_audio_to_storage",
        AsyncMock(
            return_value={
                "signed_url": "https://example.supabase.co/storage/v1/object/sign/telemost-audio/xxx",
                "expires_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
                "object_key": "meetings/x/audio.opus",
            }
        ),
    ):
        await recorder_worker._finalize_recording(_MEETING_ID, 0, "logs", False)

    assert "postprocessing" in captured["query"]
    assert captured["args"][0] == _MEETING_ID
    assert captured["args"][2] == (
        "https://example.supabase.co/storage/v1/object/sign/telemost-audio/xxx"
    )
    assert captured["args"][3] == datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_finalize_marks_failed_on_nonzero_exit(tmp_path):
    from services.telemost_recorder_api.workers import recorder_worker

    captured: dict = {}

    class FakeConn:
        async def execute(self, query, *args):
            captured["query"] = query
            captured["args"] = args

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch.object(recorder_worker, "DATA_DIR", tmp_path), patch(
        "services.telemost_recorder_api.workers.recorder_worker.get_pool",
        AsyncMock(return_value=FakePool()),
    ):
        await recorder_worker._finalize_recording(_MEETING_ID, 137, "OOM", False)

    assert "failed" in captured["query"]
    assert "exit_code=137" in captured["args"][1]


@pytest.mark.asyncio
async def test_finalize_marks_failed_with_timeout_reason(tmp_path):
    from services.telemost_recorder_api.workers import recorder_worker

    captured: dict = {}

    class FakeConn:
        async def execute(self, query, *args):
            captured["query"] = query
            captured["args"] = args

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch.object(recorder_worker, "DATA_DIR", tmp_path), patch(
        "services.telemost_recorder_api.workers.recorder_worker.get_pool",
        AsyncMock(return_value=FakePool()),
    ):
        await recorder_worker._finalize_recording(_MEETING_ID, -1, "tail", True)

    assert "failed" in captured["query"]
    assert "timeout" in captured["args"][1].lower()
