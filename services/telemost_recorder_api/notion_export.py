"""Export meeting summary + transcript to Notion database "Записи встреч".

DB schema discovered at runtime (so column rename/retype on the Notion side
doesn't break export). Current columns we populate when present:
- Name (title)         — _page_title(meeting)
- Date (date)          — meeting.started_at
- Тип (select|multi)   — _pick_notion_type() against meeting.title
- Отдел (select|multi) — _pick_notion_department() against meeting.tags
- Теги (multi_select)  — meeting.tags (canonical LLM-thematic list)

Page body uses toggleable heading_2 per section so long transcripts and
task lists don't push everything else off-screen.

Idempotency: stores notion_page_id+notion_page_url back in telemost.meetings.
Re-export updates properties + replaces body via marker-divider strategy.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

import httpx

from services.telemost_recorder_api.config import NOTION_TIMEOUT_SECONDS
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.meetings_repo import build_transcript_text

logger = logging.getLogger(__name__)

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_NOTION_RETRIES = 4
_NOTION_BACKOFF_BASE = 1.5

# Hard limits enforced by Notion API.
_RICH_TEXT_LIMIT = 1900  # < 2000 to leave headroom
_BLOCKS_PER_REQUEST = 100
# Notion rejects a block-create call when a single parent has > 100 children.
# We cap inline children per toggleable heading and split overflow into
# additional toggles ("Транскрипт (часть 2)" etc.). Keep below 100 for headroom.
_MAX_INLINE_CHILDREN = 90
# Notion multi_select option names cap at 100 chars.
_TAG_LEN_LIMIT = 100


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


def _toggle_heading(text: str, children: list[dict], level: int = 2) -> dict:
    """Toggleable heading block with inline children.

    Notion supports `is_toggleable: true` on heading_1/2/3 and treats the
    block's `children` array as the collapsed body. One API request handles
    parent+children up to depth=2; caller must cap children at
    _MAX_INLINE_CHILDREN and split overflow into a sibling toggle.
    """
    htype = f"heading_{min(level, 3)}"
    return {
        "object": "block",
        "type": htype,
        htype: {
            "rich_text": [
                {"type": "text", "text": {"content": text[:_RICH_TEXT_LIMIT]}}
            ],
            "is_toggleable": True,
            "children": children,
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


def _task_bullet(t: dict[str, Any]) -> dict:
    """One bullet per task — assignee bold, then what + optional when,
    with `Зачем:` / `Условия:` as soft line breaks in the same rich_text.
    Earlier version emitted three sibling bullets per task which read like
    a glitch (no visual nesting).
    """
    assignee = t.get("assignee") or "—"
    what = t.get("what") or "?"
    when = t.get("when")
    context = t.get("context")
    conditions = t.get("conditions")

    rich: list[dict] = [
        {
            "type": "text",
            "text": {"content": str(assignee)[:_RICH_TEXT_LIMIT]},
            "annotations": {"bold": True},
        },
        {"type": "text", "text": {"content": f" — {what}"[:_RICH_TEXT_LIMIT]}},
    ]
    if when:
        rich.append({
            "type": "text",
            "text": {"content": f" ({when})"[:_RICH_TEXT_LIMIT]},
            "annotations": {"italic": True},
        })
    if context:
        rich.append({
            "type": "text",
            "text": {"content": f"\nЗачем: {context}"[:_RICH_TEXT_LIMIT]},
            "annotations": {"color": "gray"},
        })
    if conditions:
        rich.append({
            "type": "text",
            "text": {"content": f"\nУсловия: {conditions}"[:_RICH_TEXT_LIMIT]},
            "annotations": {"color": "gray"},
        })

    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich},
    }


def _section_blocks(heading_text: str, children: list[dict]) -> list[dict]:
    """Wrap children in a toggleable heading; split if more than the
    inline-children cap so we never hit Notion's 100-children-per-parent.
    """
    if not children:
        return []
    if len(children) <= _MAX_INLINE_CHILDREN:
        return [_toggle_heading(heading_text, children, level=2)]
    out: list[dict] = []
    part = 1
    for i in range(0, len(children), _MAX_INLINE_CHILDREN):
        chunk = children[i:i + _MAX_INLINE_CHILDREN]
        suffix = "" if (part == 1 and len(children) <= _MAX_INLINE_CHILDREN) else f" (часть {part})"
        out.append(_toggle_heading(f"{heading_text}{suffix}", chunk, level=2))
        part += 1
    return out


def _build_blocks(meeting: dict[str, Any], db_has_tags_property: bool = False) -> list[dict]:
    """Convert meeting (summary + transcript) into Notion block list.

    Each section is a toggleable heading_2 with its content as inline
    children, so the user can collapse Транскрипт / Задачи independently.
    Skip the in-body "Теги" section when the DB has a multi_select Tags
    column — tags then live on the page property instead.
    """
    blocks: list[dict] = []
    summary = meeting.get("summary") or {}

    participants = summary.get("participants") or []
    if participants:
        blocks.extend(_section_blocks(
            "Участники", [_paragraph(", ".join(str(p) for p in participants))]
        ))

    topics = summary.get("topics") or []
    if topics:
        topic_bullets: list[dict] = []
        for t in topics:
            title = t.get("title", "?")
            anchor = t.get("anchor") or ""
            topic_bullets.append(_bullet(f"{title} {anchor}".strip()))
        blocks.extend(_section_blocks("Темы", topic_bullets))

    decisions = summary.get("decisions") or []
    if decisions:
        blocks.extend(_section_blocks("Решения", [_bullet(d) for d in decisions]))

    tasks = summary.get("tasks") or []
    if tasks:
        blocks.extend(_section_blocks("Задачи", [_task_bullet(t) for t in tasks]))

    if not db_has_tags_property:
        combined_tags = _combined_tags(meeting)
        if combined_tags:
            blocks.extend(_section_blocks(
                "Теги", [_paragraph(", ".join(combined_tags))]
            ))

    paragraphs = meeting.get("processed_paragraphs") or []
    if paragraphs:
        transcript = build_transcript_text(paragraphs)
        chunks: list[dict] = []
        for chunk_start in range(0, len(transcript), _RICH_TEXT_LIMIT):
            chunks.append(_paragraph(transcript[chunk_start:chunk_start + _RICH_TEXT_LIMIT]))
        blocks.extend(_section_blocks("Транскрипт", chunks))

    if not blocks:
        blocks.append(_paragraph("(пустая запись)"))

    return blocks


def _combined_tags(meeting: dict[str, Any]) -> list[str]:
    """Объединить тематические LLM-теги, название встречи и имена участников.

    Дедуплицируем без учёта регистра, сохраняем порядок: сначала название
    (самая сильная метка), затем участники, затем тематические теги.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(tag: str) -> None:
        tag = tag.strip()
        if not tag:
            return
        key = tag.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(tag)

    title = (meeting.get("title") or "").strip()
    if title:
        _add(title)

    summary = meeting.get("summary") or {}
    for participant in summary.get("participants") or []:
        _add(str(participant))

    for tag in meeting.get("tags") or []:
        _add(str(tag))

    return out


