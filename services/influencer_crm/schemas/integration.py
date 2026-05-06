"""Pydantic schemas for crm.integrations + drawer payload + Kanban transitions."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

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
    blogger_handle: Optional[str] = None
    marketer_id: Optional[int] = None
    marketer_name: Optional[str] = None
    brief_id: Optional[int] = None
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage
    outcome: Optional[Outcome] = None
    is_barter: bool = False
    cost_placement: Optional[Decimal] = None
    cost_delivery: Optional[Decimal] = None
    cost_goods: Optional[Decimal] = None
    total_cost: Decimal = Decimal("0")
    erid: Optional[str] = None
    primary_substitute_code: Optional[str] = None
    # Audience
    theme: Optional[str] = None
    audience_age: Optional[str] = None
    subscribers: Optional[int] = None
    min_reach: Optional[int] = None
    engagement_rate: Optional[Decimal] = None
    # Plan metrics
    plan_cpm: Optional[Decimal] = None
    plan_ctr: Optional[Decimal] = None
    plan_clicks: Optional[int] = None
    plan_cpc: Optional[Decimal] = None
    # Fact metrics
    fact_views: Optional[int] = None
    fact_cpm: Optional[Decimal] = None
    fact_clicks: Optional[int] = None
    fact_ctr: Optional[Decimal] = None
    fact_cpc: Optional[Decimal] = None
    fact_carts: Optional[int] = None
    cr_to_cart: Optional[Decimal] = None
    fact_orders: Optional[int] = None
    cr_to_order: Optional[Decimal] = None
    fact_revenue: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IntegrationSubstituteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    substitute_article_id: int
    code: str
    artikul_id: Optional[int]
    display_order: int
    tracking_url: Optional[str] = None


class IntegrationPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_url: Optional[str]
    posted_at: Optional[datetime]
    fact_views: Optional[int]
    fact_clicks: Optional[int]


class IntegrationDetailOut(IntegrationOut):
    blogger_handle: str
    marketer_name: str
    substitutes: list[IntegrationSubstituteOut] = Field(default_factory=list)
    posts: list[IntegrationPostOut] = Field(default_factory=list)
    # Content & links
    contract_url: Optional[str] = None
    post_url: Optional[str] = None
    tz_url: Optional[str] = None
    screen_url: Optional[str] = None
    post_content: Optional[str] = None
    analysis: Optional[str] = None
    recommended_models: Optional[str] = None
    notes: Optional[str] = None
    # Compliance
    has_marking: Optional[bool] = None
    has_contract: Optional[bool] = None
    has_deeplink: Optional[bool] = None
    has_closing_docs: Optional[bool] = None
    has_full_recording: Optional[bool] = None
    all_data_filled: Optional[bool] = None
    has_quality_content: Optional[bool] = None
    complies_with_rules: Optional[bool] = None


class IntegrationCreate(BaseModel):
    blogger_id: int
    marketer_id: int
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage = "переговоры"
    is_barter: bool = False
    cost_placement: Optional[Decimal] = None
    cost_delivery: Optional[Decimal] = None
    cost_goods: Optional[Decimal] = None
    erid: Optional[str] = None
    notes: Optional[str] = None
    # Audience
    theme: Optional[str] = None
    audience_age: Optional[str] = None
    subscribers: Optional[int] = None
    min_reach: Optional[int] = None
    engagement_rate: Optional[Decimal] = None


class IntegrationUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    blogger_id: Optional[int] = None
    marketer_id: Optional[int] = None
    publish_date: Optional[date] = None
    channel: Optional[Channel] = None
    ad_format: Optional[AdFormat] = None
    marketplace: Optional[Marketplace] = None
    stage: Optional[Stage] = None
    outcome: Optional[Outcome] = None
    is_barter: Optional[bool] = None
    cost_placement: Optional[Decimal] = None
    cost_delivery: Optional[Decimal] = None
    cost_goods: Optional[Decimal] = None
    erid: Optional[str] = None
    notes: Optional[str] = None
    # Audience
    theme: Optional[str] = None
    audience_age: Optional[str] = None
    subscribers: Optional[int] = None
    min_reach: Optional[int] = None
    engagement_rate: Optional[Decimal] = None
    # Fact metrics
    fact_views: Optional[int] = None
    fact_cpm: Optional[Decimal] = None
    fact_clicks: Optional[int] = None
    fact_ctr: Optional[Decimal] = None
    fact_cpc: Optional[Decimal] = None
    fact_carts: Optional[int] = None
    cr_to_cart: Optional[Decimal] = None
    fact_orders: Optional[int] = None
    cr_to_order: Optional[Decimal] = None
    fact_revenue: Optional[Decimal] = None
    # Content
    contract_url: Optional[str] = None
    post_url: Optional[str] = None
    tz_url: Optional[str] = None
    screen_url: Optional[str] = None
    post_content: Optional[str] = None
    analysis: Optional[str] = None
    recommended_models: Optional[str] = None
    # Compliance
    has_marking: Optional[bool] = None
    has_contract: Optional[bool] = None
    has_deeplink: Optional[bool] = None
    has_closing_docs: Optional[bool] = None
    has_full_recording: Optional[bool] = None
    all_data_filled: Optional[bool] = None
    has_quality_content: Optional[bool] = None
    complies_with_rules: Optional[bool] = None


class StageTransitionIn(BaseModel):
    """POST /integrations/{id}/stage body — Kanban drag-drop."""
    target_stage: Stage
    note: Optional[str] = None
