"""
Еженедельные сводки — персональная и командная.

Данные из Supabase, генерация через LLM.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from lyudmila_bot.services.lyuda_ai import LyudaAI
from lyudmila_bot.services.supabase_service import LyudmilaSupabase
from lyudmila_bot.models.user import BotUser

logger = logging.getLogger(__name__)


class WeeklyDigestService:
    """Сборка и генерация еженедельных сводок"""

    def __init__(self, lyuda_ai: LyudaAI, supabase: LyudmilaSupabase):
        self.ai = lyuda_ai
        self.supabase = supabase

    # ─── Персональная сводка ────────────────────────────────────

    async def generate_personal(self, user: BotUser) -> str:
        """Еженедельная персональная сводка для пользователя."""
        data = await self._get_personal_data(user)

        try:
            return await self.ai.generate_weekly_personal(data)
        except Exception as e:
            logger.exception(f"Weekly personal LLM failed: {e}")
            return self._fallback_personal(data)

    async def _get_personal_data(self, user: BotUser) -> Dict[str, Any]:
        """Собрать данные за прошлую неделю"""
        now = datetime.now()
        # Прошлая неделя: пн-вс
        monday = now - timedelta(days=now.weekday() + 7)
        week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        bid = user.bitrix_user_id

        completed = await self.supabase.get_user_completed_tasks(bid, week_start)
        # Фильтруем только прошлую неделю
        completed = [t for t in completed if t["closed_at"] and t["closed_at"] < week_end]

        created = await self.supabase.get_user_created_tasks(bid, week_start)
        created = [t for t in created if t["created_at"] and t["created_at"] < week_end]

        overdue = await self.supabase.get_overdue_tasks(bid)

        comments = await self.supabase.get_user_received_comments(bid, week_start)
        comments = [c for c in comments if c["created_at"] and c["created_at"] < week_end]

        # Среднее время выполнения
        avg_days = self._calc_avg_completion(completed)

        return {
            "user_name": user.first_name,
            "week_start": week_start.strftime("%d.%m.%Y"),
            "week_end": (week_end - timedelta(days=1)).strftime("%d.%m.%Y"),
            "completed_count": len(completed),
            "completed_tasks": self._format_completed(completed) or "Нет завершённых задач",
            "created_count": len(created),
            "created_tasks": self._format_created(created) or "Не ставил(а) задач",
            "overdue_count": len(overdue),
            "overdue_tasks": self._format_overdue(overdue) or "Нет просроченных",
            "comments": self._format_comments(comments) or "Нет комментариев",
            "avg_completion_days": f"{avg_days:.1f}" if avg_days else "—",
        }

    # ─── Командная сводка ───────────────────────────────────────

    async def generate_team(self) -> str:
        """Еженедельная командная сводка."""
        data = await self._get_team_data()

        try:
            return await self.ai.generate_weekly_team(data)
        except Exception as e:
            logger.exception(f"Weekly team LLM failed: {e}")
            return self._fallback_team(data)

    async def _get_team_data(self) -> Dict[str, Any]:
        """Собрать командные данные за прошлую неделю"""
        now = datetime.now()
        monday = now - timedelta(days=now.weekday() + 7)
        week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        summary = await self.supabase.get_team_summary(week_start)

        total_completed = sum(r["completed"] for r in summary)
        total_overdue = sum(r["overdue"] for r in summary)
        total_active = sum(r["in_progress"] for r in summary)

        # Форматируем по сотрудникам
        lines = []
        for r in summary:
            pos = f" [{r['position']}]" if r.get("position") else ""
            lines.append(
                f"{r['full_name']}{pos}: "
                f"выполнено {r['completed']}, просрочено {r['overdue']}, "
                f"в работе {r['in_progress']}"
            )

        return {
            "week_start": week_start.strftime("%d.%m.%Y"),
            "week_end": (week_end - timedelta(days=1)).strftime("%d.%m.%Y"),
            "per_employee_stats": "\n".join(lines) or "Нет данных",
            "total_active": total_active,
            "total_completed": total_completed,
            "total_overdue": total_overdue,
        }

    # ─── Форматирование ────────────────────────────────────────

    @staticmethod
    def _format_completed(tasks) -> str:
        lines = []
        for t in tasks:
            closed = t["closed_at"].strftime("%d.%m") if t.get("closed_at") else ""
            lines.append(f"- {t['title']} (закрыта {closed})")
        return "\n".join(lines)

    @staticmethod
    def _format_created(tasks) -> str:
        lines = []
        for t in tasks:
            status_map = {2: "ожидает", 3: "в работе", 4: "отложена", 5: "завершена"}
            st = status_map.get(t.get("status"), "?")
            lines.append(f"- {t['title']} ({st})")
        return "\n".join(lines)

    @staticmethod
    def _format_overdue(tasks) -> str:
        lines = []
        for t in tasks:
            dl = t["deadline"].strftime("%d.%m") if t.get("deadline") else "?"
            lines.append(f"- {t['title']} (дедлайн был {dl})")
        return "\n".join(lines)

    @staticmethod
    def _format_comments(comments) -> str:
        lines = []
        for c in comments:
            author = c.get("author_name") or f"ID:{c.get('author_id', '?')}"
            text = c["comment_text"][:100]
            task = c.get("title", "?")
            lines.append(f"- [{task}] {author}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _calc_avg_completion(completed_tasks) -> Optional[float]:
        """Среднее время выполнения (дни) для закрытых задач"""
        durations = []
        for t in completed_tasks:
            if t.get("closed_at") and t.get("created_at"):
                # created_at comes from lyudmila_tasks which may not be in this query
                # fallback: use closed_at only
                pass
        # Simplified: we don't have created_at in completed query, return None
        return None

    # ─── Fallback (без LLM) ────────────────────────────────────

    @staticmethod
    def _fallback_personal(data: Dict[str, Any]) -> str:
        name = data.get("user_name", "")
        return (
            f"<b>Еженедельная сводка для {name}</b>\n"
            f"Период: {data.get('week_start')} — {data.get('week_end')}\n\n"
            f"<b>Выполнено ({data.get('completed_count', 0)}):</b>\n"
            f"{data.get('completed_tasks', '—')}\n\n"
            f"<b>Поставлено ({data.get('created_count', 0)}):</b>\n"
            f"{data.get('created_tasks', '—')}\n\n"
            f"<b>Просрочено ({data.get('overdue_count', 0)}):</b>\n"
            f"{data.get('overdue_tasks', '—')}\n\n"
            f"<b>Комментарии:</b>\n"
            f"{data.get('comments', '—')}"
        )

    @staticmethod
    def _fallback_team(data: Dict[str, Any]) -> str:
        return (
            f"<b>Командная сводка</b>\n"
            f"Период: {data.get('week_start')} — {data.get('week_end')}\n\n"
            f"{data.get('per_employee_stats', '—')}\n\n"
            f"<b>Итого:</b> выполнено {data.get('total_completed', 0)}, "
            f"просрочено {data.get('total_overdue', 0)}, "
            f"активных {data.get('total_active', 0)}"
        )
