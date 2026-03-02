"""Run weekly report pipeline directly (bypasses Telegram bot)."""
import asyncio
import logging
import sys
from datetime import date, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def _week_bounds(reference: date) -> tuple[date, date]:
    """Get Monday-Sunday bounds for the week containing reference date."""
    monday = reference - timedelta(days=reference.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


async def run(reference_date: date):
    from agents.oleg.app import OlegApp
    from agents.oleg.pipeline.report_types import ReportRequest, ReportType

    monday, sunday = _week_bounds(reference_date)

    app = OlegApp()
    await app.setup()

    request = ReportRequest(
        report_type=ReportType.WEEKLY,
        start_date=str(monday),
        end_date=str(sunday),
        channel="wb",
    )

    print(f"Starting weekly report generation for {monday} — {sunday}...")
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
                start_date=str(monday),
                end_date=str(sunday),
                report_md=result.detailed_report or result.brief_summary or "",
                source="CLI (manual)",
                report_type=result.report_type.value,
                chain_steps=result.chain_steps,
            )
            print(f"\nNotion: {page_url}")
    except Exception as e:
        print(f"\nNotion sync failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parts = sys.argv[1].split("-")
        ref = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        ref = date.today() - timedelta(days=7)  # last week

    asyncio.run(run(ref))
