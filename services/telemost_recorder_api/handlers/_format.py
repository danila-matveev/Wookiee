"""Shared formatting helpers for handlers (status emoji, rows, escaping)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_MD_SPECIAL = ("\\", "_", "*", "[", "]", "`")

_STATUS_EMOJI = {
    "queued": "⏳",
    "recording": "🔴",
    "postprocessing": "⚙️",
    "done": "✅",
    "failed": "❌",
}

_ID_PREFIX_LEN = 8


def md_escape(s: str) -> str:
    """Escape Telegram MarkdownV1 specials in user-controlled strings."""
    for ch in _MD_SPECIAL:
        s = s.replace(ch, "\\" + ch)
    return s


def status_emoji(status: str) -> str:
    return _STATUS_EMOJI.get(status, "•")


def short_id(meeting_id: Any) -> str:
    return str(meeting_id)[:_ID_PREFIX_LEN]


def fmt_active_row(row: dict[str, Any]) -> str:
    """One row for active recordings: emoji + id + title + elapsed/queued/processing."""
    mid = short_id(row["id"])
    title = md_escape(row.get("title") or "(без названия)")
    suffix = _active_suffix(row.get("status", ""), row.get("started_at"))
    return f"{status_emoji(row.get('status', ''))} `{mid}` — {title}{suffix}"


def fmt_history_row(row: dict[str, Any]) -> str:
    """One row for finished records: emoji + id + title + start time."""
    mid = short_id(row["id"])
    title = md_escape(row.get("title") or "(без названия)")
    when = (
        row["started_at"].strftime("%d.%m %H:%M")
        if row.get("started_at")
        else "—"
    )
    return f"{status_emoji(row.get('status', ''))} `{mid}` — {title} ({when})"


def _active_suffix(status: str, started_at: datetime | None) -> str:
    if status == "queued":
        return " (в очереди)"
    if status == "postprocessing":
        return " (обработка)"
    if status == "recording" and started_at is not None:
        return f" ({_elapsed(started_at)})"
    if status == "recording":
        return " (идёт)"
    return ""


def _elapsed(started_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - started_at
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "только что началась"
    if minutes < 60:
        return f"идёт {minutes} мин"
    hours, rem = divmod(minutes, 60)
    return f"идёт {hours} ч {rem:02d} мин"
