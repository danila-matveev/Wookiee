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

    # Вебхук (основной способ подключения)
    portal_domain: str = os.getenv('BITRIX_PORTAL_DOMAIN', '')
    webhook_url: str = os.getenv('BITRIX_WEBHOOK_URL', '')

    # OAuth приложение (для будущего использования)
    client_id: str = os.getenv('BITRIX_CLIENT_ID', '')
    client_secret: str = os.getenv('BITRIX_CLIENT_SECRET', '')

    def __post_init__(self):
        # Убеждаемся что webhook_url заканчивается на /
        if self.webhook_url and not self.webhook_url.endswith('/'):
            self.webhook_url += '/'


# Глобальная конфигурация
config = BitrixConfig()