def _page_title(meeting: dict[str, Any]) -> str:
    # Prefer LLM-generated summary.title (reflects content); fall through to
    # Bitrix-enriched meeting.title (can be a generic "Dayli" from
    # time-proximity match); fall back to "Встреча".
    summary = meeting.get("summary") or {}
    llm_title = (summary.get("title") or "").strip()
    title = llm_title or (meeting.get("title") or "").strip()
    started_at = meeting.get("started_at")
    when = started_at.strftime("%d.%m %H:%M") if started_at else ""
    if title:
        return f"{title} — {when}" if when else title
    return f"Встреча {when}" if when else "Встреча"


# Маппинг названия встречи (с поправкой на ASR-варианты) на select "Тип"
# в Notion DB "Записи встреч". Опции этого select зафиксированы вручную
# (через Notion UI), и если LLM/Bitrix выдадут что-то не из этого списка —
# поле останется пустым, чтобы не плодить мусорные опции автогенерацией.
_NOTION_TYPE_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("dayli", "daily", "дейли", "дэйли"), "Dayli"),
    (("1-1", "1 на 1", "one-on-one", "one on one", "1-n-1"), "1-n-1"),
    (("планерк", "планёрк"), "Планерка"),
    (("продукт",), "Отдел продукта"),
    (("контент",), "Отдел контента"),
    (("маркетинг", "реклам"), "Отдел маркетинга"),
)

