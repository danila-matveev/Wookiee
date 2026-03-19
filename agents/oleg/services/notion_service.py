"""
Notion Service — sync reports to Notion database.

Standalone implementation (no v1 dependency).
"""
import logging
import re
from typing import Optional

import httpx

from shared.notion_blocks import md_to_notion_blocks, parse_inline, remove_empty_sections

logger = logging.getLogger(__name__)

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

_MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

# Maps every possible report_type input → (Notion "Тип анализа" label, title prefix)
_REPORT_TYPE_MAP: dict[str, tuple[str, str]] = {
    "daily":              ("Ежедневный фин анализ",     "Ежедневный фин анализ"),
    "weekly":             ("Еженедельный фин анализ",   "Еженедельный фин анализ"),
    "monthly":            ("Ежемесячный фин анализ",    "Ежемесячный фин анализ"),
    "custom":             ("Фин анализ",                "Фин анализ"),
    "marketing_daily":    ("Маркетинговый анализ",      "Ежедневный маркетинговый анализ"),
    "marketing_weekly":   ("Маркетинговый анализ",      "Еженедельный маркетинговый анализ"),
    "marketing_monthly":  ("Маркетинговый анализ",      "Ежемесячный маркетинговый анализ"),
    "marketing_custom":   ("Маркетинговый анализ",      "Маркетинговый анализ"),
    "Ценовой анализ":        ("Ценовой анализ",        "Ценовой анализ"),
    "Регрессионный анализ":  ("Регрессионный анализ",  "Регрессионный анализ"),
    "Анализ акций":          ("Анализ акций",          "Анализ акций"),
    "finolog_weekly":        ("Еженедельная сводка ДДС", "Сводка ДДС"),
    "funnel_weekly":         ("funnel_weekly", "Воронка WB (сводный)"),
    "finolog_categorization": ("Категоризация операций", "Категоризация операций"),
}


def _format_date_range_ru(start_date: str, end_date: str) -> str:
    """Format date range in Russian: '16-22 февраля 2026' or '28 января — 3 февраля 2026'."""
    try:
        sy, sm, sd = start_date.split("-")
        ey, em, ed = end_date.split("-")
        s_day, s_month, s_year = int(sd), int(sm), int(sy)
        e_day, e_month, e_year = int(ed), int(em), int(ey)

        if start_date == end_date:
            return f"{s_day} {_MONTHS_RU[s_month]} {s_year}"
        elif s_year == e_year and s_month == e_month:
            return f"{s_day}-{e_day} {_MONTHS_RU[s_month]} {s_year}"
        elif s_year == e_year:
            return f"{s_day} {_MONTHS_RU[s_month]} — {e_day} {_MONTHS_RU[e_month]} {s_year}"
        else:
            return f"{s_day} {_MONTHS_RU[s_month]} {s_year} — {e_day} {_MONTHS_RU[e_month]} {e_year}"
    except (ValueError, KeyError):
        return f"{start_date} — {end_date}"


