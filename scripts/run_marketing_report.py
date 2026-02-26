"""Run marketing report pipeline directly (bypasses Telegram bot).

Usage:
    python run_marketing_report.py                        # weekly (last week)
    python run_marketing_report.py 2026-02-25             # daily
    python run_marketing_report.py 2026-02-17 2026-02-23  # custom period
"""
import asyncio
import logging
import sys
from datetime import date, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def _parse_date(s: str) -> date:
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _week_bounds(reference: date) -> tuple[date, date]:
    """Get Monday-Sunday bounds for the week containing reference date."""
    monday = reference - timedelta(days=reference.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


async def run(start: date, end: date, report_type_str: str):
    from agents.oleg.app import OlegApp
    from agents.oleg.pipeline.report_types import ReportRequest, ReportType

    report_type_map = {
        "marketing_daily": ReportType.MARKETING_DAILY,
        "marketing_weekly": ReportType.MARKETING_WEEKLY,
        "marketing_monthly": ReportType.MARKETING_MONTHLY,
        "marketing_custom": ReportType.MARKETING_CUSTOM,
    }
    report_type = report_type_map[report_type_str]

    app = OlegApp()
    await app.setup()

    request = ReportRequest(
        report_type=report_type,
        start_date=str(start),
        end_date=str(end),
    )

    print(f"Starting marketing report ({report_type_str}) for {start} — {end}...")
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
                chain_steps=result.chain_steps,
            )
            print(f"\nNotion: {page_url}")
    except Exception as e:
        print(f"\nNotion sync failed: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) == 0:
        # Default: weekly report for last week
        monday, sunday = _week_bounds(date.today() - timedelta(days=7))
        asyncio.run(run(monday, sunday, "marketing_weekly"))

    elif len(args) == 1:
        # Single date → daily report
        target = _parse_date(args[0])
        asyncio.run(run(target, target, "marketing_daily"))

    elif len(args) == 2:
        # Two dates → custom period (adapt type by length)
        start_date = _parse_date(args[0])
        end_date = _parse_date(args[1])
        days = (end_date - start_date).days

        if days == 0:
            rtype = "marketing_daily"
        elif days <= 7:
            rtype = "marketing_weekly"
        elif days <= 31:
            rtype = "marketing_monthly"
        else:
            rtype = "marketing_custom"

        asyncio.run(run(start_date, end_date, rtype))

    else:
        print("Usage: python run_marketing_report.py [YYYY-MM-DD [YYYY-MM-DD]]")
        sys.exit(1)
