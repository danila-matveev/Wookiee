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
    FAILED = "FAILED"


class FailReason(str, Enum):
    INVALID_URL = "INVALID_URL"
    MEETING_NOT_FOUND = "MEETING_NOT_FOUND"
    JOIN_TIMEOUT = "JOIN_TIMEOUT"
    UI_DETECTION_FAILED = "UI_DETECTION_FAILED"
    NOT_ADMITTED = "NOT_ADMITTED"


_VALID_TRANSITIONS: dict[MeetingStatus, set[MeetingStatus]] = {
    MeetingStatus.PENDING: {MeetingStatus.JOINING, MeetingStatus.FAILED},
    MeetingStatus.JOINING: {MeetingStatus.IN_MEETING, MeetingStatus.WAITING_ROOM, MeetingStatus.FAILED},
    MeetingStatus.WAITING_ROOM: {MeetingStatus.IN_MEETING, MeetingStatus.FAILED},
    MeetingStatus.IN_MEETING: set(),
    MeetingStatus.FAILED: set(),
}


@dataclass
class Meeting:
    url: str
    meeting_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: MeetingStatus = field(default=MeetingStatus.PENDING)
    fail_reason: Optional[FailReason] = field(default=None)
    screenshot_path: Optional[str] = field(default=None)
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
