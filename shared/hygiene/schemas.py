"""Pydantic v2 models for the nighttime DevOps agent.

Schemas correspond to JSON / YAML contracts defined in the implementation plan
(`docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md`, §3).

All models use `extra="forbid"` to fail loud on unknown fields — schema drift is
a bug, not an opportunity for silent acceptance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]
HygieneCategory = Literal[
    "stray-binary",
    "gitignore-violation",
    "missing-readme",
    "pycache-committed",
    "orphan-imports",
    "orphan-docs",
    "skill-registry-drift",
    "broken-doc-links",
    "cross-platform-skill-prep",
    "structure-conventions",
    "lint-error",
    "type-error",
    "dead-code",
    "unused-dep",
    "coverage-drop",
    "missing-test",
]


class AskUser(BaseModel):
    """Sub-record describing a question to surface to the human owner."""

    model_config = ConfigDict(extra="forbid")

    question_ru: str = Field(..., description="Plain-Russian question for the owner")
    options: list[str] = Field(..., min_length=2, description="Allowed answers")
    default_after_7d: str = Field(
        ...,
        description="Safe default applied after queue_expire_days if no human reply",
    )


class HygieneFinding(BaseModel):
    """One hygiene finding (output of `/hygiene` skill in `--emit-json` mode)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    category: HygieneCategory
    severity: Severity
    safe_to_autofix: bool
    autofix_kind: Optional[str] = None
    files: list[str]
    rationale: str
    rollback_command: Optional[str] = None
    ask_user: Optional[AskUser] = None


class CodeQualityFinding(BaseModel):
    """One code-quality finding (output of `/code-quality-scan` skill — Phase 2)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    category: HygieneCategory
    tool: Literal["ruff", "mypy", "vulture", "pip-deptree"]
    rule: Optional[str] = None
    severity: Severity
    safe_to_autofix: bool
    autofix_kind: Optional[str] = None
    files: list[str]
    line: Optional[int] = None
    codex_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    codex_verdict: Optional[str] = None
    rationale_from_codex: Optional[str] = None
    rollback_command: Optional[str] = None
    ask_user: Optional[AskUser] = None


class ReportSummary(BaseModel):
    """Aggregate counters across one report."""

    model_config = ConfigDict(extra="forbid")

    total: int
    safe_to_autofix: int
    needs_human: int
    categories: dict[str, int] = Field(default_factory=dict)


class FixReport(BaseModel):
    """Top-level JSON report written to `.hygiene/reports/<name>-YYYY-MM-DD.json`."""

    model_config = ConfigDict(extra="forbid")

    schema_url: str = Field(
        default="https://wookiee.shop/schemas/hygiene-report-v1.json",
        alias="$schema",
    )
    version: str = "1.0.0"
    run_id: str
    started_at: datetime
    finished_at: datetime
    commit_sha: str
    findings: list[HygieneFinding] = Field(default_factory=list)
    summary: ReportSummary
    truncated: bool = False
    truncated_reason: Optional[str] = None


class QueueItem(BaseModel):
    """Entry in `.hygiene/queue.yaml` — NEEDS_HUMAN finding awaiting resolve."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source_report: str
    enqueued_at: datetime
    expires_at: datetime
    category: HygieneCategory
    files: list[str]
    question_ru: str
    options: list[str] = Field(..., min_length=2)
    default_after_7d: str
    times_surfaced: int = 1
    last_surfaced_at: datetime


class Decision(BaseModel):
    """Entry in `.hygiene/decisions.yaml` — persistent memory of human decisions."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    decided_at: datetime
    decided_by: Literal["owner-via-hygiene-resolve", "auto-expire"]
    category: HygieneCategory
    file_glob: str
    pattern: Optional[str] = None
    answer: str
    rationale_ru: str
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


class Finding(BaseModel):
    """Lightweight finding emitted by per-skill scanners (coverage, etc.).

    A trimmed cousin of HygieneFinding/CodeQualityFinding — no autofix metadata,
    just enough to surface the issue in reports and queues.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    category: HygieneCategory
    severity: Severity
    safe_to_autofix: bool = False
    files: list[str] = Field(default_factory=list)
    rationale: str
    current_pct: Optional[float] = None
    baseline_pct: Optional[float] = None
    delta_pct: Optional[float] = None
    ask_user: Optional[AskUser] = None


class CoverageReport(BaseModel):
    """Top-level report written by `/test-coverage-check` skill."""

    model_config = ConfigDict(extra="forbid")

    schema_url: str = Field(
        default="https://wookiee.shop/schemas/coverage-report-v1.json",
        alias="$schema",
    )
    version: str = "1.0.0"
    run_id: str
    started_at: datetime
    finished_at: datetime
    commit_sha: str
    current_pct: float
    baseline_pct: float
    delta_pct: float
    threshold_pct: float
    drop_threshold_pp: float
    findings: list[Finding] = Field(default_factory=list)
    blocking: bool = False
    truncated: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)


class HeartbeatSummary(BaseModel):
    """Aggregate snapshot for the morning heartbeat Telegram message."""

    model_config = ConfigDict(extra="forbid")

    date_str: str
    fixes_applied: int = 0
    fixes_examples: list[str] = Field(default_factory=list)
    needs_human_count: int = 0
    coverage_pct: Optional[float] = None
    coverage_delta_pp: Optional[float] = None
    pr_number: Optional[int] = None
    pr_status: Optional[Literal["open", "merged", "closed", "failed"]] = None
    failure: Optional[str] = None