class NotionService:
    """Sync reports to Notion database with chain metadata."""

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.database_id)

    async def _request(self, method: str, endpoint: str, payload: dict = None) -> dict:
        """Execute Notion API request."""
        url = f"{API_BASE}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error(f"Notion API {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
            return resp.json()

    async def sync_report(
        self,
        start_date: str,
        end_date: str,
        report_md: str,
        source: str = "Reporter (auto)",
        report_type: str = "Ежедневный фин анализ",
        chain_steps: int = 1,
    ) -> Optional[str]:
        """
        Sync a report to Notion (upsert).

        Returns Notion page URL or None on failure.
        """
        if not self.enabled:
            logger.warning("Notion not configured, skipping sync")
            return None

        try:
            _map = _REPORT_TYPE_MAP.get(report_type)
            if _map:
                notion_label, title_prefix = _map
            else:
                notion_label, title_prefix = report_type, report_type

            title = f"{title_prefix} за {_format_date_range_ru(start_date, end_date)}"
            report_type = notion_label

            report_md = remove_empty_sections(report_md)
            blocks = md_to_notion_blocks(report_md)

            existing = await self._find_existing_page(start_date, end_date, report_type)

            if existing:
                page_id = existing["id"]
                page_url = existing["url"]
                logger.info(f"Notion: updating existing page {page_id}")

                await self._delete_page_content(page_id)

                properties = {
                    "Name": {"title": [{"text": {"content": title}}]},
                    "Статус": {"select": {"name": "Актуальный"}},
                }
                if source:
                    properties["Источник"] = {"select": {"name": source}}
                if report_type:
                    properties["Тип анализа"] = {"select": {"name": report_type}}

                await self._request("PATCH", f"pages/{page_id}", {"properties": properties})
                await self._append_blocks(page_id, blocks)

                logger.info(f"Notion: page updated — {page_url}")
                return page_url
            else:
                logger.info(f"Notion: creating new page for {start_date} — {end_date}")

                properties = {
                    "Name": {"title": [{"text": {"content": title}}]},
                    "Период начала": {"date": {"start": start_date}},
                    "Период конца": {"date": {"start": end_date}},
                    "Статус": {"select": {"name": "Актуальный"}},
                }
                if source:
                    properties["Источник"] = {"select": {"name": source}}
                if report_type:
                    properties["Тип анализа"] = {"select": {"name": report_type}}

                page_payload = {
                    "parent": {"database_id": self.database_id},
                    "properties": properties,
                    "children": blocks[:100],
                }

                result = await self._request("POST", "pages", page_payload)
                page_id = result["id"]
                page_url = result["url"]

                if len(blocks) > 100:
                    await self._append_blocks(page_id, blocks[100:])

                logger.info(f"Notion: page created — {page_url}")
                return page_url

        except Exception as e:
            logger.error(f"Notion sync failed: {e}")
            return None

    async def get_comments(self, page_id: str) -> list[dict]:
        """Fetch all comments on a Notion page (paginated).

        Returns list of {"id": ..., "text": "...", "created_time": "..."}.
        """
        if not self.token:
            return []

        comments: list[dict] = []
        start_cursor = None
        try:
            while True:
                endpoint = f"comments?block_id={page_id}&page_size=100"
                if start_cursor:
                    endpoint += f"&start_cursor={start_cursor}"
                result = await self._request("GET", endpoint)
                for c in result.get("results", []):
                    # Extract plain text from rich_text array
                    text_parts = []
                    for rt in c.get("rich_text", []):
                        text_parts.append(rt.get("plain_text", ""))
                    comments.append({
                        "id": c.get("id", ""),
                        "text": "".join(text_parts),
                        "created_time": c.get("created_time", ""),
                    })
                if not result.get("has_more"):
                    break
                start_cursor = result.get("next_cursor")
        except Exception as e:
            logger.warning(f"Failed to fetch comments for page {page_id}: {e}")
        return comments

    async def add_comment(self, page_id: str, comment: str) -> None:
        """Add a comment to a Notion page."""
        if not self.token:
            return

        try:
            await self._request("POST", "comments", {
                "parent": {"page_id": page_id},
                "rich_text": [
                    {"type": "text", "text": {"content": comment[:2000]}},
                ],
            })
            logger.info(f"Notion comment added to page {page_id}")
        except Exception as e:
            logger.warning(f"Notion comment failed: {e}")

    async def get_recent_feedback(self, days: int = 7) -> list[dict]:
        """Fetch comments from report pages created in the last N days.

        Returns list of {page_title, page_url, report_type, comments: [{text, created_time}]}.
        Only returns pages that actually have comments.
        """
        if not self.enabled:
            return []

        from datetime import datetime, timedelta

        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            result = await self._request("POST", f"databases/{self.database_id}/query", {
                "filter": {
                    "property": "Период начала",
                    "date": {"on_or_after": since},
                },
                "sorts": [{"property": "Период начала", "direction": "descending"}],
                "page_size": 20,
            })
        except Exception as e:
            logger.warning(f"Failed to query recent pages: {e}")
            return []

        feedback = []
        for page in result.get("results", []):
            page_id = page["id"]
            page_url = page.get("url", "")

            # Extract title
            title_prop = page.get("properties", {}).get("Name", {})
            title_parts = title_prop.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts)

            # Extract report type
            type_prop = page.get("properties", {}).get("Тип анализа", {})
            type_select = type_prop.get("select", {})
            report_type = type_select.get("name", "") if type_select else ""

            comments = await self.get_comments(page_id)
            if comments:
                feedback.append({
                    "page_title": title,
                    "page_url": page_url,
                    "report_type": report_type,
                    "comments": comments,
                })

        return feedback

    async def _find_existing_page(self, start_date: str, end_date: str, report_type: str = None) -> Optional[dict]:
        """Find page by period dates and optionally by report type."""
        conditions = [
            {"property": "Период начала", "date": {"equals": start_date}},
            {"property": "Период конца", "date": {"equals": end_date}},
        ]
        if report_type:
            conditions.append({"property": "Тип анализа", "select": {"equals": report_type}})
        payload = {
            "filter": {"and": conditions}
        }
        try:
            result = await self._request("POST", f"databases/{self.database_id}/query", payload)
            pages = result.get("results", [])
            return pages[0] if pages else None
        except Exception:
            # Select option may not exist yet — retry without report_type filter
            if report_type:
                logger.info(f"Notion: retrying search without report_type filter (option may not exist yet)")
                return await self._find_existing_page(start_date, end_date, report_type=None)
            raise

    async def _delete_page_content(self, page_id: str) -> None:
        """Delete all blocks from a page recursively (pagination)."""
        while True:
            result = await self._request("GET", f"blocks/{page_id}/children?page_size=100")
            blocks = result.get("results", [])
            if not blocks:
                break

            logger.info(f"Notion: deleting {len(blocks)} blocks from page {page_id}")
            for block in blocks:
                await self._request("DELETE", f"blocks/{block['id']}")

            if not result.get("has_more"):
                break

    async def _append_blocks(self, page_id: str, blocks: list) -> None:
        """Append blocks in batches of 100."""
        for i in range(0, len(blocks), 100):
            batch = blocks[i:i + 100]
            await self._request("PATCH", f"blocks/{page_id}/children", {"children": batch})
