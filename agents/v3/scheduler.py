"""Wookiee v3 — APScheduler cron job configuration.

All 15 cron jobs:
    1.  daily_report          — daily at DAILY_REPORT_TIME (with retry logic)
    2.  weekly_report         — every Monday at WEEKLY_REPORT_TIME
    3.  monthly_report        — days 1-7 of month, Monday, at MONTHLY_REPORT_TIME
    4.  weekly_marketing_bundle — every Monday: marketing weekly + funnel weekly (parallel)
    5.  marketing_monthly     — days 1-7 of month, Monday, at MARKETING_MONTHLY_REPORT_TIME
    6.  finolog_weekly        — every Friday at FINOLOG_WEEKLY_REPORT_TIME (if key set)
    7.  monthly_price_analysis — day N of month at MONTHLY_PRICE_ANALYSIS_TIME
    8.  data_ready_check      — hourly 06-12 MSK, notifies when gates pass
    9.  notion_feedback       — every 60 min (polls Notion for new comments)
    10. anomaly_monitor       — every N hours at :30
    11. watchdog_heartbeat    — every 6h at :00
    12. promotion_scan        — every 12h at :15 (only if PROMOTION_SCAN_ENABLED)
    13. etl_daily_sync        — daily at ETL_DAILY_SYNC_TIME (marketplace sync + reconciliation + quality)
    14. etl_weekly_analysis   — weekly (Sunday) at ETL_WEEKLY_ANALYSIS_TIME (API docs + schema)
    15. finolog_categorization — daily at FINOLOG_CATEGORIZATION_TIME (transaction classification)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from agents.v3 import config
from agents.v3.delivery import messages
from agents.v3.gates import GateChecker
from agents.v3.state import StateStore

logger = logging.getLogger(__name__)

_MSK = pytz.timezone("Europe/Moscow")

# ---------------------------------------------------------------------------
# Shared singletons (created once in create_scheduler, used in callbacks)
# ---------------------------------------------------------------------------
_state_store: StateStore | None = None
_gate_checker: GateChecker = GateChecker()


def _get_state() -> StateStore:
    global _state_store
    if _state_store is None:
        _state_store = StateStore(config.STATE_DB_PATH)
    return _state_store


# ---------------------------------------------------------------------------
# Date helpers (inline — no v2 imports)
# ---------------------------------------------------------------------------

def _yesterday_msk() -> str:
    """Get yesterday's date in MSK timezone as YYYY-MM-DD string."""
    now = datetime.now(_MSK)
    return (now - timedelta(days=1)).strftime("%Y-%m-%d")


def _last_week_msk() -> tuple[str, str]:
    """Get last week Monday-Sunday as (start, end) strings."""
    now = datetime.now(_MSK)
    today = now.date()
    # Last Monday = this Monday - 7
    monday = today - timedelta(days=today.weekday() + 7)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _last_month_msk() -> tuple[str, str]:
    """Get last month first-last day as (start, end) strings."""
    now = datetime.now(_MSK)
    first_this = now.date().replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d")


