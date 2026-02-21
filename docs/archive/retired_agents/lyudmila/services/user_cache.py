"""
Кеш сотрудников Bitrix24 + нечёткий поиск имён
"""
import asyncio
import logging
from typing import Optional, Dict, List, Tuple
from thefuzz import fuzz

from agents.lyudmila import config
from agents.lyudmila.services.bitrix_service import BitrixService

logger = logging.getLogger(__name__)

# Словарь уменьшительных имён → полные формы
DIMINUTIVE_NAMES: Dict[str, List[str]] = {
    "саша": ["Александр", "Александра"],
    "шура": ["Александр", "Александра"],
    "настя": ["Анастасия"],
    "дима": ["Дмитрий"],
    "женя": ["Евгений", "Евгения"],
    "катя": ["Екатерина"],
    "лена": ["Елена"],
    "ваня": ["Иван"],
    "ира": ["Ирина"],
    "кирюша": ["Кирилл"],
    "кирилл": ["Кирилл"],
    "маша": ["Мария"],
    "миша": ["Михаил"],
    "коля": ["Николай"],
    "оля": ["Ольга"],
    "паша": ["Павел"],
    "петя": ["Пётр", "Петр"],
    "рома": ["Роман"],
    "серёжа": ["Сергей"],
    "сережа": ["Сергей"],
    "света": ["Светлана"],
    "таня": ["Татьяна"],
    "юля": ["Юлия"],
    "даня": ["Данила", "Даниил", "Данил"],
    "данила": ["Данила"],
    "наташа": ["Наталья", "Наталия"],
    "галя": ["Галина"],
    "вика": ["Виктория"],
    "люда": ["Людмила"],
    "андрей": ["Андрей"],
    "аня": ["Анна"],
    "валя": ["Валентина", "Валентин"],
    "вова": ["Владимир"],
    "влад": ["Владислав", "Владимир"],
    "гоша": ["Георгий"],
    "гриша": ["Григорий"],
    "костя": ["Константин"],
    "лёша": ["Алексей"],
    "леша": ["Алексей"],
    "алёша": ["Алексей"],
    "алеша": ["Алексей"],
    "лёня": ["Леонид"],
    "леня": ["Леонид"],
    "максим": ["Максим"],
    "макс": ["Максим"],
    "никита": ["Никита"],
    "стас": ["Станислав"],
    "тёма": ["Артём"],
    "тема": ["Артём"],
    "артём": ["Артём"],
    "артем": ["Артём"],
    "толя": ["Анатолий"],
    "федя": ["Фёдор", "Федор"],
    "яна": ["Яна"],
}


class UserCache:
    """
    Кеш сотрудников Bitrix24 с нечётким поиском по именам.

    - Загружает всех активных сотрудников при старте
    - Обновляется каждые N минут
    - Поддерживает уменьшительные имена
    - Нечёткий поиск через thefuzz
    """

    def __init__(self, bitrix_service: BitrixService):
        self.bitrix = bitrix_service
        self._users: List[Dict] = []
        self._by_id: Dict[int, Dict] = {}
        self._threshold = config.FUZZY_MATCH_THRESHOLD

    async def load(self) -> None:
        """Загрузить всех активных сотрудников из Bitrix24"""
        try:
            raw_users = await self.bitrix.get_users(active_only=True)
            self._users = []
            self._by_id = {}

            for u in raw_users:
                user_id = int(u.get('ID', 0))
                entry = {
                    'id': user_id,
                    'first_name': u.get('NAME', ''),
                    'last_name': u.get('LAST_NAME', ''),
                    'email': u.get('EMAIL', ''),
                    'position': u.get('WORK_POSITION', ''),
                    'department': u.get('UF_DEPARTMENT', []),
                    'active': u.get('ACTIVE', True),
                    'full_name': f"{u.get('NAME', '')} {u.get('LAST_NAME', '')}".strip(),
                }
                self._users.append(entry)
                self._by_id[user_id] = entry

            logger.info(f"UserCache loaded: {len(self._users)} сотрудников")
        except Exception as e:
            logger.exception(f"UserCache load failed: {e}")
            if not self._users:
                raise

    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Получить сотрудника по Bitrix ID"""
        return self._by_id.get(user_id)

    def find_by_name(self, query: str) -> List[Dict]:
        """
        Нечёткий поиск сотрудника по имени/фамилии.

        Поддерживает:
        - Полные имена: "Анастасия Лигус"
        - Уменьшительные: "Настя"
        - Фамилии: "Матвеев"

        Returns:
            Список совпадений, отсортированный по релевантности (лучший — первый)
        """
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        # Шаг 1: Развернуть уменьшительное имя
        expanded_names = DIMINUTIVE_NAMES.get(query_lower, [])

        results: List[Tuple[int, Dict]] = []

        for user in self._users:
            first = user['first_name']
            last = user['last_name']
            full = user['full_name']

            # Точное совпадение по уменьшительному
            if expanded_names:
                for expanded in expanded_names:
                    if first.lower() == expanded.lower():
                        results.append((100, user))
                        break
                else:
                    # Нечёткий поиск по полному имени тоже
                    score = fuzz.token_sort_ratio(query_lower, full.lower())
                    if score >= self._threshold:
                        results.append((score, user))
            else:
                # Точное совпадение по фамилии
                if last.lower() == query_lower or first.lower() == query_lower:
                    results.append((100, user))
                    continue

                # Нечёткий поиск
                score_full = fuzz.token_sort_ratio(query_lower, full.lower())
                score_first = fuzz.ratio(query_lower, first.lower())
                score_last = fuzz.ratio(query_lower, last.lower())
                best_score = max(score_full, score_first, score_last)

                if best_score >= self._threshold:
                    results.append((best_score, user))

        # Сортируем по score убыванию
        results.sort(key=lambda x: x[0], reverse=True)
        return [user for _, user in results]

    def get_all_names_for_prompt(self) -> str:
        """Список всех сотрудников для передачи в LLM-промпт"""
        names = [f"{u['full_name']} (ID:{u['id']})" for u in self._users]
        return ", ".join(names)

    def get_team_structure_for_prompt(self, supabase_employees=None) -> str:
        """
        Список сотрудников с должностями и ролями для LLM-промпта.

        Если передан supabase_employees (из Supabase) — использует is_internal.
        Иначе — fallback на базовый формат из кеша.
        """
        if supabase_employees:
            team_lines = []
            contractor_lines = []

            for emp in supabase_employees:
                name = emp["full_name"]
                bid = emp["bitrix_id"]
                pos = emp.get("position") or ""
                role = emp.get("custom_role") or ""

                label = f"[{pos}]" if pos else ""
                if role:
                    label += f" ({role})"

                entry = f"  {label} {name} (ID:{bid})".strip()

                if emp.get("is_internal"):
                    team_lines.append(entry)
                else:
                    contractor_lines.append(entry)

            parts = []
            if team_lines:
                parts.append("Команда (внутренние сотрудники @wookiee.shop):")
                parts.extend(team_lines)
            if contractor_lines:
                parts.append("\nВнешние подрядчики:")
                parts.extend(contractor_lines)

            return "\n".join(parts)

        # Fallback: без Supabase данных
        lines = []
        for u in self._users:
            pos = u.get('position', '')
            label = f"[{pos}] " if pos else ""
            lines.append(f"  {label}{u['full_name']} (ID:{u['id']})")
        return "Сотрудники:\n" + "\n".join(lines)

    @property
    def count(self) -> int:
        return len(self._users)
