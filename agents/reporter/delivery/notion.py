# agents/reporter/delivery/notion.py
"""Notion delivery — upsert report page."""
from __future__ import annotations

import logging

from shared.notion_client import NotionClient

from agents.reporter.config import NOTION_DATABASE_ID, NOTION_TOKEN
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


def _get_notion_client() -> NotionClient:
    return NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)


async def upsert_notion(report_md: str, scope: ReportScope) -> str | None:
    """Upsert report to Notion. Returns page URL or None on failure."""
    client = _get_notion_client()
    if not client.enabled:
        logger.warning("Notion not configured, skipping delivery")
        return None

    try:
        url = await client.sync_report(
            start_date=scope.period_from.isoformat(),
            end_date=scope.period_to.isoformat(),
            report_md=report_md,
            report_type=scope.report_type.value.replace("_", " "),
            source="Reporter V4 (auto)",
        )
        logger.info("Notion upsert OK: %s", url)
        return url
    except Exception as e:
        logger.error("Notion delivery failed: %s", e)
        return None
