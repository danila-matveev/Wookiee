"""
Email-авторизация через Bitrix24
"""
import logging
from typing import Optional, Dict, Any

from agents.lyudmila.services.bitrix_service import BitrixService, BitrixAPIError
from agents.lyudmila.services.db_service import DBService
from agents.lyudmila.models.user import BotUser

logger = logging.getLogger(__name__)


class AuthService:
    """
    Авторизация пользователей через email + Bitrix24.

    Флоу:
    1. Пользователь вводит email
    2. Ищем email в Bitrix24
    3. Если найден и активен → авторизация
    4. Если уволен → отклонение
    5. Если не найден → ошибка
    """

    def __init__(self, bitrix_service: BitrixService, db_service: DBService):
        self.bitrix = bitrix_service
        self.db = db_service
        self._sessions: Dict[int, BotUser] = {}  # telegram_id → BotUser

        # Restore sessions from DB
        self._restore_sessions()

    def _restore_sessions(self) -> None:
        """Восстановить сессии из БД при старте"""
        try:
            users = self.db.get_all_active_users()
            for u in users:
                self._sessions[u['telegram_id']] = BotUser(
                    telegram_id=u['telegram_id'],
                    bitrix_user_id=u['bitrix_user_id'],
                    email=u['email'],
                    first_name=u.get('first_name', ''),
                    last_name=u.get('last_name', ''),
                    telegram_username=u.get('telegram_username'),
                    timezone=u.get('timezone', 'Europe/Moscow'),
                    digest_enabled=bool(u.get('digest_enabled', 1)),
                    digest_time=u.get('digest_time', '09:00'),
                )
            logger.info(f"Restored {len(self._sessions)} sessions from DB")
        except Exception as e:
            logger.exception(f"Failed to restore sessions: {e}")

    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Найти сотрудника в Bitrix24 по email.

        Returns:
            Dict с данными сотрудника или None
        """
        try:
            user = await self.bitrix.get_user_by_email(email.strip().lower())
            if not user:
                return None
            return user
        except BitrixAPIError as e:
            logger.error(f"Bitrix search by email failed: {e}")
            raise

    async def authenticate(
        self,
        telegram_id: int,
        telegram_username: Optional[str],
        bitrix_user: Dict[str, Any],
    ) -> BotUser:
        """
        Авторизовать пользователя.

        Args:
            telegram_id: Telegram user ID
            telegram_username: Telegram username
            bitrix_user: данные из Bitrix24 API

        Returns:
            BotUser
        """
        user_id = int(bitrix_user.get('ID', 0))
        first_name = bitrix_user.get('NAME', '')
        last_name = bitrix_user.get('LAST_NAME', '')
        email = bitrix_user.get('EMAIL', '')

        # Проверяем что пользователь активен
        if not bitrix_user.get('ACTIVE', True):
            raise ValueError("Аккаунт деактивирован в Bitrix24")

        # Сохраняем в БД
        self.db.create_user(
            telegram_id=telegram_id,
            bitrix_user_id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            telegram_username=telegram_username,
        )

        # Создаём сессию
        bot_user = BotUser(
            telegram_id=telegram_id,
            bitrix_user_id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            telegram_username=telegram_username,
        )
        self._sessions[telegram_id] = bot_user

        logger.info(f"User authenticated: tg={telegram_id} bitrix={user_id} ({first_name} {last_name})")
        self.db.log_action(telegram_id, "auth_login", user_id)

        return bot_user

    def is_authenticated(self, telegram_id: int) -> bool:
        """Проверить авторизован ли пользователь"""
        return telegram_id in self._sessions

    def get_user(self, telegram_id: int) -> Optional[BotUser]:
        """Получить BotUser по telegram_id"""
        user = self._sessions.get(telegram_id)
        if user:
            self.db.update_last_active(telegram_id)
        return user

    def logout(self, telegram_id: int) -> None:
        """Выход из системы"""
        if telegram_id in self._sessions:
            self.db.log_action(telegram_id, "auth_logout")
            del self._sessions[telegram_id]
            logger.info(f"User logged out: tg={telegram_id}")

    @property
    def authenticated_users(self) -> Dict[int, BotUser]:
        """Все авторизованные пользователи"""
        return dict(self._sessions)
