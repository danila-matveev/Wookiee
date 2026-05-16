"""Tests for `shared.hygiene.queue`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from shared.hygiene.queue import Queue, append_items, load_queue, save_queue
from shared.hygiene.schemas import QueueItem


def _make_item(
    item_id: str = "hygiene-orphan-doc-finance-v2-spec",
    *,
    enqueued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> QueueItem:
    base = enqueued_at or datetime(2026, 5, 14, 4, 0, tzinfo=timezone.utc)
    return QueueItem(
        id=item_id,
        source_report=".hygiene/reports/hygiene-2026-05-14.json",
        enqueued_at=base,
        expires_at=expires_at or (base + timedelta(days=7)),
        category="orphan-docs",
        files=["docs/finance-v2-spec.md"],
        question_ru="Документ docs/finance-v2-spec.md нигде не используется. Это старая спека или живой документ?",
        options=["archive", "keep", "delete"],
        default_after_7d="archive",
        times_surfaced=1,
        last_surfaced_at=base,
    )


def test_load_missing_file_returns_empty_queue(tmp_path: Path) -> None:
    queue = load_queue(tmp_path / "absent.yaml")
    assert isinstance(queue, Queue)
    assert queue.items == []


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "queue.yaml"
    original = Queue(items=[_make_item()])
    save_queue(original, path)
    assert path.is_file()

    loaded = load_queue(path)
    assert len(loaded.items) == 1
    restored = loaded.items[0]
    assert restored.id == "hygiene-orphan-doc-finance-v2-spec"
    assert restored.options == ["archive", "keep", "delete"]
    assert restored.default_after_7d == "archive"


def test_add_appends_unique_item() -> None:
    queue = Queue()
    queue.add(_make_item("first"))
    queue.add(_make_item("second"))
    assert [i.id for i in queue.items] == ["first", "second"]


def test_add_duplicate_bumps_surfaced_counter() -> None:
    queue = Queue()
    first = _make_item("dup")
    queue.add(first)
    bumped = _make_item("dup")
    bumped.last_surfaced_at = first.last_surfaced_at + timedelta(days=1)
    queue.add(bumped)
    assert len(queue.items) == 1
    assert queue.items[0].times_surfaced == 2
    assert queue.items[0].last_surfaced_at == bumped.last_surfaced_at


def test_pop_returns_and_removes() -> None:
    queue = Queue(items=[_make_item("a"), _make_item("b")])
    popped = queue.pop("a")
    assert popped is not None
    assert popped.id == "a"
    assert [i.id for i in queue.items] == ["b"]


def test_pop_missing_returns_none() -> None:
    queue = Queue(items=[_make_item("a")])
    assert queue.pop("nope") is None
    assert [i.id for i in queue.items] == ["a"]


def test_find_returns_item_without_removing() -> None:
    queue = Queue(items=[_make_item("a")])
    found = queue.find("a")
    assert found is not None
    assert found.id == "a"
    assert len(queue.items) == 1


def test_expire_old_pops_aged_items() -> None:
    now = datetime(2026, 5, 21, 4, 1, tzinfo=timezone.utc)
    fresh = _make_item(
        "fresh",
        enqueued_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=6),
    )
    aged = _make_item(
        "aged",
        enqueued_at=now - timedelta(days=8),
        expires_at=now - timedelta(seconds=1),
    )
    queue = Queue(items=[fresh, aged])

    expired = queue.expire_old(now)

    assert [i.id for i in expired] == ["aged"]
    assert [i.id for i in queue.items] == ["fresh"]


def test_save_uses_atomic_write(tmp_path: Path) -> None:
    path = tmp_path / "queue.yaml"
    save_queue(Queue(items=[_make_item()]), path)
    assert not list(tmp_path.glob("*.tmp"))


def test_append_items_dedupes_by_id(tmp_path: Path) -> None:
    path = tmp_path / "queue.yaml"
    append_items(path, [_make_item("dup")])
    append_items(path, [_make_item("dup"), _make_item("fresh")])

    queue = load_queue(path)
    assert [item.id for item in queue.items] == ["dup", "fresh"]
    assert queue.items[0].times_surfaced == 2


def test_invalid_yaml_top_level_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_queue(path)
