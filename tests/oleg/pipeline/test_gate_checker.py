"""
Unit tests for agents/oleg/pipeline/gate_checker.py.

All DB access is mocked — no real DB calls are made.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from agents.oleg.pipeline.gate_checker import (
    CheckAllResult,
    GateChecker,
    GateResult,
    format_preflight_message,
)


# ---------------------------------------------------------------------------
# Helpers for mocking _db_cursor context manager
# ---------------------------------------------------------------------------

def _make_cursor(fetchone_return=None, fetchall_return=None):
    """Return a mock cursor."""
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_return
    cur.fetchall.return_value = fetchall_return or []
    return cur


@contextmanager
def _cursor_ctx(cursor):
    conn = MagicMock()
    yield conn, cursor


# ---------------------------------------------------------------------------
# Test: GateResult dataclass has required attributes
# ---------------------------------------------------------------------------

def test_gate_result_attributes():
    gate = GateResult(name="wb_orders_freshness", passed=True, detail="OK", is_hard=True)
    assert gate.name == "wb_orders_freshness"
    assert gate.passed is True
    assert gate.detail == "OK"
    assert gate.is_hard is True


def test_gate_result_soft_default():
    gate = GateResult(name="advertising_data", passed=False, is_hard=False)
    assert gate.is_hard is False
    assert gate.passed is False


# ---------------------------------------------------------------------------
# Test: CheckAllResult properties
# ---------------------------------------------------------------------------

def test_check_all_result_hard_failed():
    gates = [
        GateResult("wb_orders_freshness", passed=False, is_hard=True),
        GateResult("fin_data_freshness", passed=True, is_hard=True),
        GateResult("advertising_data", passed=False, is_hard=False),
    ]
    result = CheckAllResult(gates=gates, target_date=date.today())
    assert len(result.hard_failed) == 1
    assert result.hard_failed[0].name == "wb_orders_freshness"


def test_check_all_result_soft_warnings():
    gates = [
        GateResult("wb_orders_freshness", passed=True, is_hard=True),
        GateResult("advertising_data", passed=False, is_hard=False),
        GateResult("logistics_data", passed=False, is_hard=False),
    ]
    result = CheckAllResult(gates=gates, target_date=date.today())
    assert result.can_run is True
    assert len(result.soft_warnings) == 2


def test_check_all_result_can_run_blocks_on_hard_failure():
    gates = [
        GateResult("wb_orders_freshness", passed=False, is_hard=True),
    ]
    result = CheckAllResult(gates=gates, target_date=date.today())
    assert result.can_run is False


def test_check_all_result_can_run_true_all_hard_pass():
    gates = [
        GateResult("wb_orders_freshness", passed=True, is_hard=True),
        GateResult("ozon_orders_freshness", passed=True, is_hard=True),
        GateResult("fin_data_freshness", passed=True, is_hard=True),
        GateResult("advertising_data", passed=False, is_hard=False),
    ]
    result = CheckAllResult(gates=gates, target_date=date.today())
    assert result.can_run is True


# ---------------------------------------------------------------------------
# Test: GateChecker.check_all — all fresh (today) → can_run == True
# ---------------------------------------------------------------------------

def _patch_cursor_fresh(monkeypatch, today: date):
    """Patch _db_cursor so all freshness queries return today's date."""
    def mock_db_cursor(conn_factory):
        # Return today as datetime to also test normalization
        cur = _make_cursor(fetchone_return=(datetime.combine(today, datetime.min.time()),))
        return _cursor_ctx(cur)

    monkeypatch.setattr(
        "agents.oleg.pipeline.gate_checker._db_cursor", mock_db_cursor
    )


def test_check_all_wb_all_fresh(monkeypatch):
    today = date.today()
    call_count = [0]

    def mock_db_cursor(conn_factory):
        call_count[0] += 1
        # For soft gates: advertising sum, margin fill, logistics sum
        if call_count[0] in (4, 5, 6):
            cur = _make_cursor(fetchone_return=(100,))  # non-zero
        else:
            # Hard gates: return today as datetime
            cur = _make_cursor(fetchone_return=(datetime.combine(today, datetime.min.time()),))
        return _cursor_ctx(cur)

    monkeypatch.setattr("agents.oleg.pipeline.gate_checker._db_cursor", mock_db_cursor)

    checker = GateChecker()
    result = checker.check_all("wb", target_date=today)

    assert result.can_run is True
    assert result.hard_failed == []


