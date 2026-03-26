"""
Finolog Categorizer Agent — entry point.

Runs daily at 05:00 MSK: scans transactions, classifies, publishes to Notion,
sends brief Telegram summary.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.oleg.services.finolog_service import FinologService
from shared.notion_client import NotionClient as NotionService

from . import config
from .scanner import DailyScanner
from .store import CategorizerStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _build_scanner() -> DailyScanner:
    finolog = FinologService(
        api_key=config.FINOLOG_API_KEY,
        biz_id=config.FINOLOG_BIZ_ID,
    )
    notion = NotionService(
        token=config.NOTION_TOKEN,
        database_id=config.NOTION_DATABASE_ID,
    )
    store = CategorizerStore()
    return DailyScanner(finolog=finolog, notion=notion, store=store)


async def _send_telegram(summary) -> None:
    """Send brief summary to Telegram."""
    if not config.TELEGRAM_BOT_TOKEN or not config.ADMIN_CHAT_ID:
        logger.info("Telegram not configured, skipping notification")
        return

    import httpx

    fb = summary.feedback
    fb_line = ""
    if fb and fb.total_comments > 0:
        fb_line = f"\nФидбек вчера: {fb.total_comments} комм., {fb.rules_applied} применено"

    text = (
        f"📋 <b>Категоризация операций за {summary.scan_date:%d.%m.%Y}</b>\n\n"
        f"Новых: {summary.total_new} | Авто: {summary.auto_categorized} | "
        f"На ревью: {summary.needs_review} | Неизвестных: {summary.unknown}"
    )
    if summary.overdue_planned:
        text += f"\nПросроченных плановых: {summary.overdue_planned}"
    text += fb_line
    if summary.notion_url:
        text += f"\n\n📄 <a href=\"{summary.notion_url}\">Открыть в Notion</a>"

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(url, json={
                "chat_id": config.ADMIN_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
        logger.info("Telegram notification sent")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


async def run_scan():
    """Execute daily scan and notify."""
    logger.info("=== Starting daily categorization scan ===")
    scanner = _build_scanner()
    try:
        summary = await scanner.run()
        await _send_telegram(summary)
        logger.info(f"=== Scan complete: {summary.notion_url} ===")
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)


async def main():
    """Entry point: schedule daily scan or run once."""
    tz = pytz.timezone(config.TIMEZONE)

    # If --once flag, run immediately and exit
    if "--once" in sys.argv:
        logger.info("Running single scan (--once mode)")
        await run_scan()
        return

    # Schedule daily scan
    scheduler = AsyncIOScheduler(timezone=tz)
    h, m = config.SCAN_TIME.split(":")
    scheduler.add_job(
        run_scan,
        CronTrigger(hour=int(h), minute=int(m)),
        id="daily_scan",
        name="Daily Finolog categorization",
    )
    scheduler.start()
    logger.info(f"Scheduler started: daily scan at {config.SCAN_TIME} MSK")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
