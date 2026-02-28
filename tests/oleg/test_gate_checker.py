"""Tests for GateChecker with mocked DB."""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

import pytest

from agents.oleg.pipeline.gate_checker import GateChecker, GateCheckResult, GateResult


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
        yield MagicMock(), cursor  # (conn, cur) tuple matching _db_cursor signature

    today = date.today()
    yesterday = today - timedelta(days=1)

    with patch("shared.data_layer._get_wb_connection", return_value=MagicMock()), \
         patch("shared.data_layer._get_ozon_connection", return_value=MagicMock()), \
         patch("shared.data_layer._db_cursor", fake_cursor), \
         patch("agents.oleg.pipeline.gate_checker.get_today_msk", return_value=today), \
         patch("agents.oleg.pipeline.gate_checker.get_yesterday_msk", return_value=yesterday):
        yield


def _good_rows():
    """Rows that make all 6 gates pass."""
    return [
        (date.today(),),   # Gate 1: ETL dateupdate = today
        (50,),             # Gate 2a: source orders count for yesterday
        (50.0,),           # Gate 2b: 7-day avg count → 50/50 = 100% ≥ 30%
        (50000.0,),        # Gate 3: logistics > 0
        (100,),            # Gate 4a: yesterday orders count
        (90.0,),           # Gate 4b: 7-day avg count
        (1000000.0,),      # Gate 5a: yesterday revenue
        (900000.0,),       # Gate 5b: 7-day avg revenue
        (200, 150),        # Gate 6: total articles, filled margin
    ]


def test_all_gates_pass():
    """All gates pass with good data."""
    with _fake_db_cursor(_good_rows()):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is True
    assert len(result.gates) == 6


