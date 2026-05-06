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
