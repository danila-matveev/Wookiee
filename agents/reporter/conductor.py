# agents/reporter/conductor.py
"""Conductor — gate checks, scheduling, pipeline execution."""
from __future__ import annotations

import logging
from datetime import date

from agents.reporter.config import MAX_ATTEMPTS
from agents.reporter.delivery.telegram import send_data_ready_notification, send_error_notification
from agents.reporter.gates import GateChecker
from agents.reporter.pipeline import run_pipeline
from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope, ReportType, compute_scope, get_today_reports

logger = logging.getLogger(__name__)


async def data_ready_check(
    gate_checker: GateChecker,
    state: ReporterState,
    today: date | None = None,
) -> None:
    """Hourly check: gates pass → generate pending reports."""
    today = today or date.today()

    # Check gates
    gate_result = gate_checker.check_both()
    if not gate_result.can_generate:
        logger.info(
            "Gates not passed: %s",
            [g.name for g in gate_result.gates if not g.passed],
        )
        return

    # Notify data ready (once per day)
    await send_data_ready_notification("WB+OZON", state)

    # Determine which reports need to run
    scheduled = get_today_reports(today)
    already_done = state.get_successful_today(today)

    pending = [
        rt for rt in scheduled
        if rt.value not in already_done
    ]

    if not pending:
        logger.info("All %d reports already done for %s", len(scheduled), today)
        return

    logger.info("Generating %d reports: %s", len(pending), [r.value for r in pending])

    for rt in pending:
        scope = compute_scope(rt, today)

        # Check attempt count
        attempts = state.get_attempt_count(scope)
        if attempts >= MAX_ATTEMPTS:
            logger.warning("Max attempts (%d) reached for %s", MAX_ATTEMPTS, rt.value)
            continue

        if attempts > 0:
            state.increment_attempt(scope)

        # Add caveats to scope context
        result = await run_pipeline(scope, state)

        if result.success:
            logger.info("Report %s generated successfully", rt.value)
        else:
            logger.warning("Report %s failed: %s", rt.value, result.error or result.issues)


async def deadline_check(state: ReporterState, today: date | None = None) -> None:
    """13:00 check: alert if daily report not ready."""
    today = today or date.today()
    done = state.get_successful_today(today)

    if ReportType.FINANCIAL_DAILY.value not in done:
        scope = compute_scope(ReportType.FINANCIAL_DAILY, today)
        await send_error_notification(
            scope,
            ["Дневной отчёт не сгенерирован к дедлайну (13:00)"],
            state,
        )


async def heartbeat(state: ReporterState) -> None:
    """Periodic health status to Telegram."""
    from datetime import date as date_cls

    from aiogram import Bot

    from agents.reporter.config import ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN

    today = date_cls.today()
    runs = state.get_today_status(today)

    success = sum(1 for r in runs if r["status"] == "success")
    failed = sum(1 for r in runs if r["status"] in ("failed", "error"))
    pending = sum(1 for r in runs if r["status"] not in ("success", "failed", "error"))

    text = (
        f"💓 Reporter V4 — heartbeat\n"
        f"📅 {today.isoformat()}\n"
        f"✅ Готово: {success} | ❌ Ошибки: {failed} | ⏳ Ожидает: {pending}"
    )

    if TELEGRAM_BOT_TOKEN:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
        finally:
            await bot.session.close()
