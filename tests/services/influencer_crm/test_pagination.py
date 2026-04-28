"""Cursor encode/decode round-trips and rejects malformed input."""
from __future__ import annotations

from datetime import datetime, timezone


def test_cursor_round_trip():
    from services.influencer_crm.pagination import encode_cursor, decode_cursor

    ts = datetime(2026, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
    cursor = encode_cursor(ts, 42)

    decoded_ts, decoded_id = decode_cursor(cursor)
    assert decoded_ts == ts
    assert decoded_id == 42


def test_cursor_with_naive_datetime_is_treated_as_utc():
    from services.influencer_crm.pagination import encode_cursor, decode_cursor

    naive = datetime(2026, 1, 15, 10, 30, 45)
    cursor = encode_cursor(naive, 1)

    decoded_ts, _ = decode_cursor(cursor)
    assert decoded_ts.tzinfo == timezone.utc


def test_decode_garbage_returns_none():
    from services.influencer_crm.pagination import decode_cursor
    assert decode_cursor("not-a-real-cursor") is None
    assert decode_cursor("") is None


def test_decode_none_returns_none():
    from services.influencer_crm.pagination import decode_cursor
    assert decode_cursor(None) is None


def test_page_model_serializes_cursor():
    from services.influencer_crm.pagination import Page

    p: Page[int] = Page(items=[1, 2, 3], next_cursor="abc")
    d = p.model_dump()
    assert d["items"] == [1, 2, 3]
    assert d["next_cursor"] == "abc"
