"""Pydantic schemas for crm.integrations + drawer payload + Kanban transitions."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Russian stages (migration 013)
Stage = Literal[
    "переговоры",
    "согласовано",
    "отправка_комплекта",
    "контент",
    "запланировано",
    "аналитика",
    "завершено",
    "архив",
]
Outcome = Literal["delivered", "cancelled", "no_show", "failed_compliance"]
Channel = Literal["instagram", "telegram", "tiktok", "youtube", "vk", "rutube"]
AdFormat = Literal["story", "short_video", "long_video", "long_post", "image_post", "integration", "live_stream"]
Marketplace = Literal["wb", "ozon", "both"]


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    blogger_id: int
    blogger_handle: str | None = None
    marketer_id: int | None = None
    marketer_name: str | None = None
    brief_id: int | None = None
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage
    outcome: Outcome | None = None
    is_barter: bool = False
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    total_cost: Decimal = Decimal("0")
    erid: str | None = None
    # Audience
    theme: str | None = None
    audience_age: str | None = None
    subscribers: int | None = None
    min_reach: int | None = None
    engagement_rate: Decimal | None = None
    # Plan metrics
    plan_cpm: Decimal | None = None
    plan_ctr: Decimal | None = None
    plan_clicks: int | None = None
    plan_cpc: Decimal | None = None
    # Fact metrics
    fact_views: int | None = None
    fact_cpm: Decimal | None = None
    fact_clicks: int | None = None
    fact_ctr: Decimal | None = None
    fact_cpc: Decimal | None = None
    fact_carts: int | None = None
    cr_to_cart: Decimal | None = None
    fact_orders: int | None = None
    cr_to_order: Decimal | None = None
    fact_revenue: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class IntegrationSubstituteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    substitute_article_id: int
    code: str
    artikul_id: int | None
    display_order: int
    tracking_url: str | None = None


class IntegrationPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_url: str | None
    posted_at: datetime | None
    fact_views: int | None
    fact_clicks: int | None


class IntegrationDetailOut(IntegrationOut):
    blogger_handle: str
    marketer_name: str
    substitutes: list[IntegrationSubstituteOut] = Field(default_factory=list)
    posts: list[IntegrationPostOut] = Field(default_factory=list)
    # Content & links
    contract_url: str | None = None
    post_url: str | None = None
    tz_url: str | None = None
    screen_url: str | None = None
    post_content: str | None = None
    analysis: str | None = None
    recommended_models: str | None = None
    notes: str | None = None
    # Compliance
    has_marking: bool | None = None
    has_contract: bool | None = None
    has_deeplink: bool | None = None
    has_closing_docs: bool | None = None
    has_full_recording: bool | None = None
    all_data_filled: bool | None = None
    has_quality_content: bool | None = None
    complies_with_rules: bool | None = None


class IntegrationCreate(BaseModel):
    blogger_id: int
    marketer_id: int
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage = "переговоры"
    is_barter: bool = False
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    erid: str | None = None
    notes: str | None = None
    # Audience
    theme: str | None = None
    audience_age: str | None = None
    subscribers: int | None = None
    min_reach: int | None = None
    engagement_rate: Decimal | None = None


class IntegrationUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    blogger_id: int | None = None
    marketer_id: int | None = None
    publish_date: date | None = None
    channel: Channel | None = None
    ad_format: AdFormat | None = None
    marketplace: Marketplace | None = None
    stage: Stage | None = None
    outcome: Outcome | None = None
    is_barter: bool | None = None
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    erid: str | None = None
    notes: str | None = None
    # Audience
    theme: str | None = None
    audience_age: str | None = None
    subscribers: int | None = None
    min_reach: int | None = None
    engagement_rate: Decimal | None = None
    # Fact metrics
    fact_views: int | None = None
    fact_cpm: Decimal | None = None
    fact_clicks: int | None = None
    fact_ctr: Decimal | None = None
    fact_cpc: Decimal | None = None
    fact_carts: int | None = None
    cr_to_cart: Decimal | None = None
    fact_orders: int | None = None
    cr_to_order: Decimal | None = None
    fact_revenue: Decimal | None = None
    # Content
    contract_url: str | None = None
    post_url: str | None = None
    tz_url: str | None = None
    screen_url: str | None = None
    post_content: str | None = None
    analysis: str | None = None
    recommended_models: str | None = None
    # Compliance
    has_marking: bool | None = None
    has_contract: bool | None = None
    has_deeplink: bool | None = None
    has_closing_docs: bool | None = None
    has_full_recording: bool | None = None
    all_data_filled: bool | None = None
    has_quality_content: bool | None = None
    complies_with_rules: bool | None = None


class StageTransitionIn(BaseModel):
    """POST /integrations/{id}/stage body — Kanban drag-drop."""
    target_stage: Stage
    note: str | None = None
