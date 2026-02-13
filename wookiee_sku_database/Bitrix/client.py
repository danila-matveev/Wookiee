"""
Клиент для Bitrix24 REST API

Поддерживает два режима работы:
1. Входящий вебхук (рекомендуется для начала) - без авторизации
2. OAuth 2.0 приложение - для двусторонней интеграции

Использование (вебхук):
    from Bitrix.client import BitrixClient

    client = BitrixClient()
    print(client.call('user.current'))
    print(client.call('user.get'))
    print(client.call('department.get'))
"""

import json
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
from urllib.parse import urlencode

from Bitrix.config import config


class BitrixAPIError(Exception):
    """Ошибка API Bitrix24"""
    pass


class BitrixClient:
    """
    Клиент для Bitrix24 REST API.

    Поддерживает:
    - Работу через входящий вебхук (BITRIX_WEBHOOK_URL)
    - Работу через OAuth 2.0 (BITRIX_CLIENT_ID/SECRET)
    - Rate limiting (2 запроса/сек)
    - Пагинацию (автоматическая загрузка всех страниц)
    """

    def __init__(self):
        self.config = config
        self._session = requests.Session()
        self._last_request_time: float = 0

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
            >>> client.call('department.get')
            >>> client.call('tasks.task.list', {'filter': {'STATUS': 2}})
        """
        if not self.config.webhook_url:
            raise BitrixAPIError(
                "BITRIX_WEBHOOK_URL не указан в .env файле.\n"
                "Создайте входящий вебхук в Bitrix24 и добавьте URL."
            )

        self._rate_limit()

        url = f"{self.config.webhook_url}{method}"
        request_params = params or {}

        response = self._session.post(url, json=request_params)

        # Обработка rate limit
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 2))
            print(f"Rate limit. Ждём {retry_after} сек...")
            time.sleep(retry_after)
            return self.call(method, params)

        if response.status_code != 200:
            raise BitrixAPIError(f"HTTP {response.status_code}: {response.text}")

        result = response.json()

        if 'error' in result:
            error_msg = result.get('error_description', result['error'])
            raise BitrixAPIError(f"Ошибка API: {error_msg}")

        return result

    def call_all(self, method: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Вызов метода с автоматической пагинацией.
        Загружает ВСЕ записи, а не только первую страницу.

        Args:
            method: Название метода
            params: Параметры запроса

        Returns:
            Список всех записей
        """
        all_items = []
        start = 0
        params = params or {}

        while True:
            params['start'] = start
            response = self.call(method, params)

            result = response.get('result', [])

            # tasks.task.list возвращает {'tasks': [...]}
            if isinstance(result, dict) and 'tasks' in result:
                result = result['tasks']

            if isinstance(result, list):
                all_items.extend(result)
            else:
                all_items.append(result)
                break

            # Проверяем есть ли ещё страницы
            next_start = response.get('next')
            if next_start is None:
                break
            start = next_start

        return all_items

    def _rate_limit(self):
        """Соблюдение rate limit (2 запроса/сек)"""
        elapsed = time.time() - self._last_request_time
        min_interval = 0.5
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()


# ============================================
# ТЕСТИРОВАНИЕ
# ============================================

def test_connection():
    """
    Тестовый скрипт для проверки подключения.

    Запуск:
        python3 -c "from Bitrix.client import test_connection; test_connection()"
    """
    print("=" * 60)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К BITRIX24")
    print("=" * 60)

    client = BitrixClient()

    if not client.config.webhook_url:
        print("\nОШИБКА: BITRIX_WEBHOOK_URL не указан в .env")
        return

    print(f"\nWebhook: {client.config.webhook_url[:50]}...")

    # Тест 1: Текущий пользователь
    print("\n--- user.current ---")
    try:
        result = client.call('user.current')
        user = result.get('result', {})
        print(f"  ID: {user.get('ID')}")
        print(f"  Имя: {user.get('NAME')} {user.get('LAST_NAME')}")
        print(f"  Email: {user.get('EMAIL')}")
        print(f"  Должность: {user.get('WORK_POSITION', '-')}")
    except Exception as e:
        print(f"  Ошибка: {e}")
        return

    # Тест 2: Отделы
    print("\n--- department.get ---")
    try:
        result = client.call('department.get')
        departments = result.get('result', [])
        print(f"  Отделов: {len(departments)}")
        for dept in departments[:5]:
            print(f"  - [{dept.get('ID')}] {dept.get('NAME')}")
    except Exception as e:
        print(f"  Ошибка: {e}")

    # Тест 3: Сотрудники
    print("\n--- user.get ---")
    try:
        result = client.call('user.get')
        users = result.get('result', [])
        print(f"  Сотрудников: {len(users)}")
        for u in users[:5]:
            print(f"  - [{u.get('ID')}] {u.get('NAME')} {u.get('LAST_NAME')} — {u.get('WORK_POSITION', '-')}")
    except Exception as e:
        print(f"  Ошибка: {e}")

    # Тест 4: Задачи
    print("\n--- tasks.task.list ---")
    try:
        result = client.call('tasks.task.list', {'limit': 3})
        tasks = result.get('result', {}).get('tasks', [])
        print(f"  Задач (первые 3): {len(tasks)}")
        for t in tasks[:3]:
            print(f"  - [{t.get('id')}] {t.get('title', '')[:60]}")
    except Exception as e:
        print(f"  Ошибка: {e}")

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)


if __name__ == '__main__':
    test_connection()
