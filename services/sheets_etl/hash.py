"""Deterministic content-hash for Sheets row identity.

Idempotency contract: if any of the parts change in Sheets, the hash changes,
producing a NEW row in Supabase rather than updating the old one. Choose stable,
business-meaningful keys (handle + publish date + channel), NOT positional A1.
"""
from __future__ import annotations

import hashlib
from typing import Iterable


def _norm(part: str | None) -> str:
    if part is None:
        return ""
    return str(part).strip().lower()


def sheet_row_id(parts: Iterable[str | None]) -> str:
    """Compute deterministic 32-char MD5 hex for a row, given its key parts."""
    joined = "‖".join(_norm(p) for p in parts)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()
