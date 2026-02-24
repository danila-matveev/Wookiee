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

    app = OlegApp()
    await app.setup()

    request = ReportRequest(
        report_type=ReportType.DAILY,
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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parts = sys.argv[1].split("-")
        target = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        target = date.today() - timedelta(days=1)

    asyncio.run(run(target))