def test_hard_gate_etl_fails():
    """ETL not ran today → hard fail."""
    old_date = date.today() - timedelta(days=3)

    rows = [
        (old_date,),       # Gate 1: ETL NOT today
        (50,),             # Gate 2a
        (50.0,),           # Gate 2b: 7d avg
        (50000.0,),        # Gate 3
        (100,),            # Gate 4a
        (90.0,),           # Gate 4b
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


def test_hard_gate_source_not_loaded():
    """No orders for yesterday → hard fail."""
    rows = [
        (date.today(),),   # Gate 1: pass
        (0,),              # Gate 2a: NO orders for yesterday
        (100.0,),          # Gate 2b: 7d avg = 100 → 0/100 = 0% < 30%
        (50000.0,),        # Gate 3
        (100,),            # Gate 4a
        (90.0,),           # Gate 4b
        (1000000.0,),      # Gate 5a
        (900000.0,),       # Gate 5b
        (200, 150),        # Gate 6
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is False
    source_gate = result.gates[1]
    assert source_gate.name == "Source data loaded today"
    assert source_gate.passed is False
    assert source_gate.is_hard is True


def test_soft_gate_orders_volume_low():
    """Orders volume < 70% of avg → soft fail with caveat."""
    rows = [
        (date.today(),),   # Gate 1: pass
        (50,),             # Gate 2a: pass
        (50.0,),           # Gate 2b: 7d avg = 50 → 100% ≥ 30%
        (50000.0,),        # Gate 3: pass
        (30,),             # Gate 4a: yesterday count = 30
        (100.0,),          # Gate 4b: avg = 100 → 30% < 70%
        (1000000.0,),      # Gate 5a
        (900000.0,),       # Gate 5b
        (200, 150),        # Gate 6
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.can_generate is True
    assert result.has_caveats is True
    volume_gate = result.gates[3]
    assert volume_gate.name == "Orders volume vs avg"
    assert volume_gate.passed is False


def test_soft_gate_caveat():
    """Soft gate fails → report with caveat."""
    rows = [
        (date.today(),),   # Gate 1: pass
        (50,),             # Gate 2a: pass
        (50.0,),           # Gate 2b: 7d avg = 50 → 100% ≥ 30%
        (50000.0,),        # Gate 3: pass
        (0,),              # Gate 4a: orders = 0
        (100.0,),          # Gate 4b: avg = 100 → 0% < 70%
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
    with _fake_db_cursor(_good_rows()):
        gc = GateChecker()
        result = gc.check_all("wb")

    assert result.hard_total == 3
    assert result.soft_total == 3


def test_ozon_gates_pass():
    """Ozon marketplace gates pass with good data."""
    with _fake_db_cursor(_good_rows()):
        gc = GateChecker()
        result = gc.check_all("ozon")

    assert result.can_generate is True
    assert len(result.gates) == 6


def test_column_map_completeness():
    """Both marketplaces have all required column mappings."""
    gc = GateChecker()
    for mp in ["wb", "ozon"]:
        for col in ["dateupdate", "logistics", "revenue", "marga"]:
            assert gc._col(mp, col), f"Missing column mapping for {mp}.{col}"


def test_orders_config_completeness():
    """Both marketplaces have orders table config."""
    for mp in ["wb", "ozon"]:
        cfg = GateChecker._ORDERS_CONFIG[mp]
        assert "table" in cfg
        assert "date_col" in cfg


def test_extra_dict_populated():
    """Gate results have extra dict with structured data for formatting."""
    from datetime import datetime
    today = date.today()
    # Use a datetime for Gate 1 so update_time is extracted
    now = datetime(today.year, today.month, today.day, 7, 30, 0)
    rows = [
        (now,),            # Gate 1: ETL dateupdate = today as datetime
        (50,),             # Gate 2a: source orders count
        (50.0,),           # Gate 2b: 7d avg → 100% ≥ 30%
        (50000.0,),        # Gate 3: logistics
        (100,),            # Gate 4a: yesterday orders count
        (90.0,),           # Gate 4b: 7-day avg count
        (1000000.0,),      # Gate 5a: yesterday revenue
        (900000.0,),       # Gate 5b: 7-day avg revenue
        (200, 150),        # Gate 6: total articles, filled margin
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    # Gate 1: ETL — update_time
    etl = result.gates[0]
    assert etl.extra.get("update_time") == "07:30"

    # Gate 2: Source — order_count
    src = result.gates[1]
    assert src.extra.get("order_count") == 50

    # Gate 4: Orders volume — count + ratio
    orders = result.gates[3]
    assert orders.extra.get("count") == 100
    assert orders.extra.get("ratio") is not None

    # Gate 5: Revenue — ratio
    rev = result.gates[4]
    assert rev.extra.get("ratio") is not None

    # Gate 6: Margin — filled, total, pct
    margin = result.gates[5]
    assert margin.extra.get("filled") == 150
    assert margin.extra.get("total") == 200


def test_format_status_message_russian():
    """format_status_message outputs human-readable Russian text."""
    with _fake_db_cursor(_good_rows()):
        gc = GateChecker()
        result = gc.check_all("wb")

    msg = result.format_status_message("2026-02-25", marketplace="wb")

    # Should contain Russian date, not ISO format
    assert "25 февраля" in msg
    assert "WB" in msg
    # Should NOT contain English gate names
    assert "Hard:" not in msg
    assert "Soft:" not in msg
    assert "ETL ran today" not in msg


def test_format_status_message_fail():
    """format_status_message shows failure details when hard gate fails."""
    old_date = date.today() - timedelta(days=3)
    rows = [
        (old_date,),       # Gate 1: ETL NOT today
        (0,),              # Gate 2a: NO orders
        (100.0,),          # Gate 2b: 7d avg
        (0,),              # Gate 3: no logistics
        (100,),            # Gate 4a
        (90.0,),           # Gate 4b
        (1000000.0,),      # Gate 5a
        (900000.0,),       # Gate 5b
        (200, 150),        # Gate 6
    ]

    with _fake_db_cursor(rows):
        gc = GateChecker()
        result = gc.check_all("wb")

    msg = result.format_status_message("2026-02-25")

    assert "❌" in msg
    assert "не готовы" in msg
    assert "не обновлены" in msg or "⏳" in msg
