from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.config import get_week_bounds


def test_week_bounds_from_wednesday():
    # Среда 7 мая 2026 → неделя пн 4 мая – вс 10 мая
    current_start, current_end, prev_start, prev_end = get_week_bounds(date(2026, 5, 7))
    assert current_start == date(2026, 5, 4)
    assert current_end == date(2026, 5, 11)   # exclusive
    assert prev_start == date(2026, 4, 27)
    assert prev_end == date(2026, 5, 4)


def test_week_bounds_from_monday():
    current_start, current_end, prev_start, prev_end = get_week_bounds(date(2026, 5, 4))
    assert current_start == date(2026, 5, 4)
    assert prev_start == date(2026, 4, 27)


def test_week_bounds_from_sunday():
    current_start, current_end, prev_start, prev_end = get_week_bounds(date(2026, 5, 3))
    assert current_start == date(2026, 4, 27)
    assert current_end == date(2026, 5, 4)


def test_models_list_has_16_items():
    from modules.coo_report.config import MODELS
    assert len(MODELS) == 16


def test_bitrix_status_covers_key_codes():
    from modules.coo_report.config import BITRIX_STATUS
    assert BITRIX_STATUS["3"] == "Выполнено"
    assert BITRIX_STATUS["2"] == "В работе"
