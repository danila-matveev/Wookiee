"""
Meeting model for Lyudmila Bot
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class MeetingStructure:
    """Структурированная встреча после обработки ИИ"""
    title: str = ""
    description: str = ""
    preparation: str = ""
    pre_reading: str = ""
    datetime_text: Optional[str] = None
    start_dt: Optional[datetime] = None
    duration_minutes: int = 60
    attendees: List[str] = field(default_factory=list)
    attendee_bitrix_ids: List[int] = field(default_factory=list)
    link: Optional[str] = None
    clarification_needed: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def format_preview(self) -> str:
        """Форматирует превью встречи для Telegram (HTML)"""
        lines = []
        lines.append(f"<b>📅 Встреча:</b> {self.title}")
        lines.append("")

        if self.description:
            lines.append(f"<b>📝 Повестка:</b>")
            lines.append(self.description)
            lines.append("")

        if self.preparation:
            lines.append(f"<b>📚 Подготовить к встрече:</b>")
            lines.append(self.preparation)
            lines.append("")

        if self.pre_reading:
            lines.append(f"<b>📖 Изучить заранее:</b>")
            lines.append(self.pre_reading)
            lines.append("")

        if self.datetime_text:
            lines.append(f"<b>🕐 Дата:</b> {self.datetime_text}")

        lines.append(f"<b>⏱ Длительность:</b> {self.duration_minutes} мин")

        if self.attendees:
            lines.append(f"<b>👥 Участники:</b> {', '.join(self.attendees)}")

        if self.link:
            lines.append(f"<b>🔗 Ссылка:</b> {self.link}")

        if self.suggestions:
            lines.append("")
            lines.append("<b>💡 Предложения Людмилы:</b>")
            for s in self.suggestions:
                lines.append(f"  • {s}")

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingStructure":
        """Создаёт MeetingStructure из словаря (ответ LLM)"""
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            preparation=data.get("preparation", ""),
            pre_reading=data.get("pre_reading", ""),
            datetime_text=data.get("datetime_text"),
            duration_minutes=data.get("duration_minutes", 60),
            attendees=data.get("attendees", []),
            attendee_bitrix_ids=data.get("attendee_bitrix_ids", []),
            link=data.get("link"),
            clarification_needed=data.get("clarification_needed", []),
            suggestions=data.get("suggestions", []),
        )

    def to_dict(self) -> dict:
        """Конвертирует в словарь (FSM state + передача в LLM)"""
        return {
            "title": self.title,
            "description": self.description,
            "preparation": self.preparation,
            "pre_reading": self.pre_reading,
            "datetime_text": self.datetime_text,
            "duration_minutes": self.duration_minutes,
            "attendees": self.attendees,
            "attendee_bitrix_ids": self.attendee_bitrix_ids,
            "link": self.link,
            "clarification_needed": self.clarification_needed,
            "suggestions": self.suggestions,
        }
