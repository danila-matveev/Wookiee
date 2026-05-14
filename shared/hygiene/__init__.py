"""Shared library for the nighttime DevOps agent.

Reads and writes:
- `.hygiene/config.yaml` — runtime config (master kill-switch + thresholds)
- `.hygiene/decisions.yaml` — persistent memory of human decisions
- `.hygiene/queue.yaml` — NEEDS_HUMAN items awaiting `/hygiene-resolve`
- `.hygiene/reports/*.json` — per-night findings/fix reports

Public API:
- `load_config()` / `HygieneConfig`
- `Decisions` / `Decision`
- `Queue` / `QueueItem`
- `load_report()` / `save_report()` / `FixReport`
- Pydantic models in `shared.hygiene.schemas`

Reference: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md`.
"""

from shared.hygiene.config import HygieneConfig, load_config
from shared.hygiene.decisions import Decisions, load_decisions, save_decisions
from shared.hygiene.queue import Queue, load_queue, save_queue
from shared.hygiene.reports import (
    list_reports,
    load_report,
    reports_dir,
    save_report,
)
from shared.hygiene.schemas import (
    AskUser,
    CodeQualityFinding,
    Decision,
    FixReport,
    HygieneFinding,
    QueueItem,
    ReportSummary,
)

__all__ = [
    "AskUser",
    "CodeQualityFinding",
    "Decision",
    "Decisions",
    "FixReport",
    "HygieneConfig",
    "HygieneFinding",
    "Queue",
    "QueueItem",
    "ReportSummary",
    "list_reports",
    "load_config",
    "load_decisions",
    "load_queue",
    "load_report",
    "reports_dir",
    "save_decisions",
    "save_queue",
    "save_report",
]
