"""
Конфигурация интеграции с Bitrix24 REST API

Настройки загружаются из переменных окружения (.env файл).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")


@dataclass
class BitrixConfig:
    """Конфигурация подключения к Bitrix24"""

    # Данные приложения OAuth
    portal_domain: str = os.getenv('BITRIX_PORTAL_DOMAIN', '')
    client_id: str = os.getenv('BITRIX_CLIENT_ID', '')
    client_secret: str = os.getenv('BITRIX_CLIENT_SECRET', '')
    redirect_uri: str = os.getenv('BITRIX_REDIRECT_URI', 'http://localhost:8000/callback')

    # Файл для хранения токенов
    tokens_file: str = str(project_root / '.bitrix_tokens.json')

    @property
    def oauth_authorize_url(self) -> str:
        """URL для авторизации пользователя"""
        return f"https://{self.portal_domain}/oauth/authorize/"

    @property
    def oauth_token_url(self) -> str:
        """URL для обмена кода на токены"""
        return "https://oauth.bitrix.info/oauth/token/"

    @property
    def rest_api_url(self) -> str:
        """Базовый URL REST API"""
        return f"https://{self.portal_domain}/rest/"

    def validate(self) -> bool:
        """Проверить наличие всех обязательных настроек"""
        required = [self.portal_domain, self.client_id, self.client_secret]
        return all(required)

    def get_missing_fields(self) -> list:
        """Получить список отсутствующих полей"""
        missing = []
        if not self.portal_domain:
            missing.append('BITRIX_PORTAL_DOMAIN')
        if not self.client_id:
            missing.append('BITRIX_CLIENT_ID')
        if not self.client_secret:
            missing.append('BITRIX_CLIENT_SECRET')
        return missing


# Глобальная конфигурация
config = BitrixConfig()
