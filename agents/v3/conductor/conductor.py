"""Smart Conductor — main orchestration logic.

Coordinates: gate checks → schedule → generation → validation → delivery.
"""
import logging
from datetime import date, datetime, timedelta

from agents.v3.conductor.schedule import get_today_reports, get_missed_reports, ReportType
from agents.v3.conductor.state import ConductorState
from agents.v3.conductor.validator import quick_validate, ValidationVerdict
from agents.v3.delivery import messages

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def _compute_dates(report_type: ReportType, today: date) -> dict:
    """Compute date_from, date_to, comparison_from, comparison_to for a report type."""
    yesterday = today - timedelta(days=1)

    if report_type == ReportType.DAILY:
        return {
            "date_from": yesterday.isoformat(),
            "date_to": yesterday.isoformat(),
            "comparison_from": (yesterday - timedelta(days=1)).isoformat(),
            "comparison_to": (yesterday - timedelta(days=1)).isoformat(),
        }

    if report_type in (
        ReportType.WEEKLY, ReportType.MARKETING_WEEKLY,
        ReportType.FUNNEL_WEEKLY, ReportType.PRICE_WEEKLY,
        ReportType.FINOLOG_WEEKLY,
    ):
        # Last Monday-Sunday
        last_sunday = today - timedelta(days=today.weekday() + 1)
        last_monday = last_sunday - timedelta(days=6)
        prev_sunday = last_monday - timedelta(days=1)
        prev_monday = prev_sunday - timedelta(days=6)
        return {
            "date_from": last_monday.isoformat(),
            "date_to": last_sunday.isoformat(),
            "comparison_from": prev_monday.isoformat(),
            "comparison_to": prev_sunday.isoformat(),
        }

    # Monthly — YoY comparison (same month previous year)
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    # Same month previous year
    prev_year_start = last_month_start.replace(year=last_month_start.year - 1)
    prev_year_end = last_month_end.replace(year=last_month_end.year - 1)
    return {
        "date_from": last_month_start.isoformat(),
        "date_to": last_month_end.isoformat(),
        "comparison_from": prev_year_start.isoformat(),
        "comparison_to": prev_year_end.isoformat(),
    }


def _extract_gate_info(gate_result) -> dict:
    """Extract display info from GateCheckResult for Telegram message.

    The gate names follow patterns like "ETL ran today (wb)", "Source data loaded (wb)",
    "Orders volume (wb)", "Revenue vs avg (wb)".
    GateResult has: name, passed, is_hard, value, threshold, detail, extra (usually empty dict).

    Since extra dict is usually empty in current implementation, we fall back to parsing
    the detail string or using value/threshold when available.
    """
    info = {"updated_at": "—", "orders": 0, "revenue_ratio": 1.0}
    for g in gate_result.gates:
        if "ETL" in g.name and g.detail:
            # Try to extract update time from detail like "Последнее обновление: 2026-03-21"
            if g.extra.get("updated_at"):
                info["updated_at"] = g.extra["updated_at"]
            elif "обновление" in g.detail:
                # Fallback: extract date from detail
                parts = g.detail.split(":")
                if len(parts) >= 2:
                    info["updated_at"] = parts[-1].strip().split(",")[0].strip()
        elif "Orders volume" in g.name or "Source data loaded" in g.name:
            if g.value is not None:
                info["orders"] = int(g.value)
        elif "Revenue vs avg" in g.name:
            if g.value is not None and g.threshold:
                info["revenue_ratio"] = g.value / 100.0  # value is already percentage
    return info


def _month_name(month: int) -> str:
    names = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return names[month]


async def data_ready_check(
    gate_checker,
    conductor_state: ConductorState,
    telegram_send,          # async callable(text: str)
    orchestrator,           # module with run_daily_report, etc.
    delivery,               # async callable(report, report_type, ...)
    scheduler,              # APScheduler instance (for retry DateTrigger)
    today: date = None,
    daily_only: bool = False,  # True for catchup_check (15:00) — generate only DAILY
) -> None:
    """Main conductor entry point — called hourly by cron."""
    if today is None:
        today = date.today()

    # 1. Check gates
    wb_gates = gate_checker.check_all("wb")
    ozon_gates = gate_checker.check_all("ozon")

    if not (wb_gates.can_generate and ozon_gates.can_generate):
        logger.info("Gates not passed: wb=%s, ozon=%s", wb_gates.can_generate, ozon_gates.can_generate)
        return

    # 2. What reports are needed today?
    schedule = get_today_reports(today)
    if daily_only:
        schedule = [r for r in schedule if r == ReportType.DAILY]
    done = conductor_state.get_successful(str(today))
    pending = [r for r in schedule if r.value not in done]

    # 2b. Recover missed weekly/monthly reports from past days
    if not daily_only:
        all_successful = conductor_state.get_all_successful_types(lookback_days=7)
        failed_or_missing = conductor_state.get_failed_types(lookback_days=7)
        # Add types that were scheduled but neither succeeded nor are already pending
        missed = get_missed_reports(today, failed_or_missing)
        pending_values = {r.value for r in pending}
        for rt in missed:
            if rt.value not in all_successful and rt.value not in pending_values:
                pending.append(rt)
                logger.info("Recovering missed report: %s", rt.value)

    if not pending:
        logger.info("All reports already generated for %s", today)
        return

    # 3. Send "data ready" notification (deduplicated)
    yesterday = today - timedelta(days=1)
    day_month = f"{yesterday.day} {_month_name(yesterday.month)}"
    report_date = str(today)

    if not conductor_state.already_notified(report_date):
        pending_names = [rt.human_name for rt in pending]
        await telegram_send(messages.data_ready(day_month, pending_names))
        conductor_state.mark_notified(report_date)
    else:
        logger.debug("data_ready: already notified for %s, skipping message", report_date)

    # 4. Generate + validate each report
    for report_type in pending:
        await generate_and_validate(
            report_type=report_type,
            today=today,
            conductor_state=conductor_state,
            telegram_send=telegram_send,
            orchestrator=orchestrator,
            delivery=delivery,
            scheduler=scheduler,
            attempt=1,
        )


