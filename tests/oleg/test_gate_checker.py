"""Tests for GateChecker with mocked DB."""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

import pytest

from agents.oleg_v2.pipeline.gate_checker import GateChecker, GateCheckResult


class FakeCursor:
    """Fake DB cursor that returns pre-configured rows in sequence."""

    def __init__(self, rows):
        self._rows = list(rows)
        self._idx = 0

    def execute(self, *args, **kwargs):
        pass

    def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return (None,)


@contextmanager
def _fake_db_cursor(rows):
    """Mock _db_cursor context manager returning shared FakeCursor."""
    cursor = FakeCursor(rows)

    @contextmanager
    def fake_cursor(conn_factory):
        yield cursor  # same cursor shared across all gate checks

    with patch("shared.data_layer._get_wb_connection", return_value=MagicMock()), \
         patch("shared.data_layer._get_ozon_connection", return_value=MagicMock()), \
         patch("shared.data_layer._db_cursor", fake_cursor):
        yield


def test_all_gates_pass():
    """All gates pass with good data."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    rows = [
        (today,),          # Gate 1: ETL dateupdate = today
        (yesterday,),      # Gate 2: max date = yesterday
        (50000.0,),        # Gate 3: logistics > 0
        (100,),            # Gate 4: orders count > 0
        (1000000.0,),      # Gate 5: yesterday revenue
        (900000.0,),       # Gate 5: 7-day avg revenue
        (200, 150),        # Gate 6: total articles, filled margin
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is True
    assert len(result.gates) == 6


def test_hard_gate_etl_fails():
    """ETL not ran today → hard fail."""
    old_date = date.today() - timedelta(days=3)
    yesterday = date.today() - timedelta(days=1)

    rows = [
        (old_date,),       # Gate 1: ETL NOT today
        (yesterday,),      # Gate 2
        (50000.0,),        # Gate 3
        (100,),            # Gate 4
        (1000000.0,),      # Gate 5a
        (900000.0,),       # Gate 5b
        (200, 150),        # Gate 6
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is False
    etl_gate = result.gates[0]
    assert etl_gate.name == "ETL ran today"
    assert etl_gate.passed is False
    assert etl_gate.is_hard is True


def test_soft_gate_caveat():
    """Soft gate fails → report with caveat."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    rows = [
        (today,),          # Gate 1: pass
        (yesterday,),      # Gate 2: pass
        (50000.0,),        # Gate 3: pass
        (0,),              # Gate 4: orders = 0 → soft fail
        (1000000.0,),      # Gate 5a
        (900000.0,),       # Gate 5b
        (200, 150),        # Gate 6
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is True
    assert result.has_caveats is True
    assert len(result.caveats) >= 1


def test_db_error_graceful():
    """If DB fails, hard gates fail gracefully."""
    with patch("shared.data_layer._db_cursor", side_effect=Exception("Connection refused")), \
         patch("shared.data_layer._get_wb_connection"), \
         patch("shared.data_layer._get_ozon_connection"):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is False
    assert len(result.gates) == 6


def test_gate_result_counts():
    """Verify hard/soft counts."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    rows = [
        (today,),
        (yesterday,),
        (50000.0,),
        (100,),
        (1000000.0,),
        (900000.0,),
        (200, 150),
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.hard_total == 3
    assert result.soft_total == 3
