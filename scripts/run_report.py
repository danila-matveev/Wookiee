"""Run any report pipeline directly (bypasses Telegram bot).

Usage:
    python scripts/run_report.py daily                           # yesterday
    python scripts/run_report.py daily 2026-03-05                # specific date
    python scripts/run_report.py weekly                          # last week
    python scripts/run_report.py weekly 2026-03-03               # week containing date
    python scripts/run_report.py period 2026-02-01 2026-02-28    # arbitrary period
    python scripts/run_report.py period 2026-02-01 2026-02-28 --type monthly
    python scripts/run_report.py marketing                       # weekly marketing (last week)
    python scripts/run_report.py marketing 2026-03-05            # daily marketing
    python scripts/run_report.py marketing 2026-02-17 2026-02-23 # period marketing
    python scripts/run_report.py funnel                           # funnel weekly (last week)
    python scripts/run_report.py funnel 2026-03-03                # funnel weekly (week containing date)
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is on sys.path for cross-module imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _week_bounds(reference: date) -> tuple[date, date]:
    """Get Monday-Sunday bounds for the week containing reference date."""
    monday = reference - timedelta(days=reference.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _detect_report_type(start: date, end: date) -> str:
    """Auto-detect report type based on period length."""
    days = (end - start).days + 1
    if days == 1:
        return "daily"
    elif 6 <= days <= 8:
        return "weekly"
    elif 27 <= days <= 31:
        return "monthly"
    return "custom"


def _detect_marketing_type(start: date, end: date) -> str:
    """Auto-detect marketing report type based on period length."""
    days = (end - start).days
    if days == 0:
        return "marketing_daily"
    elif days <= 7:
        return "marketing_weekly"
    elif days <= 31:
        return "marketing_monthly"
    return "marketing_custom"


# ---------------------------------------------------------------------------
# Core: generate report and deliver to Notion
# ---------------------------------------------------------------------------

async def _generate_and_deliver(
    start: date,
    end: date,
    report_type_str: str,
    channel: str | None = None,
    context: dict | None = None,
):
    from agents.oleg.app import OlegApp
    from agents.oleg.pipeline.report_types import ReportRequest, ReportType

    report_type = ReportType(report_type_str)

    app = OlegApp()
    await app.setup()

    request = ReportRequest(
        report_type=report_type,
        start_date=str(start) if not isinstance(start, str) else start,
        end_date=str(end) if not isinstance(end, str) else end,
        channel=channel,
        context=context,
    )

    print(f"Starting {report_type_str} report for {start} — {end}...")
    result = await app.pipeline.generate_report(request)

    if result is None:
        print("FAILED: Gates did not pass")
        return

    print(f"SUCCESS! Steps: {result.chain_steps}, Cost: ${result.cost_usd:.4f}")
    print(f"Duration: {result.duration_ms}ms")
    print("--- BRIEF ---")
    print(result.brief_summary or "No summary")
    print("--- DETAILED ---")
    print(result.detailed_report or "No detailed report")

    # Deliver to Notion
    try:
        from agents.oleg import config
        from agents.oleg.services.notion_service import NotionService
        notion = NotionService(
            token=config.NOTION_TOKEN,
            database_id=config.NOTION_DATABASE_ID,
        )
        if notion.enabled:
            page_url = await notion.sync_report(
                start_date=str(start),
                end_date=str(end),
                report_md=result.detailed_report or result.brief_summary or "",
                source="CLI (manual)",
                report_type=result.report_type.value,
                chain_steps=result.chain_steps,
            )
            print(f"\nNotion: {page_url}")
    except Exception as e:
        print(f"\nNotion sync failed: {e}")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_daily(args: list[str]):
    if args:
        target = _parse_date(args[0])
    else:
        target = date.today() - timedelta(days=1)

    # Use CUSTOM type for historical dates to bypass gate checks
    # (gates check today's ETL, not the target date's ETL)
    from agents.oleg.services.time_utils import get_yesterday_msk
    yesterday = get_yesterday_msk()
    rtype = "daily" if target == yesterday else "custom"

    asyncio.run(_generate_and_deliver(target, target, rtype, channel="wb"))


def cmd_weekly(args: list[str]):
    if args:
        ref = _parse_date(args[0])
    else:
        ref = date.today() - timedelta(days=7)

    monday, sunday = _week_bounds(ref)
    asyncio.run(_generate_and_deliver(monday, sunday, "weekly", channel="wb"))


def cmd_period(args: list[str]):
    if len(args) < 2:
        print("Usage: python scripts/run_report.py period YYYY-MM-DD YYYY-MM-DD [--type daily|weekly|monthly|custom]")
        sys.exit(1)

    start = _parse_date(args[0])
    end = _parse_date(args[1])

    type_override = None
    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 < len(args):
            type_override = args[idx + 1]

    rtype = type_override or _detect_report_type(start, end)
    asyncio.run(_generate_and_deliver(start, end, rtype, channel="wb"))


def cmd_funnel(args: list[str]):
    if args:
        ref = _parse_date(args[0])
    else:
        ref = date.today() - timedelta(days=7)

    monday, sunday = _week_bounds(ref)

    async def _run():
        from agents.oleg.services.funnel_tools import get_all_models_funnel_bundle
        print(f"Pre-fetching funnel data for {monday} — {sunday}...")
        data_bundle = await get_all_models_funnel_bundle(str(monday), str(sunday))
        models_count = len(data_bundle.get("models", []))
        print(f"Found {models_count} active models with A/B articles")
        if models_count == 0:
            print("No active models — aborting")
            return
        await _generate_and_deliver(
            monday, sunday, "funnel_weekly",
            context={"data_bundle": data_bundle},
        )

    asyncio.run(_run())


def cmd_marketing(args: list[str]):
    if len(args) == 0:
        # Default: weekly report for last week
        monday, sunday = _week_bounds(date.today() - timedelta(days=7))
        asyncio.run(_generate_and_deliver(monday, sunday, "marketing_weekly"))
    elif len(args) == 1:
        # Single date → daily report
        target = _parse_date(args[0])
        asyncio.run(_generate_and_deliver(target, target, "marketing_daily"))
    elif len(args) >= 2:
        # Two dates → auto-detect type by length
        start = _parse_date(args[0])
        end = _parse_date(args[1])
        rtype = _detect_marketing_type(start, end)
        asyncio.run(_generate_and_deliver(start, end, rtype))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "daily": cmd_daily,
    "weekly": cmd_weekly,
    "period": cmd_period,
    "marketing": cmd_marketing,
    "funnel": cmd_funnel,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python scripts/run_report.py <command> [args...]")
        print(f"Commands: {', '.join(COMMANDS)}")
        print("\nExamples:")
        print("  python scripts/run_report.py daily")
        print("  python scripts/run_report.py daily 2026-03-05")
        print("  python scripts/run_report.py weekly")
        print("  python scripts/run_report.py weekly 2026-03-03")
        print("  python scripts/run_report.py period 2026-02-01 2026-02-28")
        print("  python scripts/run_report.py marketing")
        print("  python scripts/run_report.py marketing 2026-03-05")
        print("  python scripts/run_report.py funnel")
        print("  python scripts/run_report.py funnel 2026-03-03")
        sys.exit(1)

    command = sys.argv[1]
    COMMANDS[command](sys.argv[2:])
