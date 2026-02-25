"""Run report for arbitrary period (bypasses Telegram bot)."""
import asyncio
import logging
import sys
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


async def run(start: date, end: date):
    from agents.oleg.app import OlegApp
    from agents.oleg.pipeline.report_types import ReportRequest, ReportType

    app = OlegApp()
    await app.setup()

    request = ReportRequest(
        report_type=ReportType.CUSTOM,
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
                report_type="custom",
                start_date=str(start),
                end_date=str(end),
                brief_summary=result.brief_summary or "",
                detailed_report=result.detailed_report or "",
                cost_usd=result.cost_usd,
                chain_steps=result.chain_steps,
                duration_ms=result.duration_ms,
            )
            print(f"\nNotion: {page_url}")
    except Exception as e:
        print(f"\nNotion sync failed: {e}")


def _parse_date(s: str) -> date:
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_period_report.py YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)

    start_date = _parse_date(sys.argv[1])
    end_date = _parse_date(sys.argv[2])

    asyncio.run(run(start_date, end_date))
