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

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("services.telemost_recorder.speakers.os.getenv", return_value="fake-openrouter-key"):
        result = resolve_speakers(segments, participants, employees)

    assert result == {"Speaker 1": "Данила Матвеев", "Speaker 2": "Лиля Петрова"}


def test_resolve_speakers_returns_empty_on_llm_error() -> None:
    segments = [TranscriptSegment(speaker="Speaker 1", start_ms=0, end_ms=1000, text="Текст")]
    with patch("urllib.request.urlopen", side_effect=Exception("network error")), \
         patch("services.telemost_recorder.speakers.os.getenv", return_value="fake-key"):
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
