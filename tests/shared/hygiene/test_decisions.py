"""Tests for `shared.hygiene.decisions`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from shared.hygiene.decisions import Decisions, load_decisions, save_decisions
from shared.hygiene.schemas import Decision


def _make_decision(
    decision_id: str = "dec-test-1",
    *,
    category: str = "orphan-docs",
    file_glob: str = "docs/finance-v2-*.md",
    pattern: str | None = None,
    answer: str = "archive",
    expires_at: datetime | None = None,
) -> Decision:
    return Decision(
        decision_id=decision_id,
        decided_at=datetime(2026, 5, 9, 10, 24, tzinfo=timezone.utc),
        decided_by="owner-via-hygiene-resolve",
        category=category,  # type: ignore[arg-type]
        file_glob=file_glob,
        pattern=pattern,
        answer=answer,
        rationale_ru="Spec v2 заменена v3 — можно архивировать.",
        expires_at=expires_at,
    )


def test_load_missing_file_returns_empty_decisions(tmp_path: Path) -> None:
    decisions = load_decisions(tmp_path / "absent.yaml")
    assert isinstance(decisions, Decisions)
    assert decisions.decisions == []
    assert decisions.version == 1


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    original = Decisions(decisions=[_make_decision()])
    save_decisions(original, path)
    assert path.is_file()

    loaded = load_decisions(path)
    assert len(loaded.decisions) == 1
    restored = loaded.decisions[0]
    assert restored.decision_id == "dec-test-1"
    assert restored.category == "orphan-docs"
    assert restored.file_glob == "docs/finance-v2-*.md"
    assert restored.answer == "archive"
    assert restored.expires_at is None


def test_append_and_persist(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    decisions = load_decisions(path)
    decisions.append(_make_decision("dec-1"))
    decisions.append(_make_decision("dec-2", file_glob="docs/old-*.md"))
    save_decisions(decisions, path)

    reloaded = load_decisions(path)
    assert [d.decision_id for d in reloaded.decisions] == ["dec-1", "dec-2"]


def test_find_for_matches_by_category_and_glob(tmp_path: Path) -> None:
    decisions = Decisions(
        decisions=[
            _make_decision("dec-a", file_glob="docs/finance-v2-*.md"),
            _make_decision("dec-b", category="unused-dep", file_glob="requirements*.txt", pattern="pyyaml"),
        ]
    )
    hit = decisions.find_for("orphan-docs", "docs/finance-v2-spec.md")
    assert hit is not None
    assert hit.decision_id == "dec-a"

    miss = decisions.find_for("orphan-docs", "docs/other.md")
    assert miss is None


def test_find_for_pattern_filters_by_substring() -> None:
    decisions = Decisions(
        decisions=[
            _make_decision(
                "dec-c",
                category="unused-dep",
                file_glob="requirements*.txt",
                pattern="pyyaml",
            )
        ]
    )
    assert decisions.find_for(
        "unused-dep",
        "services/x/requirements.txt",
        pattern="pyyaml>=6.0",
    )
    assert decisions.find_for(
        "unused-dep",
        "services/x/requirements.txt",
        pattern="httpx>=0.27",
    ) is None
    # Without pattern arg → must be None (pattern is set on the decision).
    assert decisions.find_for("unused-dep", "services/x/requirements.txt") is None


def test_expire_old_drops_only_aged_entries() -> None:
    now = datetime(2026, 5, 14, 4, 0, tzinfo=timezone.utc)
    keep_forever = _make_decision("forever")
    aged = _make_decision("aged", expires_at=now - timedelta(seconds=1))
    fresh = _make_decision("fresh", expires_at=now + timedelta(days=1))
    decisions = Decisions(decisions=[keep_forever, aged, fresh])

    removed = decisions.expire_old(now)

    assert [d.decision_id for d in removed] == ["aged"]
    assert [d.decision_id for d in decisions.decisions] == ["forever", "fresh"]


def test_save_uses_atomic_write(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    decisions = Decisions(decisions=[_make_decision()])
    save_decisions(decisions, path)
    # No leftover .tmp sibling after a successful write.
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_yaml_top_level_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_decisions(path)
