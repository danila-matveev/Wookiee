"""
Контекст для LLM — обучение на действиях пользователя.

- Последние задачи (обнаружение дублей)
- Статистика подсказок (acceptance rate)
- Предпочтения (preferred_observer, стиль)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from agents.lyudmila.services.supabase_service import LyudmilaSupabase

logger = logging.getLogger(__name__)


class ContextService:
    """Сборка контекста из Supabase для каждого LLM-запроса"""

    def __init__(self, supabase: LyudmilaSupabase):
        self.supabase = supabase

    async def get_task_context(self, telegram_id: int, bitrix_user_id: int) -> str:
        """
        Контекст для умных подсказок при создании задачи.

        Включает:
        1. Последние 5 задач (обнаружение дублей)
        2. Статистика подсказок
        3. Предпочтения
        """
        if not self.supabase or not self.supabase._pool:
            return ""

        parts = []

        try:
            # 1. Последние задачи пользователя (для обнаружения дублей)
            recent = await self._get_recent_tasks(bitrix_user_id, limit=5)
            if recent:
                parts.append("Последние задачи этого пользователя:")
                for t in recent:
                    parts.append(f"  - {t['title']} (статус: {self._status_name(t.get('status'))})")

            # 2. Статистика подсказок
            stats = await self.supabase.get_suggestion_stats(telegram_id)
            if stats["total"] > 0:
                rate = stats["acceptance_rate"]
                if rate < 0.3:
                    parts.append(f"Пользователь редко принимает подсказки ({rate:.0%}) — будь кратче с suggestions.")
                elif rate > 0.7:
                    parts.append(f"Пользователь часто принимает подсказки ({rate:.0%}) — можешь предлагать активнее.")

            # 3. Предпочтения
            prefs = await self.supabase.get_user_preferences(telegram_id)
            if prefs:
                pref_lines = []
                for key, value in prefs.items():
                    pref_lines.append(f"  - {key}: {value}")
                if pref_lines:
                    parts.append("Предпочтения пользователя:")
                    parts.extend(pref_lines)

        except Exception as e:
            logger.warning(f"Failed to build task context: {e}")
            return ""

        if not parts:
            return ""

        return "\n".join(parts)

    async def update_preferences(self, telegram_id: int) -> None:
        """
        Анализ suggestion_log → обновление preferences.

        Если пользователь 3+ раз принял определённый тип подсказки,
        создаём предпочтение с повышенной уверенностью.
        """
        if not self.supabase or not self.supabase._pool:
            return

        try:
            async with self.supabase._pool.acquire() as conn:
                # Найти паттерны в принятых подсказках
                rows = await conn.fetch(
                    """
                    SELECT suggestion_type, suggestion_text, COUNT(*) as cnt
                    FROM lyudmila_suggestions
                    WHERE telegram_id = $1 AND accepted = true
                    GROUP BY suggestion_type, suggestion_text
                    HAVING COUNT(*) >= 3
                    ORDER BY cnt DESC
                    LIMIT 5
                    """,
                    telegram_id,
                )

                for row in rows:
                    stype = row["suggestion_type"] or "general"
                    text = row["suggestion_text"]
                    cnt = row["cnt"]
                    confidence = min(0.5 + cnt * 0.1, 0.95)

                    await self.supabase.set_user_preference(
                        telegram_id,
                        f"preferred_{stype}",
                        text,
                        confidence=confidence,
                    )
                    logger.info(
                        f"Preference updated: {telegram_id} preferred_{stype}={text} "
                        f"(confidence={confidence:.2f}, accepted {cnt}x)"
                    )

        except Exception as e:
            logger.warning(f"Failed to update preferences: {e}")

    # ─── Private ────────────────────────────────────────────────

    async def _get_recent_tasks(self, bitrix_user_id: int, limit: int = 5):
        """Последние задачи, созданные этим пользователем"""
        async with self.supabase._pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT title, status, deadline, created_at
                FROM lyudmila_tasks
                WHERE created_by = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                bitrix_user_id, limit,
            )

    @staticmethod
    def _status_name(status) -> str:
        return {
            2: "ожидает выполнения",
            3: "в работе",
            4: "отложена",
            5: "завершена",
            6: "отклонена",
        }.get(status, "?")
