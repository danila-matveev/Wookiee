"""
Authentication handler — adapted from v1 for v2 architecture.
"""
import json
import logging
from pathlib import Path
from typing import Set

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from agents.oleg import config

logger = logging.getLogger(__name__)

router = Router()


class AuthStates(StatesGroup):
    waiting_for_password = State()


class AuthService:
    """Simple file-based auth service."""

    def __init__(self):
        self.auth_enabled = config.AUTH_ENABLED
        self.hashed_password = config.HASHED_PASSWORD
        self._authenticated: Set[int] = set()
        self._load_users()

    def _load_users(self) -> None:
        path = Path(config.USERS_FILE_PATH)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._authenticated = set(data.get("users", []))
            except Exception:
                pass

    def _save_users(self) -> None:
        path = Path(config.USERS_FILE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"users": list(self._authenticated)}))

    def is_authenticated(self, user_id: int) -> bool:
        if not self.auth_enabled:
            return True
        return user_id in self._authenticated

    def register_user(self, user_id: int) -> None:
        self._authenticated.add(user_id)
        self._save_users()

    def verify_password(self, password: str) -> bool:
        import hashlib
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return hashed == self.hashed_password


def check_auth(user_id: int, auth_service: AuthService) -> bool:
    """Check if user is authenticated."""
    return auth_service.is_authenticated(user_id)
