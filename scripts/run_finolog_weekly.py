"""Standalone Finolog ДДС weekly report — bypasses v3 pipeline entirely.

Fetches real data from Finolog API via FinologService, delivers to Notion + Telegram.
No LLM agents, no orchestrator — deterministic and reliable.

Usage:
    # Generate current report (today's balances + 6-month forecast)
    python scripts/run_finolog_weekly.py

    # Generate and deliver to Notion + Telegram
    python scripts/run_finolog_weekly.py --deliver

    # Just print to stdout (dry run)
    python scripts/run_finolog_weekly.py --dry-run

    # Custom period label (for Notion title)
    python scripts/run_finolog_weekly.py --deliver --date-from 2026-03-17 --date-to 2026-03-23
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import httpx

from agents.v3 import config
from agents.oleg.services.finolog_service import FinologService
from shared.notion_client import NotionClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _last_week() -> tuple[str, str]:
    """Return (monday, sunday) of the previous full week."""
    today = date.today()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    return str(last_monday), str(last_sunday)


async def _send_telegram(html_text: str, page_url: str | None = None) -> bool:
    """Send brief HTML to Telegram admin chat."""
    if not config.TELEGRAM_BOT_TOKEN or not config.ADMIN_CHAT_ID:
        logger.warning("Telegram not configured, skipping")
        return False

    if page_url:
        html_text += f'\n\n<a href="{page_url}">📋 Полный отчёт в Notion</a>'

    from agents.v3.delivery.telegram import split_html_message
    chunks = split_html_message(html_text)

    tg_api = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for chunk in chunks:
                resp = await client.post(
                    f"{tg_api}/sendMessage",
                    json={
                        "chat_id": config.ADMIN_CHAT_ID,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                resp.raise_for_status()
        logger.info("Telegram: sent %d chunk(s)", len(chunks))
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


async def _send_notion(report_md: str, date_from: str, date_to: str) -> str | None:
    """Sync report to Notion, return page URL."""
    if not config.NOTION_TOKEN or not config.NOTION_DATABASE_ID:
        logger.warning("Notion not configured, skipping")
        return None

    notion = NotionClient(
        token=config.NOTION_TOKEN,
        database_id=config.NOTION_DATABASE_ID,
    )
    try:
        page_url = await notion.sync_report(
            start_date=date_from,
            end_date=date_to,
            report_md=report_md,
            report_type="finolog_weekly",
            source="Finolog Direct (auto)",
        )
        logger.info("Notion: %s", page_url)
        return page_url
    except Exception as exc:
        logger.error("Notion delivery failed: %s", exc)
        return None


async def run(
    date_from: str | None = None,
    date_to: str | None = None,
    deliver: bool = False,
    dry_run: bool = False,
) -> dict:
    """Main entry point: fetch data → build report → optionally deliver.

    Returns dict with report_md, brief_html, notion_url, telegram_sent.
    """
    if not config.FINOLOG_API_KEY:
        logger.error("FINOLOG_API_KEY not set in .env — cannot generate report")
        return {"error": "FINOLOG_API_KEY not set"}

    # Default period: last week
    if not date_from or not date_to:
        date_from, date_to = _last_week()

    logger.info("Generating Finolog ДДС report (period label: %s — %s)", date_from, date_to)

    # 1. Fetch data and build report
    svc = FinologService(
        api_key=config.FINOLOG_API_KEY,
        biz_id=config.FINOLOG_BIZ_ID,
    )
    report_md, brief_html = await svc.build_weekly_summary(
        cash_gap_threshold=config.FINOLOG_CASH_GAP_THRESHOLD,
    )

    result = {
        "report_md": report_md,
        "brief_html": brief_html,
        "notion_url": None,
        "telegram_sent": False,
    }

    if dry_run:
        print("=" * 60)
        print("MARKDOWN (Notion):")
        print("=" * 60)
        print(report_md)
        print()
        print("=" * 60)
        print("HTML (Telegram):")
        print("=" * 60)
        print(brief_html)
        return result

    if not deliver:
        print(report_md)
        return result

    # 2. Deliver to Notion
    page_url = await _send_notion(report_md, date_from, date_to)
    result["notion_url"] = page_url

    # 3. Deliver to Telegram
    tg_ok = await _send_telegram(brief_html, page_url)
    result["telegram_sent"] = tg_ok

    logger.info(
        "Done. Notion: %s | Telegram: %s",
        page_url or "skipped",
        "sent" if tg_ok else "skipped",
    )
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Finolog ДДС weekly report")
    parser.add_argument("--deliver", action="store_true", help="Deliver to Notion + Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Print both MD and HTML, don't deliver")
    parser.add_argument("--date-from", type=str, default=None, help="Period start (for Notion title)")
    parser.add_argument("--date-to", type=str, default=None, help="Period end (for Notion title)")
    args = parser.parse_args()

    result = asyncio.run(run(
        date_from=args.date_from,
        date_to=args.date_to,
        deliver=args.deliver,
        dry_run=args.dry_run,
    ))

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
