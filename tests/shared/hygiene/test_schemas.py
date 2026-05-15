"""Tests for `shared.hygiene.schemas` Pydantic models."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.hygiene.reports import load_report, save_report
from shared.hygiene.schemas import (
    AskUser,
    CodeQualityFinding,
    Decision,
    FixReport,
    HygieneFinding,
    QueueItem,
    ReportSummary,
)


def _now() -> datetime:
    return datetime(2026, 5, 14, 3, 0, tzinfo=timezone.utc)


def test_hygiene_finding_minimal_valid() -> None:
    finding = HygieneFinding(
        id="hygiene-orphan-import-shared-helpers-old",
        category="orphan-imports",
        severity="low",
        safe_to_autofix=True,
        autofix_kind="delete-file",
        files=["shared/helpers_old.py"],
        rationale="0 grep refs in repo, no __main__",
        rollback_command="git revert <SHA>",
        ask_user=None,
    )
    assert finding.id.startswith("hygiene-")
    assert finding.ask_user is None


def test_hygiene_finding_with_ask_user_roundtrip() -> None:
    finding = HygieneFinding(
        id="hygiene-orphan-doc-finance-v2-spec",
        category="orphan-docs",
        severity="low",
        safe_to_autofix=False,
        autofix_kind=None,
        files=["docs/finance-v2-spec.md"],
        rationale="Not referenced anywhere, content looks active",
        rollback_command=None,
        ask_user=AskUser(
            question_ru="Документ нигде не используется. Архив или живой?",
            options=["archive", "keep", "delete"],
            default_after_7d="archive",
        ),
    )
    dumped = finding.model_dump(mode="json", exclude_none=True)
    restored = HygieneFinding.model_validate(dumped)
    assert restored == finding
    assert restored.ask_user is not None
    assert restored.ask_user.default_after_7d == "archive"


def test_ask_user_requires_at_least_two_options() -> None:
    with pytest.raises(ValidationError):
        AskUser(question_ru="?", options=["only-one"], default_after_7d="only-one")


def test_code_quality_finding_validates_codex_confidence_range() -> None:
    base_kwargs = dict(
        id="ruff-E501-shared-data-layer-203",
        category="lint-error",
        tool="ruff",
        rule="E501",
        severity="low",
        safe_to_autofix=True,
        autofix_kind="ruff-fix",
        files=["shared/data_layer.py"],
        line=203,
        rollback_command="git revert <SHA>",
        ask_user=None,
    )
    ok = CodeQualityFinding(**base_kwargs, codex_confidence=0.85)
    assert ok.codex_confidence == pytest.approx(0.85)

    with pytest.raises(ValidationError):
        CodeQualityFinding(**base_kwargs, codex_confidence=1.5)


def test_queue_item_requires_two_options() -> None:
    now = _now()
    base_kwargs = dict(
        id="hygiene-orphan-doc-x",
        source_report=".hygiene/reports/hygiene-2026-05-14.json",
        enqueued_at=now,
        expires_at=now + timedelta(days=7),
        category="orphan-docs",
        files=["docs/x.md"],
        question_ru="Архив или оставить?",
        default_after_7d="archive",
        last_surfaced_at=now,
    )
    ok = QueueItem(**base_kwargs, options=["archive", "keep"])
    assert ok.times_surfaced == 1  # default

    with pytest.raises(ValidationError):
        QueueItem(**base_kwargs, options=["solo"])


def test_decision_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Decision(
            decision_id="dec-x",
            decided_at=_now(),
            decided_by="owner-via-hygiene-resolve",
            category="orphan-docs",
            file_glob="docs/x.md",
            answer="archive",
            rationale_ru="—",
            bogus="oops",  # type: ignore[call-arg]
        )


def test_decision_decided_by_must_be_known_literal() -> None:
    with pytest.raises(ValidationError):
        Decision(
            decision_id="dec-x",
            decided_at=_now(),
            decided_by="some-stranger",  # type: ignore[arg-type]
            category="orphan-docs",
            file_glob="docs/x.md",
            answer="archive",
            rationale_ru="—",
        )


def _build_minimal_report() -> FixReport:
    return FixReport(
        run_id="hygiene-2026-05-14-0300-utc",
        started_at=_now(),
        finished_at=_now() + timedelta(minutes=18),
        commit_sha="abc1234",
        findings=[],
        summary=ReportSummary(total=0, safe_to_autofix=0, needs_human=0, categories={}),
    )


def test_fix_report_roundtrip_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "hygiene-2026-05-14.json"
    original = _build_minimal_report()
    save_report(original, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["$schema"].startswith("https://wookiee.shop/schemas/")
    assert payload["run_id"] == "hygiene-2026-05-14-0300-utc"

    restored = load_report(path)
    assert restored.run_id == original.run_id
    assert restored.summary.total == 0
    assert restored.findings == []


def test_fix_report_with_findings(tmp_path: Path) -> None:
    finding = HygieneFinding(
        id="hygiene-orphan-import-shared-helpers-old",
        category="orphan-imports",
        severity="low",
        safe_to_autofix=True,
        autofix_kind="delete-file",
        files=["shared/helpers_old.py"],
        rationale="0 grep refs in repo, no __main__",
        rollback_command="git revert <SHA>",
        ask_user=None,
    )
    report = FixReport(
        run_id="hygiene-2026-05-14-0300-utc",
        started_at=_now(),
        finished_at=_now() + timedelta(minutes=18),
        commit_sha="abc1234",
        findings=[finding],
        summary=ReportSummary(
            total=1,
            safe_to_autofix=1,
            needs_human=0,
            categories={"orphan-imports": 1},
        ),
    )
    path = tmp_path / "hygiene-2026-05-14.json"
    save_report(report, path)
    restored = load_report(path)
    assert len(restored.findings) == 1
    assert restored.findings[0].category == "orphan-imports"
    assert restored.summary.categories == {"orphan-imports": 1}
