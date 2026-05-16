"""Load/save JSON reports from `.hygiene/reports/`.

Each nightly job emits one JSON file:
- `hygiene-YYYY-MM-DD.json` (from `/hygiene --emit-json`)
- `code-quality-YYYY-MM-DD.json` (Phase 2 — Codex sidecar)
- `coverage-YYYY-MM-DD.json` (Phase 3)
- `coordinator-YYYY-MM-DD.json` (`/night-coordinator` aggregate output)

Reports are validated against `FixReport` (Pydantic). Schema violations fail
loud — the night-coordinator treats a missing/invalid report as «source did not
produce output» and skips that source.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from shared.hygiene.schemas import FixReport


DEFAULT_REPORTS_DIR = Path(".hygiene/reports")


def reports_dir(base: Optional[Path] = None) -> Path:
    """Return the directory where reports live. Creates it on first call."""
    target = Path(base) if base is not None else DEFAULT_REPORTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def report_path(kind: str, when: Optional[date] = None, base: Optional[Path] = None) -> Path:
    """Build the canonical path for a report file.

    Args:
        kind: One of `"hygiene"`, `"code-quality"`, `"coverage"`, `"coordinator"`,
              `"hygiene-autofix"`. Free-form, but stick to the plan.
        when: Date for the filename (defaults to today UTC).
        base: Override base directory (defaults to `.hygiene/reports/`).
    """
    day = when if when is not None else datetime.utcnow().date()
    return reports_dir(base) / f"{kind}-{day.isoformat()}.json"


def load_report(path: Path) -> FixReport:
    """Read and validate one JSON report. Raises if missing or invalid."""
    if not path.is_file():
        raise FileNotFoundError(f"Hygiene report not found at {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FixReport.model_validate(raw)


def load_reports_for_date(when: date | str, base: Optional[Path] = None) -> list[FixReport]:
    """Load valid fix reports for one date.

    The coordinator consumes only `FixReport`-shaped reports here. Coverage has
    its own schema and is read separately by the coverage gate.
    """
    if isinstance(when, str):
        day = date.fromisoformat(when)
    else:
        day = when

    loaded: list[FixReport] = []
    for kind in ("hygiene",):
        path = report_path(kind, day, base)
        if path.exists():
            loaded.append(load_report(path))
    return loaded


def save_report(report: FixReport, path: Path) -> Path:
    """Write a `FixReport` to disk as pretty-printed UTF-8 JSON.

    Uses atomic `.tmp` + rename to avoid partial writes if the process dies.
    Returns the final path for chaining.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json", by_alias=True, exclude_none=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def list_reports(
    kind: Optional[str] = None,
    base: Optional[Path] = None,
) -> list[Path]:
    """List existing reports, sorted oldest → newest.

    Args:
        kind: If provided, filter to files starting with `"{kind}-"`.
        base: Override base directory.
    """
    target = reports_dir(base)
    pattern = f"{kind}-*.json" if kind else "*.json"
    return sorted(p for p in target.glob(pattern) if p.is_file())
