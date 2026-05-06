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
