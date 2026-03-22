import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime

from agents.v3.conductor.conductor import (
    data_ready_check,
    generate_and_validate,
    deadline_check,
)
from agents.v3.conductor.schedule import ReportType
from agents.v3.conductor.validator import ValidationVerdict, ValidationResult


@pytest.fixture
def mock_gates():
    """Mock GateChecker that returns can_generate=True for both channels."""
    checker = MagicMock()
    wb_result = MagicMock(can_generate=True, has_caveats=False, caveats=[], gates=[])
    ozon_result = MagicMock(can_generate=True, has_caveats=False, caveats=[], gates=[])
    checker.check_all.side_effect = lambda mp: wb_result if mp == "wb" else ozon_result
    return checker


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.get_successful.return_value = set()
    state.get_attempts.return_value = 0
    state.already_notified.return_value = False
    return state


@pytest.mark.asyncio
async def test_data_ready_check_skips_when_gates_fail():
    """If gates fail, data_ready_check returns without sending messages."""
    checker = MagicMock()
    fail_result = MagicMock(can_generate=False)
    checker.check_all.return_value = fail_result

    telegram = AsyncMock()
    state = MagicMock()

    await data_ready_check(
        gate_checker=checker,
        conductor_state=state,
        telegram_send=telegram,
        orchestrator=AsyncMock(),
        delivery=AsyncMock(),
        scheduler=MagicMock(),
        today=date(2026, 3, 19),
    )

    telegram.assert_not_called()


@pytest.mark.asyncio
async def test_data_ready_check_skips_when_all_done(mock_gates, mock_state):
    """If all reports already generated, skip."""
    mock_state.get_successful.return_value = {"daily"}  # Thursday — only daily needed

    telegram = AsyncMock()

    await data_ready_check(
        gate_checker=mock_gates,
        conductor_state=mock_state,
        telegram_send=telegram,
        orchestrator=AsyncMock(),
        delivery=AsyncMock(),
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    telegram.assert_not_called()


@pytest.mark.asyncio
async def test_data_ready_check_sends_data_ready_message(mock_gates, mock_state):
    """When gates pass and reports pending, sends 'data ready' message."""
    telegram = AsyncMock()
    orchestrator = MagicMock()
    orchestrator.run_daily_report = AsyncMock(return_value={
        "status": "success",
        "report": {
            "detailed_report": "x" * 600,
            "brief_report": "brief",
            "telegram_summary": "y" * 200,
        },
        "agents_called": 3,
        "agents_succeeded": 3,
        "agents_failed": 0,
    })
    delivery = AsyncMock(return_value={"notion": {"page_url": "https://notion.so/abc"}})

    await data_ready_check(
        gate_checker=mock_gates,
        conductor_state=mock_state,
        telegram_send=telegram,
        orchestrator=orchestrator,
        delivery=delivery,
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    # First call should be "data ready" message
    assert telegram.call_count >= 1
    first_msg = telegram.call_args_list[0][0][0]
    assert "Данные" in first_msg and "готовы" in first_msg
