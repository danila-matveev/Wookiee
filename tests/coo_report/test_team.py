import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.team import parse_staff_tasks, is_overdue


TODAY = date.today()
PAST_DEADLINE = (TODAY - timedelta(days=3)).strftime("%Y-%m-%dT23:59:59+03:00")
FUTURE_DEADLINE = (TODAY + timedelta(days=3)).strftime("%Y-%m-%dT23:59:59+03:00")

SAMPLE_TASKS = [
    {"ID": "1", "TITLE": "Сделать P&L", "STATUS": "3", "RESPONSIBLE_ID": "1435",
     "DEADLINE": PAST_DEADLINE, "CLOSED_DATE": "2026-05-05T10:00:00+03:00"},
    {"ID": "2", "TITLE": "Проверить WB", "STATUS": "2", "RESPONSIBLE_ID": "1435",
     "DEADLINE": FUTURE_DEADLINE, "CLOSED_DATE": None},
    {"ID": "3", "TITLE": "Просрочена задача", "STATUS": "2", "RESPONSIBLE_ID": "1435",
     "DEADLINE": PAST_DEADLINE, "CLOSED_DATE": None},
    {"ID": "4", "TITLE": "Задача Дмитрия", "STATUS": "2", "RESPONSIBLE_ID": "17",
     "DEADLINE": FUTURE_DEADLINE, "CLOSED_DATE": None},
]

SAMPLE_STAFF = {
    "1435": {"name": "Артем Колчин", "department": "Финансы", "role": "Финансовый менеджер"},
    "17":   {"name": "Дмитрий Дрозд", "department": "Склад / Закупки", "role": "Руководитель склада"},
}


def test_overdue_detection():
    task_overdue = {"STATUS": "2", "DEADLINE": PAST_DEADLINE}
    task_done = {"STATUS": "3", "DEADLINE": PAST_DEADLINE}
    task_future = {"STATUS": "2", "DEADLINE": FUTURE_DEADLINE}

    assert is_overdue(task_overdue) is True
    assert is_overdue(task_done) is False
    assert is_overdue(task_future) is False


def test_parse_counts_correctly():
    result = parse_staff_tasks(SAMPLE_TASKS, SAMPLE_STAFF)

    artem = result[1435]
    assert artem["done"] == 1
    assert artem["active"] == 1
    assert artem["overdue"] == 1


def test_parse_includes_task_titles_in_done():
    result = parse_staff_tasks(SAMPLE_TASKS, SAMPLE_STAFF)

    artem = result[1435]
    assert any("P&L" in t for t in artem["done_titles"])


def test_parse_staff_isolation():
    result = parse_staff_tasks(SAMPLE_TASKS, SAMPLE_STAFF)

    artem = result[1435]
    dmitry = result[17]
    assert artem["active"] == 1
    assert dmitry["active"] == 1
