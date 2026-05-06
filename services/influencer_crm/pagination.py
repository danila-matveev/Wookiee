"""Opaque cursor pagination: base64(json([updated_at_iso, id]))."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Generic, TypeVar, Optional

from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(updated_at: datetime, item_id: int) -> str:
    """Encode a (updated_at, id) pair as a URL-safe base64 string.

    Naive datetimes are treated as UTC; tz-aware values are normalized to UTC.
    """
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    else:
        updated_at = updated_at.astimezone(timezone.utc)
    payload = json.dumps([updated_at.isoformat(), item_id])
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: Optional[str]) -> Optional[tuple[datetime, int]]:
    """Decode an opaque cursor. Returns None on any failure (404 → first page)."""
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        ts_str, item_id = json.loads(raw)
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, int(item_id)
    except Exception:
        return None


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: Optional[str] = None
