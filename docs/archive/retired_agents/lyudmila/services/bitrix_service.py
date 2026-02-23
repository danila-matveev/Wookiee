"""
Async-обёртка для Bitrix24 REST API
Все sync-вызовы через asyncio.to_thread()
"""
import asyncio
import time
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from agents.lyudmila import config

logger = logging.getLogger(__name__)


class BitrixAPIError(Exception):
    """Ошибка API Bitrix24"""
    pass


class BitrixService:
    """
    Async-сервис для работы с Bitrix24 REST API.

    Использует входящий вебхук (без OAuth).
    Все HTTP-вызовы выполняются через asyncio.to_thread().
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or config.BITRIX_WEBHOOK_URL
        if self.webhook_url and not self.webhook_url.endswith('/'):
            self.webhook_url += '/'
        self._session = requests.Session()
        self._last_request_time: float = 0

    def _rate_limit(self) -> None:
        """Соблюдение rate limit (2 запроса/сек)"""
        elapsed = time.time() - self._last_request_time
        min_interval = 0.5
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _call_sync(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Синхронный вызов метода REST API"""
        if not self.webhook_url:
            raise BitrixAPIError("BITRIX_WEBHOOK_URL не настроен")

        self._rate_limit()

        url = f"{self.webhook_url}{method}"
        response = self._session.post(url, json=params or {})

        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 2))
            logger.warning(f"Bitrix rate limit. Ждём {retry_after} сек...")
            time.sleep(retry_after)
            return self._call_sync(method, params)

        if response.status_code != 200:
            raise BitrixAPIError(f"HTTP {response.status_code}: {response.text[:200]}")

        result = response.json()

        if 'error' in result:
            error_msg = result.get('error_description', result['error'])
            raise BitrixAPIError(f"Bitrix API: {error_msg}")

        return result

    def _call_all_sync(self, method: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Синхронный вызов с пагинацией — загружает ВСЕ записи"""
        all_items = []
        start = 0
        params = params or {}

        while True:
            params['start'] = start
            response = self._call_sync(method, params)

            result = response.get('result', [])
            if isinstance(result, dict) and 'tasks' in result:
                result = result['tasks']

            if isinstance(result, list):
                all_items.extend(result)
            else:
                all_items.append(result)
                break

            next_start = response.get('next')
            if next_start is None:
                break
            start = next_start

        return all_items

    # ─── Async public API ──────────────────────────────────────────

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Async-вызов метода Bitrix24 API"""
        try:
            return await asyncio.to_thread(self._call_sync, method, params)
        except BitrixAPIError:
            raise
        except Exception as e:
            logger.exception(f"Bitrix API error: {e}")
            raise BitrixAPIError(f"Ошибка соединения с Bitrix24: {e}")

    async def call_all(self, method: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Async-вызов с пагинацией"""
        try:
            return await asyncio.to_thread(self._call_all_sync, method, params)
        except BitrixAPIError:
            raise
        except Exception as e:
            logger.exception(f"Bitrix API error (paginated): {e}")
            raise BitrixAPIError(f"Ошибка соединения с Bitrix24: {e}")

    # ─── Пользователи ─────────────────────────────────────────────

    async def get_users(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Получить всех сотрудников (с пагинацией)"""
        params = {}
        if active_only:
            params['FILTER'] = {'ACTIVE': True}
        return await self.call_all('user.get', params)

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Найти сотрудника по email"""
        result = await self.call('user.get', {'FILTER': {'EMAIL': email}})
        users = result.get('result', [])
        return users[0] if users else None

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить сотрудника по Bitrix ID"""
        result = await self.call('user.get', {'FILTER': {'ID': user_id}})
        users = result.get('result', [])
        return users[0] if users else None

    # ─── Задачи ───────────────────────────────────────────────────

    async def get_user_tasks(
        self,
        user_id: int,
        statuses: Optional[List[int]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Получить задачи пользователя"""
        filter_params: Dict[str, Any] = {'RESPONSIBLE_ID': user_id}
        if statuses:
            filter_params['REAL_STATUS'] = statuses
        params = {
            'filter': filter_params,
            'limit': limit,
            'select': ['ID', 'TITLE', 'DESCRIPTION', 'DEADLINE', 'REAL_STATUS',
                        'RESPONSIBLE_ID', 'CREATED_BY', 'CREATED_DATE'],
        }
        result = await self.call('tasks.task.list', params)
        return result.get('result', {}).get('tasks', [])

    async def get_overdue_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить просроченные задачи пользователя"""
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        params = {
            'filter': {
                'RESPONSIBLE_ID': user_id,
                '<=DEADLINE': now,
                'REAL_STATUS': [2, 3],  # ожидает, в работе
            },
            'select': ['ID', 'TITLE', 'DEADLINE', 'REAL_STATUS'],
        }
        result = await self.call('tasks.task.list', params)
        return result.get('result', {}).get('tasks', [])

    async def create_task(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Создать задачу в Bitrix24"""
        result = await self.call('tasks.task.add', {'fields': fields})
        return result.get('result', {})

    async def add_checklist_item(self, task_id: int, title: str) -> Dict[str, Any]:
        """Добавить пункт чеклиста к задаче"""
        result = await self.call('task.checklistitem.add', {
            'TASKID': task_id,
            'FIELDS': {'TITLE': title},
        })
        return result.get('result', {})

    # ─── Календарь ────────────────────────────────────────────────

    async def get_calendar_events(
        self,
        user_id: int,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Получить события календаря пользователя"""
        if from_date is None:
            from_date = datetime.now().replace(hour=0, minute=0, second=0)
        if to_date is None:
            to_date = from_date + timedelta(days=1)

        params = {
            'type': 'user',
            'ownerId': user_id,
            'from': from_date.strftime('%Y-%m-%dT%H:%M:%S'),
            'to': to_date.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        result = await self.call('calendar.event.get', params)
        return result.get('result', [])

    async def create_calendar_event(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Создать событие в календаре"""
        result = await self.call('calendar.event.add', fields)
        return result.get('result', {})

    # ─── Здоровье ─────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Проверка подключения к Bitrix24"""
        try:
            result = await self.call('user.current')
            return 'result' in result
        except Exception as e:
            logger.error(f"Bitrix health check failed: {e}")
            return False
