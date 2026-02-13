"""
Утренний дайджест — данные из Supabase (быстро, без rate-limit)
+ группировка по датам + ИИ-обработка
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from lyudmila_bot.services.bitrix_service import BitrixService
from lyudmila_bot.services.lyuda_ai import LyudaAI
from lyudmila_bot.services.supabase_service import LyudmilaSupabase
from lyudmila_bot.models.user import BotUser

logger = logging.getLogger(__name__)


class DigestService:
    """Сборка и генерация утреннего дайджеста (данные из Supabase)"""

    def __init__(
        self,
        bitrix_service: BitrixService,
        lyuda_ai: LyudaAI,
        supabase: Optional[LyudmilaSupabase] = None,
    ):
        self.bitrix = bitrix_service
        self.ai = lyuda_ai
        self.supabase = supabase

    async def generate_digest(self, user: BotUser) -> str:
        """
        Сгенерировать утренний дайджест для пользователя.

        Если Supabase доступен — данные из него (быстро, сгруппировано).
        Иначе — fallback через Bitrix API.
        """
        digest_data = await self._get_digest_data(user)

        try:
            digest = await self.ai.generate_digest(digest_data)
            return digest
        except Exception as e:
            logger.exception(f"Digest LLM generation failed: {e}")
            return self._fallback_digest(digest_data)

    async def _get_digest_data(self, user: BotUser) -> Dict[str, Any]:
        """Собрать структурированные данные для дайджеста"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        tomorrow_start = today_end
        tomorrow_end = tomorrow_start + timedelta(days=1)
        # Конец текущей недели (воскресенье)
        days_until_sunday = 6 - now.weekday()
        week_end = today_start + timedelta(days=days_until_sunday + 1)

        meetings_text = await self._get_meetings_text(user.bitrix_user_id)

        if self.supabase and self.supabase._pool:
            # Данные из Supabase (быстро, сгруппировано)
            today_tasks = await self.supabase.get_tasks_by_deadline_range(
                user.bitrix_user_id, today_start, today_end,
            )
            tomorrow_tasks = await self.supabase.get_tasks_by_deadline_range(
                user.bitrix_user_id, tomorrow_start, tomorrow_end,
            )
            week_tasks = await self.supabase.get_tasks_by_deadline_range(
                user.bitrix_user_id, tomorrow_end, week_end,
            )
            overdue = await self.supabase.get_overdue_tasks(user.bitrix_user_id)

            # Считаем статистику
            async with self.supabase._pool.acquire() as conn:
                in_progress = await conn.fetchval(
                    "SELECT COUNT(*) FROM lyudmila_tasks WHERE responsible_id = $1 AND status IN (2, 3)",
                    user.bitrix_user_id,
                )
                total_active = await conn.fetchval(
                    "SELECT COUNT(*) FROM lyudmila_tasks WHERE responsible_id = $1 AND status IN (2, 3, 4)",
                    user.bitrix_user_id,
                )

            return {
                "user_name": user.first_name,
                "today_date": now.strftime("%d.%m.%Y (%A)"),
                "meetings": meetings_text,
                "today_tasks": self._format_tasks(today_tasks) or "Нет задач на сегодня",
                "overdue_tasks": self._format_tasks(overdue) or "Нет просроченных",
                "overdue_count": len(overdue),
                "tomorrow_tasks": self._format_tasks(tomorrow_tasks) or "Нет задач на завтра",
                "week_tasks": self._format_tasks(week_tasks) or "Нет задач до конца недели",
                "in_progress_count": in_progress or 0,
                "total_active": total_active or 0,
            }
        else:
            # Fallback: данные из Bitrix API
            tasks_text = await self._get_tasks_text_bitrix(user.bitrix_user_id)
            overdue_text = await self._get_overdue_text_bitrix(user.bitrix_user_id)

            return {
                "user_name": user.first_name,
                "today_date": now.strftime("%d.%m.%Y (%A)"),
                "meetings": meetings_text,
                "today_tasks": tasks_text,
                "overdue_tasks": overdue_text,
                "overdue_count": 0,
                "tomorrow_tasks": "—",
                "week_tasks": "—",
                "in_progress_count": 0,
                "total_active": 0,
            }

    def _format_tasks(self, tasks) -> str:
        """Форматировать список задач из Supabase Records"""
        if not tasks:
            return ""
        lines = []
        for t in tasks:
            title = t.get("title", "Без названия") if isinstance(t, dict) else t["title"]
            deadline = t.get("deadline") if isinstance(t, dict) else t["deadline"]
            dl_str = deadline.strftime("%d.%m %H:%M") if deadline else "без срока"
            lines.append(f"- {title} (дедлайн: {dl_str})")
        return "\n".join(lines)

    # ─── Bitrix fallback methods ───────────────────────────────

    async def _get_meetings_text(self, bitrix_user_id: int) -> str:
        """Встречи на сегодня (всегда из Bitrix calendar API)"""
        try:
            events = await self.bitrix.get_calendar_events(bitrix_user_id)
            if not events:
                return "Нет встреч"
            lines = []
            for e in events:
                name = e.get('NAME', e.get('name', 'Без названия'))
                from_dt = e.get('DATE_FROM', e.get('from', ''))
                lines.append(f"- {from_dt}: {name}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get meetings: {e}")
            return "Не удалось загрузить встречи"

    async def _get_tasks_text_bitrix(self, bitrix_user_id: int) -> str:
        """Задачи в работе (fallback через Bitrix API)"""
        try:
            tasks = await self.bitrix.get_user_tasks(bitrix_user_id, statuses=[3], limit=20)
            if not tasks:
                return "Нет задач в работе"
            lines = []
            for t in tasks:
                title = t.get('title', t.get('TITLE', 'Без названия'))
                deadline = t.get('deadline', t.get('DEADLINE', 'без срока'))
                lines.append(f"- {title} (дедлайн: {deadline})")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return "Не удалось загрузить задачи"

    async def _get_overdue_text_bitrix(self, bitrix_user_id: int) -> str:
        """Просроченные задачи (fallback через Bitrix API)"""
        try:
            tasks = await self.bitrix.get_overdue_tasks(bitrix_user_id)
            if not tasks:
                return "Нет просроченных задач"
            lines = []
            for t in tasks:
                title = t.get('title', t.get('TITLE', 'Без названия'))
                deadline = t.get('deadline', t.get('DEADLINE', ''))
                lines.append(f"- {title} (дедлайн: {deadline})")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get overdue tasks: {e}")
            return "Не удалось загрузить просроченные задачи"

    def _fallback_digest(self, data: Dict[str, Any]) -> str:
        """Fallback дайджест без ИИ — группировка по датам"""
        name = data.get("user_name", "")
        return (
            f"Доброе утро, <b>{name}</b>!\n\n"
            f"<b>📅 Встречи сегодня:</b>\n{data.get('meetings', '—')}\n\n"
            f"<b>📋 Задачи на сегодня:</b>\n{data.get('today_tasks', '—')}\n\n"
            f"<b>⚠️ Просроченные ({data.get('overdue_count', 0)}):</b>\n"
            f"{data.get('overdue_tasks', '—')}\n\n"
            f"<b>📆 На завтра:</b>\n{data.get('tomorrow_tasks', '—')}\n\n"
            f"<b>📅 На эту неделю:</b>\n{data.get('week_tasks', '—')}\n\n"
            f"Хорошего дня!"
        )
