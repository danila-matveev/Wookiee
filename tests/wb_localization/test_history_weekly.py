"""Тесты weekly_snapshots в history.py."""
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from services.wb_localization.history import History


@pytest.fixture
def tmp_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_history.db"
        yield History(db_path=db_path)


def test_weekly_snapshots_table_created(tmp_history):
    """При инициализации History создаётся таблица weekly_snapshots."""
    conn = sqlite3.connect(tmp_history.db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_snapshots'"
    )
    assert cursor.fetchone() is not None


def test_save_weekly_snapshots(tmp_history):
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[
            {"article": "wendy/xl", "region": "Центральный", "local_orders": 50, "nonlocal_orders": 20},
            {"article": "wendy/xl", "region": "Южный", "local_orders": 30, "nonlocal_orders": 10},
        ],
    )
    data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=1)
    assert len(data) == 2
    assert data[0]["local_orders"] == 50 or data[1]["local_orders"] == 50


def test_save_weekly_snapshots_idempotent(tmp_history):
    """Повторное сохранение той же недели обновляет, не дублирует."""
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[
            {"article": "wendy/xl", "region": "Центральный", "local_orders": 50, "nonlocal_orders": 20},
        ],
    )
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[
            {"article": "wendy/xl", "region": "Центральный", "local_orders": 70, "nonlocal_orders": 15},
        ],
    )
    data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=1)
    assert len(data) == 1
    assert data[0]["local_orders"] == 70


def test_get_weekly_snapshots_by_cabinet(tmp_history):
    """Фильтрация по кабинету."""
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[{"article": "wendy/xl", "region": "Центральный", "local_orders": 50, "nonlocal_orders": 20}],
    )
    tmp_history.save_weekly_snapshots(
        cabinet="ip",
        week_start=date(2026, 4, 13),
        snapshots=[{"article": "sunny/m", "region": "Южный", "local_orders": 10, "nonlocal_orders": 5}],
    )
    ooo_data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=1)
    ip_data = tmp_history.get_weekly_snapshots(cabinet="ip", weeks_back=1)
    assert len(ooo_data) == 1
    assert len(ip_data) == 1
    assert ooo_data[0]["article"] == "wendy/xl"
    assert ip_data[0]["article"] == "sunny/m"


def test_weeks_back_limit(tmp_history):
    """get_weekly_snapshots возвращает только последние N недель."""
    base = date(2026, 1, 6)
    for week_offset in range(15):
        tmp_history.save_weekly_snapshots(
            cabinet="ooo",
            week_start=base + timedelta(weeks=week_offset),
            snapshots=[{"article": "wendy/xl", "region": "Центральный", "local_orders": 10, "nonlocal_orders": 5}],
        )
    data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=13)
    # data includes all rows for the last 13 distinct week_starts
    unique_weeks = {d["week_start"] for d in data}
    assert len(unique_weeks) == 13
