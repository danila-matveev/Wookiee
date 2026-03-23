"""Run any report pipeline directly (bypasses Telegram bot).

Uses V3 orchestrator (micro-agent pipeline) — parallel analytical agents
followed by report-compiler.

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


def _prev_period(start: date, end: date) -> tuple[date, date]:
    """Calculate comparison period (same length, immediately preceding)."""
    length = (end - start).days + 1
    comp_end = start - timedelta(days=1)
    comp_start = comp_end - timedelta(days=length - 1)
    return comp_start, comp_end


def _detect_report_period(start: date, end: date) -> str:
    """Auto-detect report period label based on date range length."""
    days = (end - start).days + 1
    if days == 1:
        return "daily"
    elif 6 <= days <= 8:
        return "weekly"
    elif 27 <= days <= 31:
        return "monthly"
    return "weekly"


# ---------------------------------------------------------------------------
# Core: generate report via V3 orchestrator and print results
# ---------------------------------------------------------------------------

def _print_result(result: dict):
    """Print V3 orchestrator result to console."""
    status = result.get("status", "unknown")
    duration = result.get("duration_ms", 0)
    called = result.get("agents_called", 0)
    succeeded = result.get("agents_succeeded", 0)
    failed = result.get("agents_failed", 0)
    confidence = result.get("aggregate_confidence", 0.0)
    cost = result.get("total_cost_usd", 0.0)
    tokens = result.get("total_tokens", 0)

    print(f"\nStatus: {status.upper()}")
    print(f"Agents: {succeeded}/{called} succeeded, {failed} failed")
    print(f"Confidence: {confidence:.0%}")
    print(f"Duration: {duration}ms | Tokens: {tokens} | Cost: ${cost:.4f}")

    report = result.get("report", {})
    if isinstance(report, dict):
        telegram = report.get("telegram_summary")
        detailed = report.get("detailed_report")
        if telegram:
            print("\n--- TELEGRAM SUMMARY ---")
            print(telegram)
        if detailed:
            print("\n--- DETAILED REPORT ---")
            print(detailed)
    elif isinstance(report, str) and report:
        print("\n--- REPORT ---")
        print(report)

    worst = result.get("worst_limitation")
    if worst:
        print(f"\nWorst limitation: {worst}")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_daily(args: list[str]):
    from agents.v3.orchestrator import run_daily_report

    if args:
        target = _parse_date(args[0])
    else:
        target = date.today() - timedelta(days=1)

    comp_start, comp_end = _prev_period(target, target)

    print(f"Starting daily report for {target} (comparison: {comp_start} — {comp_end})...")
    result = asyncio.run(run_daily_report(
        date_from=str(target),
        date_to=str(target),
        comparison_from=str(comp_start),
        comparison_to=str(comp_end),
        trigger="user_cli",
    ))
    _print_result(result)


def cmd_weekly(args: list[str]):
    from agents.v3.orchestrator import run_weekly_report

    if args:
        ref = _parse_date(args[0])
    else:
        ref = date.today() - timedelta(days=7)

    monday, sunday = _week_bounds(ref)
    comp_start, comp_end = _prev_period(monday, sunday)

    print(f"Starting weekly report for {monday} — {sunday} (comparison: {comp_start} — {comp_end})...")
    result = asyncio.run(run_weekly_report(
        date_from=str(monday),
        date_to=str(sunday),
        comparison_from=str(comp_start),
        comparison_to=str(comp_end),
        trigger="user_cli",
    ))
    _print_result(result)


def cmd_period(args: list[str]):
    if len(args) < 2:
        print("Usage: python scripts/run_report.py period YYYY-MM-DD YYYY-MM-DD [--type daily|weekly|monthly]")
        sys.exit(1)

    start = _parse_date(args[0])
    end = _parse_date(args[1])
    comp_start, comp_end = _prev_period(start, end)

    type_override = None
    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 < len(args):
            type_override = args[idx + 1]

    rtype = type_override or _detect_report_period(start, end)

    # Route to the appropriate V3 orchestrator function
    from agents.v3 import orchestrator

    runner_map = {
        "daily": orchestrator.run_daily_report,
        "weekly": orchestrator.run_weekly_report,
        "monthly": orchestrator.run_monthly_report,
    }
    runner = runner_map.get(rtype, orchestrator.run_weekly_report)

    print(f"Starting {rtype} report for {start} — {end} (comparison: {comp_start} — {comp_end})...")
    result = asyncio.run(runner(
        date_from=str(start),
        date_to=str(end),
        comparison_from=str(comp_start),
        comparison_to=str(comp_end),
        trigger="user_cli",
    ))
    _print_result(result)


def cmd_funnel(args: list[str]):
    from agents.v3.orchestrator import run_funnel_report

    if args:
        ref = _parse_date(args[0])
    else:
        ref = date.today() - timedelta(days=7)

    monday, sunday = _week_bounds(ref)
    comp_start, comp_end = _prev_period(monday, sunday)

    print(f"Starting funnel report for {monday} — {sunday} (comparison: {comp_start} — {comp_end})...")
    result = asyncio.run(run_funnel_report(
        date_from=str(monday),
        date_to=str(sunday),
        comparison_from=str(comp_start),
        comparison_to=str(comp_end),
        trigger="user_cli",
    ))
    _print_result(result)


def cmd_marketing(args: list[str]):
    from agents.v3.orchestrator import run_marketing_report

    if len(args) == 0:
        # Default: weekly report for last week
        monday, sunday = _week_bounds(date.today() - timedelta(days=7))
        comp_start, comp_end = _prev_period(monday, sunday)
        report_period = "weekly"
        start, end = monday, sunday
    elif len(args) == 1:
        # Single date -> daily report
        start = _parse_date(args[0])
        end = start
        comp_start, comp_end = _prev_period(start, end)
        report_period = "daily"
    else:
        # Two dates -> auto-detect type by length
        start = _parse_date(args[0])
        end = _parse_date(args[1])
        comp_start, comp_end = _prev_period(start, end)
        days = (end - start).days
        if days == 0:
            report_period = "daily"
        elif days <= 7:
            report_period = "weekly"
        else:
            report_period = "monthly"

    print(f"Starting marketing ({report_period}) report for {start} — {end} (comparison: {comp_start} — {comp_end})...")
    result = asyncio.run(run_marketing_report(
        date_from=str(start),
        date_to=str(end),
        comparison_from=str(comp_start),
        comparison_to=str(comp_end),
        report_period=report_period,
        trigger="user_cli",
    ))
    _print_result(result)


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
