"""
Unified report runner for Wookiee Oleg v2.0.

Two modes:
  --type <type>    Manual single-report run (debug/restart a specific type)
  --schedule       Automatic cron-driven scheduling with lock-files and stub notifications

Usage:
    python scripts/run_report.py --type daily
    python scripts/run_report.py --type weekly --date 2026-03-30
    python scripts/run_report.py --schedule
    python scripts/run_report.py --schedule --date 2026-04-06

Design decisions (from 04-CONTEXT.md):
- D-01: One script, two modes
- D-02: Initializes all clients (LLM, Notion, Alerter, GateChecker)
- D-05: Cron-compatible polling mode (every 30 min, 07:00-18:00 MSK)
- D-06: Lock-file per report_type per date prevents duplicate runs
- D-07: Stub Telegram at stub hours (9, 11, 13, 15, 17) if data not ready
- D-08: Final notification at ~18:00 if no reports published all day
- D-09: Report order: financial > marketing > funnel > localization > DDS (last)
- D-10: Daily types every day; weekly on Monday; monthly on Monday 1-7
- D-14: Telegram message (type name + metrics + Notion link) delegated to pipeline Step 7
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agents.oleg.pipeline.report_pipeline import run_report
from agents.oleg.pipeline.report_types import REPORT_CONFIGS, ReportType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCKS_DIR = Path(os.getenv("REPORT_LOCKS_DIR", "/app/locks"))

# Stub notification hours (D-07): 09:00, 11:00, 13:00, 15:00, 17:00 MSK
STUB_HOURS: set[int] = {9, 11, 13, 15, 17}

# Report execution order (D-09): financial → marketing → funnel → localization → DDS (last)
REPORT_ORDER = [
    ReportType.DAILY,
    ReportType.WEEKLY,
    ReportType.MONTHLY,
    ReportType.MARKETING_WEEKLY,
    ReportType.MARKETING_MONTHLY,
    ReportType.FUNNEL_WEEKLY,
    ReportType.LOCALIZATION_WEEKLY,
    ReportType.FINOLOG_WEEKLY,   # always last (D-09)
]


# ---------------------------------------------------------------------------
# Pure logic functions (testable, no side effects)
# ---------------------------------------------------------------------------

def get_types_for_today(today: Optional[date] = None) -> list[ReportType]:
    """Return the list of ReportTypes to run today, in REPORT_ORDER sequence.

    Rules (D-10):
    - "daily" period: every day
    - "weekly" period: only on Monday (weekday == 0)
    - "monthly" period: only on Monday AND day-of-month in 1..7

    Returns types in REPORT_ORDER order (D-09).
    """
    if today is None:
        today = date.today()

    is_monday = today.weekday() == 0
    is_first_week_monday = is_monday and 1 <= today.day <= 7

    result = []
    for rt in REPORT_ORDER:
        config = REPORT_CONFIGS[rt]
        if config.period == "daily":
            result.append(rt)
        elif config.period == "weekly" and is_monday:
            result.append(rt)
        elif config.period == "monthly" and is_first_week_monday:
            result.append(rt)

    return result


def is_locked(
    report_type: str,
    target_date: date,
    locks_dir: Optional[Path] = None,
) -> bool:
    """Return True if this report_type has already been published for target_date.

    Lock file name: {report_type}_{target_date.isoformat()}.lock
    """
    if locks_dir is None:
        locks_dir = LOCKS_DIR
    lock_file = locks_dir / f"{report_type}_{target_date.isoformat()}.lock"
    return lock_file.exists()


def acquire_lock(
    report_type: str,
    target_date: date,
    locks_dir: Optional[Path] = None,
) -> None:
    """Create a lock file marking this report as published for target_date."""
    if locks_dir is None:
        locks_dir = LOCKS_DIR
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_file = locks_dir / f"{report_type}_{target_date.isoformat()}.lock"
    lock_file.touch()


def compute_date_range(period: str, target_date: date) -> tuple[str, str]:
    """Compute the date range string pair for a given report period.

    - "daily":   (target_date, target_date)
    - "weekly":  previous Monday to Sunday (the week before target_date's week)
    - "monthly": full previous calendar month

    Returns (date_from_iso, date_to_iso).
    """
    if period == "daily":
        iso = target_date.isoformat()
        return iso, iso

    if period == "weekly":
        # Previous Monday to Sunday (one full week before current week's Monday)
        last_monday = target_date - timedelta(days=target_date.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        return last_monday.isoformat(), last_sunday.isoformat()

    if period == "monthly":
        # Full previous calendar month
        first_of_this = target_date.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        first_of_prev = last_of_prev.replace(day=1)
        return first_of_prev.isoformat(), last_of_prev.isoformat()

    raise ValueError(f"Unknown period: {period!r}")


def should_send_stub(now: Optional[datetime] = None) -> bool:
    """Return True if we're in a stub notification window.

    Stub window: hour is in STUB_HOURS AND minute < 35
    (gives a ~35-minute window per stub hour for cron execution jitter).
    """
    if now is None:
        now = datetime.now()
    return now.hour in STUB_HOURS and now.minute < 35


def is_final_window(now: Optional[datetime] = None) -> bool:
    """Return True if we're in the final notification window (~17:55-18:00).

    Final window: hour >= 17 AND minute >= 55
    Matches D-05/D-08: cron runs until 18:00, final notification at ~17:55.
    """
    if now is None:
        now = datetime.now()
    return now.hour >= 17 and now.minute >= 55


def any_lock_today(
    target_date: date,
    locks_dir: Optional[Path] = None,
) -> bool:
    """Return True if any report was already published today (any lock file exists)."""
    if locks_dir is None:
        locks_dir = LOCKS_DIR
    if not locks_dir.exists():
        return False
    pattern = f"*_{target_date.isoformat()}.lock"
    return any(locks_dir.glob(pattern))


# ---------------------------------------------------------------------------
# Client initialization (D-02, pattern from run_oleg_v2_reports.py)
# ---------------------------------------------------------------------------

def init_clients():
    """Initialize all required clients: LLM, Notion, GateChecker, Alerter."""
    from shared.config import (
        MODEL_MAIN,
        NOTION_DATABASE_ID,
        NOTION_TOKEN,
        OPENROUTER_API_KEY,
    )
    from shared.clients.openrouter_client import OpenRouterClient
    from shared.notion_client import NotionClient
    from agents.oleg.pipeline.gate_checker import GateChecker
    from agents.oleg.watchdog.alerter import Alerter

    try:
        from aiogram import Bot
    except ImportError:
        Bot = None

    llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=MODEL_MAIN)
    notion = NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)
    gate_checker = GateChecker()

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    bot = Bot(token=tg_token) if (tg_token and Bot is not None) else None
    alerter = Alerter(bot=bot, admin_chat_id=chat_id)

    return llm, notion, gate_checker, alerter


# ---------------------------------------------------------------------------
# Orchestrator factory (Pitfall 6: new orchestrator per type)
# ---------------------------------------------------------------------------

def build_orchestrator(task_type: str, llm, model: str, pricing: dict):
    """Build a fresh OlegOrchestrator with task-type-specific agents.

    Per Pitfall 6 in 04-CONTEXT.md: create a new orchestrator per report type
    so each reporter/marketer loads the correct task-type playbook.
    """
    from agents.oleg.agents.reporter.agent import ReporterAgent
    from agents.oleg.agents.marketer.agent import MarketerAgent
    from agents.oleg.agents.funnel.agent import FunnelAgent
    from agents.oleg.agents.advisor.agent import AdvisorAgent
    from agents.oleg.agents.validator.agent import ValidatorAgent
    from agents.oleg.orchestrator.orchestrator import OlegOrchestrator

    reporter = ReporterAgent(llm, model, pricing=pricing, task_type=task_type)
    marketer = MarketerAgent(llm, model, pricing=pricing, task_type=task_type)
    funnel = FunnelAgent(llm, model, pricing=pricing)
    advisor = AdvisorAgent(llm, model, pricing=pricing)
    validator = ValidatorAgent(llm, model, pricing=pricing)

    return OlegOrchestrator(
        llm_client=llm,
        model=model,
        agents={
            "reporter": reporter,
            "marketer": marketer,
            "funnel": funnel,
            "advisor": advisor,
            "validator": validator,
        },
        pricing=pricing,
    )


# ---------------------------------------------------------------------------
# Single report runner (--type mode)
# ---------------------------------------------------------------------------

async def run_single(
    report_type: ReportType,
    target_date: date,
    llm,
    model: str,
    pricing: dict,
    notion,
    gate_checker,
    alerter,
) -> None:
    """Run a single report type manually — no lock-file check (manual mode)."""
    logger.info("=" * 60)
    logger.info("Manual run: %s for %s", report_type.value, target_date)

    config = REPORT_CONFIGS[report_type]
    date_from, date_to = compute_date_range(config.period, target_date)
    logger.info("Date range: %s — %s", date_from, date_to)

    orchestrator = build_orchestrator(report_type.value, llm, model, pricing)

    result = await run_report(
        report_type=report_type,
        target_date=target_date,
        orchestrator=orchestrator,
        notion_client=notion,
        alerter=alerter,
        gate_checker=gate_checker,
        date_from=date_from,
        date_to=date_to,
    )

    if result.success:
        logger.info("Published %s: %s", report_type.value, result.notion_url)
        if result.warnings:
            for w in result.warnings:
                logger.warning("Warning: %s", w)
    elif result.skipped:
        logger.warning("Skipped %s: %s", report_type.value, result.reason)
    else:
        logger.error("Failed %s: %s", report_type.value, result.reason)


# ---------------------------------------------------------------------------
# Schedule runner (--schedule mode, D-05 through D-10)
# ---------------------------------------------------------------------------

async def run_schedule(
    target_date: date,
    llm,
    model: str,
    pricing: dict,
    notion,
    gate_checker,
    alerter,
) -> None:
    """Run scheduled reports for today — cron-driven with lock-files and stub notifications.

    Steps:
    1. Determine which types to run today (D-10)
    2. For each type, skip if locked (already published today)
    3. Run pipeline for unlocked types
    4. Acquire lock on success
    5. Send stub notification if data not ready at stub hour (D-07)
    6. Send final notification at 18:00 window if nothing published all day (D-08)
    """
    types = get_types_for_today(target_date)
    if not types:
        logger.info("No report types scheduled for today (%s)", target_date)
        return

    logger.info(
        "Scheduled types for %s: %s",
        target_date,
        [rt.value for rt in types],
    )

    now = datetime.now()
    published_any = False

    for rt in types:
        if is_locked(rt.value, target_date):
            logger.info("Skipping %s — already published today", rt.value)
            published_any = True  # was already published in a prior cron run
            continue

        config = REPORT_CONFIGS[rt]
        date_from, date_to = compute_date_range(config.period, target_date)

        logger.info(
            "Running %s (%s → %s)",
            rt.value,
            date_from,
            date_to,
        )

        orchestrator = build_orchestrator(rt.value, llm, model, pricing)

        result = await run_report(
            report_type=rt,
            target_date=target_date,
            orchestrator=orchestrator,
            notion_client=notion,
            alerter=alerter,
            gate_checker=gate_checker,
            date_from=date_from,
            date_to=date_to,
        )

        if result.success:
            acquire_lock(rt.value, target_date)
            published_any = True
            logger.info("Published %s: %s", rt.value, result.notion_url)
            # D-14: Telegram message (type name + metrics + Notion link) is
            # handled INSIDE report_pipeline.py Step 7 via chain_result.telegram_summary.
            # Runner does NOT send its own Telegram for successful reports.
            if result.warnings:
                for w in result.warnings:
                    logger.warning("Warning for %s: %s", rt.value, w)
        elif result.skipped:
            logger.info("Skipped %s: %s", rt.value, result.reason)
        else:
            logger.error("Failed %s: %s", rt.value, result.reason)

    # ------------------------------------------------------------------
    # Stub / final notifications (D-07, D-08)
    # ------------------------------------------------------------------
    # Check whether ANYTHING was published today across all cron runs
    already_published_today = published_any or any_lock_today(target_date)

    if not already_published_today:
        if is_final_window(now):
            # D-08: Final notification if no reports published all day
            logger.warning("Final window reached, no reports published today — sending alert")
            try:
                await alerter.send_alert(
                    "Данные не появились за день. Ни один отчёт не был опубликован."
                )
            except Exception as e:
                logger.error("Failed to send final notification: %s", e)
        elif should_send_stub(now):
            # D-07: Stub notification every 2 hours if data not ready
            logger.info("Stub hour reached, data not ready — sending stub notification")
            try:
                await alerter.send_alert(
                    "Данные пока не готовы, отслеживаем. "
                    f"Запланировано типов: {len(types)}."
                )
            except Exception as e:
                logger.error("Failed to send stub notification: %s", e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Parse args and dispatch to --type or --schedule mode."""
    parser = argparse.ArgumentParser(
        description="Wookiee Report Runner — unified entry point for all report generation",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--type",
        choices=[t.value for t in ReportType],
        metavar="TYPE",
        help=(
            "Run a single report type manually. "
            f"Choices: {', '.join(t.value for t in ReportType)}"
        ),
    )
    group.add_argument(
        "--schedule",
        action="store_true",
        help="Auto-schedule based on day: daily every day, weekly on Monday, monthly Mon 1-7",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Target date (ISO format). Defaults to today.",
    )
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()

    from shared.config import MODEL_MAIN, PRICING  # noqa: PLC0415

    llm, notion, gate_checker, alerter = init_clients()
    model = MODEL_MAIN
    pricing = PRICING

    if args.type:
        await run_single(
            ReportType(args.type),
            target_date,
            llm,
            model,
            pricing,
            notion,
            gate_checker,
            alerter,
        )
    else:
        await run_schedule(
            target_date,
            llm,
            model,
            pricing,
            notion,
            gate_checker,
            alerter,
        )


if __name__ == "__main__":
    asyncio.run(main())
