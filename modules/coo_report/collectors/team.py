"""Сборщик данных по задачам команды из Битрикс24."""

import json
import subprocess
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.coo_report.config import COO_STAFF, BITRIX_DONE_STATUSES, BITRIX_ACTIVE_STATUSES

OUTPUT_PATH = Path("/tmp/coo_team.json")

_BITRIX_FIELD_MAP = {
    'responsibleId': 'RESPONSIBLE_ID',
    'status': 'STATUS',
    'deadline': 'DEADLINE',
    'closedDate': 'CLOSED_DATE',
    'title': 'TITLE',
    'id': 'ID',
}


def _normalize_task(task: dict) -> dict:
    result = dict(task)
    for lower, upper in _BITRIX_FIELD_MAP.items():
        if lower in result and upper not in result:
            result[upper] = result[lower]
    return result
BITRIX_DATA_PATH = Path("/tmp/bitrix_report_data.json")
FETCH_SCRIPT = PROJECT_ROOT / "modules" / "bitrix-analytics" / "fetch_data.py"
MAX_DATA_AGE_HOURS = 24


def is_overdue(task: dict) -> bool:
    """Задача просрочена: не завершена И дедлайн в прошлом."""
    if task.get("STATUS") in BITRIX_DONE_STATUSES:
        return False
    deadline_str = task.get("DEADLINE", "")
    if not deadline_str:
        return False
    try:
        deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        now = datetime.now(timezone(timedelta(hours=3)))  # UTC+3
        return deadline < now
    except (ValueError, TypeError):
        return False


def _ensure_fresh_data() -> bool:
    """
    Проверяет возраст /tmp/bitrix_report_data.json.
    Если файл старше MAX_DATA_AGE_HOURS — перезапускает fetch_data.py.
    Возвращает True если данные актуальны (не пришлось обновлять).
    """
    if BITRIX_DATA_PATH.exists():
        age_hours = (datetime.now().timestamp() - BITRIX_DATA_PATH.stat().st_mtime) / 3600
        if age_hours < MAX_DATA_AGE_HOURS:
            return True

    print("Данные Битрикс устарели или отсутствуют, обновляю...", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, str(FETCH_SCRIPT), "--days", "7", "--output", str(BITRIX_DATA_PATH)],
        capture_output=True, text=True, timeout=300,
    )
    return result.returncode == 0


def parse_staff_tasks(tasks: list, staff: dict) -> dict:
    """
    Разбирает список задач Битрикс по сотрудникам из COO_STAFF.

    staff: {str(id): {name, department, role}} — из JSON-файла Битрикс.
    """
    result: dict = {}

    for staff_id_str, info in staff.items():
        staff_id = int(staff_id_str)
        if staff_id not in COO_STAFF:
            continue
        result[staff_id] = {
            "name": COO_STAFF[staff_id],
            "full_name": info.get("name", ""),
            "role": info.get("role", ""),
            "done": 0,
            "active": 0,
            "overdue": 0,
            "done_titles": [],
            "overdue_titles": [],
            "active_titles": [],
        }

    for task in tasks:
        try:
            responsible_id = int(task.get("RESPONSIBLE_ID", 0))
        except (ValueError, TypeError):
            continue

        if responsible_id not in result:
            continue

        person = result[responsible_id]
        status = str(task.get("STATUS", ""))
        title = task.get("TITLE", "—")

        if status in BITRIX_DONE_STATUSES:
            person["done"] += 1
            person["done_titles"].append(title)
        elif is_overdue(task):
            person["overdue"] += 1
            person["overdue_titles"].append(title)
        elif status in BITRIX_ACTIVE_STATUSES:
            person["active"] += 1
            person["active_titles"].append(title)

    return result


def collect(ref_date: date = None) -> dict:
    """Собирает данные по задачам команды."""
    refreshed = _ensure_fresh_data()

    if not BITRIX_DATA_PATH.exists():
        return {
            "error": "Данные Битрикс недоступны — fetch_data.py не запустился",
            "staff": {},
        }

    raw = json.loads(BITRIX_DATA_PATH.read_text(encoding="utf-8"))
    tasks = [_normalize_task(t) for t in raw.get("tasks", [])]
    staff = raw.get("staff", {})
    period = raw.get("period", {})

    parsed = parse_staff_tasks(tasks, staff)

    return {
        "staff": {str(k): v for k, v in parsed.items()},
        "data_refreshed": not refreshed,
        "bitrix_period": period,
    }


if __name__ == "__main__":
    ref = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    data = collect(ref)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Команда сохранена → {OUTPUT_PATH}")
    for uid, info in data.get("staff", {}).items():
        name = info.get("name", uid)
        print(f"  {name:12s}  выполнено {info['done']}  в работе {info['active']}  просрочено {info['overdue']}")