async def generate_and_validate(
    report_type: ReportType,
    today: date,
    conductor_state: ConductorState,
    telegram_send,
    orchestrator,
    delivery,
    scheduler,
    attempt: int = 1,
) -> None:
    """Generate a single report, validate, deliver or retry."""
    report_date = str(today)

    conductor_state.log(report_date, report_type.value, status="running", attempt=attempt)
    logger.info("Generating %s (attempt %d/%d)", report_type.value, attempt, MAX_ATTEMPTS)

    try:
        # Compute dates
        dates = _compute_dates(report_type, today)

        # Call orchestrator
        method_name = report_type.orchestrator_method
        method = getattr(orchestrator, method_name)

        kwargs = {**dates, "channel": "both", "trigger": "cron"}
        if report_type in (ReportType.MARKETING_WEEKLY, ReportType.MARKETING_MONTHLY):
            kwargs["report_period"] = "weekly" if "weekly" in report_type.value else "monthly"

        result = await method(**kwargs)

    except Exception as e:
        logger.exception("Orchestrator error for %s: %s", report_type.value, e)
        result = {"status": "failed", "report": None, "agents_called": 0,
                  "agents_succeeded": 0, "agents_failed": 0}

    # Validate
    validation = quick_validate(result)

    if validation.verdict == ValidationVerdict.PASS:
        # Deliver
        try:
            delivery_result = await delivery(
                report=result,
                report_type=report_type.value,
                start_date=dates["date_from"],
                end_date=dates["date_to"],
            )
            notion_url = delivery_result.get("notion", {}).get("page_url")
        except Exception as e:
            logger.exception("Delivery error: %s", e)
            notion_url = None

        conductor_state.log(report_date, report_type.value, status="success",
                           attempt=attempt, notion_url=notion_url)
        logger.info("Report %s delivered successfully", report_type.value)

    elif validation.verdict == ValidationVerdict.RETRY and attempt < MAX_ATTEMPTS:
        # Schedule retry via DateTrigger
        pause_minutes = 1 if attempt == 1 else 5
        conductor_state.log(report_date, report_type.value, status="retrying",
                           attempt=attempt, error=validation.reason)
        logger.warning("Report %s failed validation (attempt %d): %s. Retrying in %d min.",
                       report_type.value, attempt, validation.reason, pause_minutes)

        if scheduler is not None:
            try:
                from apscheduler.triggers.date import DateTrigger
                from pytz import timezone as pytz_timezone
                msk = pytz_timezone("Europe/Moscow")
                scheduler.add_job(
                    generate_and_validate,
                    trigger=DateTrigger(run_date=datetime.now(msk) + timedelta(minutes=pause_minutes)),
                    kwargs={
                        "report_type": report_type,
                        "today": today,
                        "conductor_state": conductor_state,
                        "telegram_send": telegram_send,
                        "orchestrator": orchestrator,
                        "delivery": delivery,
                        "scheduler": scheduler,
                        "attempt": attempt + 1,
                    },
                    id=f"retry_{report_type.value}_{report_date}_{attempt + 1}",
                    replace_existing=True,
                )
            except Exception as e:
                logger.exception("Failed to schedule retry: %s", e)

    else:
        # All attempts exhausted or verdict == FAIL
        conductor_state.log(report_date, report_type.value, status="failed",
                           attempt=attempt, error=validation.reason)
        # Отправляем ошибку только на последней попытке (промежуточные ретраи молчат)
        if attempt >= MAX_ATTEMPTS:
            alert = messages.report_error(
                report_date, report_type.human_name,
                validation.reason, attempt, MAX_ATTEMPTS,
            )
            await telegram_send(alert)
        else:
            logger.warning("Report %s attempt %d/%d failed: %s", report_type, attempt, MAX_ATTEMPTS, validation.reason)
        logger.error("Report %s failed after %d attempts: %s",
                     report_type.value, attempt, validation.reason)


async def deadline_check(
    conductor_state: ConductorState,
    telegram_send,
    gate_checker,
    today: date = None,
) -> None:
    """Called at deadline (12:00 MSK). Alert if no reports generated."""
    if today is None:
        today = date.today()

    schedule = get_today_reports(today)
    done = conductor_state.get_successful(str(today))
    missing = [r for r in schedule if r.value not in done]

    if not missing:
        return

    # Diagnose
    wb_gates = gate_checker.check_all("wb")
    ozon_gates = gate_checker.check_all("ozon")

    if not wb_gates.can_generate or not ozon_gates.can_generate:
        diagnostics = "Данные не поступили"
        if not wb_gates.can_generate:
            diagnostics += " (WB gates не прошли)"
        if not ozon_gates.can_generate:
            diagnostics += " (OZON gates не прошли)"
    else:
        diagnostics = "Gates OK, но отчёты не были запущены"

    missing_names = ", ".join(r.human_name for r in missing)

    # Translate diagnostics to human-readable
    if "не поступили" in diagnostics.lower():
        human_diagnostics = "Данные от маркетплейсов ещё не поступили"
    elif "gates ok" in diagnostics.lower():
        human_diagnostics = "Данные есть, но генерация не запустилась"
    else:
        human_diagnostics = diagnostics

    from agents.v3.delivery import messages
    await telegram_send(messages.deadline_missed(missing_names, human_diagnostics))
