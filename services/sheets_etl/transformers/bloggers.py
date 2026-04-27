"""БД БЛОГЕРЫ → crm.bloggers + crm.blogger_channels.

Returns (bloggers, channels). Channels carry `display_handle_ref` so the loader
can resolve blogger_id after upserting bloggers.
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_int

LINK_COLS: dict[int, str] = {
    1: "instagram",
    3: "vk",
    4: "telegram",
    5: "tiktok",
    6: "youtube",
}


def _handle_from_url(url: str) -> str:
    url = url.strip().rstrip("/")
    return url.rsplit("/", 1)[-1] if "/" in url else url


def transform(values: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not values or len(values) < 2:
        return [], []
    bloggers: list[dict[str, Any]] = []
    channels: list[dict[str, Any]] = []

    for raw in values[1:]:
        if not raw or not raw[0]:
            continue
        display_handle = str(raw[0]).strip()
        if not display_handle:
            continue
        srid = sheet_row_id([display_handle])
        bloggers.append({
            "display_handle": display_handle,
            "status": "active",
            "sheet_row_id": srid,
        })
        for col, kind in LINK_COLS.items():
            url = str(raw[col]).strip() if len(raw) > col and raw[col] else ""
            if not url:
                continue
            ch = {
                "display_handle_ref": display_handle,
                "channel": kind,
                "handle": _handle_from_url(url),
                "url": url,
                "followers": None,
            }
            if kind == "instagram" and len(raw) > 2:
                ch["followers"] = parse_int(raw[2])
            channels.append(ch)
    return bloggers, channels
