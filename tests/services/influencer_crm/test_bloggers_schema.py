"""Tests for BloggerSummaryOut and ChannelBrief schema classes."""
from __future__ import annotations


def test_blogger_summary_out_has_required_fields():
    from services.influencer_crm.schemas.blogger import BloggerSummaryOut

    required = {
        "id", "display_handle", "status",
        "channels", "integrations_count", "integrations_done",
        "total_spent", "avg_cpm_fact",
    }
    actual = set(BloggerSummaryOut.model_fields.keys())
    missing = required - actual
    assert not missing, f"BloggerSummaryOut missing fields: {missing}"


def test_channel_brief_model():
    from services.influencer_crm.schemas.blogger import ChannelBrief

    cb = ChannelBrief(id=1, channel="instagram", handle="@test", url=None)
    assert cb.channel == "instagram"
    assert cb.url is None


def test_blogger_summary_out_channels_default_empty():
    from services.influencer_crm.schemas.blogger import BloggerSummaryOut

    b = BloggerSummaryOut(
        id=1, display_handle="@test", real_name=None, status="active",
        default_marketer_id=None, price_story_default=None,
        price_reels_default=None, created_at=None, updated_at=None,
        channels=[], integrations_count=0, integrations_done=0,
        last_integration_at=None, total_spent="0", avg_cpm_fact=None,
    )
    assert b.channels == []
