"""
Authentication Service for Wookiee Bot
Handles password verification and user authorization
"""
import json
import bcrypt
from pathlib import Path
from typing import Optional, Set
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Service for managing user authentication"""

    def __init__(self, hashed_password: str, persistence_path: Optional[str] = None):
        self.hashed_password = hashed_password.encode() if isinstance(hashed_password, str) else hashed_password
        self._persistence_path = Path(persistence_path) if persistence_path else None
        self._authenticated_users: Set[int] = set()
        self._load_users()

    def _load_users(self) -> None:
        """Load authenticated users from disk."""
        if not self._persistence_path or not self._persistence_path.exists():
            return
        try:
            data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            self._authenticated_users = set(data.get("user_ids", []))
            logger.info(f"Loaded {len(self._authenticated_users)} authenticated users from disk")
        except Exception as e:
            logger.warning(f"Failed to load authenticated users: {e}")

    def reload(self) -> None:
        """Reload authenticated users from disk (used by long-lived agents)."""
        self._load_users()

    @property
    def authenticated_users(self) -> Set[int]:
        """Always return up-to-date users by reloading from disk."""
        self.reload()
        return self._authenticated_users

    def _save_users(self) -> None:
        """Persist authenticated users to disk."""
        if not self._persistence_path:
            return
        try:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(
                json.dumps({"user_ids": sorted(self._authenticated_users)}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save authenticated users: {e}")

    def verify_password(self, password: str) -> bool:
        """
        Verify password against stored hash

        Args:
            password: Plain text password to verify

        Returns:
            True if password is correct, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode(), self.hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def authenticate_user(self, user_id: int, password: str) -> bool:
        """
        Authenticate user with password

        Args:
            user_id: Telegram user ID
            password: Password provided by user

        Returns:
            True if authentication successful, False otherwise
        """
        if self.verify_password(password):
            self._authenticated_users.add(user_id)
            self._save_users()
            logger.info(f"User {user_id} authenticated successfully")
            return True
        else:
            logger.warning(f"Failed authentication attempt for user {user_id}")
            return False

    def is_authenticated(self, user_id: int) -> bool:
        """
        Check if user is already authenticated

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is authenticated, False otherwise
        """
        return user_id in self.authenticated_users

    def logout_user(self, user_id: int) -> None:
        """
        Log out user (remove from authenticated set)

        Args:
            user_id: Telegram user ID
        """
        self._authenticated_users.discard(user_id)
        self._save_users()
        logger.info(f"User {user_id} logged out")

    @staticmethod
    def generate_password_hash(password: str) -> str:
        """
        Generate bcrypt hash for a password

        Args:
            password: Plain text password

        Returns:
            Bcrypt hash as string
        """
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
