"""
Unit tests for agents/oleg/pipeline/report_pipeline.py

Tests cover:
- REL-02: Retry on empty LLM responses
- REL-03: Report with zero real content is NOT published
- REL-04: Missing sections get Russian human-readable placeholders
- REL-05: All required sections present after validate_and_degrade
- REL-07: Notion published BEFORE Telegram; Telegram failure does not fail pipeline
"""
from __future__ import annotations

import asyncio
from datetime import date
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from agents.oleg.pipeline.report_pipeline import (
    ReportPipelineResult,
    _is_substantial,
    _run_chain_with_retry,
    validate_and_degrade,
    has_substantial_content,
    run_report,
    DEGRADATION_PLACEHOLDER,
)
from agents.oleg.pipeline.report_types import ReportType
from agents.oleg.orchestrator.chain import ChainResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chain_result(detailed: str = "", summary: str = "", telegram_summary: str = "") -> ChainResult:
    """Build a minimal ChainResult for testing."""
    return ChainResult(
        summary=summary,
        detailed=detailed,
        telegram_summary=telegram_summary,
    )


def _good_chain_result() -> ChainResult:
    """A chain result that passes _is_substantial check."""
    detailed = (
        "## Финансовые результаты\n\n"
        "Выручка выросла на 15% по сравнению с предыдущим периодом. "
        "Маржа составила 32%, что соответствует плановым показателям.\n\n"
        "## Рекламные расходы\n\n"
        "ДРР внутренний снизился до 8%. Эффективность рекламы улучшилась.\n\n"
        "## Прогноз\n\n"
        "Ожидается сохранение текущей тенденции в следующем периоде.\n"
    )
    return _make_chain_result(detailed=detailed, telegram_summary="Краткая сводка")


# ---------------------------------------------------------------------------
# REL-02: _is_substantial
# ---------------------------------------------------------------------------

class TestIsSubstantial:
    def test_returns_false_for_short_result(self):
        result = _make_chain_result(detailed="Короткий текст")
        assert _is_substantial(result) is False

    def test_returns_false_for_result_without_headings(self):
        # Long but no ## headings
        detailed = "A" * 300  # > 200 chars but no ##
        result = _make_chain_result(detailed=detailed)
        assert _is_substantial(result) is False

    def test_returns_true_for_good_result(self):
        result = _good_chain_result()
        assert _is_substantial(result) is True

    def test_returns_false_when_detailed_is_none(self):
        result = ChainResult(summary="test", detailed=None)
        assert _is_substantial(result) is False

    def test_returns_false_for_exactly_200_chars_no_heading(self):
        detailed = "X" * 200
        result = _make_chain_result(detailed=detailed)
        assert _is_substantial(result) is False

    def test_returns_true_for_201_chars_with_heading(self):
        detailed = "## Заголовок\n\n" + "X" * 190  # total > 200 with heading
        result = _make_chain_result(detailed=detailed)
        assert _is_substantial(result) is True


# ---------------------------------------------------------------------------
# REL-02: _run_chain_with_retry
# ---------------------------------------------------------------------------

