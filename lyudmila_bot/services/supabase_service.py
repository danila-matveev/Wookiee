"""
Supabase (PostgreSQL) как память Людмилы.

Все запросы через asyncpg — async, быстро, без rate-limit.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import asyncpg

from lyudmila_bot import config

logger = logging.getLogger(__name__)


class LyudmilaSupabase:
    """
    Supabase-клиент Людмилы.

    Хранит:
    - Сотрудников (is_internal / подрядчики)
    - Задачи за 6 месяцев
    - Комментарии к задачам
    - Подсказки и предпочтения пользователей
    """

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Создать пул подключений к Supabase"""
        dsn = (
            f"postgresql://{config.SUPABASE_USER}:{config.SUPABASE_PASSWORD}"
            f"@{config.SUPABASE_HOST}:{config.SUPABASE_PORT}/{config.SUPABASE_DB}"
        )
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=5,
            ssl="require",
        )
        logger.info("Supabase pool connected")

    async def close(self) -> None:
        """Закрыть пул"""
        if self._pool:
            await self._pool.close()
            logger.info("Supabase pool closed")

    async def health_check(self) -> bool:
        """Проверка подключения"""
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            return False

    # ─── Сотрудники ────────────────────────────────────────────

    async def upsert_employees(self, employees: List[Dict[str, Any]]) -> int:
        """Batch upsert сотрудников. Возвращает кол-во."""
        if not employees:
            return 0

        async with self._pool.acquire() as conn:
            count = 0
            for emp in employees:
                await conn.execute(
                    """
                    INSERT INTO lyudmila_employees
                        (bitrix_id, first_name, last_name, full_name, email,
                         position, department_ids, is_internal, is_active, synced_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
                    ON CONFLICT (bitrix_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        position = EXCLUDED.position,
                        department_ids = EXCLUDED.department_ids,
                        is_internal = EXCLUDED.is_internal,
                        is_active = EXCLUDED.is_active,
                        synced_at = now()
                    """,
                    emp["bitrix_id"],
                    emp.get("first_name", ""),
                    emp.get("last_name", ""),
                    emp.get("full_name", ""),
                    emp.get("email", ""),
                    emp.get("position", ""),
                    emp.get("department_ids", []),
                    emp.get("is_internal", False),
                    emp.get("is_active", True),
                )
                count += 1
            return count

    async def get_team_members(self) -> List[asyncpg.Record]:
        """Внутренняя команда (is_internal=true, is_active=true)"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_id, first_name, last_name, full_name, email,
                       position, custom_role
                FROM lyudmila_employees
                WHERE is_internal = true AND is_active = true
                ORDER BY full_name
                """
            )

    async def get_contractors(self) -> List[asyncpg.Record]:
        """Внешние подрядчики (is_internal=false, is_active=true)"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_id, first_name, last_name, full_name, email,
                       position, custom_role
                FROM lyudmila_employees
                WHERE is_internal = false AND is_active = true
                ORDER BY full_name
                """
            )

    async def get_employee_by_bitrix_id(self, bitrix_id: int) -> Optional[asyncpg.Record]:
        """Один сотрудник по Bitrix ID"""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM lyudmila_employees WHERE bitrix_id = $1",
                bitrix_id,
            )

    async def get_all_active_employees(self) -> List[asyncpg.Record]:
        """Все активные сотрудники"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_id, first_name, last_name, full_name, email,
                       position, is_internal, custom_role
                FROM lyudmila_employees
                WHERE is_active = true
                ORDER BY full_name
                """
            )

    # ─── Задачи ────────────────────────────────────────────────

    async def upsert_tasks(self, tasks: List[Dict[str, Any]]) -> int:
        """Batch upsert задач. Возвращает кол-во."""
        if not tasks:
            return 0

        async with self._pool.acquire() as conn:
            count = 0
            for t in tasks:
                await conn.execute(
                    """
                    INSERT INTO lyudmila_tasks
                        (bitrix_task_id, title, description, status, priority,
                         responsible_id, created_by, deadline, created_at, closed_at,
                         auditors, accomplices, synced_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, now())
                    ON CONFLICT (bitrix_task_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        status = EXCLUDED.status,
                        priority = EXCLUDED.priority,
                        responsible_id = EXCLUDED.responsible_id,
                        created_by = EXCLUDED.created_by,
                        deadline = EXCLUDED.deadline,
                        closed_at = EXCLUDED.closed_at,
                        auditors = EXCLUDED.auditors,
                        accomplices = EXCLUDED.accomplices,
                        synced_at = now()
                    """,
                    t["bitrix_task_id"],
                    t.get("title", ""),
                    t.get("description", ""),
                    t.get("status"),
                    t.get("priority"),
                    t.get("responsible_id"),
                    t.get("created_by"),
                    t.get("deadline"),
                    t.get("created_at"),
                    t.get("closed_at"),
                    t.get("auditors", []),
                    t.get("accomplices", []),
                )
                count += 1
            return count

    async def get_user_tasks_history(
        self, bitrix_user_id: int, months: int = 6,
    ) -> List[asyncpg.Record]:
        """Задачи пользователя за N месяцев (исполнитель)"""
        since = datetime.now() - timedelta(days=months * 30)
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_task_id, title, status, priority,
                       deadline, created_at, closed_at, created_by
                FROM lyudmila_tasks
                WHERE responsible_id = $1 AND created_at >= $2
                ORDER BY created_at DESC
                """,
                bitrix_user_id, since,
            )

    async def get_user_completed_tasks(
        self, bitrix_user_id: int, since: datetime,
    ) -> List[asyncpg.Record]:
        """Завершённые задачи за период"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_task_id, title, closed_at, created_by
                FROM lyudmila_tasks
                WHERE responsible_id = $1 AND status = 5 AND closed_at >= $2
                ORDER BY closed_at DESC
                """,
                bitrix_user_id, since,
            )

    async def get_overdue_tasks(self, bitrix_user_id: int) -> List[asyncpg.Record]:
        """Просроченные задачи (дедлайн < сейчас, статус в работе)"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_task_id, title, deadline, status, created_by
                FROM lyudmila_tasks
                WHERE responsible_id = $1
                  AND deadline < now()
                  AND status IN (2, 3)
                ORDER BY deadline
                """,
                bitrix_user_id,
            )

    async def get_tasks_by_deadline_range(
        self, bitrix_user_id: int, from_dt: datetime, to_dt: datetime,
    ) -> List[asyncpg.Record]:
        """Задачи с дедлайном в заданном диапазоне"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_task_id, title, deadline, status, priority, created_by
                FROM lyudmila_tasks
                WHERE responsible_id = $1
                  AND deadline >= $2 AND deadline < $3
                  AND status IN (2, 3)
                ORDER BY deadline
                """,
                bitrix_user_id, from_dt, to_dt,
            )

    async def get_user_created_tasks(
        self, bitrix_user_id: int, since: datetime,
    ) -> List[asyncpg.Record]:
        """Задачи, поставленные пользователем за период"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT bitrix_task_id, title, status, responsible_id, deadline, created_at
                FROM lyudmila_tasks
                WHERE created_by = $1 AND created_at >= $2
                ORDER BY created_at DESC
                """,
                bitrix_user_id, since,
            )

    async def get_team_summary(self, since: datetime) -> List[asyncpg.Record]:
        """Сводка по всей внутренней команде за период"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT
                    e.bitrix_id,
                    e.full_name,
                    e.position,
                    COUNT(t.id) FILTER (WHERE t.status = 5 AND t.closed_at >= $1) AS completed,
                    COUNT(t.id) FILTER (WHERE t.status IN (2,3) AND t.deadline < now()) AS overdue,
                    COUNT(t.id) FILTER (WHERE t.status IN (2,3)) AS in_progress
                FROM lyudmila_employees e
                LEFT JOIN lyudmila_tasks t ON t.responsible_id = e.bitrix_id
                WHERE e.is_internal = true AND e.is_active = true
                GROUP BY e.bitrix_id, e.full_name, e.position
                ORDER BY e.full_name
                """,
                since,
            )

    # ─── Комментарии ───────────────────────────────────────────

    async def upsert_comments(self, comments: List[Dict[str, Any]]) -> int:
        """Batch upsert комментариев"""
        if not comments:
            return 0

        async with self._pool.acquire() as conn:
            count = 0
            for c in comments:
                await conn.execute(
                    """
                    INSERT INTO lyudmila_task_comments
                        (bitrix_task_id, author_id, comment_text, created_at, synced_at)
                    VALUES ($1, $2, $3, $4, now())
                    ON CONFLICT DO NOTHING
                    """,
                    c["bitrix_task_id"],
                    c.get("author_id"),
                    c.get("comment_text", ""),
                    c.get("created_at"),
                )
                count += 1
            return count

    async def get_task_comments(self, bitrix_task_id: int) -> List[asyncpg.Record]:
        """Комментарии к задаче"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT c.author_id, c.comment_text, c.created_at, e.full_name AS author_name
                FROM lyudmila_task_comments c
                LEFT JOIN lyudmila_employees e ON e.bitrix_id = c.author_id
                WHERE c.bitrix_task_id = $1
                ORDER BY c.created_at DESC
                LIMIT 20
                """,
                bitrix_task_id,
            )

    async def get_user_received_comments(
        self, bitrix_user_id: int, since: datetime,
    ) -> List[asyncpg.Record]:
        """Комментарии к задачам пользователя (обратная связь)"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT c.bitrix_task_id, t.title, c.author_id, e.full_name AS author_name,
                       c.comment_text, c.created_at
                FROM lyudmila_task_comments c
                JOIN lyudmila_tasks t ON t.bitrix_task_id = c.bitrix_task_id
                LEFT JOIN lyudmila_employees e ON e.bitrix_id = c.author_id
                WHERE t.responsible_id = $1
                  AND c.author_id != $1
                  AND c.created_at >= $2
                ORDER BY c.created_at DESC
                LIMIT 30
                """,
                bitrix_user_id, since,
            )

    # ─── Подсказки и предпочтения ─────────────────────────────

    async def log_suggestion(
        self,
        telegram_id: int,
        entity_type: str,
        text: str,
        suggestion_type: Optional[str] = None,
        accepted: Optional[bool] = None,
    ) -> None:
        """Записать подсказку"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO lyudmila_suggestions
                    (telegram_id, entity_type, suggestion_text, suggestion_type, accepted)
                VALUES ($1, $2, $3, $4, $5)
                """,
                telegram_id, entity_type, text, suggestion_type, accepted,
            )

    async def update_suggestion(self, suggestion_id: int, accepted: bool) -> None:
        """Обновить статус подсказки (принята/отклонена)"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE lyudmila_suggestions SET accepted = $1 WHERE id = $2",
                accepted, suggestion_id,
            )

    async def get_suggestion_stats(self, telegram_id: int) -> Dict[str, Any]:
        """Статистика принятия подсказок пользователем"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE accepted = true) AS accepted,
                    COUNT(*) FILTER (WHERE accepted = false) AS rejected,
                    COUNT(*) FILTER (WHERE accepted IS NULL) AS pending
                FROM lyudmila_suggestions
                WHERE telegram_id = $1
                """,
                telegram_id,
            )
            if row:
                total = row["total"] or 0
                acc = row["accepted"] or 0
                return {
                    "total": total,
                    "accepted": acc,
                    "rejected": row["rejected"] or 0,
                    "acceptance_rate": acc / total if total > 0 else 0.0,
                }
            return {"total": 0, "accepted": 0, "rejected": 0, "acceptance_rate": 0.0}

    async def get_user_preferences(self, telegram_id: int) -> Dict[str, str]:
        """Предпочтения пользователя (key → value)"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT preference_key, preference_value, confidence
                FROM lyudmila_user_preferences
                WHERE telegram_id = $1
                ORDER BY confidence DESC
                """,
                telegram_id,
            )
            return {r["preference_key"]: r["preference_value"] for r in rows}

    async def set_user_preference(
        self,
        telegram_id: int,
        key: str,
        value: str,
        confidence: float = 0.5,
    ) -> None:
        """Установить/обновить предпочтение"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO lyudmila_user_preferences
                    (telegram_id, preference_key, preference_value, confidence, updated_at)
                VALUES ($1, $2, $3, $4, now())
                ON CONFLICT (telegram_id, preference_key) DO UPDATE SET
                    preference_value = EXCLUDED.preference_value,
                    confidence = EXCLUDED.confidence,
                    updated_at = now()
                """,
                telegram_id, key, value, confidence,
            )