# Маппинг тематических LLM-тегов на select "Отдел". Source of truth — список
# тегов canonical, который LLM получает в промте.
_NOTION_DEPARTMENT_BY_TAG: dict[str, str] = {
    "логистика": "Логистика",
    "поставки": "Логистика",
    "маркетплейс": "Маркетплейсы",
    "финансы": "Финансы",
    "отчётность": "Финансы",
    "продажи": "Продаж и маркетинга",
    "маркетинг": "Продаж и маркетинга",
    "реклама": "Продаж и маркетинга",
    "конкуренты": "Продаж и маркетинга",
    "продукт": "Продукт",
    "ассортимент": "Продукт",
    "бренд": "Продукт",
    "разработка": "Продукт",
    "контент": "SMM и контента",
    "креативы": "SMM и контента",
}


def _pick_notion_type(meeting: dict[str, Any]) -> str | None:
    """Сматчить название встречи на опцию select 'Тип' в Notion."""
    title = (meeting.get("title") or "").lower()
    if not title:
        return None
    for needles, option in _NOTION_TYPE_KEYWORDS:
        if any(n in title for n in needles):
            return option
    return None


def _pick_notion_department(meeting: dict[str, Any]) -> str | None:
    """Сматчить тематические теги встречи на опцию select 'Отдел'."""
    tags = [str(t).lower().strip() for t in (meeting.get("tags") or [])]
    if not tags:
        return None
    # Order: walk through canonical mapping (predictable), pick first matching tag.
    for tag in tags:
        dep = _NOTION_DEPARTMENT_BY_TAG.get(tag)
        if dep:
            return dep
    return None


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen or not item:
            continue
        seen.add(key)
        out.append(item)
    return out


def _select_value(schema_type: str | None, name: str) -> dict | None:
    """Build a property value compatible with whatever type the column is
    declared as in Notion. Returns None if column doesn't exist."""
    if schema_type == "select":
        return {"select": {"name": name}}
    if schema_type == "multi_select":
        return {"multi_select": [{"name": name[:_TAG_LEN_LIMIT]}]}
    return None


# Default schema used when the caller didn't fetch real one from Notion
# (e.g. unit tests). Matches the columns we always assumed existed prior to
# schema-discovery and excludes "Теги" so legacy body section still renders.
_DEFAULT_SCHEMA: dict[str, str] = {
    "Name": "title",
    "Date": "date",
    "Тип": "select",
    "Отдел": "select",
}


def _page_properties(
    meeting: dict[str, Any], schema: dict[str, str] | None = None,
) -> dict:
    """Build Notion property payload from current DB schema.

    Skips columns that don't exist (or have unexpected types) instead of
    rejecting the whole page — that keeps export resilient to manual schema
    edits in the Notion UI.
    """
    if schema is None:
        schema = _DEFAULT_SCHEMA
    props: dict[str, Any] = {}

    if schema.get("Name") == "title":
        props["Name"] = {"title": [{"text": {"content": _page_title(meeting)[:200]}}]}

    started_at = meeting.get("started_at")
    if started_at and schema.get("Date") == "date":
        props["Date"] = {"date": {"start": started_at.date().isoformat()}}

    note_type = _pick_notion_type(meeting)
    if note_type:
        value = _select_value(schema.get("Тип"), note_type)
        if value:
            props["Тип"] = value

    department = _pick_notion_department(meeting)
    if department:
        value = _select_value(schema.get("Отдел"), department)
        if value:
            props["Отдел"] = value

    if schema.get("Теги") == "multi_select":
        raw_tags = [str(t).strip() for t in (meeting.get("tags") or []) if str(t).strip()]
        tags = _dedup_preserve_order(raw_tags)
        if tags:
            props["Теги"] = {
                "multi_select": [{"name": t[:_TAG_LEN_LIMIT]} for t in tags]
            }

    return props


