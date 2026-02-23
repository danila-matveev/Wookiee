"""
Task model for Lyudmila Bot
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class TaskStructure:
    """Структурированная задача после обработки ИИ"""
    is_valid_task: bool = True
    feedback: str = ""
    title: str = ""
    description: str = ""
    target_result: str = ""
    assignee_name: Optional[str] = None
    assignee_bitrix_id: Optional[int] = None
    deadline_text: Optional[str] = None
    deadline: Optional[datetime] = None
    observers: List[str] = field(default_factory=list)
    observer_bitrix_ids: List[int] = field(default_factory=list)
    co_executors: List[str] = field(default_factory=list)
    co_executor_bitrix_ids: List[int] = field(default_factory=list)
    checklist: List[str] = field(default_factory=list)
    clarification_needed: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def format_preview(self) -> str:
        """Форматирует превью задачи для Telegram (HTML)"""
        lines = []
        lines.append(f"<b>📋 Задача:</b> {self.title}")
        lines.append("")

        if self.description:
            lines.append(f"<b>📝 Описание:</b>")
            lines.append(self.description)
            lines.append("")

        if self.target_result:
            lines.append(f"<b>🎯 Целевой результат:</b>")
            lines.append(self.target_result)
            lines.append("")

        if self.assignee_name:
            lines.append(f"<b>👤 Исполнитель:</b> {self.assignee_name}")

        if self.deadline_text:
            lines.append(f"<b>📅 Дедлайн:</b> {self.deadline_text}")

        if self.observers:
            lines.append(f"<b>👁 Наблюдатели:</b> {', '.join(self.observers)}")

        if self.co_executors:
            lines.append(f"<b>👥 Соисполнители:</b> {', '.join(self.co_executors)}")

        if self.checklist:
            lines.append("")
            lines.append("<b>✅ Чеклист:</b>")
            for i, item in enumerate(self.checklist, 1):
                lines.append(f"  {i}. {item}")

        if self.suggestions:
            lines.append("")
            lines.append("<b>💡 Предложения Людмилы:</b>")
            for s in self.suggestions:
                lines.append(f"  • {s}")

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict) -> "TaskStructure":
        """Создаёт TaskStructure из словаря (ответ LLM)"""
        return cls(
            is_valid_task=data.get("is_valid_task", True),
            feedback=data.get("feedback", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            target_result=data.get("target_result", ""),
            assignee_name=data.get("assignee_name"),
            assignee_bitrix_id=data.get("assignee_bitrix_id"),
            deadline_text=data.get("deadline_text"),
            observers=data.get("observers", []),
            observer_bitrix_ids=data.get("observer_bitrix_ids", []),
            co_executors=data.get("co_executors", []),
            co_executor_bitrix_ids=data.get("co_executor_bitrix_ids", []),
            checklist=data.get("checklist", []),
            clarification_needed=data.get("clarification_needed", []),
            suggestions=data.get("suggestions", []),
        )

    def to_dict(self) -> dict:
        """Конвертирует в словарь (FSM state + передача в LLM)"""
        return {
            "is_valid_task": self.is_valid_task,
            "feedback": self.feedback,
            "title": self.title,
            "description": self.description,
            "target_result": self.target_result,
            "assignee_name": self.assignee_name,
            "assignee_bitrix_id": self.assignee_bitrix_id,
            "deadline_text": self.deadline_text,
            "observers": self.observers,
            "observer_bitrix_ids": self.observer_bitrix_ids,
            "co_executors": self.co_executors,
            "co_executor_bitrix_ids": self.co_executor_bitrix_ids,
            "checklist": self.checklist,
            "clarification_needed": self.clarification_needed,
            "suggestions": self.suggestions,
        }
