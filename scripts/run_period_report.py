"""Run report for arbitrary period (bypasses Telegram bot)."""
import asyncio
import logging
import sys
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def _detect_report_type(start: date, end: date) -> "ReportType":
    """Auto-detect report type based on period length."""
    from agents.oleg.pipeline.report_types import ReportType

    days = (end - start).days + 1
    if days == 1:
        return ReportType.DAILY
    elif 6 <= days <= 8:
        return ReportType.WEEKLY
    elif 27 <= days <= 31:
        return ReportType.MONTHLY
    return ReportType.CUSTOM


async def run(start: date, end: date, report_type_override: str = None):
    from agents.oleg.app import OlegApp
    from agents.oleg.pipeline.report_types import ReportRequest, ReportType

    app = OlegApp()
    await app.setup()

    if report_type_override:
        rtype = ReportType(report_type_override)
    else:
        rtype = _detect_report_type(start, end)

    request = ReportRequest(
        report_type=rtype,
        start_date=str(start),
        end_date=str(end),
        channel="wb",
    )

    print(f"Starting report generation for {start} — {end}...")
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


def _parse_date(s: str) -> date:
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_period_report.py YYYY-MM-DD YYYY-MM-DD [--type daily|weekly|monthly|custom]")
        sys.exit(1)

    start_date = _parse_date(sys.argv[1])
    end_date = _parse_date(sys.argv[2])

    type_override = None
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        if idx + 1 < len(sys.argv):
            type_override = sys.argv[idx + 1]

    asyncio.run(run(start_date, end_date, report_type_override=type_override))
