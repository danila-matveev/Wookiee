"""
Синхронизация Bitrix24 → Supabase.

- Сотрудники: все активные, классификация по email
- Задачи: последние 6 месяцев (первая загрузка), потом инкрементально
- Комментарии: к недавним задачам
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from agents.lyudmila.services.bitrix_service import BitrixService
from agents.lyudmila.services.supabase_service import LyudmilaSupabase

logger = logging.getLogger(__name__)

# Домен внутренних сотрудников
INTERNAL_DOMAIN = "@wookiee.shop"


class BitrixSyncService:
    """
    Синхронизация данных из Bitrix24 в Supabase.

    Расписание:
    - Сотрудники: каждые 30 мин
    - Задачи (инкрементально): каждый час
    - Полная синхронизация: раз в сутки (ночью)
    """

    def __init__(self, bitrix: BitrixService, supabase: LyudmilaSupabase):
        self.bitrix = bitrix
        self.supabase = supabase

    # ─── Сотрудники ────────────────────────────────────────────

    async def sync_employees(self) -> int:
        """
        Синхронизировать всех активных сотрудников из Bitrix.

        Классификация:
        - email.endswith('@wookiee.shop') → is_internal=True
        - Остальные → is_internal=False (подрядчики)
        """
        logger.info("Sync employees: start")
        try:
            raw_users = await self.bitrix.get_users(active_only=True)
            employees = []

            for u in raw_users:
                email = u.get("EMAIL", "") or ""
                is_internal = email.lower().endswith(INTERNAL_DOMAIN)

                dept_ids = u.get("UF_DEPARTMENT", [])
                if isinstance(dept_ids, str):
                    dept_ids = []

                employees.append({
                    "bitrix_id": int(u.get("ID", 0)),
                    "first_name": u.get("NAME", ""),
                    "last_name": u.get("LAST_NAME", ""),
                    "full_name": f"{u.get('NAME', '')} {u.get('LAST_NAME', '')}".strip(),
                    "email": email,
                    "position": u.get("WORK_POSITION", ""),
                    "department_ids": [int(d) for d in dept_ids] if dept_ids else [],
                    "is_internal": is_internal,
                    "is_active": True,
                })

            count = await self.supabase.upsert_employees(employees)
            logger.info(f"Sync employees: {count} upserted ({sum(1 for e in employees if e['is_internal'])} internal)")
            return count

        except Exception as e:
            logger.exception(f"Sync employees failed: {e}")
            return 0

    # ─── Задачи ────────────────────────────────────────────────

    async def sync_tasks(self, months: int = 6) -> int:
        """
        Полная синхронизация задач за N месяцев.
        Используется при первом запуске.
        """
        logger.info(f"Sync tasks (full, {months} months): start")
        since = datetime.now() - timedelta(days=months * 30)

        try:
            # Bitrix task list с фильтром по дате
            raw_tasks = await self.bitrix.call_all("tasks.task.list", {
                "filter": {
                    ">=CREATED_DATE": since.strftime("%Y-%m-%dT%H:%M:%S"),
                },
                "select": [
                    "ID", "TITLE", "DESCRIPTION", "REAL_STATUS", "PRIORITY",
                    "RESPONSIBLE_ID", "CREATED_BY", "DEADLINE",
                    "CREATED_DATE", "CLOSED_DATE",
                    "AUDITORS", "ACCOMPLICES",
                ],
            })

            tasks = self._map_tasks(raw_tasks)
            count = await self.supabase.upsert_tasks(tasks)
            logger.info(f"Sync tasks (full): {count} upserted")
            return count

        except Exception as e:
            logger.exception(f"Sync tasks (full) failed: {e}")
            return 0

    async def sync_recent_tasks(self, hours: int = 2) -> int:
        """
        Инкрементальная синхронизация — только изменённые задачи.
        Используется по расписанию каждый час.
        """
        logger.info("Sync tasks (incremental): start")
        since = datetime.now() - timedelta(hours=hours)

        try:
            # Задачи, изменённые за последние N часов
            raw_tasks = await self.bitrix.call_all("tasks.task.list", {
                "filter": {
                    ">=CHANGED_DATE": since.strftime("%Y-%m-%dT%H:%M:%S"),
                },
                "select": [
                    "ID", "TITLE", "DESCRIPTION", "REAL_STATUS", "PRIORITY",
                    "RESPONSIBLE_ID", "CREATED_BY", "DEADLINE",
                    "CREATED_DATE", "CLOSED_DATE",
                    "AUDITORS", "ACCOMPLICES",
                ],
            })

            tasks = self._map_tasks(raw_tasks)
            count = await self.supabase.upsert_tasks(tasks)
            logger.info(f"Sync tasks (incremental): {count} upserted")
            return count

        except Exception as e:
            logger.exception(f"Sync tasks (incremental) failed: {e}")
            return 0

    # ─── Комментарии ───────────────────────────────────────────

    async def sync_task_comments(self, task_ids: Optional[List[int]] = None) -> int:
        """
        Синхронизировать комментарии к задачам.

        Если task_ids не указаны — берёт задачи, изменённые за последний месяц.
        """
        logger.info("Sync comments: start")

        if task_ids is None:
            # Берём задачи из Supabase, изменённые за последний месяц
            since = datetime.now() - timedelta(days=30)
            try:
                from agents.lyudmila.services.supabase_service import LyudmilaSupabase
                async with self.supabase._pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT bitrix_task_id FROM lyudmila_tasks
                        WHERE synced_at >= $1
                        ORDER BY synced_at DESC
                        LIMIT 200
                        """,
                        since,
                    )
                task_ids = [r["bitrix_task_id"] for r in rows]
            except Exception as e:
                logger.error(f"Failed to get recent task IDs: {e}")
                return 0

        if not task_ids:
            logger.info("Sync comments: no tasks to sync")
            return 0

        total = 0
        for task_id in task_ids:
            try:
                result = await self.bitrix.call("task.commentitem.getlist", {
                    "TASKID": task_id,
                })
                raw_comments = result.get("result", [])

                comments = []
                for c in raw_comments:
                    # Пропускаем системные комментарии
                    if c.get("AUTHOR_ID") == "0":
                        continue

                    text = c.get("POST_MESSAGE", "")
                    if not text or len(text.strip()) < 3:
                        continue

                    created_at = self._parse_datetime(c.get("POST_DATE"))
                    comments.append({
                        "bitrix_task_id": task_id,
                        "author_id": int(c.get("AUTHOR_ID", 0)),
                        "comment_text": text[:2000],  # Ограничиваем длину
                        "created_at": created_at,
                    })

                if comments:
                    count = await self.supabase.upsert_comments(comments)
                    total += count

            except Exception as e:
                logger.warning(f"Sync comments for task {task_id} failed: {e}")
                continue

        logger.info(f"Sync comments: {total} upserted from {len(task_ids)} tasks")
        return total

    # ─── Полная синхронизация ──────────────────────────────────

    async def full_sync(self) -> Dict[str, int]:
        """
        Полная синхронизация (при первом запуске / ночная).

        Порядок: сотрудники → задачи → комментарии.
        """
        logger.info("=== Full sync: START ===")

        emp_count = await self.sync_employees()
        task_count = await self.sync_tasks(months=6)
        comment_count = await self.sync_task_comments()

        result = {
            "employees": emp_count,
            "tasks": task_count,
            "comments": comment_count,
        }
        logger.info(f"=== Full sync: DONE === {result}")
        return result

    # ─── Helpers ───────────────────────────────────────────────

    def _map_tasks(self, raw_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Маппинг сырых задач Bitrix → формат для Supabase"""
        result = []
        for t in raw_tasks:
            # Bitrix возвращает поля в разных форматах (camelCase / UPPER_CASE)
            task_id = int(t.get("id", t.get("ID", 0)))
            if not task_id:
                continue

            auditors = t.get("auditors", t.get("AUDITORS", []))
            accomplices = t.get("accomplices", t.get("ACCOMPLICES", []))

            result.append({
                "bitrix_task_id": task_id,
                "title": t.get("title", t.get("TITLE", "")),
                "description": (t.get("description", t.get("DESCRIPTION", "")) or "")[:5000],
                "status": self._safe_int(t.get("status", t.get("REAL_STATUS"))),
                "priority": self._safe_int(t.get("priority", t.get("PRIORITY"))),
                "responsible_id": self._safe_int(t.get("responsibleId", t.get("RESPONSIBLE_ID"))),
                "created_by": self._safe_int(t.get("createdBy", t.get("CREATED_BY"))),
                "deadline": self._parse_datetime(t.get("deadline", t.get("DEADLINE"))),
                "created_at": self._parse_datetime(t.get("createdDate", t.get("CREATED_DATE"))),
                "closed_at": self._parse_datetime(t.get("closedDate", t.get("CLOSED_DATE"))),
                "auditors": [int(a) for a in auditors] if auditors else [],
                "accomplices": [int(a) for a in accomplices] if accomplices else [],
            })
        return result

    @staticmethod
    def _safe_int(val: Any) -> Optional[int]:
        """Безопасное преобразование в int"""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(val: Any) -> Optional[datetime]:
        """Парсинг даты из Bitrix (несколько форматов)"""
        if not val:
            return None
        if isinstance(val, datetime):
            return val

        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y",
        ):
            try:
                return datetime.strptime(str(val), fmt)
            except ValueError:
                continue

        logger.debug(f"Unparseable datetime: {val}")
        return None
