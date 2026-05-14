"""Read/write `.hygiene/decisions.yaml` — persistent memory of human decisions.

`/night-coordinator` consults this file BEFORE queuing a new finding. If a
finding pattern matches an existing decision (same category + matching glob),
the saved answer is reused so the human doesn't get asked twice.

Decisions never expire automatically by default (`expires_at: None`). If a
decision was written with an `expires_at`, `expire_old_decisions()` will remove
it once the timestamp passes.
"""

from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shared.hygiene.schemas import Decision


DEFAULT_DECISIONS_PATH = Path(".hygiene/decisions.yaml")


def _glob_matches(glob: str, file_path: str) -> bool:
    """Match `file_path` against `glob` with two strategies (whichever hits).

    - Direct `fnmatch` on the full path (so `docs/finance-v2-*.md` works).
    - `fnmatch` on the basename (so `requirements*.txt` also matches
      `services/x/requirements.txt`).
    """
    if fnmatch.fnmatch(file_path, glob):
        return True
    return fnmatch.fnmatch(Path(file_path).name, glob)


class Decisions(BaseModel):
    """In-memory representation of `.hygiene/decisions.yaml`."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    decisions: list[Decision] = Field(default_factory=list)

    def find_for(
        self,
        category: str,
        file_path: str,
        pattern: Optional[str] = None,
    ) -> Optional[Decision]:
        """Return the first decision matching the given category and file path.

        Match rules:
        - `category` must equal the decision's category exactly
        - `file_path` must match `decision.file_glob` (fnmatch)
        - If `decision.pattern` is set, the supplied `pattern` must contain it
        """
        for decision in self.decisions:
            if decision.category != category:
                continue
            if not _glob_matches(decision.file_glob, file_path):
                continue
            if decision.pattern and (pattern is None or decision.pattern not in pattern):
                continue
            return decision
        return None

    def append(self, decision: Decision) -> None:
        """Append a new decision in-memory. Caller must call `save_decisions()`."""
        self.decisions.append(decision)

    def expire_old(self, now: Optional[datetime] = None) -> list[Decision]:
        """Drop decisions whose `expires_at` has passed.

        Returns the list of removed decisions (for logging / audit). Decisions
        with `expires_at = None` are never removed.
        """
        ts = now if now is not None else datetime.now(timezone.utc)
        kept: list[Decision] = []
        removed: list[Decision] = []
        for decision in self.decisions:
            if decision.expires_at is not None and decision.expires_at <= ts:
                removed.append(decision)
            else:
                kept.append(decision)
        self.decisions = kept
        return removed


def load_decisions(path: Optional[Path] = None) -> Decisions:
    """Parse `.hygiene/decisions.yaml`. Missing file → empty `Decisions()`."""
    target = Path(path) if path is not None else DEFAULT_DECISIONS_PATH
    if not target.is_file():
        return Decisions()
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if raw is None:
        return Decisions()
    if not isinstance(raw, dict):
        raise ValueError(
            f"decisions.yaml at {target} must be a YAML mapping at the top level"
        )
    return Decisions.model_validate(raw)


def save_decisions(decisions: Decisions, path: Optional[Path] = None) -> None:
    """Serialize `Decisions` back to YAML.

    Writes via a `.tmp` sibling then atomic-rename to avoid corruption if the
    process dies mid-write.
    """
    target = Path(path) if path is not None else DEFAULT_DECISIONS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = decisions.model_dump(mode="json", exclude_none=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    tmp.replace(target)
