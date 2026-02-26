"""Run daily report pipeline directly (bypasses Telegram bot)."""
import asyncio
import logging
import sys
from datetime import date, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


async def run(target_date: date):
    from agents.oleg.app import OlegApp
    from agents.oleg.pipeline.report_types import ReportRequest, ReportType
    from agents.oleg.services.time_utils import get_yesterday_msk

    app = OlegApp()
    await app.setup()

    # Use CUSTOM type for historical dates to bypass gate checks
    # (gates check today's ETL, not the target date's ETL)
    yesterday = get_yesterday_msk()
    report_type = ReportType.DAILY if target_date == yesterday else ReportType.CUSTOM

    request = ReportRequest(
        report_type=report_type,
        start_date=target_date,
        end_date=target_date,
        channel="wb",
    )

    print(f"Starting daily report generation for {target_date}...")
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
                report_type="daily",
                start_date=str(target_date),
                end_date=str(target_date),
                brief_summary=result.brief_summary or "",
                detailed_report=result.detailed_report or "",
                cost_usd=result.cost_usd,
                chain_steps=result.chain_steps,
                duration_ms=result.duration_ms,
            )
            print(f"\nNotion: {page_url}")
    except Exception as e:
        print(f"\nNotion sync failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parts = sys.argv[1].split("-")
        target = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        target = date.today() - timedelta(days=1)

    asyncio.run(run(target))