def _day_before(date_str: str) -> str:
    """Get the day before a date string."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d - timedelta(days=1)).strftime("%Y-%m-%d")


def _parse_hm(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' string into (hour, minute) ints."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


# ---------------------------------------------------------------------------
# Admin notification helper (delegates to monitor.py with rate limiting)
# ---------------------------------------------------------------------------

from agents.v3.monitor import _send_admin  # noqa: E402


# ---------------------------------------------------------------------------
# Delivery helper
# ---------------------------------------------------------------------------

async def _deliver(
    result: dict,
    report_type: str,
    date_from: str,
    date_to: str,
    caveats: list[str] | None = None,
) -> dict:
    """Call the delivery router with standard v3 config."""
    from agents.v3.delivery.router import deliver
    return await deliver(
        report=result,
        report_type=report_type,
        start_date=date_from,
        end_date=date_to,
        config={
            "telegram_bot_token": config.TELEGRAM_BOT_TOKEN,
            "chat_ids": [config.ADMIN_CHAT_ID] if config.ADMIN_CHAT_ID else [],
            "notion_token": config.NOTION_TOKEN,
            "notion_database_id": config.NOTION_DATABASE_ID,
        },
        caveats=caveats,
    )


# ---------------------------------------------------------------------------
# Job: daily report (with retry logic)
# ---------------------------------------------------------------------------

async def _run_daily_report_attempt(
    scheduler: AsyncIOScheduler,
    trigger: str = "cron",
) -> None:
    """Core daily report logic. Retries on gate failure (max 3, 30 min apart)."""
    date_to = _yesterday_msk()
    date_from = date_to
    comparison_to = _day_before(date_to)
    comparison_from = comparison_to

    state = _get_state()

    if state.is_delivered("daily_report", date_to):
        logger.info("daily_report already delivered for %s, skipping", date_to)
        return

    # Gate check
    gate_result = _gate_checker.check_both()

    if not gate_result.can_generate:
        retries = state.get_retries("daily_report", date_to)
        if retries < 3:
            new_count = state.increment_retries("daily_report", date_to)
            retry_at = datetime.now(_MSK) + timedelta(minutes=30)
            logger.warning(
                "daily_report gates failed for %s (attempt %d/3), retry at %s",
                date_to, new_count, retry_at.isoformat(),
            )
            status_msg = gate_result.format_status_message()
            await _send_admin(messages.report_error(date_to, "дневной фин", str(status_msg), new_count, 3))
            scheduler.add_job(
                _run_daily_report_attempt,
                trigger=DateTrigger(run_date=retry_at.astimezone(pytz.utc)),
                args=[scheduler, "retry"],
                id=f"daily_report_retry_{date_to}_{new_count}",
                misfire_grace_time=1800,
                coalesce=True,
                max_instances=1,
                replace_existing=True,
            )
        else:
            logger.error(
                "daily_report gates failed for %s — all 3 retries exhausted", date_to
            )
            status_msg = gate_result.format_status_message()
            await _send_admin(messages.report_retries_exhausted(date_to, "дневной фин"))
            state.set(f"skipped:daily_report:{date_to}", "gates_failed")
        return

    # Gates passed — run report
    try:
        from agents.v3.orchestrator import run_daily_report
        result = await run_daily_report(
            date_from=date_from,
            date_to=date_to,
            comparison_from=comparison_from,
            comparison_to=comparison_to,
            channel="both",
            trigger=trigger,
        )
        caveats = gate_result.caveats if gate_result.has_caveats else None
        await _deliver(result, "daily", date_from, date_to, caveats=caveats)
        state.mark_delivered("daily_report", date_to)
        logger.info("daily_report for %s delivered (status=%s)", date_to, result.get("status"))
    except Exception as exc:
        logger.exception("daily_report failed for %s: %s", date_to, exc)
        await _send_admin(messages.report_exception("дневной фин", date_from, date_to, exc))


async def _job_daily_report(scheduler: AsyncIOScheduler) -> None:
    """Cron callback: daily report."""
    await _run_daily_report_attempt(scheduler, trigger="cron")


# ---------------------------------------------------------------------------
# Job: data-ready check (hourly 06-12, auto-triggers daily if gates pass)
# ---------------------------------------------------------------------------

async def _job_data_ready_check(scheduler: AsyncIOScheduler) -> None:
    """Hourly check (06-12 MSK): fire daily report if gates pass ahead of schedule."""
    date_to = _yesterday_msk()
    state = _get_state()

    if state.is_delivered("daily_report", date_to):
        return
    if state.exists(f"skipped:daily_report:{date_to}"):
        return

    gate_result = _gate_checker.check_both()
    if gate_result.can_generate:
        logger.info("data_ready_check: gates passed for %s — triggering daily report early", date_to)
        await _send_admin(messages.data_ready(date_to, ["дневной фин"]))
        await _run_daily_report_attempt(scheduler, trigger="data_ready_check")
    else:
        logger.debug("data_ready_check: gates not yet passed for %s", date_to)


# ---------------------------------------------------------------------------
# Job: notion feedback collection
# ---------------------------------------------------------------------------

async def _job_notion_feedback() -> None:
    """Collect Notion feedback and process into persistent agent instructions.

    Runs 1h before daily report. Launches the prompt-tuner micro-agent which:
    1. Fetches recent comments from Notion report pages
    2. Classifies each comment and decides target micro-agents
    3. Saves actionable instructions to StateStore
    4. Posts confirmation comments on Notion
    """
    if not config.PROMPT_TUNER_ENABLED:
        logger.debug("notion_feedback: PromptTuner disabled")
        return

    from agents.v3.runner import run_agent

    try:
        result = await run_agent(
            agent_name="prompt-tuner",
            task=(
                "Обработай новые комментарии из Notion. "
                "Получи фидбек, определи какие комментарии содержат actionable инструкции, "
                "сохрани их для соответствующих агентов и подтверди в Notion."
            ),
            trigger="cron",
            task_type="prompt_tuner",
            timeout=config.AGENT_TIMEOUT,
        )

        if result["status"] == "success":
            logger.info("notion_feedback: prompt-tuner completed in %dms", result["duration_ms"])
        else:
            logger.warning(
                "notion_feedback: prompt-tuner %s — %s",
                result["status"],
                result["raw_output"][:300],
            )
            if result["status"] == "failed":
                await _send_admin(messages.report_exception("prompt-tuner", "", "", Exception(result['raw_output'][:300])))
    except Exception as exc:
        logger.exception("notion_feedback (prompt-tuner) failed: %s", exc)
        await _send_admin(messages.report_exception("prompt-tuner", "", "", exc))


# ---------------------------------------------------------------------------
# Job: weekly report (Monday)
# ---------------------------------------------------------------------------

async def _job_weekly_report() -> None:
    """Cron callback: weekly analytics report (Monday)."""
    date_from, date_to = _last_week_msk()
    comparison_to = _day_before(date_from)
    comparison_from = (
        datetime.strptime(comparison_to, "%Y-%m-%d") - timedelta(days=6)
    ).strftime("%Y-%m-%d")

    state = _get_state()
    if state.is_delivered("weekly_report", date_to):
        logger.info("weekly_report already delivered for week ending %s", date_to)
        return

    try:
        from agents.v3.orchestrator import run_weekly_report
        result = await run_weekly_report(
            date_from=date_from,
            date_to=date_to,
            comparison_from=comparison_from,
            comparison_to=comparison_to,
            channel="both",
            trigger="cron",
        )
        await _deliver(result, "weekly", date_from, date_to)
        state.mark_delivered("weekly_report", date_to)
        logger.info("weekly_report for %s–%s delivered", date_from, date_to)
    except Exception as exc:
        logger.exception("weekly_report failed: %s", exc)
        await _send_admin(messages.report_exception("недельный фин", date_from, date_to, exc))


# ---------------------------------------------------------------------------
# Job: monthly report (days 1-7, Monday)
# ---------------------------------------------------------------------------

async def _job_monthly_report() -> None:
    """Cron callback: monthly analytics report (first Monday 1-7)."""
    date_from, date_to = _last_month_msk()
    # Comparison: same month a year ago
    from datetime import date as date_cls
    prev_year_start = date_cls.fromisoformat(date_from).replace(year=date_cls.fromisoformat(date_from).year - 1)
    prev_year_end = date_cls.fromisoformat(date_to).replace(year=date_cls.fromisoformat(date_to).year - 1)
    comparison_from = prev_year_start.strftime("%Y-%m-%d")
    comparison_to = prev_year_end.strftime("%Y-%m-%d")

    state = _get_state()
    if state.is_delivered("monthly_report", date_to):
        logger.info("monthly_report already delivered for month ending %s", date_to)
        return

    try:
        from agents.v3.orchestrator import run_monthly_report
        result = await run_monthly_report(
            date_from=date_from,
            date_to=date_to,
            comparison_from=comparison_from,
            comparison_to=comparison_to,
            channel="both",
            trigger="cron",
        )
        await _deliver(result, "monthly", date_from, date_to)
        state.mark_delivered("monthly_report", date_to)
        logger.info("monthly_report for %s–%s delivered", date_from, date_to)
    except Exception as exc:
        logger.exception("monthly_report failed: %s", exc)
        await _send_admin(messages.report_exception("месячный фин", date_from, date_to, exc))


# ---------------------------------------------------------------------------
# Job: weekly marketing bundle (marketing weekly + funnel weekly, parallel)
# ---------------------------------------------------------------------------

async def _job_weekly_marketing_bundle() -> None:
    """Cron callback: run marketing weekly + funnel weekly in parallel (Monday)."""
    date_from, date_to = _last_week_msk()
    comparison_to = _day_before(date_from)
    comparison_from = (
        datetime.strptime(comparison_to, "%Y-%m-%d") - timedelta(days=6)
    ).strftime("%Y-%m-%d")

    state = _get_state()

    async def _run_marketing() -> None:
        if state.is_delivered("marketing_weekly", date_to):
            logger.info("marketing_weekly already delivered for week ending %s", date_to)
            return
        try:
            from agents.v3.orchestrator import run_marketing_report
            result = await run_marketing_report(
                date_from=date_from,
                date_to=date_to,
                comparison_from=comparison_from,
                comparison_to=comparison_to,
                report_period="weekly",
                channel="both",
                trigger="cron",
            )
            await _deliver(result, "marketing_weekly", date_from, date_to)
            state.mark_delivered("marketing_weekly", date_to)
            logger.info("marketing_weekly for %s–%s delivered", date_from, date_to)
        except Exception as exc:
            logger.exception("marketing_weekly failed: %s", exc)
            await _send_admin(messages.report_exception("маркетинговый", date_from, date_to, exc))

    async def _run_funnel() -> None:
        if state.is_delivered("funnel_weekly", date_to):
            logger.info("funnel_weekly already delivered for week ending %s", date_to)
            return
        try:
            from agents.v3.orchestrator import run_funnel_report
            result = await run_funnel_report(
                date_from=date_from,
                date_to=date_to,
                comparison_from=comparison_from,
                comparison_to=comparison_to,
                channel="both",
                trigger="cron",
            )
            await _deliver(result, "funnel_weekly", date_from, date_to)
            state.mark_delivered("funnel_weekly", date_to)
            logger.info("funnel_weekly for %s–%s delivered", date_from, date_to)
        except Exception as exc:
            logger.exception("funnel_weekly failed: %s", exc)
            await _send_admin(messages.report_exception("воронка", date_from, date_to, exc))

    await asyncio.gather(_run_marketing(), _run_funnel())


# ---------------------------------------------------------------------------
# Job: marketing monthly (days 1-7, Monday)
# ---------------------------------------------------------------------------

async def _job_marketing_monthly() -> None:
    """Cron callback: monthly marketing report (first Monday 1-7)."""
    date_from, date_to = _last_month_msk()
    from datetime import date as date_cls
    prev_year_start = date_cls.fromisoformat(date_from).replace(year=date_cls.fromisoformat(date_from).year - 1)
    prev_year_end = date_cls.fromisoformat(date_to).replace(year=date_cls.fromisoformat(date_to).year - 1)
    comparison_from = prev_year_start.strftime("%Y-%m-%d")
    comparison_to = prev_year_end.strftime("%Y-%m-%d")

    state = _get_state()
    if state.is_delivered("marketing_monthly", date_to):
        logger.info("marketing_monthly already delivered for month ending %s", date_to)
        return

    try:
        from agents.v3.orchestrator import run_marketing_report
        result = await run_marketing_report(
            date_from=date_from,
            date_to=date_to,
            comparison_from=comparison_from,
            comparison_to=comparison_to,
            report_period="monthly",
            channel="both",
            trigger="cron",
        )
        await _deliver(result, "marketing_monthly", date_from, date_to)
        state.mark_delivered("marketing_monthly", date_to)
        logger.info("marketing_monthly for %s–%s delivered", date_from, date_to)
    except Exception as exc:
        logger.exception("marketing_monthly failed: %s", exc)
        await _send_admin(messages.report_exception("маркетинговый месячный", date_from, date_to, exc))


# ---------------------------------------------------------------------------
# Job: finolog weekly (Friday)
# ---------------------------------------------------------------------------

async def _job_finolog_weekly() -> None:
    """Cron callback: Finolog ДДС weekly report (Friday)."""
    date_from, date_to = _last_week_msk()

    state = _get_state()
    if state.is_delivered("finolog_weekly", date_to):
        logger.info("finolog_weekly already delivered for week ending %s", date_to)
        return

    try:
        from agents.v3.orchestrator import run_finolog_report
        result = await run_finolog_report(
            date_from=date_from,
            date_to=date_to,
            trigger="cron",
        )
        await _deliver(result, "finolog_weekly", date_from, date_to)
        state.mark_delivered("finolog_weekly", date_to)
        logger.info("finolog_weekly for %s–%s delivered", date_from, date_to)
    except Exception as exc:
        logger.exception("finolog_weekly failed: %s", exc)
        await _send_admin(messages.report_exception("ДДС", date_from, date_to, exc))


# ---------------------------------------------------------------------------
# Job: monthly price analysis (day N of month)
# ---------------------------------------------------------------------------

async def _job_price_analysis() -> None:
    """Cron callback: monthly price analysis."""
    date_from, date_to = _last_month_msk()
    from datetime import date as date_cls
    prev_year_start = date_cls.fromisoformat(date_from).replace(year=date_cls.fromisoformat(date_from).year - 1)
    prev_year_end = date_cls.fromisoformat(date_to).replace(year=date_cls.fromisoformat(date_to).year - 1)
    comparison_from = prev_year_start.strftime("%Y-%m-%d")
    comparison_to = prev_year_end.strftime("%Y-%m-%d")

    state = _get_state()
    if state.is_delivered("price_analysis", date_to):
        logger.info("price_analysis already delivered for month ending %s", date_to)
        return

    try:
        from agents.v3.orchestrator import run_price_analysis
        result = await run_price_analysis(
            date_from=date_from,
            date_to=date_to,
            comparison_from=comparison_from,
            comparison_to=comparison_to,
            channel="both",
            trigger="cron",
        )
        await _deliver(result, "price_analysis", date_from, date_to)
        state.mark_delivered("price_analysis", date_to)
        logger.info("price_analysis for %s–%s delivered", date_from, date_to)
    except Exception as exc:
        logger.exception("price_analysis failed: %s", exc)
        await _send_admin(messages.report_exception("ценовой анализ", date_from, date_to, exc))


# ---------------------------------------------------------------------------
# Stubs for Task 9 (anomaly monitor, watchdog, promotion scan)
# ---------------------------------------------------------------------------

async def _job_anomaly_monitor() -> None:
    """Cron callback: anomaly monitor — collect and store, no standalone Telegram alerts.

    Results are embedded into daily/weekly reports by the conductor.
    """
    gate_result = _gate_checker.check_both()
    if not gate_result.can_generate:
        logger.info("anomaly_monitor: gates not passed, skipping (data not ready)")
        return

    from agents.v3.monitor import get_anomaly_monitor
    monitor = get_anomaly_monitor()
    try:
        await monitor.check_and_store()
    except Exception as exc:
        logger.exception("anomaly_monitor job failed: %s", exc)


async def _job_watchdog() -> None:
    """Cron callback: watchdog heartbeat — runs every WATCHDOG_HEARTBEAT_INTERVAL_HOURS hours."""
    from agents.v3.monitor import get_watchdog
    watchdog = get_watchdog()
    try:
        await watchdog.heartbeat()
    except Exception as exc:
        logger.exception("watchdog_heartbeat job failed: %s", exc)
        await _send_admin(messages.report_exception("watchdog", "", "", exc))


async def _job_promotion_scan() -> None:
    """Stub: promotion scan — implementation in Task 9."""
    logger.debug("promotion_scan: tick (stub)")


# ---------------------------------------------------------------------------
# Job: ETL daily sync (marketplace data)
# ---------------------------------------------------------------------------

async def _job_etl_daily_sync() -> None:
    """Cron callback: marketplace ETL sync + reconciliation + data quality check."""
    date_to = _yesterday_msk()
    state = _get_state()

    if state.is_delivered("etl_daily_sync", date_to):
        logger.info("etl_daily_sync already completed for %s, skipping", date_to)
        return

    try:
        from services.etl.marketplace_sync import run_marketplace_sync
        from services.etl.reconciliation_check import run_reconciliation_check
        from services.etl.data_quality_check import run_data_quality_check

        sync_result = await run_marketplace_sync()
        recon_result = await run_reconciliation_check(days=1)
        quality_result = await run_data_quality_check()

        state.mark_delivered("etl_daily_sync", date_to)

        # Alert on failures
        if not recon_result.get("passed", True):
            reason = recon_result.get('status', 'UNKNOWN')
            await _send_admin(messages.report_exception("Сверка данных маркетплейсов", date_to, date_to, Exception(reason)))
        if not quality_result.get("overall_ok", True):
            await _send_admin(messages.data_quality_issue(date_to))

        logger.info("etl_daily_sync for %s completed", date_to)
    except Exception as exc:
        logger.exception("etl_daily_sync failed: %s", exc)
        await _send_admin(messages.report_exception("Синхронизация данных", date_to, date_to, exc))


# ---------------------------------------------------------------------------
# Job: ETL weekly analysis (API docs + schema)
# ---------------------------------------------------------------------------

async def _job_etl_weekly_analysis() -> None:
    """Cron callback: API documentation + schema analysis (weekly, Sunday)."""
    date_to = _yesterday_msk()
    state = _get_state()

    if state.is_delivered("etl_weekly_analysis", date_to):
        logger.info("etl_weekly_analysis already completed for %s, skipping", date_to)
        return

    try:
        from services.etl.api_docs_check import run_api_docs_check
        from services.etl.schema_check import run_schema_check
        from shared.clients.openrouter_client import OpenRouterClient

        llm = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model=config.ETL_LLM_MODEL,
        )
        await run_api_docs_check(llm_client=llm)
        await run_schema_check(llm_client=llm)

        state.mark_delivered("etl_weekly_analysis", date_to)
        logger.info("etl_weekly_analysis for %s completed", date_to)
    except Exception as exc:
        logger.exception("etl_weekly_analysis failed: %s", exc)
        await _send_admin(messages.report_exception("Еженедельная проверка данных", "", "", exc))


# ---------------------------------------------------------------------------
# Job: Finolog categorization (transaction classification)
# ---------------------------------------------------------------------------

async def _job_finolog_categorization() -> None:
    """Cron callback: daily Finolog transaction categorization."""
    date_to = _yesterday_msk()
    state = _get_state()

    if state.is_delivered("finolog_categorization", date_to):
        logger.info("finolog_categorization already completed for %s, skipping", date_to)
        return

    try:
        from agents.finolog_categorizer.app import run_scan
        await run_scan()
        state.mark_delivered("finolog_categorization", date_to)
        logger.info("finolog_categorization for %s completed", date_to)
    except Exception as exc:
        logger.exception("finolog_categorization failed: %s", exc)
        await _send_admin(messages.report_exception("категоризация Finolog", "", "", exc))


# ---------------------------------------------------------------------------
# Job: localization weekly report (Monday 13:00 MSK)
# ---------------------------------------------------------------------------

async def _job_localization_weekly() -> None:
    """Cron callback: weekly localization / logistics cost report."""
    import asyncio
    from services.wb_localization.run_localization import run_service_report
    from services.wb_localization.report_md import (
        format_localization_weekly_md,
        format_localization_tg_summary,
    )
    from services.wb_localization.history import History

    date_to = _yesterday_msk()
    date_from = (datetime.strptime(date_to, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")

    state = _get_state()
    if state.is_delivered("localization_weekly", date_to):
        logger.info("localization_weekly already delivered for %s", date_to)
        return

    logger.info("Starting localization weekly report for %s — %s", date_from, date_to)
    history = History()

    # Load average base logistics tariff from WB API (fallback: 80₽)
    avg_base_logistics = 80.0
    try:
        from shared.clients.wb_client import WBClient
        from services.sheets_sync.config import CABINET_OOO
        wb = WBClient(api_key=CABINET_OOO.wb_api_key, cabinet_name="ooo")
        try:
            tariffs = wb.get_box_tariffs()
            if tariffs:
                rates = [t.get("deliveryBase", 0) for t in tariffs if t.get("deliveryBase", 0) > 0]
                if rates:
                    avg_base_logistics = sum(rates) / len(rates)
                    logger.info("Avg base logistics tariff: %.1f₽", avg_base_logistics)
        finally:
            wb.close()
    except Exception as e:
        logger.warning("Failed to load tariffs, using default %.0f₽: %s", avg_base_logistics, e)

    cabinet_keys = ["ip", "ooo"]
    results: list[dict] = []
    caveats: list[str] = []

    for i, cab_key in enumerate(cabinet_keys):
        try:
            result = await asyncio.to_thread(
                run_service_report,
                cabinet_key=cab_key,
                days=91,
                history_store=history,
            )
            result["avg_base_logistics"] = avg_base_logistics
            results.append(result)
        except Exception as e:
            logger.error("Localization report failed for %s: %s", cab_key, e)
            caveats.append(f"Кабинет {cab_key}: ошибка ({e})")
        if i < len(cabinet_keys) - 1:
            await asyncio.sleep(60)

    if not results:
        logger.error("No localization results — skipping delivery")
        await _send_admin("Еженедельный отчёт по логистике: нет данных ни по одному кабинету")
        return

    md = format_localization_weekly_md(results, period_days=91)
    tg = format_localization_tg_summary(results)

    envelope = {
        "status": "success",
        "report": {"detailed_report": md, "telegram_summary": tg},
        "agents_called": 0,
    }

    await _deliver(envelope, "localization_weekly", date_from, date_to, caveats=caveats or None)
    state.mark_delivered("localization_weekly", date_to)
    logger.info("Localization weekly delivered for %s", date_to)


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

def _setup_legacy_scheduler() -> AsyncIOScheduler:
    """Build and return a configured AsyncIOScheduler with all 15 jobs."""
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

    job_defaults = {
        "misfire_grace_time": 3600,
        "coalesce": True,
        "max_instances": 1,
    }

    # ── Parse schedule times ────────────────────────────────────────────────
    daily_h, daily_m = _parse_hm(config.DAILY_REPORT_TIME)
    weekly_h, weekly_m = _parse_hm(config.WEEKLY_REPORT_TIME)
    monthly_h, monthly_m = _parse_hm(config.MONTHLY_REPORT_TIME)
    mktw_h, mktw_m = _parse_hm(config.MARKETING_WEEKLY_REPORT_TIME)
    mktmo_h, mktmo_m = _parse_hm(config.MARKETING_MONTHLY_REPORT_TIME)
    funnel_h, funnel_m = _parse_hm(config.FUNNEL_WEEKLY_REPORT_TIME)
    finolog_h, finolog_m = _parse_hm(config.FINOLOG_WEEKLY_REPORT_TIME)
    price_h, price_m = _parse_hm(config.MONTHLY_PRICE_ANALYSIS_TIME)

    # ── 1. Daily report ─────────────────────────────────────────────────────
    scheduler.add_job(
        _job_daily_report,
        trigger=CronTrigger(hour=daily_h, minute=daily_m, timezone=config.TIMEZONE),
        args=[scheduler],
        id="daily_report",
        **job_defaults,
    )

    # ── 2. Weekly report (Monday) ────────────────────────────────────────────
    scheduler.add_job(
        _job_weekly_report,
        trigger=CronTrigger(day_of_week="mon", hour=weekly_h, minute=weekly_m, timezone=config.TIMEZONE),
        id="weekly_report",
        **job_defaults,
    )

    # ── 3. Monthly report (first Monday of month, days 1-7) ──────────────────
    scheduler.add_job(
        _job_monthly_report,
        trigger=CronTrigger(
            day="1-7", day_of_week="mon",
            hour=monthly_h, minute=monthly_m,
            timezone=config.TIMEZONE,
        ),
        id="monthly_report",
        **job_defaults,
    )

    # ── 4. Weekly marketing bundle (Monday) ──────────────────────────────────
    scheduler.add_job(
        _job_weekly_marketing_bundle,
        trigger=CronTrigger(day_of_week="mon", hour=mktw_h, minute=mktw_m, timezone=config.TIMEZONE),
        id="weekly_marketing_bundle",
        **job_defaults,
    )

    # ── 5. Marketing monthly (first Monday 1-7) ───────────────────────────────
    scheduler.add_job(
        _job_marketing_monthly,
        trigger=CronTrigger(
            day="1-7", day_of_week="mon",
            hour=mktmo_h, minute=mktmo_m,
            timezone=config.TIMEZONE,
        ),
        id="marketing_monthly",
        **job_defaults,
    )

    # ── 6. Finolog weekly (Friday) — only if key set ──────────────────────────
    if config.FINOLOG_API_KEY:
        scheduler.add_job(
            _job_finolog_weekly,
            trigger=CronTrigger(day_of_week="fri", hour=finolog_h, minute=finolog_m, timezone=config.TIMEZONE),
            id="finolog_weekly",
            **job_defaults,
        )
    else:
        logger.info("finolog_weekly job skipped: FINOLOG_API_KEY not set")

    # ── 7. Monthly price analysis (day N of month) ────────────────────────────
    scheduler.add_job(
        _job_price_analysis,
        trigger=CronTrigger(
            day=config.MONTHLY_PRICE_ANALYSIS_DAY,
            hour=price_h, minute=price_m,
            timezone=config.TIMEZONE,
        ),
        id="monthly_price_analysis",
        **job_defaults,
    )

    # ── 8. Data-ready check (hourly 06-12 MSK) ────────────────────────────────
    scheduler.add_job(
        _job_data_ready_check,
        trigger=CronTrigger(hour="6-12", minute=0, timezone=config.TIMEZONE),
        args=[scheduler],
        id="data_ready_check",
        **job_defaults,
    )

    # ── 9. Notion feedback (every 60 min) ────────────────────────────────────
    from apscheduler.triggers.interval import IntervalTrigger
    scheduler.add_job(
        _job_notion_feedback,
        trigger=IntervalTrigger(minutes=60),
        id="notion_feedback",
        **job_defaults,
    )

    # ── 10. Anomaly monitor (every N hours at :30) ────────────────────────────
    interval_h = config.ANOMALY_MONITOR_INTERVAL_HOURS
    scheduler.add_job(
        _job_anomaly_monitor,
        trigger=CronTrigger(
            hour=f"*/{interval_h}", minute=30,
            timezone=config.TIMEZONE,
        ),
        id="anomaly_monitor",
        **job_defaults,
    )

    # ── 11. Watchdog heartbeat (every 6h at :00) ──────────────────────────────
    watchdog_h = config.WATCHDOG_HEARTBEAT_INTERVAL_HOURS
    scheduler.add_job(
        _job_watchdog,
        trigger=CronTrigger(
            hour=f"*/{watchdog_h}", minute=0,
            timezone=config.TIMEZONE,
        ),
        id="watchdog_heartbeat",
        **job_defaults,
    )

    # ── 12. Promotion scan (every 12h at :15, only if enabled) ───────────────
    if config.PROMOTION_SCAN_ENABLED:
        scheduler.add_job(
            _job_promotion_scan,
            trigger=CronTrigger(hour="*/12", minute=15, timezone=config.TIMEZONE),
            id="promotion_scan",
            **job_defaults,
        )
    else:
        logger.info("promotion_scan job skipped: PROMOTION_SCAN_ENABLED=false")

    # ── 13. ETL daily sync ────────────────────────────────────────────────────
    if config.ETL_ENABLED:
        etl_daily_h, etl_daily_m = _parse_hm(config.ETL_DAILY_SYNC_TIME)
        scheduler.add_job(
            _job_etl_daily_sync,
            trigger=CronTrigger(
                hour=etl_daily_h, minute=etl_daily_m,
                timezone=config.TIMEZONE,
            ),
            id="etl_daily_sync",
            **job_defaults,
        )
    else:
        logger.info("etl_daily_sync job skipped: ETL_ENABLED=false")

    # ── 14. ETL weekly analysis (Sunday) ──────────────────────────────────────
    if config.ETL_ENABLED:
        etl_weekly_h, etl_weekly_m = _parse_hm(config.ETL_WEEKLY_ANALYSIS_TIME)
        scheduler.add_job(
            _job_etl_weekly_analysis,
            trigger=CronTrigger(
                day_of_week=config.ETL_WEEKLY_ANALYSIS_DAY,
                hour=etl_weekly_h, minute=etl_weekly_m,
                timezone=config.TIMEZONE,
            ),
            id="etl_weekly_analysis",
            **job_defaults,
        )

    # ── 15. Finolog categorization (daily) ────────────────────────────────────
    if config.FINOLOG_CATEGORIZATION_ENABLED and config.FINOLOG_API_KEY:
        cat_h, cat_m = _parse_hm(config.FINOLOG_CATEGORIZATION_TIME)
        scheduler.add_job(
            _job_finolog_categorization,
            trigger=CronTrigger(
                hour=cat_h, minute=cat_m,
                timezone=config.TIMEZONE,
            ),
            id="finolog_categorization",
            **job_defaults,
        )
    else:
        logger.info("finolog_categorization job skipped: disabled or FINOLOG_API_KEY not set")

    # ── 16. Localization weekly (Monday 13:00) ───────────────────────────────
    if config.LOCALIZATION_WEEKLY_ENABLED:
        loc_h, loc_m = _parse_hm(config.LOCALIZATION_WEEKLY_REPORT_TIME)
        scheduler.add_job(
            _job_localization_weekly,
            trigger=CronTrigger(
                day_of_week="mon", hour=loc_h, minute=loc_m,
                timezone=config.TIMEZONE,
            ),
            id="localization_weekly",
            **job_defaults,
        )

    logger.info(
        "Scheduler configured with %d jobs: %s",
        len(scheduler.get_jobs()),
        [j.id for j in scheduler.get_jobs()],
    )
    return scheduler


# ---------------------------------------------------------------------------
# Conductor scheduler
# ---------------------------------------------------------------------------

def _setup_conductor_scheduler() -> AsyncIOScheduler:
    """Conductor mode: smart triggers instead of individual report cron jobs.

    Jobs:
    1. data_ready_check — hourly 06:00-12:00 (gates + generate + validate)
    2. deadline_check — 12:00 (alert if reports missing)
    3. catchup_check — 15:00 (reuses data_ready_check with daily_only=True)
    4. anomaly_monitor — every N hours
    5. watchdog_heartbeat — every 6h (log-only, no Telegram)
    6. notion_feedback — every 60 min
    + Non-report jobs (ETL, promotion scan, finolog categorization) unchanged
    """
    from agents.v3.conductor.state import ConductorState
    from agents.v3.conductor.conductor import data_ready_check, deadline_check

    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    job_defaults = {
        "misfire_grace_time": 3600,
        "coalesce": True,
        "max_instances": 1,
    }

    state = ConductorState(db_path=config.STATE_DB_PATH)
    state.ensure_table()

    from agents.v3 import orchestrator

    # 1. data_ready_check — hourly 06:00-12:00
    scheduler.add_job(
        data_ready_check,
        trigger=CronTrigger(hour="6-12", minute=0, timezone=config.TIMEZONE),
        kwargs={
            "gate_checker": _gate_checker,
            "conductor_state": state,
            "telegram_send": _send_admin,
            "orchestrator": orchestrator,
            "delivery": _deliver,
            "scheduler": scheduler,
        },
        id="data_ready_check",
        **job_defaults,
    )

    # 2. deadline_check — 12:00
    scheduler.add_job(
        deadline_check,
        trigger=CronTrigger(hour=config.CONDUCTOR_DEADLINE_HOUR, minute=0, timezone=config.TIMEZONE),
        kwargs={
            "conductor_state": state,
            "telegram_send": _send_admin,
            "gate_checker": _gate_checker,
        },
        id="deadline_check",
        **job_defaults,
    )

    # 3. catchup_check — 15:00 (reuses data_ready_check with daily_only=True)
    scheduler.add_job(
        data_ready_check,
        trigger=CronTrigger(hour=config.CONDUCTOR_CATCHUP_HOUR, minute=0, timezone=config.TIMEZONE),
        kwargs={
            "gate_checker": _gate_checker,
            "conductor_state": state,
            "telegram_send": _send_admin,
            "orchestrator": orchestrator,
            "delivery": _deliver,
            "scheduler": scheduler,
            "daily_only": True,
        },
        id="catchup_check",
        **job_defaults,
    )

    # 4. Anomaly monitor
    interval_h = config.ANOMALY_MONITOR_INTERVAL_HOURS
    scheduler.add_job(
        _job_anomaly_monitor,
        trigger=CronTrigger(hour=f"*/{interval_h}", minute=30, timezone=config.TIMEZONE),
        id="anomaly_monitor",
        **job_defaults,
    )

    # 5. Watchdog heartbeat (log-only in conductor mode)
    watchdog_h = config.WATCHDOG_HEARTBEAT_INTERVAL_HOURS
    scheduler.add_job(
        _job_watchdog,
        trigger=CronTrigger(hour=f"*/{watchdog_h}", minute=0, timezone=config.TIMEZONE),
        id="watchdog_heartbeat",
        **job_defaults,
    )

    # 6. Notion feedback
    from apscheduler.triggers.interval import IntervalTrigger
    scheduler.add_job(
        _job_notion_feedback,
        trigger=IntervalTrigger(minutes=60),
        id="notion_feedback",
        **job_defaults,
    )

    # ── Non-report jobs (unchanged from legacy) ──────────────────────────
    if config.PROMOTION_SCAN_ENABLED:
        scheduler.add_job(
            _job_promotion_scan,
            trigger=CronTrigger(hour="*/12", minute=15, timezone=config.TIMEZONE),
            id="promotion_scan",
            **job_defaults,
        )

    if config.ETL_ENABLED:
        etl_daily_h, etl_daily_m = _parse_hm(config.ETL_DAILY_SYNC_TIME)
        scheduler.add_job(
            _job_etl_daily_sync,
            trigger=CronTrigger(hour=etl_daily_h, minute=etl_daily_m, timezone=config.TIMEZONE),
            id="etl_daily_sync",
            **job_defaults,
        )
        etl_weekly_h, etl_weekly_m = _parse_hm(config.ETL_WEEKLY_ANALYSIS_TIME)
        scheduler.add_job(
            _job_etl_weekly_analysis,
            trigger=CronTrigger(
                day_of_week=config.ETL_WEEKLY_ANALYSIS_DAY,
                hour=etl_weekly_h, minute=etl_weekly_m,
                timezone=config.TIMEZONE,
            ),
            id="etl_weekly_analysis",
            **job_defaults,
        )

    if config.FINOLOG_CATEGORIZATION_ENABLED and config.FINOLOG_API_KEY:
        cat_h, cat_m = _parse_hm(config.FINOLOG_CATEGORIZATION_TIME)
        scheduler.add_job(
            _job_finolog_categorization,
            trigger=CronTrigger(hour=cat_h, minute=cat_m, timezone=config.TIMEZONE),
            id="finolog_categorization",
            **job_defaults,
        )

    # Localization weekly report (Monday 13:00 MSK)
    if config.LOCALIZATION_WEEKLY_ENABLED:
        loc_h, loc_m = _parse_hm(config.LOCALIZATION_WEEKLY_REPORT_TIME)
        scheduler.add_job(
            _job_localization_weekly,
            trigger=CronTrigger(
                day_of_week="mon", hour=loc_h, minute=loc_m,
                timezone=config.TIMEZONE,
            ),
            id="localization_weekly",
            **job_defaults,
        )

    logger.info(
        "Conductor scheduler configured with %d jobs: %s",
        len(scheduler.get_jobs()),
        [j.id for j in scheduler.get_jobs()],
    )
    return scheduler


def create_scheduler() -> AsyncIOScheduler:
    """Build scheduler — conductor mode or legacy based on config."""
    if config.USE_CONDUCTOR:
        return _setup_conductor_scheduler()
    return _setup_legacy_scheduler()
