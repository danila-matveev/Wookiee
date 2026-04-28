"""Tests for /bloggers endpoints + schemas."""
from __future__ import annotations

from decimal import Decimal


def test_blogger_out_serializes_money_as_string():
    from services.influencer_crm.schemas.blogger import BloggerOut

    b = BloggerOut(
        id=1,
        display_handle="@user",
        status="active",
        default_marketer_id=2,
        price_story_default=Decimal("1500.00"),
        price_reels_default=None,
    )
    d = b.model_dump(mode="json")
    assert d["price_story_default"] == "1500.00"
    assert d["price_reels_default"] is None


def test_blogger_create_requires_handle():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.blogger import BloggerCreate

    with pytest.raises(ValidationError):
        BloggerCreate()  # type: ignore[call-arg]