# ---------------------------------------------------------------------------
# Test: stale WB dateupdate → can_run == False, hard_failed contains wb_orders_freshness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("marketplace,stale_gate", [
    ("wb", "wb_orders_freshness"),
    ("ozon", "ozon_orders_freshness"),
])
def test_check_all_stale_dateupdate_blocks(monkeypatch, marketplace, stale_gate):
    today = date.today()
    yesterday = date(today.year, today.month, today.day).__class__.fromordinal(today.toordinal() - 1)
    call_count = [0]

    def mock_db_cursor(conn_factory):
        call_count[0] += 1
        call_num = call_count[0]
        # Hard gates: gate 1 = wb_orders_freshness (stale for wb test),
        # gate 2 = ozon_orders_freshness (stale for ozon test),
        # gate 3 = fin_data_freshness (fresh)
        if marketplace == "wb" and call_num == 1:
            # wb_orders_freshness: stale
            cur = _make_cursor(fetchone_return=(yesterday,))
        elif marketplace == "ozon" and call_num == 2:
            # ozon_orders_freshness: stale
            cur = _make_cursor(fetchone_return=(yesterday,))
        elif call_num <= 3:
            # other hard gates: fresh
            cur = _make_cursor(fetchone_return=(today,))
        else:
            # soft gates
            cur = _make_cursor(fetchone_return=(50,))
        return _cursor_ctx(cur)

    monkeypatch.setattr("agents.oleg.pipeline.gate_checker._db_cursor", mock_db_cursor)

    checker = GateChecker()
    result = checker.check_all(marketplace, target_date=today)

    assert result.can_run is False
    failed_names = [g.name for g in result.hard_failed]
    assert stale_gate in failed_names


# ---------------------------------------------------------------------------
# Test: soft gate failure → can_run still True, soft_warnings non-empty
# ---------------------------------------------------------------------------

def test_soft_gate_failure_does_not_block(monkeypatch):
    today = date.today()
    call_count = [0]

    def mock_db_cursor(conn_factory):
        call_count[0] += 1
        if call_count[0] <= 3:
            # Hard gates: all pass (fresh today)
            cur = _make_cursor(fetchone_return=(today,))
        else:
            # Soft gates: all return 0 (fail)
            cur = _make_cursor(fetchone_return=(0,))
        return _cursor_ctx(cur)

    monkeypatch.setattr("agents.oleg.pipeline.gate_checker._db_cursor", mock_db_cursor)

    checker = GateChecker()
    result = checker.check_all("wb", target_date=today)

    assert result.can_run is True
    assert len(result.soft_warnings) > 0


# ---------------------------------------------------------------------------
# Test: datetime vs date normalization
# ---------------------------------------------------------------------------

def test_datetime_normalization(monkeypatch):
    """dateupdate returned as datetime object must still compare correctly with date."""
    today = date.today()
    today_as_datetime = datetime(today.year, today.month, today.day, 6, 0, 0)
    call_count = [0]

    def mock_db_cursor(conn_factory):
        call_count[0] += 1
        if call_count[0] <= 3:
            cur = _make_cursor(fetchone_return=(today_as_datetime,))
        else:
            cur = _make_cursor(fetchone_return=(1,))
        return _cursor_ctx(cur)

    monkeypatch.setattr("agents.oleg.pipeline.gate_checker._db_cursor", mock_db_cursor)

    checker = GateChecker()
    result = checker.check_all("wb", target_date=today)
    assert result.can_run is True


# ---------------------------------------------------------------------------
# Test: DiagnosticRunner compatibility
# (check_all returns result with .gates[].passed, .gates[].name, .gates[].detail)
# ---------------------------------------------------------------------------

def test_diagnostic_runner_compatibility(monkeypatch):
    today = date.today()
    call_count = [0]

    def mock_db_cursor(conn_factory):
        call_count[0] += 1
        if call_count[0] <= 3:
            cur = _make_cursor(fetchone_return=(today,))
        else:
            cur = _make_cursor(fetchone_return=(1,))
        return _cursor_ctx(cur)

    monkeypatch.setattr("agents.oleg.pipeline.gate_checker._db_cursor", mock_db_cursor)

    checker = GateChecker()
    result = checker.check_all("wb", target_date=today)

    # DiagnosticRunner iterates gate_result.gates and accesses .passed, .name, .detail
    for gate in result.gates:
        assert hasattr(gate, "passed")
        assert hasattr(gate, "name")
        assert hasattr(gate, "detail")


# ---------------------------------------------------------------------------
# Test: format_preflight_message
# ---------------------------------------------------------------------------

def test_format_preflight_message_success():
    gates = [
        GateResult("wb_orders_freshness", passed=True, is_hard=True),
        GateResult("ozon_orders_freshness", passed=True, is_hard=True),
        GateResult("fin_data_freshness", passed=True, is_hard=True),
    ]
    result = CheckAllResult(
        gates=gates,
        target_date=date(2026, 3, 31),
        summary_metrics={"wb_orders": 100, "ozon_orders": 50},
    )
    msg = format_preflight_message(result, ["Ежедневный", "Маркетинговый"])
    assert "✅" in msg
    assert "2026-03-31" in msg or "31" in msg
    assert "Ежедневный" in msg


def test_format_preflight_message_failure():
    gates = [
        GateResult("wb_orders_freshness", passed=False, detail="Данные устарели", is_hard=True),
    ]
    result = CheckAllResult(gates=gates, target_date=date(2026, 3, 31))
    msg = format_preflight_message(result, [])
    assert "❌" in msg
    assert "не готовы" in msg
