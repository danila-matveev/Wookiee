"""Export meeting summary + transcript to Notion database "Записи встреч".

DB schema:
- Name (title)    — page title ("Встреча 12.05 18:30" or meeting.title)
- Date (date)     — meeting.started_at
- Person (people) — left empty (Notion people != Telegram users)
- Отдел (select)  — left empty
- Тип (select)    — left empty
- Summary (files), Full file (files) — left empty (we put everything in page body)

Idempotency: stores notion_page_id+notion_page_url back in telemost.meetings.
Re-export updates the existing page instead of creating a duplicate.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

import httpx

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.meetings_repo import build_transcript_text

logger = logging.getLogger(__name__)

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_HTTP_TIMEOUT = 30.0

# Hard limits enforced by Notion API.
_RICH_TEXT_LIMIT = 1900  # < 2000 to leave headroom
_BLOCKS_PER_REQUEST = 100


class NotionExportError(RuntimeError):
    """Raised when Notion API rejects the request or env is missing."""


def _env() -> tuple[str, str]:
    token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_MEETINGS_DB_ID")
    if not token or not db_id:
        raise NotionExportError(
            "NOTION_TOKEN or NOTION_MEETINGS_DB_ID missing in env"
        )
    return token, db_id


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": text[:_RICH_TEXT_LIMIT]}}
            ]
        },
    }


def _heading(text: str, level: int = 2) -> dict:
    htype = f"heading_{min(level, 3)}"
    return {
        "object": "block",
        "type": htype,
        htype: {
            "rich_text": [
                {"type": "text", "text": {"content": text[:_RICH_TEXT_LIMIT]}}
            ]
        },
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {"type": "text", "text": {"content": text[:_RICH_TEXT_LIMIT]}}
            ]
        },
    }


def _build_blocks(meeting: dict[str, Any]) -> list[dict]:
    """Convert meeting (summary + transcript) into Notion block list."""
    blocks: list[dict] = []
    summary = meeting.get("summary") or {}

    participants = summary.get("participants") or []
    if participants:
        blocks.append(_heading("Участники", level=2))
        blocks.append(_paragraph(", ".join(participants)))

    topics = summary.get("topics") or []
    if topics:
        blocks.append(_heading("Темы", level=2))
        for t in topics:
            title = t.get("title", "?")
            anchor = t.get("anchor") or ""
            blocks.append(_bullet(f"{title} {anchor}".strip()))

    decisions = summary.get("decisions") or []
    if decisions:
        blocks.append(_heading("Решения", level=2))
        for d in decisions:
            blocks.append(_bullet(d))

    tasks = summary.get("tasks") or []
    if tasks:
        blocks.append(_heading("Задачи", level=2))
        for t in tasks:
            assignee = t.get("assignee") or "—"
            what = t.get("what", "?")
            when = t.get("when")
            suffix = f" ({when})" if when else ""
            blocks.append(_bullet(f"{assignee} — {what}{suffix}"))
            context = t.get("context")
            if context:
                blocks.append(_bullet(f"Зачем: {context}"))
            conditions = t.get("conditions")
            if conditions:
                blocks.append(_bullet(f"Условия: {conditions}"))

    tags = meeting.get("tags") or []
    if tags:
        blocks.append(_heading("Теги", level=2))
        blocks.append(_paragraph(", ".join(tags)))

    paragraphs = meeting.get("processed_paragraphs") or []
    if paragraphs:
        blocks.append(_heading("Транскрипт", level=2))
        transcript = build_transcript_text(paragraphs)
        # Notion paragraph block has 2000-char rich_text limit, so chunk.
        for chunk_start in range(0, len(transcript), _RICH_TEXT_LIMIT):
            blocks.append(_paragraph(transcript[chunk_start:chunk_start + _RICH_TEXT_LIMIT]))

    if not blocks:
        blocks.append(_paragraph("(пустая запись)"))

    return blocks


def _page_title(meeting: dict[str, Any]) -> str:
    title = (meeting.get("title") or "").strip()
    started_at = meeting.get("started_at")
    when = started_at.strftime("%d.%m %H:%M") if started_at else ""
    if title:
        return f"{title} — {when}" if when else title
    return f"Встреча {when}" if when else "Встреча"


def _page_properties(meeting: dict[str, Any]) -> dict:
    props: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": _page_title(meeting)[:200]}}]},
    }
    started_at = meeting.get("started_at")
    if started_at:
        props["Date"] = {"date": {"start": started_at.date().isoformat()}}
    return props


async def _notion_request(
    method: str, endpoint: str, token: str, payload: dict | None = None,
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    url = f"{_NOTION_API_BASE}/{endpoint}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.request(method, url, headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error("Notion API %s %s: %s", method, endpoint, resp.text[:500])
            raise NotionExportError(f"Notion API {resp.status_code}: {resp.text[:200]}")
        return resp.json()


async def _append_blocks_paginated(page_id: str, token: str, blocks: list[dict]) -> None:
    for i in range(0, len(blocks), _BLOCKS_PER_REQUEST):
        batch = blocks[i:i + _BLOCKS_PER_REQUEST]
        await _notion_request(
            "PATCH", f"blocks/{page_id}/children", token, {"children": batch},
        )


async def _delete_existing_children(page_id: str, token: str) -> None:
    while True:
        result = await _notion_request(
            "GET", f"blocks/{page_id}/children?page_size=100", token,
        )
        children = result.get("results", [])
        if not children:
            break
        for child in children:
            await _notion_request("DELETE", f"blocks/{child['id']}", token)
        if not result.get("has_more"):
            break


async def export_meeting_to_notion(meeting_id: UUID) -> tuple[str, str]:
    """Create (or update if already exported) a Notion page for this meeting.

    Returns (page_id, page_url). Stores notion_page_id+url back in telemost.meetings
    so the next call reuses the same page.
    """
    token, db_id = _env()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, started_at, summary, tags, processed_paragraphs,
                   notion_page_id, notion_page_url
            FROM telemost.meetings WHERE id = $1
            """,
            meeting_id,
        )
    if not row:
        raise NotionExportError(f"meeting {meeting_id} not found")
    meeting = dict(row)
    import json as _json
    for k in ("summary", "processed_paragraphs"):
        if isinstance(meeting.get(k), str):
            meeting[k] = _json.loads(meeting[k])

    properties = _page_properties(meeting)
    blocks = _build_blocks(meeting)

    existing_id = meeting.get("notion_page_id")
    if existing_id:
        await _notion_request(
            "PATCH", f"pages/{existing_id}", token, {"properties": properties},
        )
        await _delete_existing_children(existing_id, token)
        await _append_blocks_paginated(existing_id, token, blocks)
        page_url = meeting.get("notion_page_url") or ""
        return existing_id, page_url

    created = await _notion_request(
        "POST", "pages", token,
        {"parent": {"database_id": db_id}, "properties": properties},
    )
    page_id = created["id"]
    page_url = created.get("url", "")
    await _append_blocks_paginated(page_id, token, blocks)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE telemost.meetings
            SET notion_page_id = $1, notion_page_url = $2
            WHERE id = $3
            """,
            page_id, page_url, meeting_id,
        )
    logger.info("Exported meeting %s to Notion: %s", meeting_id, page_url)
    return page_id, page_url
