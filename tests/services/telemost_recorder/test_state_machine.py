import pytest
from services.telemost_recorder.state import FailReason, Meeting, MeetingStatus


def test_initial_status_is_pending() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    assert m.status == MeetingStatus.PENDING


def test_pending_to_joining() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    assert m.status == MeetingStatus.JOINING


def test_joining_to_in_meeting() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    assert m.status == MeetingStatus.IN_MEETING


def test_joining_to_waiting_room() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.WAITING_ROOM)
    assert m.status == MeetingStatus.WAITING_ROOM


def test_waiting_room_to_in_meeting() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.WAITING_ROOM)
    m.transition(MeetingStatus.IN_MEETING)
    assert m.status == MeetingStatus.IN_MEETING


def test_waiting_room_to_failed() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.WAITING_ROOM)
    m.transition(MeetingStatus.FAILED, FailReason.NOT_ADMITTED)
    assert m.status == MeetingStatus.FAILED
    assert m.fail_reason == FailReason.NOT_ADMITTED


def test_pending_directly_to_in_meeting_is_invalid() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.IN_MEETING)


def test_in_meeting_can_transition_to_recording() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    m.transition(MeetingStatus.RECORDING)
    assert m.status == MeetingStatus.RECORDING


def test_failed_is_terminal() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.FAILED, FailReason.JOIN_TIMEOUT)
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.JOINING)


def test_meeting_id_is_unique() -> None:
    m1 = Meeting(url="https://telemost.yandex.ru/j/123")
    m2 = Meeting(url="https://telemost.yandex.ru/j/123")
    assert m1.meeting_id != m2.meeting_id
