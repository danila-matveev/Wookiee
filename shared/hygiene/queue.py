"""Read/write `.hygiene/queue.yaml` — NEEDS_HUMAN items awaiting resolve.

Each item is a question the agent collected during a nightly run and parked for
the owner to answer. `/hygiene-resolve` reads the queue interactively; if an
item ages past `queue_expire_days`, `expire_old_items()` applies the safe
default and records the resolution in `decisions.yaml`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shared.hygiene.schemas import QueueItem


DEFAULT_QUEUE_PATH = Path(".hygiene/queue.yaml")


class Queue(BaseModel):
    """In-memory representation of `.hygiene/queue.yaml`."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    items: list[QueueItem] = Field(default_factory=list)

    def add(self, item: QueueItem) -> None:
        """Append a fresh item, or bump `times_surfaced` on a duplicate id."""
        for existing in self.items:
            if existing.id == item.id:
                existing.times_surfaced += 1
                existing.last_surfaced_at = item.last_surfaced_at
                return
        self.items.append(item)

    def pop(self, item_id: str) -> Optional[QueueItem]:
        """Remove and return the queue item with the given id, or None."""
        for index, existing in enumerate(self.items):
            if existing.id == item_id:
                return self.items.pop(index)
        return None

    def find(self, item_id: str) -> Optional[QueueItem]:
        """Look up an item by id without removing it."""
        for existing in self.items:
            if existing.id == item_id:
                return existing
        return None

    def expire_old(
        self,
        now: Optional[datetime] = None,
    ) -> list[QueueItem]:
        """Pop and return items whose `expires_at` has passed.

        Caller is responsible for converting each expired item into a Decision
        (with `decided_by="auto-expire"` and `answer=item.default_after_7d`)
        and saving it to `decisions.yaml`.
        """
        ts = now if now is not None else datetime.now(timezone.utc)
        kept: list[QueueItem] = []
        expired: list[QueueItem] = []
        for item in self.items:
            if item.expires_at <= ts:
                expired.append(item)
            else:
                kept.append(item)
        self.items = kept
        return expired


def load_queue(path: Optional[Path] = None) -> Queue:
    """Parse `.hygiene/queue.yaml`. Missing file → empty `Queue()`."""
    target = Path(path) if path is not None else DEFAULT_QUEUE_PATH
    if not target.is_file():
        return Queue()
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if raw is None:
        return Queue()
    if not isinstance(raw, dict):
        raise ValueError(
            f"queue.yaml at {target} must be a YAML mapping at the top level"
        )
    return Queue.model_validate(raw)


def save_queue(queue: Queue, path: Optional[Path] = None) -> None:
    """Serialize `Queue` back to YAML (atomic write via .tmp + rename)."""
    target = Path(path) if path is not None else DEFAULT_QUEUE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = queue.model_dump(mode="json", exclude_none=True)
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


def append_items(path: Path, items: list[QueueItem]) -> None:
    """Append items to a queue file, de-duping by id via `Queue.add()`."""
    queue = load_queue(path)
    for item in items:
        queue.add(item)
    save_queue(queue, path)
