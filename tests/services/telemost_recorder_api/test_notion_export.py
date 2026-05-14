"""notion_export — block formatting, env handling, HTTP errors."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.notion_export import (
    NotionExportError,
    _build_blocks,
    _combined_tags,
    _delete_until_marker,
    _page_properties,
    _page_title,
    _pick_notion_department,
    _pick_notion_type,
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


def test_pick_notion_type_matches_dayli_variants():
    assert _pick_notion_type({"title": "Dayli"}) == "Dayli"
    assert _pick_notion_type({"title": "ДЕЙЛИ команды"}) == "Dayli"
    assert _pick_notion_type({"title": "Daily standup"}) == "Dayli"


def test_pick_notion_type_matches_other_options():
    assert _pick_notion_type({"title": "1-1 с Алиной"}) == "1-n-1"
    assert _pick_notion_type({"title": "Планёрка продаж"}) == "Планерка"
    assert _pick_notion_type({"title": "Обсуждение продуктовой стратегии"}) == "Отдел продукта"


def test_pick_notion_type_returns_none_when_no_match():
    assert _pick_notion_type({"title": ""}) is None
    assert _pick_notion_type({"title": "Просто звонок"}) is None


def test_pick_notion_department_maps_tags():
    assert _pick_notion_department({"tags": ["логистика"]}) == "Логистика"
    assert _pick_notion_department({"tags": ["продажи", "креативы"]}) == "Продаж и маркетинга"
    assert _pick_notion_department({"tags": ["продукт"]}) == "Продукт"
    assert _pick_notion_department({"tags": ["контент"]}) == "SMM и контента"
    assert _pick_notion_department({"tags": []}) is None
    assert _pick_notion_department({"tags": ["прочее"]}) is None


def test_page_properties_includes_notion_select_when_match():
    """Свойства Тип и Отдел в Notion-странице должны заполняться, а не оставаться Empty."""
    props = _page_properties({
        "title": "Dayli команды",
        "started_at": None,
        "tags": ["продукт", "разработка"],
    })
    assert props["Тип"]["select"]["name"] == "Dayli"
    assert props["Отдел"]["select"]["name"] == "Продукт"


def test_page_properties_omits_select_when_no_match():
    """Если совпадений нет — не плодим мусорные опции, оставляем Empty."""
    props = _page_properties({
        "title": "Какая-то встреча",
        "started_at": None,
        "tags": ["прочее"],
    })
    assert "Тип" not in props
    assert "Отдел" not in props


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


def test_combined_tags_merges_title_participants_topical():
    """Title + участники + LLM-теги в одной коллекции для Notion-поиска."""
    tags = _combined_tags(_meeting())
    # Title первым (самая сильная метка)
    assert tags[0] == "Daily standup"
    # Участники
    assert "Данила" in tags
    assert "Алина" in tags
    # Тематические LLM-теги
    assert "продукт" in tags
    assert "креативы" in tags


def test_combined_tags_dedupes_case_insensitive():
    """Если LLM вернул 'Алина' (имя совпадает с участником) — не дублируем."""
    m = _meeting(
        title="алина", tags=["Алина", "АЛИНА", "продукт"],
        summary={"participants": ["Алина"], "topics": [], "decisions": [], "tasks": []},
    )
    tags = _combined_tags(m)
    # Один "алина" (нижнего регистра пришёл из title), потом "продукт"
    lower = [t.lower() for t in tags]
    assert lower.count("алина") == 1
    assert "продукт" in tags


def test_combined_tags_works_without_title():
    tags = _combined_tags(_meeting(title=None))
    assert "Данила" in tags
    assert "продукт" in tags


def test_build_blocks_tags_section_uses_combined_tags():
    blocks = _build_blocks(_meeting())
    # Тэги-секция теперь — toggleable heading_2 с inline children.
    tag_heading = next(
        b for b in blocks
        if b["type"].startswith("heading_")
        and b[b["type"]]["rich_text"][0]["text"]["content"] == "Теги"
    )
    htype = tag_heading["type"]
    children = tag_heading[htype].get("children") or []
    assert children, "Tags toggle must have an inline paragraph child"
    tag_paragraph = children[0]["paragraph"]["rich_text"][0]["text"]["content"]
    assert "Daily standup" in tag_paragraph
    assert "Алина" in tag_paragraph
    assert "продукт" in tag_paragraph


def test_build_blocks_skips_empty_sections():
    m = _meeting(
        title=None,
        summary={"participants": [], "topics": [], "decisions": [], "tasks": []},
        tags=[],
        processed_paragraphs=[],
    )
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
    # Transcript paragraphs now live as children of a toggleable heading_2.
    def _walk(bs):
        for b in bs:
            yield b
            btype = b.get("type", "")
            inner = b.get(btype) or {}
            for child in inner.get("children") or []:
                yield from _walk([child])
    transcript_paragraphs = [
        b for b in _walk(blocks)
        if b.get("type") == "paragraph"
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


def _marker_text_for(meeting_id) -> str:
    return f"<<<wookiee-marker-{meeting_id}>>>"


def _block_marker_text(block: dict) -> str:
    btype = block.get("type")
    if btype != "paragraph":
        return ""
    rt = block.get("paragraph", {}).get("rich_text") or []
    if not rt:
        return ""
    return rt[0].get("text", {}).get("content", "")


def _patch_pool(meeting: dict) -> MagicMock:
    class _RowDict(dict):
        pass
    row = _RowDict(meeting)

    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.execute = AsyncMock(return_value=None)

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


@pytest.mark.asyncio
async def test_reexport_inserts_marker_before_new_content(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_MEETINGS_DB_ID", "db_id")

    m = _meeting(notion_page_id="page_a", notion_page_url="https://www.notion.so/a")
    pool = _patch_pool(m)
    marker_text = _marker_text_for(m["id"])

    calls: list[tuple[str, str, dict | None]] = []

    async def fake_request(method, endpoint, token, payload=None):
        calls.append((method, endpoint, payload))
        if method == "GET":
            return {"results": [], "has_more": False}
        return {}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=fake_request,
    ):
        await export_meeting_to_notion(m["id"])

    patch_children = [
        (i, ep, payload) for i, (method, ep, payload) in enumerate(calls)
        if method == "PATCH" and ep == "blocks/page_a/children"
    ]
    assert len(patch_children) >= 2, "expected marker append + content append(s)"

    first_idx, _, first_payload = patch_children[0]
    first_children = first_payload["children"]
    assert len(first_children) == 1
    assert _block_marker_text(first_children[0]) == marker_text

    second_idx, _, second_payload = patch_children[1]
    assert second_idx > first_idx
    second_children = second_payload["children"]
    # Регулярные блоки — должен быть heading_2 "Участники" среди них.
    headings = [
        b[b["type"]]["rich_text"][0]["text"]["content"]
        for b in second_children if b.get("type", "").startswith("heading_")
    ]
    assert "Участники" in headings
    # И ни в одном из регулярных блоков не должно быть маркера.
    assert not any(_block_marker_text(b) == marker_text for b in second_children)

    pages_patch_idx = next(
        i for i, (method, ep, _) in enumerate(calls)
        if method == "PATCH" and ep == "pages/page_a"
    )
    assert pages_patch_idx < first_idx


@pytest.mark.asyncio
async def test_reexport_deletes_until_marker_on_success(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_MEETINGS_DB_ID", "db_id")

    m = _meeting(notion_page_id="page_b", notion_page_url="https://www.notion.so/b")
    pool = _patch_pool(m)
    marker_text = _marker_text_for(m["id"])

    # Симулируем состояние страницы после append:
    # старые блоки -> маркер -> новые блоки.
    old_block_1 = {"id": "old_1", "type": "heading_2",
                   "heading_2": {"rich_text": [{"text": {"content": "Старое"}}]}}
    old_block_2 = {"id": "old_2", "type": "paragraph",
                   "paragraph": {"rich_text": [{"text": {"content": "stale"}}]}}
    marker_block = {"id": "marker_id", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": marker_text}}]}}
    new_block = {"id": "new_1", "type": "paragraph",
                 "paragraph": {"rich_text": [{"text": {"content": "fresh"}}]}}

    calls: list[tuple[str, str]] = []

    async def fake_request(method, endpoint, token, payload=None):
        calls.append((method, endpoint))
        if method == "GET" and endpoint.startswith("blocks/page_b/children"):
            return {
                "results": [old_block_1, old_block_2, marker_block, new_block],
                "has_more": False,
            }
        return {}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=fake_request,
    ):
        await export_meeting_to_notion(m["id"])

    deletes = [ep for method, ep in calls if method == "DELETE"]
    assert "blocks/old_1" in deletes
    assert "blocks/old_2" in deletes
    assert "blocks/marker_id" in deletes
    assert "blocks/new_1" not in deletes
    # Порядок: удаляем до маркера включительно, потом останавливаемся.
    marker_pos = deletes.index("blocks/marker_id")
    assert deletes[:marker_pos + 1] == ["blocks/old_1", "blocks/old_2", "blocks/marker_id"]

    gets = [ep for method, ep in calls if method == "GET"]
    assert any(ep.startswith("blocks/page_b/children") and "page_size=100" in ep for ep in gets)


@pytest.mark.asyncio
async def test_reexport_recovers_from_failed_append(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_MEETINGS_DB_ID", "db_id")

    m = _meeting(notion_page_id="page_c", notion_page_url="https://www.notion.so/c")
    marker_text = _marker_text_for(m["id"])

    pool = _patch_pool(m)

    # Первый вызов: маркер добавлен, потом append-новых блоков падает.
    # Состояние страницы после краха: старые блоки + маркер (мокаем GET для второго вызова).
    old_block = {"id": "old_x", "type": "paragraph",
                 "paragraph": {"rich_text": [{"text": {"content": "old"}}]}}
    marker_block = {"id": "marker_x", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": marker_text}}]}}

    call_counter = {"n": 0}
    second_call_log: list[tuple[str, str, dict | None]] = []

    async def first_request(method, endpoint, token, payload=None):
        call_counter["n"] += 1
        # PATCH pages — ok.
        # PATCH blocks/page_c/children — первый вызов это marker append, ok.
        # PATCH blocks/page_c/children — второй вызов это content append, fail.
        if method == "PATCH" and endpoint == "blocks/page_c/children":
            children = (payload or {}).get("children") or []
            is_marker_only = (
                len(children) == 1
                and _block_marker_text(children[0]) == marker_text
            )
            if not is_marker_only:
                raise NotionExportError("simulated append failure")
        return {}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=first_request,
    ):
        with pytest.raises(NotionExportError):
            await export_meeting_to_notion(m["id"])

    # Второй вызов: маркер уже на странице, новые блоки добавляются нормально.
    async def second_request(method, endpoint, token, payload=None):
        second_call_log.append((method, endpoint, payload))
        if method == "GET" and endpoint.startswith("blocks/page_c/children"):
            return {"results": [old_block, marker_block], "has_more": False}
        return {}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=second_request,
    ):
        await export_meeting_to_notion(m["id"])

    # Должны видеть: PATCH pages, PATCH marker append, PATCH content append,
    # GET children, DELETE old_x, DELETE marker_x.
    methods = [(method, endpoint) for method, endpoint, _ in second_call_log]
    assert ("PATCH", "pages/page_c") in methods
    patch_children = [
        payload for method, ep, payload in second_call_log
        if method == "PATCH" and ep == "blocks/page_c/children"
    ]
    # Первый PATCH children в этом вызове — снова marker append (идемпотентно),
    # второй и далее — реальный контент.
    assert len(patch_children) >= 2
    first_payload_children = patch_children[0]["children"]
    assert (
        len(first_payload_children) == 1
        and _block_marker_text(first_payload_children[0]) == marker_text
    )
    deletes = [ep for method, ep in methods if method == "DELETE"]
    assert "blocks/old_x" in deletes
    assert "blocks/marker_x" in deletes


@pytest.mark.asyncio
async def test_delete_until_marker_skips_when_marker_missing(caplog):
    """Defensive: если маркер не найден на странице (race, ручное удаление,
    silent loss на стороне Notion) — НЕ удаляем ничего, чтобы не стереть
    свежий контент. Логируем warning.
    """
    import logging

    page_id = "page_defensive"
    marker_text = "<<<wookiee-marker-missing>>>"

    block_1 = {"id": "b1", "type": "paragraph",
               "paragraph": {"rich_text": [{"text": {"content": "first"}}]}}
    block_2 = {"id": "b2", "type": "paragraph",
               "paragraph": {"rich_text": [{"text": {"content": "second"}}]}}
    block_3 = {"id": "b3", "type": "paragraph",
               "paragraph": {"rich_text": [{"text": {"content": "third"}}]}}

    calls: list[tuple[str, str]] = []

    async def fake_request(method, endpoint, token, payload=None):
        calls.append((method, endpoint))
        if method == "GET":
            return {
                "results": [block_1, block_2, block_3],
                "has_more": False,
            }
        return {}

    with patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=fake_request,
    ):
        with caplog.at_level(
            logging.WARNING,
            logger="services.telemost_recorder_api.notion_export",
        ):
            await _delete_until_marker(page_id, marker_text, "tok")

    deletes = [ep for method, ep in calls if method == "DELETE"]
    assert deletes == [], "no DELETE calls expected when marker is missing"
    assert any(
        "Marker" in rec.message and "not found" in rec.message
        for rec in caplog.records
    ), "expected warning log about missing marker"


@pytest.mark.asyncio
async def test_export_to_new_page_does_not_use_marker(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "tok")
    monkeypatch.setenv("NOTION_MEETINGS_DB_ID", "db_id")

    m = _meeting()  # notion_page_id is None — new page.
    pool = _patch_pool(m)
    marker_text = _marker_text_for(m["id"])

    captured: list[tuple[str, str, dict | None]] = []

    async def fake_request(method, endpoint, token, payload=None):
        captured.append((method, endpoint, payload))
        if method == "POST" and endpoint == "pages":
            return {"id": "page_new", "url": "https://www.notion.so/new"}
        return {}

    with patch(
        "services.telemost_recorder_api.notion_export.get_pool",
        AsyncMock(return_value=pool),
    ), patch(
        "services.telemost_recorder_api.notion_export._notion_request",
        side_effect=fake_request,
    ):
        page_id, page_url = await export_meeting_to_notion(m["id"])

    assert page_id == "page_new"
    # Ни один из children-payload'ов не содержит блок с marker-текстом.
    for method, endpoint, payload in captured:
        if method != "PATCH" or not endpoint.endswith("/children"):
            continue
        children = (payload or {}).get("children") or []
        for block in children:
            assert _block_marker_text(block) != marker_text
