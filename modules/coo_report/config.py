"""Конфигурация скилла /coo-report."""

from datetime import date, timedelta


NOTION_TEMPLATE_ID = "35658a2bd5878028ad75f1773a0f8593"
NOTION_PARENT_ID = "35658a2bd587803b8ab5fc540e4318e7"

MODELS = [
    "wendy", "vuki", "ruby", "audrey", "charlotte", "moon",
    "set vuki", "joy", "set moon", "lana", "eva", "set ruby",
    "bella", "set bella", "alice", "valery",
]

COO_STAFF = {
    1435: "Артём",
    41:   "Светлана",
    11:   "Валерия",
    1057: "Настя",
    2223: "Лиля",
    17:   "Дмитрий",
    19:   "Маша",
    1625: "Алина",
}

BITRIX_STATUS = {
    "1": "Не начата",
    "2": "В работе",
    "3": "Выполнено",
    "4": "Ожидание",
    "5": "В ожидании",
    "6": "Отложено",
    "7": "Отклонено",
}

BITRIX_DONE_STATUSES = {"3"}
BITRIX_ACTIVE_STATUSES = {"2"}
BITRIX_PENDING_STATUSES = {"1", "4", "5", "6"}


def get_week_bounds(ref_date: date = None) -> tuple[date, date, date, date]:
    """
    Возвращает (current_start, current_end, prev_start, prev_end).

    current_start — понедельник недели, содержащей ref_date.
    current_end   — следующий понедельник (exclusive, для WHERE date < current_end).

    По умолчанию (ref_date=None) берётся прошлая неделя — текущая может быть
    незакрытой и данные по ней могут быть неполными.
    """
    if ref_date is None:
        ref_date = date.today() - timedelta(days=7)
    days_since_monday = ref_date.weekday()
    current_start = ref_date - timedelta(days=days_since_monday)
    current_end = current_start + timedelta(days=7)
    prev_start = current_start - timedelta(days=7)
    prev_end = current_start
    return current_start, current_end, prev_start, prev_end