async def _fetch_db_schema(token: str, db_id: str) -> dict[str, str]:
    """Return {property_name: property_type} for the meetings DB.

    Single GET per export call — small payload, no caching across calls
    because we want schema edits to land without restarting the API.
    """
    data = await _notion_request("GET", f"databases/{db_id}", token)
    return {
        name: (prop or {}).get("type", "")
        for name, prop in (data.get("properties") or {}).items()
    }


async def _notion_request(
    method: str, endpoint: str, token: str, payload: dict | None = None,
) -> dict:
    """Call Notion API with retry on 429/5xx. Respects Retry-After header on 429."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    url = f"{_NOTION_API_BASE}/{endpoint}"
    last_error: str | None = None
    for attempt in range(_NOTION_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=NOTION_TIMEOUT_SECONDS) as client:
                resp = await client.request(method, url, headers=headers, json=payload)
        except httpx.HTTPError as e:
            last_error = f"network: {e}"
            logger.warning(
                "Notion %s %s network error attempt %d/%d: %s",
                method, endpoint, attempt + 1, _NOTION_RETRIES, e,
            )
            await asyncio.sleep(_NOTION_BACKOFF_BASE * (2 ** attempt))
            continue
        if resp.status_code < 400:
            return resp.json()
        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = float(resp.headers.get("Retry-After", _NOTION_BACKOFF_BASE * (2 ** attempt)))
            last_error = f"{resp.status_code}: {resp.text[:200]}"
            logger.warning(
                "Notion %s %s -> %s, retrying in %.1fs (attempt %d/%d)",
                method, endpoint, resp.status_code, retry_after, attempt + 1, _NOTION_RETRIES,
            )
            await asyncio.sleep(retry_after)
            continue
        logger.error("Notion API %s %s: %s", method, endpoint, resp.text[:500])
        raise NotionExportError(f"Notion API {resp.status_code}: {resp.text[:200]}")
    raise NotionExportError(f"Notion API unavailable after retries: {last_error}")


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


def _block_text(block: dict) -> str:
    btype = block.get("type")
    if btype != "paragraph":
        return ""
    rt = block.get("paragraph", {}).get("rich_text") or []
    parts: list[str] = []
    for piece in rt:
        text = piece.get("text") or {}
        content = text.get("content") or piece.get("plain_text") or ""
        parts.append(content)
    return "".join(parts)


async def _delete_until_marker(page_id: str, marker_text: str, token: str) -> None:
    """Delete every block from the top of the page up to and including
    the one whose text matches marker_text.

    Defensive: collect block ids into a buffer first. Only delete after
    the marker is found, so a missing marker can't wipe freshly appended
    content (e.g. if marker-append silently lost its block on Notion's side).
    """
    to_delete: list[str] = []
    cursor: str | None = None
    found = False
    while True:
        endpoint = f"blocks/{page_id}/children?page_size=100"
        if cursor:
            endpoint += f"&start_cursor={cursor}"
        result = await _notion_request("GET", endpoint, token)
        children = result.get("results", []) or []
        for child in children:
            to_delete.append(child["id"])
            if _block_text(child) == marker_text:
                found = True
                break
        if found:
            break
        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")

    if not found:
        logger.warning(
            "Marker %r not found on page %s; skipping cleanup to avoid wiping content",
            marker_text, page_id,
        )
        return

    for block_id in to_delete:
        await _notion_request("DELETE", f"blocks/{block_id}", token)


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

    schema = await _fetch_db_schema(token, db_id)
    properties = _page_properties(meeting, schema)
    db_has_tags_property = schema.get("Теги") == "multi_select"
    blocks = _build_blocks(meeting, db_has_tags_property=db_has_tags_property)

    existing_id = meeting.get("notion_page_id")
    if existing_id:
        await _notion_request(
            "PATCH", f"pages/{existing_id}", token, {"properties": properties},
        )
        marker_text = f"<<<wookiee-marker-{meeting_id}>>>"
        marker_block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": marker_text}}]
            },
        }
        await _notion_request(
            "PATCH", f"blocks/{existing_id}/children", token,
            {"children": [marker_block]},
        )
        await _append_blocks_paginated(existing_id, token, blocks)
        await _delete_until_marker(existing_id, marker_text, token)
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
