"""
User models for Lyudmila Bot
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotUser:
    """Авторизованный пользователь бота"""
    telegram_id: int
    bitrix_user_id: int
    email: str
    first_name: str
    last_name: str
    telegram_username: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    timezone: str = "Europe/Moscow"
    digest_enabled: bool = True
    digest_time: str = "09:00"
    is_active: bool = True

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
