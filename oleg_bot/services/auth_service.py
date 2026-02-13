"""
Authentication Service for Wookiee Bot
Handles password verification and user authorization
"""
import bcrypt
from typing import Dict, Set
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Service for managing user authentication"""

    def __init__(self, hashed_password: str):
        """
        Initialize auth service

        Args:
            hashed_password: bcrypt hashed password for bot access
        """
        self.hashed_password = hashed_password.encode() if isinstance(hashed_password, str) else hashed_password
        self.authenticated_users: Set[int] = set()

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
            self.authenticated_users.add(user_id)
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
        self.authenticated_users.discard(user_id)
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
