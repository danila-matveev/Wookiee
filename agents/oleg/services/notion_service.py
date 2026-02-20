"""
Async Notion Service — синхронизация отчётов и комментариев.

Async-обёртка над логикой из scripts/notion_sync.py.
"""
import json
import logging
import re
from typing import Optional

import httpx

from agents.oleg.config import NOTION_TOKEN, NOTION_DATABASE_ID

logger = logging.getLogger(__name__)

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionService:
    """Async Notion API service for report sync and comments."""

    def __init__(self, token: str = "", database_id: str = ""):
        self.token = token or NOTION_TOKEN
        self.database_id = database_id or NOTION_DATABASE_ID

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
        source: str = "Telegram Bot",
    ) -> Optional[str]:
        """
        Sync report to Notion. Returns page URL or None on failure.

        If a page with matching period exists — updates it.
        If not — creates a new page.
        """
        if not self.enabled:
            logger.warning("Notion not configured, skipping sync")
            return None

        try:
            title = f"Аналитика {start_date.replace('-', '.')} — {end_date.replace('-', '.')}"
            
            # Remove empty sections to avoid orphan headers in Notion
            report_md = _remove_empty_sections(report_md)
            blocks = md_to_notion_blocks(report_md)

            existing = await self._find_existing_page(start_date, end_date)

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

    async def _find_existing_page(self, start_date: str, end_date: str) -> Optional[dict]:
        """Find page by period dates."""
        payload = {
            "filter": {
                "and": [
                    {"property": "Период начала", "date": {"equals": start_date}},
                    {"property": "Период конца", "date": {"equals": end_date}},
                ]
            }
        }
        result = await self._request("POST", f"databases/{self.database_id}/query", payload)
        pages = result.get("results", [])
        return pages[0] if pages else None

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


# =============================================================================
# MARKDOWN → NOTION BLOCKS (from scripts/notion_sync.py)
# =============================================================================

def _parse_inline(text):
    """Parse bold markers into Notion rich_text array."""
    parts = []
    segments = re.split(r'(\*\*[^*]+\*\*)', text)
    for seg in segments:
        if seg.startswith('**') and seg.endswith('**'):
            parts.append({
                "type": "text",
                "text": {"content": seg[2:-2]},
                "annotations": {
                    "bold": True, "italic": False, "strikethrough": False,
                    "underline": False, "code": False, "color": "default",
                },
            })
        elif seg:
            parts.append({"type": "text", "text": {"content": seg}})
    return parts if parts else [{"type": "text", "text": {"content": text}}]


def _remove_empty_sections(md_text: str) -> str:
    """
    Removes headers that have no content before the next header of same or higher level.
    """
    lines = md_text.split('\n')
    parsed = []
    
    # 1. Parse lines
    for line in lines:
        stripped = line.strip()
        if not stripped:
            parsed.append({'type': 'empty', 'text': line})
            continue
            
        match = re.match(r'^(#+)\s+(.+)', stripped)
        if match:
            level = len(match.group(1))
            parsed.append({'type': 'header', 'level': level, 'text': line})
        else:
            parsed.append({'type': 'content', 'text': line})
            
    # 2. Identify empty headers
    indices_to_remove = set()
    
    for i in range(len(parsed)):
        item = parsed[i]
        if item['type'] == 'header':
            has_content = False
            for j in range(i + 1, len(parsed)):
                next_item = parsed[j]
                
                # Found content -> keep header
                if next_item['type'] == 'content':
                    has_content = True
                    break
                
                # Found another header
                if next_item['type'] == 'header':
                    # If same or higher level (H2 after H3, H3 after H3) -> stop, current header is empty
                    if next_item['level'] <= item['level']:
                        break
                    # If deeper header (H4 after H3) -> continue looking for its content
            
            if not has_content:
                indices_to_remove.add(i)
                
    # 3. Rebuild text
    result_lines = []
    for i in range(len(parsed)):
        if i not in indices_to_remove:
            result_lines.append(parsed[i]['text'])
            
    return '\n'.join(result_lines)


def md_to_notion_blocks(md_text: str) -> list:
    """Convert Markdown report to Notion block array."""
    blocks = []
    lines = md_text.split('\n')
    i = 0
    table_rows = []
    in_table = False
    in_code_block = False
    code_content = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        num_cols = max(len(r) for r in table_rows)
        notion_rows = []
        for row in table_rows:
            while len(row) < num_cols:
                row.append('')
            cells_rt = [
                [{"type": "text", "text": {"content": cell.replace('**', '')[:2000]}}]
                for cell in row[:num_cols]
            ]
            notion_rows.append({
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": cells_rt},
            })
        blocks.append({
            "object": "block",
            "type": "table",
            "table": {
                "table_width": num_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": notion_rows,
            },
        })
        table_rows = []

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": '\n'.join(code_content)[:2000]}}],
                        "language": "plain text",
                    },
                })
                code_content = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_content.append(line)
            i += 1
            continue

        # Tables
        if '|' in line and line.strip().startswith('|'):
            stripped = line.strip()
            if re.match(r'^[\|\-\s:]+$', stripped):
                i += 1
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)

            next_is_table = (
                i + 1 < len(lines)
                and lines[i + 1].strip().startswith('|')
                and '|' in lines[i + 1]
            )
            if not next_is_table:
                flush_table()
                in_table = False
            i += 1
            continue

        # Headings (support # to ######, mapping to h1-h3)
        header_match = re.match(r'^(#+)\s+(.+)', line.strip())
        if header_match:
            level = len(header_match.group(1))
            content = header_match.group(2).strip()
            # Notion only supports heading_1, heading_2, heading_3
            notion_level = min(level, 3)
            block_type = f"heading_{notion_level}"
            
            blocks.append({
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                },
            })
            i += 1
            continue

        # Divider
        if line.strip() == '---':
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # Bullet list
        if line.strip().startswith('- '):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _parse_inline(line.strip()[2:])},
            })
            i += 1
            continue

        # Numbered list
        if re.match(r'^\d+\.\s', line.strip()):
            text = re.sub(r'^\d+\.\s*', '', line.strip())
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _parse_inline(text)},
            })
            i += 1
            continue

        # Empty line
        if line.strip() == '':
            i += 1
            continue

        # Paragraph
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _parse_inline(line)},
        })
        i += 1

    return blocks
