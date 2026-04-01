"""
Unit tests for scripts/run_report.py schedule logic, lock-file, and date ranges.

TDD RED phase: all tests defined against the contract before implementation.

Functions under test (will be in scripts/run_report.py):
- get_types_for_today(today: date) -> list[ReportType]
- is_locked(report_type: str, target_date: date, locks_dir: Path) -> bool
- acquire_lock(report_type: str, target_date: date, locks_dir: Path) -> None
- compute_date_range(period: str, target_date: date) -> tuple[str, str]
- should_send_stub(now: datetime) -> bool
- is_final_window(now: datetime) -> bool
- REPORT_ORDER: list[ReportType]
- STUB_HOURS: set[int]
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import pytest

# Ensure project root is on sys.path for `from scripts.run_report import ...`
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.run_report import (
    REPORT_ORDER,
    STUB_HOURS,
    acquire_lock,
    compute_date_range,
    get_types_for_today,
    is_final_window,
    is_locked,
    should_send_stub,
)
from agents.oleg.pipeline.report_types import REPORT_CONFIGS, ReportType


# ---------------------------------------------------------------------------
# Schedule logic: get_types_for_today
# ---------------------------------------------------------------------------

def test_daily_every_day():
    """Tuesday: only DAILY is returned."""
    # 2026-03-31 is a Tuesday
    result = get_types_for_today(date(2026, 3, 31))
    assert ReportType.DAILY in result
    assert ReportType.WEEKLY not in result
    assert ReportType.MONTHLY not in result
    assert ReportType.MARKETING_WEEKLY not in result
    assert ReportType.FUNNEL_WEEKLY not in result
    assert ReportType.FINOLOG_WEEKLY not in result
    assert ReportType.LOCALIZATION_WEEKLY not in result


def test_weekly_on_monday():
    """Monday (2026-03-30): DAILY + all weekly types, NO monthly types."""
    # 2026-03-30 is a Monday, day 30 — outside 1-7 so no monthly
    result = get_types_for_today(date(2026, 3, 30))
    assert ReportType.DAILY in result
    assert ReportType.WEEKLY in result
    assert ReportType.MARKETING_WEEKLY in result
    assert ReportType.FUNNEL_WEEKLY in result
    assert ReportType.FINOLOG_WEEKLY in result
    assert ReportType.LOCALIZATION_WEEKLY in result
    assert ReportType.MONTHLY not in result
    assert ReportType.MARKETING_MONTHLY not in result


def test_monthly_first_monday():
    """Monday, day 6 (2026-04-06): all 8 types including monthly."""
    # 2026-04-06 is a Monday, day 6 — in range 1-7
    result = get_types_for_today(date(2026, 4, 6))
    assert len(result) == 8
    assert ReportType.DAILY in result
    assert ReportType.WEEKLY in result
    assert ReportType.MONTHLY in result
    assert ReportType.MARKETING_WEEKLY in result
    assert ReportType.MARKETING_MONTHLY in result
    assert ReportType.FUNNEL_WEEKLY in result
    assert ReportType.FINOLOG_WEEKLY in result
    assert ReportType.LOCALIZATION_WEEKLY in result


def test_monthly_not_on_tuesday():
    """Wednesday, day 1 (2026-04-01): only DAILY — monthly only on Mondays."""
    # 2026-04-01 is a Wednesday, day 1 — monthly period, but NOT a Monday
    result = get_types_for_today(date(2026, 4, 1))
    assert result == [ReportType.DAILY]
    assert ReportType.MONTHLY not in result
    assert ReportType.WEEKLY not in result


def test_monthly_not_after_7th():
    """Monday, day 13 (2026-04-13): weekly types but NOT monthly (day > 7)."""
    # 2026-04-13 is a Monday, day 13 — outside 1-7
    result = get_types_for_today(date(2026, 4, 13))
    assert ReportType.DAILY in result
    assert ReportType.WEEKLY in result
    assert ReportType.MONTHLY not in result
    assert ReportType.MARKETING_MONTHLY not in result


def test_report_order():
    """Monthly Monday returns types in exact defined order."""
    # 2026-04-06 is Monday, day 6 — all 8 types in order
    result = get_types_for_today(date(2026, 4, 6))
    expected_order = [
        ReportType.DAILY,
        ReportType.WEEKLY,
        ReportType.MONTHLY,
        ReportType.MARKETING_WEEKLY,
        ReportType.MARKETING_MONTHLY,
        ReportType.FUNNEL_WEEKLY,
        ReportType.LOCALIZATION_WEEKLY,
        ReportType.FINOLOG_WEEKLY,
    ]
    assert result == expected_order


# ---------------------------------------------------------------------------
# Lock-file logic: is_locked, acquire_lock
# ---------------------------------------------------------------------------

def test_lock_prevents_rerun(tmp_path: Path):
    """is_locked returns False before acquire_lock, True after."""
    assert not is_locked("daily", date(2026, 3, 31), locks_dir=tmp_path)
    acquire_lock("daily", date(2026, 3, 31), locks_dir=tmp_path)
    assert is_locked("daily", date(2026, 3, 31), locks_dir=tmp_path)


def test_lock_different_date(tmp_path: Path):
    """Lock for date A does not affect date B."""
    acquire_lock("daily", date(2026, 3, 31), locks_dir=tmp_path)
    assert not is_locked("daily", date(2026, 4, 1), locks_dir=tmp_path)


def test_lock_different_type(tmp_path: Path):
    """Lock for type A does not affect type B."""
    acquire_lock("daily", date(2026, 3, 31), locks_dir=tmp_path)
    assert not is_locked("weekly", date(2026, 3, 31), locks_dir=tmp_path)


# ---------------------------------------------------------------------------
# Date range computation: compute_date_range
# ---------------------------------------------------------------------------

def test_compute_date_range_daily():
    """Daily: returns (target_date, target_date)."""
    result = compute_date_range("daily", date(2026, 3, 31))
    assert result == ("2026-03-31", "2026-03-31")


def test_compute_date_range_weekly():
    """Weekly (Monday 2026-03-30): returns previous Mon-Sun (2026-03-23 to 2026-03-29)."""
    result = compute_date_range("weekly", date(2026, 3, 30))
    assert result == ("2026-03-23", "2026-03-29")


def test_compute_date_range_monthly():
    """Monthly (2026-04-06): returns full previous month (2026-03-01 to 2026-03-31)."""
    result = compute_date_range("monthly", date(2026, 4, 6))
    assert result == ("2026-03-01", "2026-03-31")


# ---------------------------------------------------------------------------
# Stub notification logic: should_send_stub, is_final_window
# ---------------------------------------------------------------------------

def test_should_send_stub_at_9():
    """should_send_stub returns True at 09:15 (9 is in STUB_HOURS, minute < 35)."""
    assert should_send_stub(datetime(2026, 3, 31, 9, 15)) is True


def test_should_send_stub_at_10():
    """should_send_stub returns False at 10:15 (10 not in STUB_HOURS)."""
    assert should_send_stub(datetime(2026, 3, 31, 10, 15)) is False


def test_should_send_stub_at_11():
    """should_send_stub returns True at 11:00 (11 is in STUB_HOURS, minute < 35)."""
    assert should_send_stub(datetime(2026, 3, 31, 11, 0)) is True


def test_should_send_stub_after_35_minutes():
    """should_send_stub returns False at 09:40 (minute >= 35, window passed)."""
    assert should_send_stub(datetime(2026, 3, 31, 9, 40)) is False


def test_is_final_window_at_1755():
    """is_final_window returns True at 17:55 (hour=17, minute=55)."""
    assert is_final_window(datetime(2026, 3, 31, 17, 55)) is True


def test_is_final_window_at_1500():
    """is_final_window returns False at 15:00 (hour < 17)."""
    assert is_final_window(datetime(2026, 3, 31, 15, 0)) is False


def test_is_final_window_at_1725():
    """is_final_window returns False at 17:25 (minute < 55)."""
    assert is_final_window(datetime(2026, 3, 31, 17, 25)) is False


# ---------------------------------------------------------------------------
# Constants: STUB_HOURS, REPORT_ORDER
# ---------------------------------------------------------------------------

def test_stub_hours_values():
    """STUB_HOURS must be exactly {9, 11, 13, 15, 17}."""
    assert STUB_HOURS == {9, 11, 13, 15, 17}


def test_report_order_length():
    """REPORT_ORDER must contain all 8 ReportType values."""
    assert len(REPORT_ORDER) == 8


def test_report_order_finolog_last():
    """FINOLOG_WEEKLY must be the last element in REPORT_ORDER (D-09)."""
    assert REPORT_ORDER[-1] == ReportType.FINOLOG_WEEKLY


# ---------------------------------------------------------------------------
# SCHED-04: display_name_ru for all 8 types
# ---------------------------------------------------------------------------

def test_display_name_ru_all_8():
    """Every ReportType in REPORT_CONFIGS has a non-empty display_name_ru."""
    for rt in ReportType:
        assert rt in REPORT_CONFIGS, f"Missing config for {rt}"
        config = REPORT_CONFIGS[rt]
        assert config.display_name_ru, f"display_name_ru is empty for {rt}"
        assert len(config.display_name_ru) > 0, f"display_name_ru empty for {rt}"


# ---------------------------------------------------------------------------
# D-14 smoke test: Telegram summary in pipeline
# ---------------------------------------------------------------------------

def test_telegram_summary_in_pipeline():
    """Smoke test: report_pipeline.py contains telegram_summary usage + notion_url appending (D-14)."""
    pipeline_path = Path(_PROJECT_ROOT) / "agents" / "oleg" / "pipeline" / "report_pipeline.py"
    assert pipeline_path.exists(), f"Pipeline file not found: {pipeline_path}"
    content = pipeline_path.read_text(encoding="utf-8")
    assert "telegram_summary" in content, "report_pipeline.py must reference telegram_summary"
    assert "notion_url" in content, "report_pipeline.py must reference notion_url"
    # Confirm that telegram_summary is combined with notion_url (the D-14 pattern)
    assert "telegram_summary" in content and "notion_url" in content