class TestRunChainWithRetry:
    @pytest.mark.asyncio
    async def test_good_result_on_first_try_no_retry(self):
        """Good result on first try -> returns immediately, no extra calls."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_chain = AsyncMock(return_value=_good_chain_result())

        result = await _run_chain_with_retry(
            orchestrator=mock_orchestrator,
            task="task",
            task_type="daily",
            context={},
        )
        assert result is not None
        assert _is_substantial(result)
        mock_orchestrator.run_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_first_retry_succeeds_on_second(self):
        """Empty on first try, good on second -> returns good result."""
        empty_result = _make_chain_result(detailed="short")
        good_result = _good_chain_result()

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_chain = AsyncMock(side_effect=[empty_result, good_result])

        result = await _run_chain_with_retry(
            orchestrator=mock_orchestrator,
            task="task",
            task_type="daily",
            context={},
        )
        assert result is not None
        assert _is_substantial(result)
        assert mock_orchestrator.run_chain.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_three_times_returns_none(self):
        """Empty on all 3 attempts (1 initial + 2 retries) -> returns None."""
        empty_result = _make_chain_result(detailed="short")

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_chain = AsyncMock(return_value=empty_result)

        result = await _run_chain_with_retry(
            orchestrator=mock_orchestrator,
            task="task",
            task_type="daily",
            context={},
            max_retries=2,
        )
        assert result is None
        assert mock_orchestrator.run_chain.call_count == 3

    @pytest.mark.asyncio
    async def test_default_max_retries_is_2(self):
        """Default max_retries=2 means 3 total attempts."""
        empty_result = _make_chain_result(detailed="short")

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_chain = AsyncMock(return_value=empty_result)

        result = await _run_chain_with_retry(
            orchestrator=mock_orchestrator,
            task="task",
            task_type="daily",
            context={},
        )
        assert result is None
        assert mock_orchestrator.run_chain.call_count == 3


# ---------------------------------------------------------------------------
# REL-04: validate_and_degrade
# ---------------------------------------------------------------------------

class TestValidateAndDegrade:
    def test_missing_section_gets_russian_placeholder(self):
        """Missing required section -> placeholder with 'временно недоступны'."""
        required_sections = ["## Финансовые результаты", "## Прогноз"]
        report_md = "## Финансовые результаты\n\nТекст."
        result = validate_and_degrade(
            report_md=report_md,
            report_type=ReportType.DAILY,
            required_sections=required_sections,
        )
        assert "## Прогноз" in result
        assert "временно недоступны" in result

    def test_degraded_section_text_no_technical_errors(self):
        """Degradation text must not contain technical error language."""
        required_sections = ["## Финансовые результаты", "## Рекламные расходы"]
        report_md = "## Финансовые результаты\n\nТекст."
        result = validate_and_degrade(
            report_md=report_md,
            report_type=ReportType.DAILY,
            required_sections=required_sections,
        )
        assert "Error" not in result
        assert "Exception" not in result
        assert "traceback" not in result

    def test_all_sections_present_no_change(self):
        """Report with all required sections -> returned unchanged (no placeholder added)."""
        required_sections = ["## Финансовые результаты"]
        report_md = "## Финансовые результаты\n\nТекст с данными."
        result = validate_and_degrade(
            report_md=report_md,
            report_type=ReportType.DAILY,
            required_sections=required_sections,
        )
        assert DEGRADATION_PLACEHOLDER not in result

    def test_all_required_sections_present_after_degrade(self):
        """After validate_and_degrade, every required section heading exists."""
        required_sections = [
            "## Финансовые результаты",
            "## Рекламные расходы",
            "## Прогноз",
        ]
        report_md = "## Финансовые результаты\n\nТекст."
        result = validate_and_degrade(
            report_md=report_md,
            report_type=ReportType.DAILY,
            required_sections=required_sections,
        )
        for heading in required_sections:
            assert heading in result


# ---------------------------------------------------------------------------
# REL-03: has_substantial_content
# ---------------------------------------------------------------------------

class TestHasSubstantialContent:
    def test_report_with_real_content_returns_true(self):
        required_sections = ["## Финансовые результаты", "## Прогноз"]
        report_md = (
            "## Финансовые результаты\n\nДлинный текст с реальными данными.\n\n"
            "## Прогноз\n\nЕщё один длинный текст."
        )
        assert has_substantial_content(
            report_md=report_md,
            required_sections=required_sections,
        ) is True

    def test_report_with_only_placeholders_returns_false(self):
        required_sections = ["## Финансовые результаты", "## Прогноз"]
        report_md = (
            f"## Финансовые результаты\n\n{DEGRADATION_PLACEHOLDER}\n\n"
            f"## Прогноз\n\n{DEGRADATION_PLACEHOLDER}"
        )
        assert has_substantial_content(
            report_md=report_md,
            required_sections=required_sections,
        ) is False

    def test_mixed_content_returns_true(self):
        """At least one real section -> True even if others degraded."""
        required_sections = ["## Финансовые результаты", "## Прогноз"]
        report_md = (
            "## Финансовые результаты\n\nРеальный текст с данными.\n\n"
            f"## Прогноз\n\n{DEGRADATION_PLACEHOLDER}"
        )
        assert has_substantial_content(
            report_md=report_md,
            required_sections=required_sections,
        ) is True

    def test_empty_required_sections_uses_length_fallback(self):
        """No required sections -> fallback to length check (> 500 chars)."""
        long_report = "X" * 600
        assert has_substantial_content(
            report_md=long_report,
            required_sections=[],
        ) is True

        short_report = "X" * 400
        assert has_substantial_content(
            report_md=short_report,
            required_sections=[],
        ) is False


# ---------------------------------------------------------------------------
# REL-07: publish+notify order
# ---------------------------------------------------------------------------

class TestPublishNotifyOrder:
    @pytest.mark.asyncio
    async def test_notion_called_before_telegram(self):
        """sync_report must be called BEFORE send_alert (call order verification)."""
        call_order = []

        async def mock_sync_report(*args, **kwargs):
            call_order.append("notion")
            return "https://notion.so/test-page"

        async def mock_send_alert(message: str):
            call_order.append("telegram")
            return True

        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(return_value=_good_chain_result())

        notion_client = MagicMock()
        notion_client.sync_report = mock_sync_report

        alerter = MagicMock()
        alerter.send_alert = mock_send_alert

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        # Find last notion and first post-pipeline telegram call
        notion_idx = next((i for i, c in enumerate(call_order) if c == "notion"), None)
        # After notion, telegram should appear
        telegram_after_notion = [i for i, c in enumerate(call_order) if c == "telegram" and i > (notion_idx or -1)]

        assert notion_idx is not None, "Notion publish was not called"
        assert len(telegram_after_notion) > 0, "Telegram was not called after Notion"

    @pytest.mark.asyncio
    async def test_notion_fails_telegram_not_called(self):
        """If sync_report fails (returns None), send_alert must NOT be called for final notification."""
        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(return_value=_good_chain_result())

        notion_client = MagicMock()
        notion_client.sync_report = AsyncMock(return_value=None)  # Notion fails

        alerter = MagicMock()
        alerter.send_alert = AsyncMock(return_value=True)

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        assert result.failed is True
        assert result.success is False
        # The final notification (with Notion URL) should not have been called
        # Pre-flight alert may still be called; we check no success telegram
        # We verify by checking no call contained the success pattern
        for c in alerter.send_alert.call_args_list:
            msg = c[0][0] if c[0] else c[1].get("message", "")
            assert "опубликован" not in msg or "notion.so" not in msg

    @pytest.mark.asyncio
    async def test_telegram_fails_pipeline_still_success(self):
        """Telegram failure after Notion success -> pipeline returns success (D-13)."""
        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(return_value=_good_chain_result())

        notion_client = MagicMock()
        notion_url = "https://notion.so/test-page"
        notion_client.sync_report = AsyncMock(return_value=notion_url)

        alerter = MagicMock()
        # Pre-flight send succeeds but final notification fails
        alerter.send_alert = AsyncMock(side_effect=[True, Exception("Telegram unavailable")])

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        assert result.success is True
        assert result.notion_url == notion_url
        # Telegram failure should be recorded as warning
        assert any("Telegram" in w or "telegram" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_telegram_message_contains_notion_url(self):
        """Telegram message after Notion publish must contain the Notion URL."""
        notion_url = "https://notion.so/my-report-12345"

        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(return_value=_good_chain_result())

        notion_client = MagicMock()
        notion_client.sync_report = AsyncMock(return_value=notion_url)

        sent_messages = []

        async def capture_send(message: str):
            sent_messages.append(message)
            return True

        alerter = MagicMock()
        alerter.send_alert = capture_send

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        # Find the final notification message (should contain Notion URL)
        url_messages = [m for m in sent_messages if notion_url in m]
        assert len(url_messages) > 0, f"No message contained Notion URL. Messages: {sent_messages}"


# ---------------------------------------------------------------------------
# run_report: gate check integration
# ---------------------------------------------------------------------------

class TestRunReportGateCheck:
    @pytest.mark.asyncio
    async def test_hard_gate_failure_skips_pipeline(self):
        """Hard gate failure -> pipeline returns skipped=True, no orchestrator call."""
        hard_failed_gate = MagicMock()
        hard_failed_gate.detail = "WB данные не загружены"

        gate_result = MagicMock()
        gate_result.can_run = False
        gate_result.hard_failed = [hard_failed_gate]
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock()

        notion_client = MagicMock()
        notion_client.sync_report = AsyncMock()

        alerter = MagicMock()
        alerter.send_alert = AsyncMock(return_value=True)

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        assert result.skipped is True
        assert result.success is False
        orchestrator.run_chain.assert_not_called()
        notion_client.sync_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_empty_after_retries_returns_failed(self):
        """LLM returns empty 3 times -> pipeline fails with descriptive reason."""
        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(
            return_value=_make_chain_result(detailed="short")
        )

        notion_client = MagicMock()
        notion_client.sync_report = AsyncMock()

        alerter = MagicMock()
        alerter.send_alert = AsyncMock(return_value=True)

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        assert result.failed is True
        assert result.success is False
        assert "retry" in result.reason.lower() or "пуст" in result.reason.lower()
        notion_client.sync_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_report_not_published(self):
        """Report with all placeholder sections -> not published to Notion."""
        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        # Return a report that, after degradation, will be all placeholders
        # We simulate this by returning a chain result with no real section content
        all_placeholder_md = (
            f"## Финансовые результаты\n\n{DEGRADATION_PLACEHOLDER}\n\n"
            f"## Рекламные расходы\n\n{DEGRADATION_PLACEHOLDER}\n"
        )
        chain_result = _make_chain_result(
            detailed=all_placeholder_md,
            telegram_summary="",
        )

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(return_value=chain_result)

        notion_client = MagicMock()
        notion_client.sync_report = AsyncMock()

        alerter = MagicMock()
        alerter.send_alert = AsyncMock(return_value=True)

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        assert result.failed is True
        assert result.success is False
        notion_client.sync_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_content_is_published(self):
        """Report with mixed real+placeholder sections -> IS published."""
        gate_result = MagicMock()
        gate_result.can_run = True
        gate_result.hard_failed = []
        gate_result.soft_warnings = []

        gate_checker = MagicMock()
        gate_checker.check_all = MagicMock(return_value=gate_result)

        # Has at least one real section
        mixed_md = (
            "## Финансовые результаты\n\n"
            "Выручка 1.5M руб, маржа 28%. Хороший результат квартала.\n\n"
            "## Рекламные расходы\n\n"
            f"{DEGRADATION_PLACEHOLDER}\n"
        )
        chain_result = _make_chain_result(
            detailed=mixed_md,
            telegram_summary="Краткая сводка",
        )

        orchestrator = MagicMock()
        orchestrator.run_chain = AsyncMock(return_value=chain_result)

        notion_client = MagicMock()
        notion_url = "https://notion.so/published-page"
        notion_client.sync_report = AsyncMock(return_value=notion_url)

        alerter = MagicMock()
        alerter.send_alert = AsyncMock(return_value=True)

        result = await run_report(
            report_type=ReportType.DAILY,
            target_date=date(2026, 3, 31),
            orchestrator=orchestrator,
            notion_client=notion_client,
            alerter=alerter,
            gate_checker=gate_checker,
        )

        assert result.success is True
        assert result.notion_url == notion_url
        notion_client.sync_report.assert_called_once()


# ---------------------------------------------------------------------------
# ReportPipelineResult
# ---------------------------------------------------------------------------

class TestReportPipelineResult:
    def test_default_state(self):
        r = ReportPipelineResult()
        assert r.success is False
        assert r.skipped is False
        assert r.failed is False
        assert r.reason == ""
        assert r.notion_url == ""
        assert r.warnings == []

    def test_success_state(self):
        r = ReportPipelineResult(success=True, notion_url="https://notion.so/page")
        assert r.success is True
        assert r.notion_url == "https://notion.so/page"
