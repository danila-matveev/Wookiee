"""notion_export — block formatting, env handling, HTTP errors."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.notion_export import (
    NotionExportError,
    _build_blocks,
    _page_properties,
    _page_title,
    export_meeting_to_notion,
)


def _meeting(**overrides):
    base = {
        "id": uuid4(),
        "title": "Daily standup",
        "started_at": datetime(2026, 5, 12, 14, 30),
        "summary": {
            "participants": ["Данила", "Алина"],
            "topics": [{"title": "Wendy redesign", "anchor": "[02:15]"}],
            "decisions": ["Запустить тест креативов"],
            "tasks": [
                {"assignee": "Алина", "what": "ТЗ на упаковку Moon", "when": "до пятницы"},
            ],
        },
        "tags": ["продукт", "креативы"],
        "processed_paragraphs": [
            {"start_ms": 0, "speaker": "Данила", "text": "Привет команде"},
        ],
        "notion_page_id": None,
        "notion_page_url": None,
    }
    base.update(overrides)
    return base


def test_page_title_combines_title_and_date():
    m = _meeting()
    assert _page_title(m) == "Daily standup — 12.05 14:30"


def test_page_title_falls_back_to_date_only():
    m = _meeting(title=None)
    assert _page_title(m) == "Встреча 12.05 14:30"


def test_page_title_falls_back_to_generic_when_nothing():
    m = _meeting(title=None, started_at=None)
    assert _page_title(m) == "Встреча"


def test_page_properties_includes_date_iso():
    m = _meeting()
    props = _page_properties(m)
    assert props["Name"]["title"][0]["text"]["content"].startswith("Daily standup")
    assert props["Date"]["date"]["start"] == "2026-05-12"


def test_page_properties_omits_date_when_missing():
    m = _meeting(started_at=None)
    props = _page_properties(m)
    assert "Date" not in props


def test_build_blocks_contains_all_sections():
    blocks = _build_blocks(_meeting())
    headings = [
        b[b["type"]]["rich_text"][0]["text"]["content"]
        for b in blocks if b["type"].startswith("heading_")
    ]
    assert "Участники" in headings
    assert "Темы" in headings
    assert "Решения" in headings
    assert "Задачи" in headings
    assert "Теги" in headings
    assert "Транскрипт" in headings


def test_build_blocks_skips_empty_sections():
    m = _meeting(summary={"participants": [], "topics": [], "decisions": [], "tasks": []},
                 tags=[], processed_paragraphs=[])
    blocks = _build_blocks(m)
    # Only fallback "(пустая запись)" paragraph
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"


def test_build_blocks_chunks_long_transcript():
    long_text = "А" * 5000
    m = _meeting(processed_paragraphs=[
        {"start_ms": 0, "speaker": "Данила", "text": long_text},
    ])
    blocks = _build_blocks(m)
    transcript_paragraphs = [
        b for b in blocks
        if b["type"] == "paragraph"
        and "А" in b["paragraph"]["rich_text"][0]["text"]["content"]
    ]
    # 5000-char "А" inside [00:00] Данила: ... → builds to >5000 chars,
    # must be split into multiple paragraph blocks (<1900 chars each).
    assert len(transcript_paragraphs) >= 3
    for p in transcript_paragraphs:
        assert len(p["paragraph"]["rich_text"][0]["text"]["content"]) <= 1900


@pytest.mark.asyncio
async def test_export_raises_when_env_missing(monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_MEETINGS_DB_ID", raising=False)
    with pytest.raises(NotionExportError):
        await export_meeting_to_notion(uuid4())


@pytest.mark.asyncio
async def test_export_creates_page_and_persists_id(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_MEETINGS_DB_ID", "db_id")

    m = _meeting()
    fetched_row = MagicMock()
    fetched_row.__iter__ = lambda self: iter(m.items())
    fetched_row.items = lambda: m.items()
    fetched_row.keys = lambda: m.keys()
    fetched_row.__getitem__ = lambda self, k: m[k]
    fetched_row.get = m.get

    # asyncpg.Record is dict-like; mock with a real dict wrapped to support dict(row).
    class _RowDict(dict):
        pass
    row = _RowDict(m)

    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.execute = AsyncMock(return_value=None)

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)

    captured: list[tuple[str, str, dict | None]] = []

    async def fake_request(method, endpoint, token, payload=None):
        captured.append((method, endpoint, payload))
        if method == "POST" and endpoint == "pages":
            return {"id": "page_xyz", "url": "https://www.notion.so/page-xyz"}
        return {"results": [], "has_more": False}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=fake_request,
    ):
        page_id, page_url = await export_meeting_to_notion(m["id"])

    assert page_id == "page_xyz"
    assert page_url == "https://www.notion.so/page-xyz"
    # 1 POST pages + at least 1 PATCH children
    methods = [(m_, e_) for m_, e_, _ in captured]
    assert ("POST", "pages") in methods
    assert any(m_ == "PATCH" and e_.startswith("blocks/page_xyz/children") for m_, e_ in methods)
    # UPDATE should have been called to persist notion_page_id
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    assert "notion_page_id" in args[0]
    assert args[1] == "page_xyz"


@pytest.mark.asyncio
async def test_export_updates_existing_page_when_id_present(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_MEETINGS_DB_ID", "db_id")

    m = _meeting(notion_page_id="old_page", notion_page_url="https://www.notion.so/old")

    class _RowDict(dict):
        pass
    row = _RowDict(m)

    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.execute = AsyncMock(return_value=None)

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)

    captured: list[tuple[str, str]] = []

    async def fake_request(method, endpoint, token, payload=None):
        captured.append((method, endpoint))
        return {"results": [], "has_more": False}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=fake_request,
    ):
        page_id, page_url = await export_meeting_to_notion(m["id"])

    assert page_id == "old_page"
    assert page_url == "https://www.notion.so/old"
    # Must NOT create new page
    assert ("POST", "pages") not in captured
    # Must PATCH page properties + (GET children + PATCH new children)
    assert ("PATCH", "pages/old_page") in captured
    # No UPDATE on the meeting row (page_id stays the same)
    conn.execute.assert_not_awaited()
