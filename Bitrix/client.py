"""
OAuth 2.0 клиент для Bitrix24 REST API

Использование:
    from Bitrix.client import BitrixClient

    client = BitrixClient()

    # Шаг 1: Получить URL для авторизации
    print(client.get_auth_url())

    # Шаг 2: После авторизации обменять код на токены
    client.authorize('код_из_redirect_url')

    # Шаг 3: Делать API запросы
    result = client.call('user.current')
    print(result)
"""

import json
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlencode

from Bitrix.config import config


class BitrixAuthError(Exception):
    """Ошибка авторизации Bitrix24"""
    pass


class BitrixAPIError(Exception):
    """Ошибка API Bitrix24"""
    pass


class BitrixClient:
    """
    OAuth 2.0 клиент для Bitrix24 REST API.

    Поддерживает:
    - Авторизацию через OAuth 2.0
    - Автоматическое обновление токенов
    - Rate limiting (2 запроса/сек)
    - Хранение токенов в файле
    """

    def __init__(self):
        self.config = config
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[datetime] = None
        self._session = requests.Session()
        self._last_request_time: float = 0

        # Загружаем токены из файла при инициализации
        self._load_tokens()

    def get_auth_url(self) -> str:
        """
        Получить URL для авторизации пользователя.

        Returns:
            URL для перехода в браузере
        """
        if not self.config.validate():
            missing = self.config.get_missing_fields()
            raise BitrixAuthError(
                f"Не заполнены настройки в .env: {', '.join(missing)}\n"
                "Создайте приложение в Bitrix24 и заполните переменные."
            )

        params = {
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri,
            'response_type': 'code',
        }
        return f"{self.config.oauth_authorize_url}?{urlencode(params)}"

    def authorize(self, code: str) -> Dict[str, Any]:
        """
        Обменять authorization code на токены.

        Args:
            code: Код из redirect URL после авторизации

        Returns:
            Словарь с токенами
        """
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'redirect_uri': self.config.redirect_uri,
            'code': code
        }

        response = self._session.post(self.config.oauth_token_url, data=data)

        if response.status_code != 200:
            raise BitrixAuthError(f"Ошибка авторизации: {response.text}")

        tokens = response.json()

        if 'error' in tokens:
            raise BitrixAuthError(f"Ошибка: {tokens.get('error_description', tokens['error'])}")

        self._update_tokens(tokens)
        self._save_tokens()

        print(f"Авторизация успешна! Токены сохранены в {self.config.tokens_file}")
        return tokens

    def refresh_tokens(self) -> Dict[str, Any]:
        """
        Обновить токены используя refresh_token.

        Returns:
            Новые токены
        """
        if not self.refresh_token:
            raise BitrixAuthError("Refresh token отсутствует. Выполните авторизацию заново.")

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'refresh_token': self.refresh_token
        }

        response = self._session.post(self.config.oauth_token_url, data=data)

        if response.status_code != 200:
            raise BitrixAuthError(f"Ошибка обновления токена: {response.text}")

        tokens = response.json()

        if 'error' in tokens:
            raise BitrixAuthError(f"Ошибка: {tokens.get('error_description', tokens['error'])}")

        self._update_tokens(tokens)
        self._save_tokens()

        return tokens

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Вызов метода REST API Bitrix24.

        Args:
            method: Название метода (например 'user.get')
            params: Параметры запроса

        Returns:
            Ответ API

        Examples:
            >>> client.call('user.current')
            >>> client.call('user.get', {'ID': 1})
            >>> client.call('tasks.task.list', {'filter': {'STATUS': 2}})
        """
        self._ensure_valid_token()
        self._rate_limit()

        url = f"{self.config.rest_api_url}{method}"

        request_params = params.copy() if params else {}
        request_params['auth'] = self.access_token

        response = self._session.post(url, json=request_params)

        # Обработка rate limit
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 2))
            print(f"Rate limit. Ждём {retry_after} сек...")
            time.sleep(retry_after)
            return self.call(method, params)

        if response.status_code != 200:
            raise BitrixAPIError(f"Ошибка API ({response.status_code}): {response.text}")

        result = response.json()

        if 'error' in result:
            error_msg = result.get('error_description', result['error'])
            raise BitrixAPIError(f"Ошибка API: {error_msg}")

        return result

    def is_authorized(self) -> bool:
        """Проверить наличие токенов"""
        return self.access_token is not None

    def _update_tokens(self, tokens: Dict[str, Any]):
        """Обновить токены в памяти"""
        self.access_token = tokens['access_token']
        self.refresh_token = tokens['refresh_token']
        expires_in = tokens.get('expires_in', 3600)
        # Обновляем за 60 сек до истечения
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

    def _ensure_valid_token(self):
        """Проверить и при необходимости обновить токен"""
        if not self.access_token:
            raise BitrixAuthError(
                "Токен не установлен. Выполните авторизацию:\n"
                f"1. Откройте URL: {self.get_auth_url()}\n"
                "2. Авторизуйтесь и скопируйте код из redirect URL\n"
                "3. Вызовите client.authorize('код')"
            )

        if self.expires_at and datetime.now() >= self.expires_at:
            print("Токен истёк. Обновляем...")
            self.refresh_tokens()

    def _rate_limit(self):
        """Соблюдение rate limit (2 запроса/сек)"""
        elapsed = time.time() - self._last_request_time
        min_interval = 0.5  # 2 запроса в секунду
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _save_tokens(self):
        """Сохранить токены в файл"""
        data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
        with open(self.config.tokens_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_tokens(self):
        """Загрузить токены из файла"""
        tokens_path = Path(self.config.tokens_file)
        if not tokens_path.exists():
            return

        try:
            with open(tokens_path, 'r') as f:
                data = json.load(f)

            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            if data.get('expires_at'):
                self.expires_at = datetime.fromisoformat(data['expires_at'])
        except (json.JSONDecodeError, KeyError):
            pass


# ============================================
# УДОБНЫЕ МЕТОДЫ ДЛЯ ТЕСТИРОВАНИЯ
# ============================================

def test_connection():
    """
    Тестовый скрипт для проверки подключения.

    Запуск:
        python -c "from Bitrix.client import test_connection; test_connection()"
    """
    print("=" * 60)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К BITRIX24")
    print("=" * 60)

    client = BitrixClient()

    # Проверяем конфигурацию
    if not client.config.validate():
        missing = client.config.get_missing_fields()
        print(f"\nОШИБКА: Не заполнены настройки в .env файле:")
        for field in missing:
            print(f"  - {field}")
        print("\nИнструкция:")
        print("1. Создайте приложение в Bitrix24")
        print("2. Заполните переменные в .env файле")
        return

    # Проверяем токены
    if not client.is_authorized():
        print("\nТокены не найдены. Необходима авторизация.")
        print("\nШаг 1: Перейдите по ссылке:")
        print("-" * 60)
        print(client.get_auth_url())
        print("-" * 60)
        print("\nШаг 2: Авторизуйтесь в Bitrix24")
        print("Шаг 3: Скопируйте параметр 'code' из URL")
        print("Шаг 4: Выполните:")
        print("  client.authorize('ваш_код')")
        return

    # Тестовый запрос
    print("\nВыполняем тестовый запрос user.current...")
    try:
        result = client.call('user.current')
        user = result.get('result', {})
        print(f"\nУспешно! Авторизован как:")
        print(f"  ID: {user.get('ID')}")
        print(f"  Имя: {user.get('NAME')} {user.get('LAST_NAME')}")
        print(f"  Email: {user.get('EMAIL')}")
    except Exception as e:
        print(f"\nОшибка: {e}")


if __name__ == '__main__':
    test_connection()
