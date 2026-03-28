"""Integration test: full conductor flow with mocked orchestrator + delivery."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date
import tempfile
import os

from agents.v3.conductor.conductor import data_ready_check, deadline_check
from agents.v3.conductor.state import ConductorState
from agents.v3.conductor.schedule import ReportType


@pytest.fixture
def full_setup():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    state = ConductorState(db_path=db_path)
    state.ensure_table()

    gate_checker = MagicMock()
    wb_result = MagicMock(can_generate=True, has_caveats=False, caveats=[], gates=[])
    ozon_result = MagicMock(can_generate=True, has_caveats=False, caveats=[], gates=[])
    gate_checker.check_all.side_effect = lambda mp: wb_result if mp == "wb" else ozon_result

    telegram_messages = []
    async def telegram_send(text):
        telegram_messages.append(text)

    orchestrator = MagicMock()
    good_report = {
        "status": "success",
        "report": {
            "detailed_report": "# Отчёт\n\n## ▶ Финансовые показатели\n| Метрика | Значение |\n|---|---|\n| Выручка | 1.2M |\n\n## ▶ Заказы и продажи\nТекст анализа заказов\n\n## ▶ Маржинальность\nТекст анализа маржи\n\n" * 5,
            "brief_report": "Краткая сводка за день",
            "telegram_summary": "📊 Сводка за 19 марта:\n• Маржа: 255 тыс\n• Заказы: 1164 шт (+9.9%)" + " " * 100,
        },
        "agents_called": 3,
        "agents_succeeded": 3,
        "agents_failed": 0,
    }
    for method in ["run_daily_report", "run_weekly_report", "run_monthly_report",
                   "run_marketing_report", "run_funnel_report", "run_finolog_report",
                   "run_price_analysis"]:
        setattr(orchestrator, method, AsyncMock(return_value=good_report))

    delivery = AsyncMock(return_value={"notion": {"page_url": "https://notion.so/test"}})

    yield {
        "state": state,
        "gate_checker": gate_checker,
        "telegram_send": telegram_send,
        "telegram_messages": telegram_messages,
        "orchestrator": orchestrator,
        "delivery": delivery,
        "db_path": db_path,
    }
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_full_thursday_flow(full_setup):
    """Thursday: 1 daily report generated, telegram messages sent."""
    s = full_setup
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    # Should have "data ready" message
    assert any("готовы" in m for m in s["telegram_messages"])

    # Should have called orchestrator once (daily only)
    s["orchestrator"].run_daily_report.assert_called_once()

    # Should have delivered
    s["delivery"].assert_called_once()

    # State should show success
    done = s["state"].get_successful("2026-03-19")
    assert "daily" in done


@pytest.mark.asyncio
async def test_idempotent_second_run(full_setup):
    """Running data_ready_check twice should not duplicate reports."""
    s = full_setup
    kwargs = {
        "gate_checker": s["gate_checker"],
        "conductor_state": s["state"],
        "telegram_send": s["telegram_send"],
        "orchestrator": s["orchestrator"],
        "delivery": s["delivery"],
        "scheduler": MagicMock(),
        "today": date(2026, 3, 19),
    }

    await data_ready_check(**kwargs)
    msg_count_1 = len(s["telegram_messages"])

    await data_ready_check(**kwargs)
    msg_count_2 = len(s["telegram_messages"])

    # Second run should not produce any new messages
    assert msg_count_2 == msg_count_1


@pytest.mark.asyncio
async def test_deadline_check_alerts_on_missing(full_setup):
    """deadline_check sends alert if reports not generated."""
    s = full_setup
    await deadline_check(
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        gate_checker=s["gate_checker"],
        today=date(2026, 3, 19),
    )

    assert any("не все отчёты готовы" in m or "Не готовы" in m for m in s["telegram_messages"])


@pytest.mark.asyncio
async def test_retry_schedules_date_trigger(full_setup):
    """When validation fails, scheduler.add_job is called with DateTrigger for retry."""
    s = full_setup
    bad_report = {
        "status": "success",
        "report": {
            "detailed_report": "Не удалось сформировать ответ.",
            "brief_report": "",
            "telegram_summary": "Не удалось сформировать ответ.",
        },
        "agents_called": 1,
        "agents_succeeded": 1,
        "agents_failed": 0,
    }
    s["orchestrator"].run_daily_report = AsyncMock(return_value=bad_report)

    mock_scheduler = MagicMock()

    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=mock_scheduler,
        today=date(2026, 3, 19),
    )

    # Scheduler should have add_job called for retry
    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    assert "retry_daily" in str(call_kwargs)


@pytest.mark.asyncio
async def test_exhausted_report_not_retried_same_day(full_setup):
    """A report that exhausted all attempts today should not be re-queued via get_missed_reports.

    Regression test for the infinite hourly spam bug:
    - A report fails all MAX_ATTEMPTS → status='failed', attempts=3
    - get_missed_reports returns it as failed_or_missing
    - Without the exhausted check, data_ready_check would re-queue it every hour
    - With the fix, exhausted_today blocks the re-queue for the same date
    """
    from agents.v3.conductor.conductor import MAX_ATTEMPTS

    s = full_setup

    # Simulate a report that has already been attempted MAX_ATTEMPTS times and failed today
    report_date = "2026-03-28"
    s["state"].log(report_date, "weekly", status="failed", attempt=MAX_ATTEMPTS)

    exhausted = s["state"].get_exhausted_types(report_date, MAX_ATTEMPTS)
    assert "weekly" in exhausted

    # Confirm that data_ready_check on the same day (Saturday — no weekly scheduled, but missed recovery)
    # does NOT re-add the exhausted weekly report
    msgs_before = len(s["telegram_messages"])
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 28),  # Saturday — would recover missed weekly from Monday
    )
    # The orchestrator's run_weekly_report should NOT have been called
    s["orchestrator"].run_weekly_report.assert_not_called()


@pytest.mark.asyncio
async def test_single_combined_data_ready_message(full_setup):
    """All data-ready info should arrive as ONE message, not 3 separate ones."""
    s = full_setup
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    # Count "data ready" messages (messages containing "готовы")
    ready_msgs = [m for m in s["telegram_messages"] if "готовы" in m]
    assert len(ready_msgs) == 1, f"Expected 1 data-ready message, got {len(ready_msgs)}: {ready_msgs}"

    # The single message should contain both WB and OZON
    msg = ready_msgs[0]
    assert "WB" in msg
    assert "OZON" in msg


@pytest.mark.asyncio
async def test_deadline_check_silent_when_all_done(full_setup):
    """deadline_check is silent if all reports generated."""
    s = full_setup
    # First generate the report
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 19),
    )
    msg_before = len(s["telegram_messages"])

    await deadline_check(
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        gate_checker=s["gate_checker"],
        today=date(2026, 3, 19),
    )

    # No new messages
    assert len(s["telegram_messages"]) == msg_before
